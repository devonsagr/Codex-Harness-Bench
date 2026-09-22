"""Durable, idempotent preparation; downloads never hold the main API lock."""
import copy
import threading
from .files import fingerprint, now
from .service import identifier
from .public_sources import catalog, task_bundle, install, DOWNLOAD_LOCK


def start(app,data):
    data=copy.deepcopy(data);request_id=identifier(data.get('requestId'))
    ids=data.get('taskIds');configs=data.get('configIds')
    if not isinstance(ids,list) or not 1<=len(ids)<=10 or any(not isinstance(t,str) for t in ids) or len(set(ids))!=len(ids):raise ValueError('请选择1至10道题。')
    if not isinstance(configs,list) or not 1<=len(configs)<=2:raise ValueError('请选择一至两套配置。')
    for tid in ids:identifier(tid)
    source_ids={'deepswe-'+t['id']:t['id'] for t in catalog(app)['tasks']}
    with app.lock:
        saved=next((j for j in app.db.list('preparation_job') if j['id']==request_id),None)
        if saved:
            if saved['fingerprint']!=fingerprint(data):raise ValueError('同一准备请求的内容已改变，请重新创建。')
            if saved['status'] in {'running','completed'}:return saved
        if any(j['status']=='running' for j in app.db.list('preparation_job')):raise ValueError('另一次评测正在准备，请等待完成后再创建。')
        config_revisions={cid:app.db.get('config',identifier(cid))['revision'] for cid in configs}
        existing={t['id']:t for t in app.db.list('task')}
        archived={t['id'] for t in app.db.list('task',True)}
        for tid in ids:
            if tid in archived:raise ValueError('请先恢复已归档题目。')
            if tid not in existing and tid not in source_ids:raise ValueError('所选题目不存在。')
        task_revisions={tid:existing[tid]['revision'] for tid in ids if tid in existing}
        job=app.db.save('preparation_job',{'id':request_id,'fingerprint':fingerprint(data),'status':'running',
            'phase':'核对所选题目','taskIds':ids,'startedAt':now(),'runId':None,'error':None},saved['revision'] if saved else None)

    def update(**values):
        with app.lock:
            job=app.db.get('preparation_job',request_id);job.update(values)
            return app.db.save('preparation_job',job,job['revision'])

    def worker():
        try:
            from .native_verifier import supported,prepare_environment,runtime
            for tid in ids:
                if tid in source_ids:
                    update(phase='准备题目与固定源码 · '+source_ids[tid])
                    with DOWNLOAD_LOCK:
                        task=install(app,source_ids[tid],task_bundle(app,source_ids[tid]))
                    if tid in task_revisions and task['revision']!=task_revisions[tid]:raise ValueError('准备期间题目被编辑，请重新核对后创建。')
                    if supported(task) and (task.get('publicSource',{}).get('environmentStatus')!='ready-windows' or not (runtime(app)/'go/bin/go.exe').is_file()):
                        task=prepare_environment(app,task,lambda phase:update(phase=phase))
                    task_revisions[tid]=task['revision']
            update(phase='从缓存复制到本次独立工作区')
            with app.lock:
                if any(app.db.get('config',cid)['revision']!=rev for cid,rev in config_revisions.items()):raise ValueError('准备期间配置已修改，请重新核对后创建。')
                if any(app.db.get('task',tid)['revision']!=rev for tid,rev in task_revisions.items()):raise ValueError('准备期间题目已修改，请重新核对后创建。')
                run=app.prepare(data)
            update(status='completed',phase='独立工作区已准备',runId=run['id'],endedAt=now())
        except Exception as exc:
            message=str(exc)
            safe=message if isinstance(exc,ValueError) and len(message)<250 and any('\u4e00'<=c<='\u9fff' for c in message) else '准备失败；已缓存内容保留，请检查网络与磁盘后重试。'
            update(status='failed',phase='尚未完成工作区准备',error=safe,endedAt=now())
    thread=threading.Thread(target=worker,daemon=True)
    app.preparation_thread=thread;thread.start()
    return job
