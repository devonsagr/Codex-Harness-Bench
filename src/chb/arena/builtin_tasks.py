"""Bundled task installation; no network, execution, or overwrite of saved tasks."""
import json
import tomllib
import subprocess
import re
import os
import shutil
import time

BUNDLED = {'search-notes-v1','storage-migration-v1','csv-catalog-v1','invoice-reconcile-v1','web-metrics-v1'}
CREATIVE_WEB = 'creative-web-v1'
CREATIVE_WEB_VERIFIER_VERSION = '2026-09-28-browser-v3'
OPEN_WORK = 'open-work-v1'


def creative_web_catalog(root):
    path=root/'tasks'/CREATIVE_WEB/'catalog.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []


def creative_prompt(entry):
    return entry['prompt']+'\n\n交付约定：直接在当前工作目录制作，打开 index.html 即可离线预览；不依赖外网、CDN 或收费服务。视觉风格、布局与实现路径由你决定。'


def open_work_catalog(root):
    path=root/'tasks'/OPEN_WORK/'catalog.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []


def creative_verifier_needs_refresh(app,task,image):
    """Refresh only the trusted creative checker; old captured digests stay frozen."""
    if image!='chb-verifier:'+CREATIVE_WEB or not any(
            task.get('id')=='original-creative-'+entry['id'] for entry in creative_web_catalog(app.root)):
        return False
    from .service import shell
    try:
        result=shell(['docker','image','inspect',image,'--format',
                      '{{ index .Config.Labels "org.chb.verifier.version" }}'],timeout=15)
    except (OSError,subprocess.SubprocessError):return False
    return result.returncode==0 and result.stdout.strip()!=CREATIVE_WEB_VERIFIER_VERSION


def prepare_missing_verifier(app, task, image):
    """Build only a trusted bundled verifier after an explicit check request."""
    from .evalplus_source import prepare as prepare_evalplus, IMAGE as EVALPLUS_IMAGE
    evalplus=task.get('sourceKind')=='evalplus-local' and image==EVALPLUS_IMAGE
    name=task.get('id','').removeprefix('original-')
    from .behavior import IMAGE, check_definition
    behavior=image==IMAGE and check_definition(task,app.root) is not None
    creative=image=='chb-verifier:'+CREATIVE_WEB and any(task.get('id')=='original-creative-'+entry['id'] for entry in creative_web_catalog(app.root))
    from .community_tasks import IMAGE as COMMUNITY_IMAGE, catalog as community_catalog
    community=image==COMMUNITY_IMAGE and task.get('sourceKind')=='community-adapted' and any(task.get('id')=='community-'+entry['id'] for entry in community_catalog(app.root))
    if not creative and not behavior and not community and not evalplus and (task.get('id')!='original-'+name or name not in BUNDLED or image!='chb-verifier:'+name):return False
    from .service import shell
    engine=shell(['docker','info','--format','{{.OSType}}'],timeout=15)
    if (engine.returncode or engine.stdout.strip()!='linux') and os.name=='nt' and shutil.which('docker'):
        subprocess.run(['docker','desktop','start','--detach'],capture_output=True,timeout=30)
        for _ in range(6):
            time.sleep(3)
            engine=shell(['docker','info','--format','{{.OSType}}'],timeout=5)
            if engine.returncode==0 and engine.stdout.strip()=='linux':break
    if engine.returncode or engine.stdout.strip()!='linux':
        raise ValueError('Docker Linux 引擎不可用；本次验收未开始，也不记零分。')
    if evalplus:return prepare_evalplus(app,task,image)
    if (creative or behavior or community or name=='web-metrics-v1') and shell(['docker','image','inspect','chb-reviewer:machine-v1'],timeout=20).returncode:
        reviewer=subprocess.run(['docker','build','-t','chb-reviewer:machine-v1',str(app.root/'reviewer')],
                                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=900)
        if reviewer.returncode:raise ValueError('浏览器验收基础镜像自动准备失败；本次未记分。'+reviewer.stderr[-800:])
    folder=app.root/'tasks'/('community-web-v1' if community else CREATIVE_WEB if creative or behavior else name)/'tests'
    result=subprocess.run(['docker','build','-t',image,*(['-f',str(folder/'Dockerfile.behavior')] if behavior else []),str(folder)],
                          capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=900)
    if result.returncode:raise ValueError('内置题验收镜像自动准备失败；本次未记分。'+result.stderr[-800:])
    return True

