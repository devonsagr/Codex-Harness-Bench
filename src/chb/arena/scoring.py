"""Transparent score policy. Absent evidence is null, never an invented score."""
import math
import hashlib
import re
from .contracts import expected_checks, string
from .files import fingerprint

DIMENSIONS = {'intent': '需求完成与切中度', 'maintainability': '可维护性', 'robustness': '边界与健壮性', 'ux': '交互与视觉'}
DEFAULT_POLICY = {'version': 'arena-review-v1', 'objectiveWeight': 50, 'humanWeight': 50,
                  'dimensions': {'intent': 30, 'maintainability': 25, 'robustness': 25, 'ux': 20}}
RUBRICS = {
    'intent': ('需求完成与切中度','对照本题需求与实际交付；不能用完成声明替代证据。'),
    'maintainability': ('可维护性','结构、可读性、已有约定与后续修改成本。'),
    'robustness': ('边界与健壮性','异常输入、失败恢复、状态一致性与边界行为。'),
    'ux': ('交互与可访问性','实际使用页面，检查交互反馈、布局、键盘与可访问性。'),
    'verification': ('验证与回归','测试是否覆盖要求，是否实际执行，是否遗漏回归。'),
    'instruction': ('规则与范围遵守','按本次规则、授权范围和确认约定检查执行记录。'),
    'handoff': ('交付与可复现性','启动、依赖、使用说明及接手者能否复现结果。'),
    'security': ('安全与隐私','按本题约束检查凭据、权限、输入处理和数据暴露。'),
    'performance': ('性能与资源行为','基于实测响应、吞吐或资源记录，不能凭代码猜分。')}
DESKTOP_POLICY = {'version':'arena-review-v2','objectiveWeight':50,'humanWeight':50,
                  'dimensions':{k:1 for k in list(RUBRICS)[:7]},
                  'rubrics':{k:{'label':v[0],'description':v[1]} for k,v in list(RUBRICS.items())[:7]}}


def number(value, minimum=0, maximum=100):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f'分值必须是 {minimum}–{maximum} 的有限数值。')
    return value


def policy(value):
    value = value or DEFAULT_POLICY
    a, b = number(value.get('objectiveWeight')), number(value.get('humanWeight'))
    dims = value.get('dimensions', {})
    if value.get('version')=='arena-review-v2':
        rubrics=value.get('rubrics',{})
        if not isinstance(dims,dict) or not isinstance(rubrics,dict) or not 1<=len(dims)<=16 or set(dims)!=set(rubrics):raise ValueError('评分项与权重需对应，最多16项。')
        for k,v in rubrics.items():
            if not re.fullmatch('[a-z][a-z0-9_-]{0,49}',k) or not isinstance(v,dict):raise ValueError('评分项编号无效。')
            string(v.get('label'),'评分项名称',80,True);string(v.get('description'),'评分依据',1000,True)
        if any(number(v)<0 for v in dims.values()) or sum(dims.values())<=0 or a+b!=100:raise ValueError('主权重须合计100，至少启用一个评分项。')
        extra={}
        if value.get('dimensionUnit') is not None:
            if value['dimensionUnit']!='percent' or abs(sum(dims.values())-100)>=.005:raise ValueError('人工内部占比须合计100%。')
            extra['dimensionUnit']='percent'
        if 'requireDimensionEvidence' in value:
            if type(value['requireDimensionEvidence'])!=bool:raise ValueError('评分证据设置无效。')
            extra['requireDimensionEvidence']=value['requireDimensionEvidence']
        return {'version':'arena-review-v2','objectiveWeight':a,'humanWeight':b,'dimensions':dims,'rubrics':rubrics,**extra}
    if set(dims) != set(DIMENSIONS) or any(number(v) < 0 for v in dims.values()) or sum(dims.values()) <= 0 or a+b != 100:
        raise ValueError('主权重之和须为 100；人工维度须完整且至少一项权重大于零。')
    return {'version': 'arena-review-v1', 'objectiveWeight': a, 'humanWeight': b, 'dimensions': dims}


