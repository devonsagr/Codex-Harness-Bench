"""Describe observed repeatability, without inventing confidence or correctness."""
from math import isfinite

PROTOCOL_FIELDS = ('model', 'reasoningEffort', 'judgePromptSha256',
                   'reviewEnvironment', 'imageId', 'codexVersion', 'serviceTier')


def comparison_key(packet):
    """Freeze input conditions; check timestamps/durations are observations."""
    from .files import fingerprint
    return fingerprint({'task':packet['task'], 'policy':packet['policy'],
                        'scoringContract':packet.get('scoringContract'),
                        'manifestHash':packet['manifestHash'], 'evaluationScope':packet['evaluationScope'],
                        'checks':[{k:c.get(k) for k in ('id','imageId','argv')} for c in packet.get('checks',[])],
                        'behaviorProtocol':{k:(packet.get('behaviorAcceptance') or {}).get(k) for k in ('version','imageId')}})


def summarize(trial, score):
    current = next((r for r in trial.get('reviews', []) if r.get('id') == score.get('machineReviewId')), None)
    result = {'status': 'unmeasured', 'independentRuns': 0, 'sameProtocolRuns': 0,
              'ranges': [], 'missingProtocol': [], 'calibrated': False}
    if not current:
        return result
    # Local reviews have no container ID. All other protocol fields must be
    # present; matching missing values is not evidence of equal conditions.
    required = [k for k in PROTOCOL_FIELDS if k != 'imageId' or current.get('reviewEnvironment') == 'docker']
    condition_fields = ('judgeComparisonKey',) if current.get('judgeComparisonKey') else ('judgePacketSha256','evidenceKey')
    required.extend(condition_fields)
    missing = [k for k in required if not current.get(k)]
    if missing:
        result['missingProtocol'] = missing
        return result
    seen = set()
    runs = []
    for report in trial.get('reviews', []):
        if report.get('captureId') != current.get('captureId'):
            continue
        # A reparse of one CLI job is still one observation, never a repeat.
        job = report.get('jobPath')
        if not job or report.get('revalidatedFrom') or job in seen:
            continue
        seen.add(job)
        if report.get('scoreSchema') != 'arena-machine-v1':
            continue
        result['independentRuns'] += 1
        if all(report.get(k) == current.get(k) for k in (*PROTOCOL_FIELDS,*condition_fields)):
            runs.append(report)
    result['sameProtocolRuns'] = len(runs)
    result['status'] = 'observed' if len(runs) >= 2 else 'single-run' if runs else 'unmeasured'
    for key in current.get('ratings', {}):
        values = [r.get('ratings', {}).get(key, {}).get('score') for r in runs]
        values = [v for v in values if type(v) in (int, float) and isfinite(v) and 0 <= v <= 100]
        if len(values) >= 2:
            result['ranges'].append({'dimension': key, 'samples': len(values), 'min': min(values),
                                     'max': max(values), 'spread': round(max(values)-min(values), 2)})
    return result