def import_originals(app):
    """Install missing bundled tasks, preserving edits and archived records."""
    names={'search-notes-v1':('笔记搜索修复','swe-bugfix',False,'Python',['coding','debugging','maintainability']),
           'storage-migration-v1':('笔记存储演进：归档与 SQLite','long-horizon',False,'Python',['coding','data','long-context','reliability']),
           'csv-catalog-v1':('CSV 目录导入修复','data-analysis',False,'Python',['coding','data','debugging']),
           'invoice-reconcile-v1':('业务账务核对：退款、异常与精确金额','business-workflow',False,'Python',['coding','data','reasoning','reliability']),
           'web-metrics-v1':('业务指标网页：筛选、漏斗与 CSV 导出','web-interface',True,'HTML/JavaScript',['coding','frontend','browser','data','requirements'])}
    saved=[]
    for name,(title,family,frontend,language,tags) in names.items():
        tid='original-'+name
        if any(t['id']==tid for t in app.db.list('task')+app.db.list('task',True)):continue
        folder=app.root/'tasks'/name
        if not (folder/'task.toml').is_file():continue
        definition=tomllib.loads((folder/'task.toml').read_text(encoding='utf-8'))
        baseline=app.import_files('baseline',{'path':str(folder/'environment/fixture'),'name':title+' 起点'})
        prompt=(folder/'instruction.md').read_text(encoding='utf-8').replace('/app','当前工作目录')
        stages=[];checks=[]
        for i,step in enumerate(definition.get('steps',[])):
            stages.append({'title':step['name'],'prompt':(folder/'steps'/step['name']/'instruction.md').read_text(encoding='utf-8').replace('/app','当前工作目录')})
            checks.append({'label':step['name']+' 独立验收','image':'chb-verifier:'+name,'argv':['env','CHB_STAGE='+step['name'],'python','-I','/tests/verify.py','/app'],'weight':1,'timeout':45,'stageIndex':i})
        if not stages:
            stages=[{'title':'完成修复','prompt':prompt}]
            check_argv=['node','/tests/verify.cjs','/app'] if frontend else ['python','-I','/tests/verify.py','/app']
            checks=[{'label':'独立验收','image':'chb-verifier:'+name,'argv':check_argv,'weight':1,'timeout':90 if frontend else 45}]
        saved.append(app.save_task({'id':tid,'title':title,'inputPrompt':prompt,'stages':stages,'checks':checks,'baselineId':baseline['id'],'requiresBaseline':True,
          'hasFrontendUI':frontend,'taskFamily':family,'capabilityTags':tags,'language':language,
          'taskParadigm':'open-ended-project' if len(stages)>1 or family in {'business-workflow','web-interface'} else 'deterministic-bugfix',
          'channel':'frontend-ui' if frontend else 'deepswe-core','difficulty':'Medium',
          'sourceKind':'repository-original','referenceUrl':'https://github.com/devonsagr/1/tree/main/tasks/'+name,'license':'MIT',
          'environmentNote':('HTML/JavaScript · 离线可打开；独立 Chromium 浏览器验收需先准备项目 reviewer 镜像。' if frontend else 'Python 3.12+ · 标准库，无第三方依赖。已有测试：python -m unittest discover -s tests -v。'),
          'sourceNote':'项目原创完整题目。仅导入 environment/fixture；参考解和独立验收器不交给桌面。容器路径在题面改写为当前工作目录。桌面真实成绩仍需重新执行。'}))
    saved.extend(import_creative_web(app))
    saved.extend(import_open_work(app))
    from .community_tasks import install as import_community
    saved.extend(import_community(app))
    return {'imported':saved}


