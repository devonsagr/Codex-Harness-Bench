"""Discover or import native traces bound to the exact prepared workspace."""
from datetime import datetime
from contextlib import closing
import json
import os
import sqlite3
from pathlib import Path

def normalized_path(value):
    return os.path.normcase(str(Path(value).resolve()).removeprefix('\\\\?\\'))


def read_trace(raw, workspace, previous_session=None):
    if not isinstance(raw,str) or len(raw)>15_000_000: raise ValueError('日志须为不超过 15 MB 的 JSONL 文本。')
    rows=[]
    for line in raw.splitlines():
        if line.strip():
            item=json.loads(line)
            if not isinstance(item,dict):raise ValueError('每条日志必须是 JSON 对象。')
            rows.append(item)
    metadata=[r.get('payload',{}) for r in rows if r.get('type')=='session_meta']
    if not metadata: raise ValueError('需要含 session_meta 与 cwd 的 Codex 原生日志，不能把其他任务的用量计入本次。')
    sessions={m.get('id') for m in metadata}
    if len(sessions)!=1 or not next(iter(sessions)):raise ValueError('日志混合了不同会话。')
    session=next(iter(sessions))
    if previous_session and previous_session!=session:raise ValueError('多轮日志的会话编号与此前不同。')
    expected=normalized_path(workspace)
    if any(not isinstance(m.get('cwd'),str) or normalized_path(m['cwd'])!=expected for m in metadata):raise ValueError('日志工作区与本次准备的目录不一致。')
    totals=[];models=set();efforts=set();errors=[];active=None;seconds=0;observed=False;started=None;ended=None;last_started=None;activity='unknown'
    for row in rows:
        p=row.get('payload') or {}
        if row.get('type')=='turn_context':
            if p.get('model'):models.add(p['model'])
            if p.get('effort'):efforts.add(p['effort'])
        if row.get('type')!='event_msg':continue
        if p.get('type')=='token_count':
            total=(p.get('info') or {}).get('total_token_usage')
            if total:
                required=['input_tokens','output_tokens','cached_input_tokens']
                if any(type(total.get(k)) is not int or total[k]<0 for k in required):raise ValueError('原生用量缺失或包含无效值。')
                if total['cached_input_tokens']>total['input_tokens']:raise ValueError('缓存输入不能大于总输入。')
                if totals and any(total[k]<totals[-1][k] for k in required):raise ValueError('累计用量出现回退，不能可靠合计。')
                totals.append(total)
        if p.get('type') in {'error','warning'}:
            msg=str(p.get('message',''))
            errors.append('quota_exhausted' if 'out of credits' in msg.lower() else 'rate_limit' if '429' in msg else 'execution_error')
        try:stamp=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
        except (KeyError,ValueError,AttributeError):continue
        if p.get('type') in {'task_started','turn_started'}:
            active=stamp;started=started or stamp;last_started=stamp;activity='running'
        if p.get('type') in {'task_complete','turn_completed','turn_aborted'} and active:
            seconds+=max(0,(stamp-active).total_seconds());active=None;observed=True;ended=stamp
            activity='interrupted' if p['type']=='turn_aborted' else 'completed'
    last=totals[-1] if totals else None
    return {'sessionId':session,'source':'codex-native-trace','models':sorted(models),'reasoningLevels':sorted(efforts),
            'inputTokens':last['input_tokens'] if last else None,'outputTokens':last['output_tokens'] if last else None,
            'cacheReadTokens':last['cached_input_tokens'] if last else None,
            'cacheWriteTokens':last.get('cache_write_input_tokens') if last else None,
            'reasoningTokens':last.get('reasoning_output_tokens') if last else None,
            'totalTokens':last['input_tokens']+last['output_tokens'] if last else None,
            'cacheHitRate':round(last['cached_input_tokens']/last['input_tokens']*100,2) if last and last['input_tokens'] else None,
            'activeSeconds':round(seconds,3) if observed and not active else None,'cost':None,'errors':errors,
            'activity':activity,'startedAt':started.isoformat() if started else None,'lastStartedAt':last_started.isoformat() if last_started else None,
            'endedAt':ended.isoformat() if ended and not active else None,
            'note':'读取同一原生会话最终累计值，不累加重复累计事件；缓存包含在输入中。原生声明不等于独立证明规则已完全遵循。'}


def discover_trace(home, workspace, previous_session=None):
    """Query only this workspace's index entries; never walk unrelated rollouts."""
    home=Path(home).resolve()
    indexes=sorted(home.glob('state_*.sqlite'),key=lambda p:p.stat().st_mtime,reverse=True)
    if not indexes:return None,'本机会话索引尚不可用，可手动导入日志。'
    target=str(Path(workspace).resolve()).removeprefix('\\\\?\\')
    with closing(sqlite3.connect(indexes[0].as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
        rows=db.execute('SELECT id,rollout_path FROM threads WHERE cwd COLLATE NOCASE IN (?,?,?)',
                        (target,'\\\\?\\'+target,target.replace('\\','/'))).fetchall()
    if previous_session:rows=[r for r in rows if r[0]==previous_session]
    if not rows:return None,'等待此工作区的 Codex 会话。'
    if len(rows)!=1:return None,'此目录有多个会话，请导入目标会话日志后继续自动同步。'
    session,path=rows[0];file=Path(path)
    resolved=Path(str(file.resolve()).removeprefix('\\\\?\\'))
    allowed=[home/'sessions',home/'archived_sessions']
    if not any(resolved.is_relative_to(root) for root in allowed) or file.is_symlink():
        raise ValueError('会话日志不在 Codex 日志目录中。')
    if file.stat().st_size>15_000_000:raise ValueError('本题日志超过 15 MB，自动同步暂不支持。')
    raw=file.read_text(encoding='utf-8')
    # The last line may still be in flight; never accept malformed earlier lines.
    if raw and not raw.endswith('\n'):
        try:json.loads(raw.rsplit('\n',1)[-1])
        except ValueError:raw=raw.rpartition('\n')[0]
    usage=read_trace(raw,workspace,previous_session)
    if usage['sessionId']!=session:raise ValueError('会话索引和日志身份不一致。')
    return usage,'已自动同步本题会话。'
