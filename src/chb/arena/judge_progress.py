"""Bounded, read-only execution evidence for a trial's owned judge jobs."""
import json
import re
import time
from datetime import datetime
from .files import safe_path


def redact(text):
    text=str(text)
    text=re.sub(r'(?i)(Bearer\s+)[\w.\-]+',r'\1[redacted]',text)
    text=re.sub(r'\bsk-[A-Za-z0-9_-]{12,}', '[redacted]', text)
    return re.sub(r'(?i)(["\']?(?:access_token|refresh_token|id_token|api_key|password)["\']?\s*[:=]\s*["\']?)[^\s,"\'}]+',r'\1[redacted]',text)


def read_judge_usage(job):
    """Read cumulative CLI counters, including a cancelled run's last rollout."""
    paths=([job/'events.jsonl'] if (job/'events.jsonl').is_file() else [])
    paths+=list(job.glob('harbor/**/agent/codex.txt'))[:2]
    paths+=list(job.glob('harbor/**/agent/sessions/**/rollout-*.jsonl'))[:4]
    latest=None
    for candidate in paths:
        path=safe_path(job,candidate.relative_to(job).as_posix())
        with path.open('rb') as stream:
            size=path.stat().st_size;start=max(0,size-1_000_000);stream.seek(start)
            lines=stream.read(1_000_000).decode('utf-8',errors='replace').splitlines()
        for line in lines[1:] if start else lines:
            try:event=json.loads(line)
            except ValueError:continue
            if not isinstance(event,dict):continue
            payload=event.get('payload') if isinstance(event.get('payload'),dict) else {}
            item=event.get('item') if isinstance(event.get('item'),dict) else {}
            info=payload.get('info') if isinstance(payload.get('info'),dict) else {}
            usage=(event.get('usage') or item.get('usage') or
                   (info.get('total_token_usage') if payload.get('type')=='token_count' else None))
            if not isinstance(usage,dict):continue
            names=('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens')
            if not all(type(usage.get(key,0)) is int and 0<=usage.get(key,0)<=1_000_000_000 for key in names):continue
            if 'input_tokens' not in usage or 'output_tokens' not in usage:continue
            row={'inputTokens':usage['input_tokens'],'cachedInputTokens':usage.get('cached_input_tokens',0),
                 'outputTokens':usage['output_tokens'],'reasoningOutputTokens':usage.get('reasoning_output_tokens',0)}
            if latest is None or row['inputTokens']+row['outputTokens']>latest['inputTokens']+latest['outputTokens']:
                latest=row
    return latest


def read_operation_usage(app,rid,tid,execution,job):
    """Include previous feedback jobs without double-counting this CLI job."""
    from .judge_repair import combined_usage
    from .service import identifier
    repair=execution.get('automaticRepair') or {}
    prior=[row.get('jobId') for row in repair.get('attempts',[]) if row.get('jobId')]
    if repair.get('previousJobId'):prior.append(repair['previousJobId'])
    ids=list(dict.fromkeys([*prior,job.name]))
    return combined_usage([{'usage':read_judge_usage(safe_path(app.local,
        f'runs/{rid}/{tid}/reviews/{identifier(key)}'))} for key in ids])


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
    commands={};messages=[];truncated=False;last_activity=None
    for log in logs:
        # Verify ownership/no symlink before reading only the last 1 MB.
        path=safe_path(job,log.relative_to(job).as_posix())
        with path.open('rb') as stream:
            last_activity=max(last_activity or 0,path.stat().st_mtime)
            size=path.stat().st_size;start=max(0,size-1_000_000);stream.seek(start)
            raw=stream.read(1_000_000)
        truncated|=bool(start)
        lines=raw.decode('utf-8',errors='replace').splitlines()
        for line in lines[1:] if start else lines:
            try:event=json.loads(line)
            except ValueError:continue  # The writer may not have finished the last line.
            if not isinstance(event,dict):continue
            item=event.get('item',{})
            if isinstance(item,dict) and item.get('type')=='agent_message' and event.get('type')=='item.completed':
                message=item.get('text','')
                try:
                    structured=json.loads(message)
                    if isinstance(structured,dict) and isinstance(structured.get('summary'),str):message=structured['summary']
                except (ValueError,TypeError):pass
                messages.append(redact(message)[:4000])
            if not isinstance(item,dict) or item.get('type')!='command_execution':continue
            if event.get('type') not in {'item.started','item.updated','item.completed'}:continue
            key=str(item.get('id',''))
            commands[key]={'id':key,'status':'completed' if event['type']=='item.completed' else 'running',
                'command':redact(item.get('command',''))[:6000],
                'output':redact(item.get('aggregated_output',''))[-10000:],'exitCode':item.get('exit_code')}
    rows=list(commands.values())
    prompt=safe_path(job,'task/instruction.md')
    instruction=''
    if prompt.is_file():
        with prompt.open('r',encoding='utf-8') as stream:instruction=redact(stream.read(200001))
    packet=safe_path(job,'task/environment/judge-packet.json')
    protocol=safe_path(job,'protocol.json')
    packet_info=None
    if packet.is_file() and protocol.is_file() and protocol.stat().st_size<10000:
        try:
            packet_info={'path':str(packet),'bytes':packet.stat().st_size,
                         'sha256':json.loads(protocol.read_text(encoding='utf-8')).get('packetSha256')}
        except (ValueError,OSError):pass
    started=execution.get('startedAt');end=execution.get('endedAt')
    try:elapsed=max(0,int((datetime.fromisoformat(end).timestamp() if end else time.time())-datetime.fromisoformat(started).timestamp()))
    except (ValueError,TypeError):elapsed=None
    runtime=safe_path(job,'runtime.json');runtime_info={}
    if runtime.is_file() and runtime.stat().st_size<10000:runtime_info=json.loads(runtime.read_text(encoding='utf-8'))
    route=safe_path(job,'connection.json')
    if route.is_file() and route.stat().st_size<10000:execution={**execution,'connection':json.loads(route.read_text(encoding='utf-8'))}
    return {'execution':{**execution,'jobId':job_id,'logDirectory':str(job),'elapsedSeconds':elapsed,
                         'lastActivitySecondsAgo':max(0,int(time.time()-last_activity)) if last_activity else None},
            'usage':read_operation_usage(app,rid,tid,execution,job),
            'instruction':instruction[:200000],'instructionTruncated':len(instruction)>200000,
            'packet':packet_info,'messages':messages[-10:],
            'runtime':runtime_info,
            'commands':rows[-30:],'truncated':truncated or len(rows)>30,
            'error':trial.get('lastJobError',{}).get('message')}
