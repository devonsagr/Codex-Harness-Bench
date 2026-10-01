"""Report program facts independently of AI opinions and delivery state."""
import json
from .files import fingerprint


def summary(task, trial):
    contract = task.get('fixedSuite') or {}
    if not isinstance(contract, dict):return None
    if task.get('revision') != 1 or len(task.get('stages', [])) != 1:
        return None
    if contract.get('version') == 'evalplus-originfmt-v1' and task.get('sourceKind') == 'evalplus-local':
        scope, expected = '原始扩展函数测试', ['suite']
    elif contract.get('version') == 'community-engine-v1' and task.get('sourceKind') == 'community-adapted':
        scope, expected = '功能核心测试（不含视觉与完整界面）', contract.get('caseIds', [])
        if not isinstance(expected,list) or not expected or len(expected)>100 or any(not isinstance(x,str) for x in expected) or len(set(expected))!=len(expected):return None
    else:return None
    capture = (trial.get('captures') or [{}])[-1]
    configured = task.get('checks') or []
    check = next((c for c in capture.get('checks', []) if c.get('id') == 'suite'), None)
    valid, rows = False, []
    if (check and configured and configured[0].get('id') == 'suite'
            and check.get('imageId', '').startswith('sha256:') and not check.get('outputTruncated')
            and check.get('argv') == configured[0].get('argv') and check.get('status') in {'passed', 'failed'}):
        try:
            payload = json.loads(check.get('output', ''))
            rows = payload['rows']
            valid = (payload.get('version') == contract['version'] and payload.get('task') == contract['task']
                     and payload.get('testSha256') == contract.get('testSha256')
                     and isinstance(rows, list) and len(rows) == len(expected)
                     and {r['id'] for r in rows} == set(expected)
                     and all(r.get('status') in {'passed', 'failed', 'unverified'} and isinstance(r.get('detail'), str) for r in rows)
                     and (check['status']=='passed')==all(r['status']=='passed' for r in rows))
        except (KeyError, ValueError, TypeError):pass
    if not valid:
        rows = [{'id': key, 'status': 'unverified', 'detail': '未取得当前快照完整有效的程序报告。'} for key in expected]
    counts = {key: sum(r['status'] == key for r in rows) for key in ('passed', 'failed', 'unverified')}
    return {'version': contract['version'], 'scope': scope, 'rows': rows, **counts, 'total': len(expected), 'inputCount': contract.get('inputCount'),
            'status': 'failed' if counts['failed'] else 'unverified' if counts['unverified'] else 'passed',
            'score': round(100 * counts['passed'] / len(expected), 1) if not counts['unverified'] else None,
            'captureHash': capture.get('manifest', {}).get('sha256'),
            'protocol': fingerprint({'contract': contract, 'image': (check or {}).get('imageId')}),
            'qualityCertified': False}
