"""Supplemental frontend acceptance. Never rewrites a frozen scoring contract."""
import json
from .files import fingerprint

VERSION = 'creative-behavior-v3'
IMAGE = 'chb-verifier:' + VERSION
PROBES = {
    'golden-gate-fog-v1': {'scene-switch': '切换改变场景', 'scene-return': '切回恢复场景', 'scene-keyboard': '键盘切换场景'},
    'mini-exhibit-3d-v1': {'rotate-left': '左转改变展品画面', 'rotate-right': '右转改变展品画面', 'rotate-keyboard': '键盘旋转'},
    'energy-dashboard-v1': {'weekly-total': '本周总量 63 kWh', 'weekly-comparison': '比上周下降 10%', 'daily-values': '七天数据对照'},
    'pixel-postcard-v1': {'draw': '绘制改变画布', 'undo': '撤销恢复绘制前状态', 'clear': '清空两次不同绘制', 'export': '下载内容与画布一致'},
    'meteor-rescue-v1': {'start': '开始进入游戏', 'pause': '暂停画布停止变化', 'resume': '继续后恢复变化', 'restart': '重开计分归零'},
}
COMMON = {'mobile-layout': '390 / 768 / 1280px 布局', 'runtime-errors': '操作路径无脚本异常', 'offline': '离线运行'}
UNCOVERED = {
    'golden-gate-fog-v1': '桥塔、悬索和空间关系是否正确，地标辨识、文字对比与审美。',
    'mini-exhibit-3d-v1': '三个立体部分、真实几何与遮挡、连续旋转精度和审美。',
    'energy-dashboard-v1': '图表几何比例、误导性文案、信息层次和审美。',
    'pixel-postcard-v1': '12×12 逻辑网格、四色、橡皮擦、触控、刷新说明和审美。',
    'meteor-rescue-v1': '移动、碰撞、真实得分与失败条件、触控、减少动态效果和审美。',
}


def task_key(task, root):
    from .builtin_tasks import creative_web_catalog, creative_prompt
    key = task.get('id', '').removeprefix('original-creative-')
    if (key not in PROBES or task.get('sourceKind') != 'repository-original'
            or task.get('revision') != 1 or len(task.get('stages', [])) != 1):
        return None
    entry = next((e for e in creative_web_catalog(root) if e['id'] == key), None)
    # An edited/custom requirement needs its own adapter. IDs alone are unsafe.
    if not entry or task.get('inputPrompt') != creative_prompt(entry):
        return None
    if task['stages'][0].get('prompt') != creative_prompt(entry):
        return None
    return key


def check_definition(task, root):
    key = task_key(task, root)
    if key is None:
        return None
    return {'id': VERSION, 'label': '逐题功能补充验收（独立于原评分）', 'weight': 1,
            'image': IMAGE, 'argv': ['node', '/tests/behavior.cjs', '/app', key, '/tmp/chb-behavior'], 'timeout': 100,
            'stageIndex': 0, 'kind': 'functional'}


def summarize(task, capture, root):
    key = task_key(task, root)
    if key is None or not capture:
        return None
    labels = {**PROBES[key], **COMMON}
    records = capture.get('behaviorChecks', [])
    record = records[-1] if records else None
    valid = False
    payload = {}
    if record and record.get('captureHash') == capture['manifest']['sha256'] and record.get('taskHash') == fingerprint(task):
        try:
            payload = json.loads(record.get('output', ''))
            rows = payload['rows']
            valid = (record.get('status') == 'passed' and not record.get('outputTruncated')
                     and payload.get('version') == VERSION and payload.get('task') == key
                     and isinstance(rows, list) and len(rows) == len(labels)
                     and {r['id'] for r in rows} == set(labels)
                     and all(r['status'] in {'passed', 'failed', 'unverified'} and isinstance(r.get('detail'), str)
                             and isinstance(r.get('evidence'), dict) for r in rows))
        except (ValueError, KeyError, TypeError):
            valid = False
    rows = [{**row, 'label': labels[row['id']]} for row in payload['rows']] if valid else [
        {'id': id_, 'label': label, 'status': 'unverified', 'detail': '尚未取得此快照的有效专项结果。', 'evidence': {}}
        for id_, label in labels.items()]
    counts = {state: sum(r['status'] == state for r in rows) for state in ('passed', 'failed', 'unverified')}
    return {'version': VERSION, 'status': 'failed' if counts['failed'] else 'incomplete' if counts['unverified'] else 'passed',
            'rows': rows, **counts, 'total': len(rows),
            # Coverage is about this enumerated probe suite, never all requirements.
            'coverage': round((counts['passed'] + counts['failed']) / len(rows) * 100, 1),
            'uncovered': UNCOVERED[key], 'imageId': record.get('imageId') if record else None,
            'at': record.get('at') if record else None, 'captureHash': capture['manifest']['sha256'],
            'rawStatus': record.get('status') if record else 'not-run',
            'attemptId': record.get('attemptId') if record else None,
            'images': record.get('images', []) if record else []}


def screenshot(app, rid, tid, data):
    """Serve only content-addressed PNGs declared by this owned attempt."""
    import base64
    from .files import safe_path, hash_bytes
    from .service import identifier
    _, trial = app.trial(rid, tid)
    record = next((r for c in trial['captures'] for r in c.get('behaviorChecks', []) + c.get('behaviorAttempts', [])
                   if r.get('attemptId') == data.get('attemptId')), None)
    name = data.get('path')
    if not record or not isinstance(name, str) or name not in record.get('images', []):
        raise ValueError('截图不属于这份专项验收。')
    folder = f'runs/{rid}/{tid}/behavior-checks/{identifier(record["attemptId"])}/artifacts'
    path = safe_path(app.local, folder + '/' + name)
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError('截图不存在或超过预览上限。')
    raw = path.read_bytes()
    if not raw.startswith(b'\x89PNG\r\n\x1a\n') or hash_bytes(raw) + '.png' != name:
        raise ValueError('截图内容与验收哈希不一致。')
    return {'image': 'data:image/png;base64,' + base64.b64encode(raw).decode()}
