"""Evidence-backed machine scores and append-only, per-dimension human corrections."""
from .contracts import string
from .files import fingerprint
from .scoring import number, acceptance


def dimensions(policy, task):
    return {k:w for k,w in policy['dimensions'].items() if w>0 and (k!='ux' or task.get('hasFrontendUI'))}


def evidence_key(capture):
    return fingerprint({'id':capture['id'],'manifest':capture['manifest'],'checks':capture['checks']})


def validate_machine(value, packet, commands):
    """Validate provenance, not the truth of a model's interpretation."""
    rows=value.get('ratings')
    expected=dimensions(packet['policy'],packet['task'])
    if not isinstance(rows,dict) or set(rows)!=set(expected):raise ValueError('机器评分必须逐项覆盖冻结的评分维度。')
    def evidence(items):
        if not isinstance(items,list) or len(items)>20:raise ValueError('评分引用格式无效。')
        verified=[]
        for item in items:
            if not isinstance(item,dict):raise ValueError('评分引用格式无效。')
            quote=item.get('quote')
            if not isinstance(quote,str) or not quote.strip() or len(quote)>3000:raise ValueError('评分引用缺少原文。')
            if 'path' in item:
                if not isinstance(item['path'],str):raise ValueError('文件引用路径无效。')
                lines=packet['files'].get(item['path'],'').splitlines();line=item.get('line')
                if type(line) is not int or not 1<=line<=len(lines) or quote not in lines[line-1]:raise ValueError('机器评分引用的文件行不存在。')
                verified.append({'path':item['path'],'line':line,'quote':quote})
            elif 'command' in item:
                command=item['command']
                if not isinstance(command,str) or not command.strip():raise ValueError('命令引用无效。')
                match=next((c for c in commands if command in c['command'] and quote in c['output']),None)
                if match is None:raise ValueError('机器评分引用的执行记录不存在。')
                verified.append({'commandId':match['id'],'command':match['command'],'exitCode':match['exitCode'],'quote':quote})
            elif 'checkId' in item:
                match=next((c for c in packet['checks'] if c['id']==item['checkId'] and quote in c.get('output','')),None)
                if match is None:raise ValueError('机器评分引用的检查记录不存在。')
                verified.append({'checkId':match['id'],'status':match['status'],'quote':quote})
            else:raise ValueError('评分必须引用文件、执行记录或检查。')
        return verified
    ratings={}
    for key,row in rows.items():
        if not isinstance(row,dict):raise ValueError('机器评分项格式无效。')
        if 'score' not in row:raise ValueError('评分项须明确返回分数或 null。')
        score=None if row['score'] is None else number(row['score'])
        reason=string(row.get('reason'),'评分理由',5000,True)
        refs=evidence(row.get('evidence',[]))
        method=row.get('method')
        if method not in {'static','runtime','unverified'}:raise ValueError('评分取证方式无效。')
        if score is not None and (not refs or method=='unverified'):raise ValueError('没有证据的维度不能生成分数。')
        if method=='runtime' and not any('commandId' in r or 'checkId' in r for r in refs):raise ValueError('运行结论必须引用实际执行记录。')
        if key in {'ux','performance'} and score is not None and method!='runtime':raise ValueError('交互或性能评分需要实际运行证据。')
        ratings[key]={'score':score,'reason':reason,'method':method,'evidence':refs}
    criteria=value.get('criteria',{})
    if not isinstance(criteria,dict) or set(criteria)!={c['id'] for c in packet['task'].get('criteria',[])}:raise ValueError('机器验收必须覆盖冻结的需求条目。')
    verified={}
    for key,row in criteria.items():
        if not isinstance(row,dict) or row.get('status') not in {'met','partial','unmet','unverified'}:raise ValueError('机器验收状态无效。')
        refs=evidence(row.get('evidence',[]))
        if row['status']!='unverified' and not refs:raise ValueError('需求验收缺少证据。')
        verified[key]={'status':row['status'],'notes':string(row.get('notes'),'需求验收理由',5000,True),'evidence':refs}
    return {'ratings':ratings,'criteria':verified,'scores':{k:r['score'] for k,r in ratings.items() if r['score'] is not None},
            'scoreSchema':'arena-machine-v1','evidenceKey':packet['evidenceKey'],
            'commands':commands,'scoresAreAdvisory':False,
            'note':'AI 判断计入机器分；引用校验只证明材料存在，不保证结论正确。运行证据与静态判断分别标注。'}


