"""Bounded, read-only execution evidence for a trial's owned judge jobs."""
import json
import re
from .files import safe_path


def redact(text):
    text=str(text)
    text=re.sub(r'(?i)(Bearer\s+)[\w.\-]+',r'\1[redacted]',text)
    text=re.sub(r'\bsk-[A-Za-z0-9_-]{12,}', '[redacted]', text)
    return re.sub(r'(?i)(["\']?(?:access_token|refresh_token|id_token|api_key|password)["\']?\s*[:=]\s*["\']?)[^\s,"\'}]+',r'\1[redacted]',text)


def read_progress(app,rid,tid):
    from .service import identifier
    run=app.db.get('run',identifier(rid))
    trial=next((t for t in run['trials'] if t['id']==identifier(tid)),None)
    if trial is None:raise ValueError('运行项不存在。')
    execution=trial.get('judgeExecution',{})
    folder=safe_path(app.local,f'runs/{rid}/{tid}/reviews')
    job_id=execution.get('jobId')
    if not job_id:
        if execution:return {'execution':execution,'commands':[],'truncated':False,'error':trial.get('lastJobError',{}).get('message')}
        candidates=sorted(folder.glob('job-*'),key=lambda p:p.stat().st_mtime,reverse=True)
        if not candidates:return {'execution':execution,'commands':[],'truncated':False}
        job_id=candidates[0].name
    job=safe_path(folder,identifier(job_id))
    logs=[job/'events.jsonl'] if (job/'events.jsonl').is_file() else list(job.glob('harbor/**/agent/codex.txt'))[:2]
    commands={};truncated=False
    for log in logs:
        # Verify ownership/no symlink before reading only the last 1 MB.
        path=safe_path(job,log.relative_to(job).as_posix())
        with path.open('rb') as stream:
            size=path.stat().st_size;start=max(0,size-1_000_000);stream.seek(start)
            raw=stream.read(1_000_000)
        truncated|=bool(start)
        lines=raw.decode('utf-8',errors='replace').splitlines()
        for line in lines[1:] if start else lines:
            try:event=json.loads(line)
            except ValueError:continue  # The writer may not have finished the last line.
            if not isinstance(event,dict):continue
            item=event.get('item',{})
            if not isinstance(item,dict) or item.get('type')!='command_execution':continue
            if event.get('type') not in {'item.started','item.updated','item.completed'}:continue
            key=str(item.get('id',''))
            commands[key]={'id':key,'status':'completed' if event['type']=='item.completed' else 'running',
                'command':redact(item.get('command',''))[:6000],
                'output':redact(item.get('aggregated_output',''))[-10000:],'exitCode':item.get('exit_code')}
    rows=list(commands.values())
    return {'execution':{**execution,'jobId':job_id,'logDirectory':str(job)},
            'commands':rows[-30:],'truncated':truncated or len(rows)>30,
            'error':trial.get('lastJobError',{}).get('message')}
