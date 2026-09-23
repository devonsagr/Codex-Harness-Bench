"""Authenticated HTTP operations; no arbitrary file-serving or shell endpoint."""
import copy
import io
import json
from pathlib import Path
import zipfile
from .files import inventory, verify_snapshot, now
from .service import identifier, text
from .jobs import start_job, stop_job
from . import task_import
from . import skills, config_import
from .builtin_tasks import import_originals
from . import codex_apply
from .contracts import task_view


def post(app,route,data):
    parts=route.removeprefix('/api/arena/').split('/')
    if parts==['runs','prepare-async']:
        from .preparation import start
        return start(app,data)
    if parts==['sources','preview']:
        from .public_sources import preview
        return preview(app,identifier(data.get('taskId')))
    if parts==['sources','prepare']:
        from .public_sources import start
        return start(app,data)
    if parts==['storage','status']:
        from .storage import status
        return status(app)
    if parts==['storage','workspace']:
        from .storage import workspace
        return workspace(app,data)
    if parts==['storage','delete-run']:
        from .delete_run import delete
        return delete(app,data)
    if parts==['baselines','import-github']:
        from .repository_source import import_repository
        return import_repository(app,data)
    with app.lock:
        if parts==['configs','save']:return app.save_config(data)
        if parts==['codex','restore-initial']:
            from .initial_config import restore
            return restore(app,data)
        if parts==['codex','status']:return codex_apply.status(app)
        if parts==['codex','apply']:return codex_apply.apply(app,data)
        if parts==['codex','switch']:return codex_apply.switch(app,data)
        if parts==['codex','restore']:return codex_apply.restore(app,data)
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
            if action in {'inspection-status','inspection-file','inspection-prepare','inspection-open','inspection-save'}:
                from .human_inspection import operate
                return operate(app,rid,tid,action,data)
            if action=='judge-progress':
                from .judge_progress import read_progress
                return read_progress(app,rid,tid)
            if action=='judge-revalidate':
                from .jobs import revalidate_saved_review
                return revalidate_saved_review(app,rid,tid)
            if action=='apply-config':
                run,trial=app.trial(rid,tid)
                if run.get('archived') or trial['state']!='prepared':raise ValueError('仅在本题开始前应用冻结配置。')
                config=next(c for c in run['configs'] if c['id']==trial['configId'])
                result=codex_apply.switch(app,{'revision':config['revision']},frozen=config)
                trial['codexApplicationId']=result['id']
                trial['appliedHostFingerprint']=app.host_fingerprint()
                app.event(run,'已将本题冻结配置写入本机 Codex；桌面实际生效仍需核对。',tid)
                app.db.save('run',run,run['revision'])
                return result
            if action=='native-log':
                from .files import safe_path
                run,trial=app.trial(rid,tid)
                execution=trial.get('nativeExecution') or {}
                suite=data.get('suite',1)
                if type(suite) is not int or not 1<=suite<=7:raise ValueError('测试组编号无效。')
                if not execution.get('jobId'):return {'output':'尚未执行测试','truncated':False}
                log=safe_path(app.local,f"runs/{rid}/{tid}/native-checks/{identifier(execution['jobId'])}/suite-{suite}.jsonl")
                if not log.is_file():return {'output':'该测试组尚未产生输出','truncated':False}
                with log.open('rb') as stream:
                    length=log.stat().st_size;stream.seek(max(0,length-20000));body=stream.read(20000)
                return {'output':body.decode('utf-8',errors='replace'),'truncated':length>20000}
            if action=='native-check':return start_job(app,rid,tid,'native',data)
            if action in {'check','judge'}:return start_job(app,rid,tid,action,data)
            if action=='stop':return stop_job(app,rid,tid)
            return app.mutate(rid,tid,action,data)
    raise ValueError('没有这个操作。')




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