def calculate_machine(run,trial):
    captures=trial.get('captures',[]);latest=captures[-1] if captures else None
    task=next(t for t in run['tasks'] if t['id']==trial['taskId']);weights=dimensions(run['policy'],task)
    key=evidence_key(latest) if latest else None
    reviews=[r for r in trial.get('reviews',[]) if latest and r['captureId']==latest['id'] and r.get('scoreSchema')=='arena-machine-v1' and r.get('evidenceKey')==key]
    report=reviews[-1] if reviews else None
    rows=(report or {}).get('ratings',{})
    raw={k:rows.get(k,{}).get('score') for k in weights}
    corrections=[r for r in trial.get('machineCorrections',[]) if report and r['reviewId']==report['id'] and r['evidenceKey']==key]
    overrides={}
    for correction in corrections:
        for dim,row in correction['changes'].items():
            if row['score'] is None:overrides.pop(dim,None)
            else:overrides[dim]=row
    effective={k:overrides[k]['score'] if k in overrides else raw[k] for k in weights}
    def average(scores):
        known={k:v for k,v in scores.items() if v is not None};total=sum(weights[k] for k in known)
        return round(sum(weights[k]*v for k,v in known.items())/total,2) if total else None
    coverage=round(sum(weights[k] for k in raw if raw[k] is not None)/sum(weights.values())*100,2)
    complete=all(v is not None for v in effective.values())
    original=average(raw);adjusted=average(effective)
    checks=latest['checks'] if latest else []
    objective=None
    if task['checks'] and latest:
        from .scoring import calculate
        # Keep existing multi-stage deterministic score semantics, without changing the run.
        objective=calculate({**run,'policy':{**run['policy'],'version':'arena-review-v2'}},trial)['objective']
    return {'machine':original,'machineReviewId':report['id'] if report else None,'machineEvidenceKey':key,
            'machineCoverage':coverage,'machineRatings':rows,'machineOverrides':overrides,'effectiveScores':effective,
            'objective':objective,'human':None,'overall':adjusted if complete and trial['state']=='completed' else None,
            'provisional':not complete or trial['state']!='completed','partialScore':adjusted,
            'adjudicatedOverall':adjusted if overrides and complete and trial['state']=='completed' else None,
            'adjudicatedObjective':None,'objectiveReviewId':None,'objectiveEvidenceKey':key,'humanReviewId':None,'varianceMargin':None,
            'acceptance':acceptance(task,trial,report,{c['stageIndex']:c for c in captures}),
            'coverage':{'configuredChecks':len(task['checks']),'executedChecks':len(checks)}}


def validate_correction(data,score):
    if not score['machineReviewId'] or data.get('reviewId')!=score['machineReviewId'] or data.get('evidenceKey')!=score['machineEvidenceKey']:
        raise ValueError('机器评分或证据已变化，请刷新后重新调整。')
    changes=data.get('changes')
    if not isinstance(changes,dict) or not changes or not set(changes)<=set(score['effectiveScores']):raise ValueError('请选择需要修正的评分项。')
    result={}
    for key,row in changes.items():
        if not isinstance(row,dict):raise ValueError('修正格式无效。')
        result[key]={'score':None if row.get('score') is None else number(row['score']),
                     'reason':string(row.get('reason'),'修正理由与证据',5000,True)}
    return result