def validate_review(value, task, constraints, capture=None, scoring_policy=None):
    scores = value.get('scores', {})
    applicable = set(DIMENSIONS) if task.get('hasFrontendUI') else set(DIMENSIONS)-{'ux'}
    if scoring_policy and scoring_policy.get('version')=='arena-review-v2':
        applicable={k for k,w in scoring_policy['dimensions'].items() if w>0 and (k!='ux' or task.get('hasFrontendUI'))}
    if set(scores) != applicable:
        raise ValueError('请为所有适用维度填写评分；非界面题不填写 UX 分数。')
    notes = value.get('notes', '')
    if not isinstance(notes, str) or not notes.strip() or len(notes) > 10000:
        raise ValueError('请填写评分依据（1–10000 字符）。')
    readiness = value.get('readiness')
    if readiness not in {'ready_to_merge', 'minor_polish', 'major_rework', 'rejected'}:
        raise ValueError('请选择交付可用程度。')
    checks = value.get('constraints', {})
    ids = {c['id'] for c in constraints if c.get('isActive')}
    if set(checks) != ids or any(x not in {'met', 'unmet', 'unverified', 'not_applicable'} for x in checks.values()):
        raise ValueError('请逐项记录个人约束的满足情况；没有证据可以选未核实。')
    result={'scores': {k: number(v) for k,v in scores.items()}, 'notes': notes.strip(), 'readiness': readiness, 'constraints': checks}
    if scoring_policy and scoring_policy.get('requireDimensionEvidence'):
        evidence=value.get('dimensionEvidence',{})
        if not isinstance(evidence,dict) or set(evidence)!=applicable:raise ValueError('请为每个计分维度填写实际证据。')
        result['dimensionEvidence']={k:string(v,'维度评分依据',3000,True) for k,v in evidence.items()}
    if task.get('schemaVersion')==2:
        items=value.get('criteria',{})
        if not isinstance(items,dict) or set(items)!={c['id'] for c in task.get('criteria',[])}:
            raise ValueError('请逐项记录本题验收条目，未操作的项目保持未核实。')
        verified={}
        capture=capture or {'manifest':{'files':{}},'checks':[]}
        for cid,row in items.items():
            if not isinstance(row,dict) or row.get('status') not in {'met','partial','unmet','unverified','not_applicable'}:
                raise ValueError('验收状态无效。')
            note=string(row.get('notes',''),'逐项验收依据',5000,row['status']!='unverified')
            entry={'status':row['status'],'notes':note}
            if row.get('filePath'):
                path=string(row['filePath'],'证据文件路径',1000)
                if path not in capture['manifest']['files']:raise ValueError('验收引用的文件不在此快照中。')
                entry.update(filePath=path,fileSha256=capture['manifest']['files'][path])
            if row.get('checkId'):
                check=next((c for c in capture['checks'] if c['id']==row['checkId']),None)
                if check is None:raise ValueError('验收引用的检查不在此快照的执行记录中。')
                evidence={key:check.get(key) for key in ['id','label','status','exitCode','imageId','seconds']}
                evidence['outputSha256']=hashlib.sha256(check.get('output','').encode('utf-8')).hexdigest()
                entry.update(checkId=check['id'],checkEvidence=evidence)
            verified[cid]=entry
        constraint_notes=value.get('constraintNotes',{})
        if not isinstance(constraint_notes,dict) or not set(constraint_notes)<=ids:
            raise ValueError('个人约束依据包含未知条目。')
        result.update(contractVersion=2,criteria=verified,constraintNotes={cid:string(constraint_notes.get(cid,''),'个人约束依据',5000,status!='unverified') for cid,status in checks.items()},
                      revisionReason=string(value.get('revisionReason',''),'复审修订原因',3000))
    return result


