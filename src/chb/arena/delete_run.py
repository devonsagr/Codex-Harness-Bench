"""Explicit deletion of an entire evaluation, separate from workspace cleanup."""
import json
import shutil
from pathlib import Path
from .files import safe_path
from .service import identifier
from .storage import reject_links,status

def delete(app,data):
    rid=identifier(data.get('runId'))
    if data.get('confirmation')!='永久删除评测 '+rid:raise ValueError('请按提示输入“永久删除评测 记录编号”。此操作同时删除整次评测的快照、日志、评分及工作区。')
    if data.get('desktopStopped') is not True:raise ValueError('请先确认这次评测的所有 Codex 对话已停止写入。')
    with app.lock:
        run=app.db.get('run',rid)
        if data.get('revision')!=run['revision']:raise ValueError('评测已更新，请刷新并重新核对删除范围。')
        if any((rid,t['id']) in app.jobs or t['state'] in {'working','checking','judging'} or t.get('ownedContainers') for t in run['trials']):raise ValueError('评测仍有执行或检查，不能删除。')
        owned=[safe_path(app.local,'runs/'+rid),safe_path(app.local,'trash/workspaces/'+rid)]
        runtime=(app.local/'reviewer-runtime').resolve()
        # Only receipt-declared private scratch folders, never supplied arbitrary paths.
        for receipt in owned[0].glob('*/reviews/job-*/runtime.json'):
            checked=safe_path(owned[0],receipt.relative_to(owned[0]).as_posix())
            if checked.stat().st_size>10000:raise ValueError('裁判运行回执异常，未开始删除。')
            value=json.loads(checked.read_text(encoding='utf-8'))
            for key,prefix in [('workspace','chb-review-work-'),('temporaryHome','chb-review-home-')]:
                path=Path(value[key])
                if path.resolve().parent!=runtime or not path.name.startswith(prefix):raise ValueError('裁判运行目录越界，未开始删除。')
                owned.append(safe_path(runtime,path.name))
        for path in owned:reject_links(path)
        # Durable intent leaves the evaluation visible for retry after partial deletion.
        run['deletionPending']=True
        run=app.db.save('run',run,run['revision'])
        for path in owned[2:]+owned[:2]:
            if path.exists():shutil.rmtree(path)
        with app.db.connect() as db:
            db.execute('PRAGMA secure_delete=ON')
            db.execute('BEGIN IMMEDIATE')
            preparations=[r['id'] for r in db.execute("SELECT id,body FROM records WHERE kind='preparation_job'") if json.loads(r['body']).get('runId')==rid]
            for kind,key in [('run',rid)]+[('preparation_job',key) for key in preparations]:
                db.execute('DELETE FROM revisions WHERE kind=? AND id=?',(kind,key))
                db.execute('DELETE FROM records WHERE kind=? AND id=?',(kind,key))
        with app.db.connect() as db:db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    return status(app)
