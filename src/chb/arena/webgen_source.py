"""Pinned upstream briefs and UI criteria, locally adapted to desktop delivery.

Never redistribute the dataset here: upstream has no repository license file.
This does not install WebVoyager or claim parity with its official scores.
"""
import hashlib
import json
import re
import urllib.request

COMMIT = 'c89e0743438e458d617cebaf7a682e0e66e41049'
SHA256 = 'e6451c1c5aed85ab01a15ab7c6be2bc737d4df28ca8b9ae15805a237878dee29'
SMALL_TYPES = {'Personal Portfolio Sites', 'Company Brochure Sites', 'Productivity Applications', 'Browser-Based Games'}
URL = f'https://raw.githubusercontent.com/mnluzimu/WebGen-Bench/{COMMIT}/data/test.jsonl'


def definitions(raw):
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('WebGen-Bench固定数据校验失败。')
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) != 101 or len({r['id'] for r in rows}) != 101:
        raise ValueError('WebGen-Bench题目数量或编号无效。')
    return rows


def short_candidate(row):
    # Scope filter only, not a promised execution time or evaluation result.
    prompt = row['instruction']
    return (row['application_type'] in SMALL_TYPES and len(prompt) < 850 and len(row['ui_instruct']) <= 7 and not re.search(
        r'\b(api|database|payment|authentication|login|log in|stock|real.time|social network|e.commerce|multi.user|account|simulation|multiplayer|booking|reservation)\b',
        prompt, re.I))


def task_definition(row, baseline_id):
    title = re.sub(r'^(Please |please )?(implement|create|build|develop)\s+(?:(an|a|the)\s+)?', '', row['instruction']).split('.')[0]
    criteria = [{'id': f'ui-{index+1}', 'label': item['task'][:800],
                 'description': item['expected_result'], 'required': True, 'dimension': 'intent'}
                for index, item in enumerate(row['ui_instruct'])]
    return {'id': 'webgen-' + row['id'], 'title': 'WebGen · ' + title[:100],
        'schemaVersion': 2, 'inputPrompt': row['instruction'],
        'stages': [{'title': '实现并验证网页', 'prompt': row['instruction']}], 'criteria': criteria,
        'evaluationRubric': ['原题UI操作及预期结果逐项核对；met / partial / unmet / unverified。',
            '本地采用统一等级裁判，不是原版WebVoyager，不发布官方reward。'],
        'checks': [], 'baselineId': baseline_id, 'requiresBaseline': True,
        'hasFrontendUI': True, 'taskFamily': 'web-interface', 'capabilityTags': ['frontend','browser','reasoning'],
        'language': 'Web', 'taskParadigm': 'open-ended-project', 'channel': 'frontend-ui',
        'difficulty': 'Medium' if short_candidate(row) else 'Long',
        'description': row['application_type'], 'sourceKind': 'webgen-bench-local',
        'referenceUrl': f'https://github.com/mnluzimu/WebGen-Bench/blob/{COMMIT}/data/test.jsonl',
        'license': '上游仓库未声明许可；数据仅下载到本机，不随本项目分发',
        'environmentNote': '空白网页起点；原题可能需要服务或数据，按题面实现并写明启动方式。默认随机选题只纳入规模过滤通过的题。',
        'sourceNote': f'WebGen-Bench test/{row["id"]}；固定提交{COMMIT}。保留原题与UI检查条件；本地桌面适配，裁判与执行协议不同，不冒称官方成绩。'}


def install(app):
    cache = app.local / 'public-sources' / 'webgen-bench' / COMMIT
    cache.mkdir(parents=True, exist_ok=True)
    file = cache / 'test.jsonl'
    if file.is_file():
        raw = file.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=45) as response:
            raw = response.read(1_000_001)
        definitions(raw)  # verify before caching or saving any task
        file.write_bytes(raw)
    rows = definitions(raw)
    existing = {t['id'] for t in app.db.list('task') + app.db.list('task', True)}
    missing = [r for r in rows if 'webgen-' + r['id'] not in existing]
    if not missing:
        return {'added': 0, 'total': len(rows), 'shortCandidates': sum(map(short_candidate, rows))}
    baseline = app.import_files('baseline', {'path': str(app.root / 'tasks/creative-web-v1/environment/fixture'),
                                           'name': '公开网页任务 · 空白起点'})
    for row in missing:
        app.save_task(task_definition(row, baseline['id']))
    return {'added': len(missing), 'total': len(rows), 'shortCandidates': sum(map(short_candidate, rows)),
            'commit': COMMIT, 'sha256': SHA256, 'officialVerifier': False}
