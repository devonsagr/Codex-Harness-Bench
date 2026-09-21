"""Pinned public task downloads. Verifiers never enter development baselines."""
import json
import threading
import time
import tomllib
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from .files import now, snapshot, verify_snapshot, safe_path
from .repository_source import unpack, import_repository


def catalog(app):
    return json.loads((app.root/'catalog/public-task-sources.json').read_text(encoding='utf-8'))


def bundle(app):
    source=catalog(app)
    root=safe_path(app.local,'public-sources/deepswe/'+source['revision'])
    receipt=root/'manifest.json'
    if receipt.exists():
        verify_snapshot(root/'files',json.loads(receipt.read_text(encoding='utf-8')))
        return root/'files'
    root.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='download-',dir=root.parent) as temp:
        stage=Path(temp); archive=stage/'bundle.tar.gz'; extracted=stage/'extracted';extracted.mkdir()
        url='https://codeload.github.com/datacurve-ai/deep-swe/tar.gz/'+source['revision']
        size=0; deadline=time.monotonic()+120
        with urlopen(Request(url,headers={'User-Agent':'Codex-Harness-Bench'}),timeout=20) as response,archive.open('wb') as out:
            if not response.url.startswith('https://codeload.github.com/'):raise ValueError('公开题包下载发生未知重定向。')
            while chunk:=response.read(65536):
                size+=len(chunk)
                if size>50_000_000 or time.monotonic()>deadline:raise ValueError('题包下载超过大小或时间限制。')
                out.write(chunk)
        ids={t['id'] for t in source['tasks']}
        def include(name):
            parts=name.split('/')
            return name in {'LICENSE','PROVENANCE.md','README.md'} or (len(parts)>=3 and parts[0]=='tasks' and parts[1] in ids and parts[2] in {'instruction.md','task.toml','tests','environment'})
        unpack(archive,extracted,include)
        for task in source['tasks']:
            folder=extracted/'tasks'/task['id']
            definition=tomllib.loads((folder/'task.toml').read_text(encoding='utf-8'))
            meta=definition['metadata']
            # Three upstream abbreviated SHAs have already been resolved in the index.
            if meta['repository_url']!=task['repositoryUrl'] or not task['baseCommit'].startswith(meta['base_commit_hash']):
                raise ValueError('题包定义与固定索引不一致，未安装。')
            if not (folder/'instruction.md').is_file() or not (folder/'tests/test.sh').is_file():raise ValueError('公开题包缺少题面或验收入口。')
        staged=stage/'ready';staged.mkdir()
        manifest=snapshot(extracted,staged/'files')
        (staged/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        staged.rename(root)
    return root/'files'


def install(app,task_id,files):
    source=catalog(app); item=next(t for t in source['tasks'] if t['id']==task_id)
    tid='deepswe-'+task_id
    existing=next((t for t in app.db.list('task')+app.db.list('task',True) if t['id']==tid),None)
    if existing:return existing
    folder=files/'tasks'/task_id
    definition=tomllib.loads((folder/'task.toml').read_text(encoding='utf-8'))
    baseline=next((b for b in app.db.list('baseline') if b.get('sourceUrl')==item['repositoryUrl'] and b.get('sourceCommit')==item['baseCommit']),None)
    if baseline:verify_snapshot(app.local/'baselines'/baseline['id']/'files',baseline['manifest'])
    else:baseline=import_repository(app,{'url':item['repositoryUrl'],'commit':item['baseCommit']})
    prompt=(folder/'instruction.md').read_text(encoding='utf-8')
    # Preserve original wording; environment instructions remain outside the development prompt.
    with app.lock:
        return app.save_task({'id':tid,'title':item['title'],'description':definition['metadata'].get('display_description',''),
            'inputPrompt':prompt,'taskParadigm':'deterministic-bugfix' if item['category']=='bugfix' else 'open-ended-project',
            'requiresBaseline':True,'baselineId':baseline['id'],'channel':'deepswe-core','difficulty':'未标注','hasFrontendUI':False,
            'checks':[],'sourceKind':'deepswe','referenceUrl':item['taskUrl'],'license':source['license'],
            'sourceNote':'固定版本源码已下载；隐藏验收在 public-sources 中单独保存，参考解未解包。桌面改编运行，不是官方排行榜同条件运行。',
            'environmentNote':f"{item['language']} · 上游 Linux 环境；源码已就绪，本机依赖未验证。上游镜像：{definition['environment'].get('docker_image','见环境定义')}。原生验收尚未接入，不生成官方通过率。",
            'publicSource':{'id':task_id,'revision':source['revision'],'baseCommit':item['baseCommit'],'category':item['category'],
                'language':item['language'],'sourceReady':True,'environmentStatus':'unverified','verifierStatus':'downloaded-not-integrated'}})


def start(app,data):
    items=data.get('taskIds',[]);source=catalog(app);known={t['id'] for t in source['tasks']}
    if not isinstance(items,list) or len(items)>10 or any(not isinstance(t,str) or t not in known for t in items):raise ValueError('请选择索引中的题目，每次最多准备10道；空列表仅下载题包。')
    items=list(dict.fromkeys(items))
    environment=data.get('prepareEnvironment') is True
    if environment and items!=['tengo-callable-instance-isolation']:raise ValueError('请选择已支持的 Tengo 本机环境。')
    with app.lock:
        if getattr(app,'source_thread',None) and app.source_thread.is_alive():return app.db.get('source_job','deepswe-download')
        old=app.db.list('source_job');revision=next((x['revision'] for x in old if x['id']=='deepswe-download'),None)
        job=app.db.save('source_job',{'id':'deepswe-download','status':'running','phase':'下载并校验题包','startedAt':now(),'taskIds':items,'completed':[],'errors':[]},revision)
        def update(**values):
            with app.lock:
                current=app.db.get('source_job',job['id']);current.update(values);return app.db.save('source_job',current,current['revision'])
        def work():
            completed=[];errors=[]
            try:
                files=bundle(app)
                for tid in items:
                    update(phase='准备源码 · '+tid)
                    try:
                        task=install(app,tid,files)
                        if environment:
                            from .native_verifier import prepare_environment
                            task=prepare_environment(app,task,lambda phase:update(phase=phase))
                        completed.append(task['id'])
                    except Exception as exc:errors.append({'taskId':tid,'message':str(exc)[:600]})
                    update(completed=completed,errors=errors)
                phase=('本机环境与故障起点已验证' if environment and not errors else '已保存题包与源码；按题查看环境状态') if items else '已保存全部题面与验收包；目标源码需按题下载'
                update(status='partial' if errors else 'completed',phase=phase,endedAt=now())
            except Exception as exc:update(status='failed',phase='题包准备失败，可重试',errors=[{'taskId':'bundle','message':str(exc)[:600]}],endedAt=now())
        app.source_thread=threading.Thread(target=work,daemon=True);app.source_thread.start()
        return job
