"""Authenticated HTTP operations; no arbitrary file-serving or shell endpoint."""
import copy
import io
import json
from pathlib import Path
import tomllib
import zipfile
from .files import inventory, verify_snapshot, now
from .service import identifier, text
from .jobs import start_job, stop_job
from . import task_import
from . import skills, config_import
from .contracts import task_view


def post(app,route,data):
    parts=route.removeprefix('/api/arena/').split('/')
    with app.lock:
        if parts==['configs','save']:return app.save_config(data)
        if parts==['tasks','save']:return app.save_task(data)
        if parts==['tasks','import-preview']:return task_import.preview(app,data.get('document'))
        if parts==['tasks','import']:return task_import.commit(app,data)
        if parts==['tasks','import-originals']:return import_originals(app)
        if parts==['skills','import']:return app.import_files('skill',data)
        if parts==['skills','scan']:return skills.scan(app,data)
        if parts==['skills','import-selected']:return skills.import_selected(app,data)
        if parts==['configs','import-preview']:return config_import.preview(app,data)
        if parts==['configs','import-source']:return config_import.commit(app,data)
        if parts==['baselines','import']:return app.import_files('baseline',data)
        if parts==['configs','import-current']:
            return config_import.commit(app,{**data,'scope':'global'})
        if parts==['runs','prepare']:return app.prepare(data)
        if len(parts)==3 and parts[2]=='archive' and parts[0] in {'configs','tasks','runs'}:
            kind={'configs':'config','tasks':'task','runs':'run'}[parts[0]]
            if kind=='run' and any(k[0]==parts[1] for k in app.jobs):raise ValueError('请先结束后台检查再归档。')
            if kind=='run' and any(t.get('ownedContainers') for t in app.db.get('run',identifier(parts[1]))['trials']):raise ValueError('请先确认检查容器已清理，再归档记录。')
            result=app.db.archive(kind,identifier(parts[1]),bool(data.get('archived')),data.get('revision'))
            return task_view(result) if kind=='task' else result
        if len(parts)==3 and parts[0]=='runs' and parts[2]=='restore-config':return app.restore_config(identifier(parts[1]),identifier(data.get('configId')))
        if len(parts)==5 and parts[0]=='runs' and parts[2]=='trials':
            rid,tid,action=identifier(parts[1]),identifier(parts[3]),parts[4]
            if action in {'check','judge'}:return start_job(app,rid,tid,action,data)
            if action=='stop':return stop_job(app,rid,tid)
            return app.mutate(rid,tid,action,data)
    raise ValueError('没有这个操作。')


def import_originals(app):
    """Opt-in adapters for this repository's three complete, separately verified fixtures."""
    names={'search-notes-v1':'笔记搜索修复','storage-migration-v1':'笔记存储演进：归档与 SQLite','csv-catalog-v1':'CSV 目录导入修复'}
    saved=[]
    for name,title in names.items():
        tid='original-'+name
        if any(t['id']==tid for t in app.db.list('task')+app.db.list('task',True)):continue
        folder=app.root/'tasks'/name
        definition=tomllib.loads((folder/'task.toml').read_text(encoding='utf-8'))
        baseline=app.import_files('baseline',{'path':str(folder/'environment/fixture'),'name':title+' 起点'})
        prompt=(folder/'instruction.md').read_text(encoding='utf-8').replace('/app','当前工作目录')
        stages=[];checks=[]
        for i,step in enumerate(definition.get('steps',[])):
            stages.append({'title':step['name'],'prompt':(folder/'steps'/step['name']/'instruction.md').read_text(encoding='utf-8').replace('/app','当前工作目录')})
            checks.append({'label':step['name']+' 独立验收','image':'chb-verifier:'+name,'argv':['env','CHB_STAGE='+step['name'],'python','-I','/tests/verify.py','/app'],'weight':1,'timeout':45,'stageIndex':i})
        if not stages:
            stages=[{'title':'完成修复','prompt':prompt}]
            checks=[{'label':'独立验收','image':'chb-verifier:'+name,'argv':['python','-I','/tests/verify.py','/app'],'weight':1,'timeout':45}]
        saved.append(app.save_task({'id':tid,'title':title,'inputPrompt':prompt,'stages':stages,'checks':checks,'baselineId':baseline['id'],
          'hasFrontendUI':False,'taskParadigm':'open-ended-project' if len(stages)>1 else 'deterministic-bugfix','channel':'deepswe-core','difficulty':'Medium',
          'sourceKind':'repository-original','referenceUrl':'https://github.com/devonsagr/1/tree/main/tasks/'+name,'license':'MIT',
          'sourceNote':'项目原创完整题目。仅导入 environment/fixture；参考解和独立验收器不交给桌面。容器路径在题面改写为当前工作目录。桌面真实成绩仍需重新执行。'}))
    return {'imported':saved}


def export(app,rid):
    with app.lock:
        run=app.db.get('run',identifier(rid))
        if any(k[0]==rid for k in app.jobs):raise ValueError('后台操作仍在进行，请完成后导出。')
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('record.json',json.dumps(app.present_run(run),ensure_ascii=False,indent=2))
            archive.writestr('README.txt','本地评测导出，包含私有规则与产物。原生完整日志、认证文件和宿主配置原文不包含在内。\n来源为桌面手动执行与工作台回收；不可据此冒充自动验证全部完成。\n')
            total=0
            for trial in run['trials']:
                folder=app.local/'runs'/rid/trial['id']
                sources=[('baseline',folder/'baseline',trial['baseline'])]+[(c['id'],folder/'captures'/c['id']/'files',c['manifest']) for c in trial['captures']]
                for label,source,manifest in sources:
                    verify_snapshot(source,manifest)
                    for name,body in inventory(source)[0].items():
                        total+=len(body)
                        if total>200_000_000:raise ValueError('导出超过 200 MB，请在本地按运行目录保存证据。')
                        archive.writestr(trial['id']+'/'+label+'/'+name,body)
        return buffer.getvalue()