def acceptance(task, trial, review, by_stage):
    if task.get('schemaVersion')!=2:return {'status':'legacy_unavailable','required':0,'met':0,'items':[]}
    required=[c for c in task.get('criteria',[]) if c['required']]
    items=[]
    for criterion in required:
        status=(review or {}).get('criteria',{}).get(criterion['id'],{}).get('status','unverified')
        linked=[]
        for stage,check in expected_checks(task):
            if criterion['id'] in check.get('criterionIds',[]):
                actual=next((c for c in by_stage.get(stage,{}).get('checks',[]) if c['id']==check['id']),None)
                linked.append(actual['status'] if actual else 'unverified')
        if 'failed' in linked or status in {'partial','unmet'}:verdict='not_met'
        elif status=='not_applicable':verdict='needs_review'
        elif status!='met' or any(s!='passed' for s in linked):verdict='unverified'
        else:verdict='met'
        items.append({'id':criterion['id'],'status':verdict})
    statuses={c['status'] for c in items}
    status=next((s for s in ['not_met','needs_review','unverified'] if s in statuses),'met') if required else 'not_configured'
    if required and status=='met' and trial['state']!='completed':status='in_progress'
    return {'status':status,'required':len(required),'met':sum(c['status']=='met' for c in items),'items':items}


def calculate(run, trial):
    stages = trial.get('captures', [])
    latest = stages[-1] if stages else None
    task=next(t for t in run['tasks'] if t['id']==trial['taskId'])
    by_stage={c['stageIndex']:c for c in stages}
    checks=[check for c in by_stage.values() for check in c.get('checks',[])]
    configured=len(task['checks'])
    if task.get('schemaVersion')==2:
        slots=expected_checks(task)
        configured=len(slots)
        checks=[]
        for stage,definition in slots:
            matches=[c for c in by_stage.get(stage,{}).get('checks',[]) if c['id']==definition['id']]
            if len(matches)==1:checks.append({**matches[0],'weight':definition['weight']})
    objective = None
    if configured and len(checks) == configured and all(c['status'] in {'passed','failed'} for c in checks):
        objective = round(sum(c['weight'] for c in checks if c['status']=='passed') / sum(c['weight'] for c in checks)*100,2)
    reviews = [r for r in trial.get('reviews',[]) if latest and r['captureId']==latest['id'] and r['kind']=='human']
    human, review = None, reviews[-1] if reviews else None
    weights = run['policy']['dimensions']
    if review:
        applicable = review['scores']
        total = sum(weights[k] for k in applicable)
        human = round(sum(weights[k]*v for k,v in applicable.items())/total,2) if total else None
    a,b = run['policy']['objectiveWeight'],run['policy']['humanWeight']
    overall = round(((objective or 0)*a+(human or 0)*b)/100,2) if (not a or objective is not None) and (not b or human is not None) else None
    if trial['state'] != 'completed':
        overall = None
    evidence_key=fingerprint({'captures':[{k:c.get(k) for k in ['id','stageIndex','manifest','checks']} for c in by_stage.values()],
                              'checks':task['checks']})
    decisions=[r for r in trial.get('objectiveReviews',[]) if latest and r['captureId']==latest['id'] and r['evidenceKey']==evidence_key]
    decision=decisions[-1] if decisions else None
    adjusted=decision['score'] if objective is not None and decision else None
    adjusted_overall=round(((adjusted or 0)*a+(human or 0)*b)/100,2) if adjusted is not None and (not b or human is not None) and trial['state']=='completed' else None
    return {'objective':objective,'human':human,'overall':overall,'provisional':overall is None,
            'objectiveEvidenceKey':evidence_key,'adjudicatedObjective':adjusted,'adjudicatedOverall':adjusted_overall,
            'objectiveReviewId':decision['id'] if decision and adjusted is not None else None,
            'acceptance':acceptance(task,trial,review,by_stage),
            'coverage':{'configuredChecks':configured,'executedChecks':len(checks)},
            'humanReviewId':review['id'] if review else None,'varianceMargin':None}