def import_creative_web(app):
    """Install a shared starter and distinct creative briefs without changing saved revisions."""
    entries=creative_web_catalog(app.root)
    missing=[entry for entry in entries if not any(t['id']=='original-creative-'+entry['id'] for t in app.db.list('task')+app.db.list('task',True))]
    if not missing:return []
    folder=app.root/'tasks'/CREATIVE_WEB
    baseline=app.import_files('baseline',{'path':str(folder/'environment/fixture'),'name':'原创网页创作题 · 空白起点'})
    saved=[]
    for entry in missing:
        prompt=creative_prompt(entry)
        saved.append(app.save_task({
            'id':'original-creative-'+entry['id'],'title':entry['title'],'description':entry['category'],
            'inputPrompt':prompt,'stages':[{'title':'完成创作与自检','prompt':prompt}],
            'checks':[{'label':'离线浏览器基础检查（不评审美）','image':'chb-verifier:'+CREATIVE_WEB,
                       'argv':['node','/tests/verify.cjs','/app',entry['profile']],'weight':1,'timeout':90,'kind':'functional'}],
            'evaluationRubric':entry['reviewFocus'],'baselineId':baseline['id'],'requiresBaseline':True,
            'hasFrontendUI':True,'taskFamily':'web-interface','capabilityTags':entry['tags'],
            'language':'HTML/CSS/JavaScript','taskParadigm':'open-ended-project','channel':'frontend-ui',
            'difficulty':entry['difficulty'],'sourceKind':'repository-original',
            'referenceUrl':'https://github.com/devonsagr/1/tree/main/tasks/creative-web-v1',
            'license':'MIT','environmentNote':'离线静态网页起点；直接打开 index.html。程序烟检使用隔离 Chromium 和共享 verifier 镜像，首次点击检查自动准备。',
            'sourceNote':'原创开放题。程序只检查页面可运行、基本结构/交互与窄屏；主题表达、视觉质量和需求完成度需查看实际页面后复核。不得把烟检通过当成完整网页成绩。'}))
    return saved


def import_open_work(app):
    """Install distinct bundled starters; no hidden answer or generic smoke score."""
    saved=[]
    for entry in open_work_catalog(app.root):
        slug=entry['id']
        if not re.fullmatch(r'[a-z0-9-]{4,64}',slug):raise ValueError('开放任务编号无效。')
        tid='original-open-'+slug
        if any(task['id']==tid for task in app.db.list('task')+app.db.list('task',True)):continue
        folder=app.root/'tasks'/OPEN_WORK/'environment'/slug
        if not folder.is_dir():raise ValueError('开放任务缺少独立起点：'+slug)
        baseline=app.import_files('baseline',{'path':str(folder),'name':entry['title']+' 起点'})
        prompt=entry['prompt']+'\n\n交付约定：只在当前工作目录处理本题，使用本地文件；必要假设须标明。程序检查尚未配置，实际交付须回收后由有引用的 AI 审查及人工复核，不得把起点或题面当作已完成。'
        stages=[{'title':stage['title'],'prompt':prompt+'\n\n本阶段要求：'+stage['prompt']} for stage in entry.get('stages',[])] or [{'title':'完成任务并自检','prompt':prompt}]
        saved.append(app.save_task({
            'id':tid,'title':entry['title'],'description':entry['category'],
            'inputPrompt':prompt,'stages':stages,'checks':[],
            'evaluationRubric':entry['reviewFocus'],'baselineId':baseline['id'],'requiresBaseline':True,
            'hasFrontendUI':False,'taskFamily':entry['family'],'capabilityTags':entry['tags'],
            'language':'Python/文档','taskParadigm':'open-ended-project','channel':entry['channel'],
            'difficulty':entry['difficulty'],'sourceKind':'repository-original',
            'referenceUrl':'https://github.com/devonsagr/1/tree/main/tasks/open-work-v1',
            'license':'MIT','environmentNote':'每题有不同的离线文件起点；无外部 API 或服务。尚无独立程序验收，需按本题依据审查实际产物。',
            'sourceNote':'项目原创开放实践题；与 DeepSWE 原题和网页基础烟检分开。程序检查为零不表示零分或完成，AI 质量意见和人工复核须附实际证据。'}))
    return saved
