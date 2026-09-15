"""Transparent score policy. Absent evidence is null, never an invented score."""
import math

DIMENSIONS = {'intent': '需求完成与切中度', 'maintainability': '可维护性', 'robustness': '边界与健壮性', 'ux': '交互与视觉'}
DEFAULT_POLICY = {'version': 'arena-review-v1', 'objectiveWeight': 50, 'humanWeight': 50,
                  'dimensions': {'intent': 30, 'maintainability': 25, 'robustness': 25, 'ux': 20}}


def number(value, minimum=0, maximum=100):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f'分值必须是 {minimum}–{maximum} 的有限数值。')
    return value


def policy(value):
    value = value or DEFAULT_POLICY
    a, b = number(value.get('objectiveWeight')), number(value.get('humanWeight'))
    dims = value.get('dimensions', {})
    if set(dims) != set(DIMENSIONS) or any(number(v) < 0 for v in dims.values()) or sum(dims.values()) <= 0 or a+b != 100:
        raise ValueError('主权重之和须为 100；人工维度须完整且至少一项权重大于零。')
    return {'version': 'arena-review-v1', 'objectiveWeight': a, 'humanWeight': b, 'dimensions': dims}


def validate_review(value, task, constraints):
    scores = value.get('scores', {})
    applicable = set(DIMENSIONS) if task.get('hasFrontendUI') else set(DIMENSIONS)-{'ux'}
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
    return {'scores': {k: number(v) for k,v in scores.items()}, 'notes': notes.strip(), 'readiness': readiness, 'constraints': checks}


def calculate(run, trial):
    stages = trial.get('captures', [])
    latest = stages[-1] if stages else None
    task=next(t for t in run['tasks'] if t['id']==trial['taskId'])
    by_stage={c['stageIndex']:c for c in stages}
    checks=[check for c in by_stage.values() for check in c.get('checks',[])]
    configured=len(task['checks'])
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
    return {'objective':objective,'human':human,'overall':overall,'provisional':overall is None,
            'coverage':{'configuredChecks':configured,'executedChecks':len(checks)},
            'humanReviewId':review['id'] if review else None,'varianceMargin':None}
