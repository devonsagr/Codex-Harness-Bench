"""Pinned HumanEval+ OriginFmt tests, adapted to a desktop solution.py file.

The malformed task-32 export is excluded from the runnable set. This is not an official
pass@k run: generation, sandbox, timeout and Python version differ.
"""
import gzip
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

COMMIT = '200defce9e3429d28ca215b6dd061c0f7f31c18b'
SHA256 = 'daa7661c8189924068069b0872a440b491edb60f8bdf431d5957adc88d18bae5'
URL = f'https://raw.githubusercontent.com/evalplus/humanevalplus_release/{COMMIT}/HumanEvalPlus-OriginFmt.jsonl.gz'
VERSION = 'evalplus-originfmt-v1'
IMAGE = 'chb-verifier:' + VERSION
EXCLUDED = {'HumanEval/32'}


def input_count(test):
    for node in ast.walk(ast.parse(test)):
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.List) and any(isinstance(t,ast.Name) and t.id=='inputs' for t in node.targets):
            return len(node.value.elts)
    return None


def definitions(raw):
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('HumanEval+ 固定数据校验失败。')
    rows = [json.loads(line) for line in gzip.decompress(raw).splitlines() if line.strip()]
    if len(rows) != 164 or {r['task_id'] for r in rows} != {f'HumanEval/{i}' for i in range(164)}:
        raise ValueError('HumanEval+ 题目编号或数量无效。')
    return rows


def dataset(app):
    folder = app.local / 'public-sources' / 'evalplus' / COMMIT
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / 'HumanEvalPlus-OriginFmt.jsonl.gz'
    if file.is_file():
        raw = file.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=45) as response:
            raw = response.read(2_000_001)
        definitions(raw)
        file.write_bytes(raw)
    return definitions(raw)


def task_definition(row, baseline_id):
    if row['task_id'] in EXCLUDED:
        raise ValueError('此固定导出题未通过验收器资格检查，不加入可运行题库。')
    index = row['task_id'].split('/')[1]
    prompt = ('实现 solution.py 中的函数，保持原始签名。仅使用 Python 标准库；不要读取隐藏测试。\n\n'
              + row['prompt'])
    return {'id': 'evalplus-' + index, 'title': 'HumanEval+ · ' + row['entry_point'],
        'inputPrompt': prompt, 'stages': [{'title': '实现函数并自检', 'prompt': prompt}],
        'criteria': [{'id': 'suite', 'label': '原始扩展测试全部通过', 'description': '按固定 OriginFmt 测试判定，不由 AI 选择样例。', 'required': True, 'dimension': 'intent'}],
        'checks': [{'id': 'suite', 'label': 'HumanEval+ 原始扩展测试', 'image': IMAGE,
                    'argv': ['python', '-I', '/tests/verify.py', '/app', index], 'weight': 1, 'timeout': 40, 'kind': 'functional'}],
        'baselineId': baseline_id, 'requiresBaseline': True, 'hasFrontendUI': False,
        'taskFamily': 'swe-bugfix', 'capabilityTags': ['coding', 'reasoning', 'reliability'],
        'language': 'Python', 'taskParadigm': 'deterministic-bugfix', 'channel': 'deepswe-core', 'difficulty': 'Short',
        'sourceKind': 'evalplus-local', 'referenceUrl': 'https://github.com/evalplus/evalplus',
        'license': 'Apache-2.0（上游数据）；本地适配沿用项目许可',
        'environmentNote': 'Python 3.12 + NumPy 1.26.4 隔离验收；桌面只交付 solution.py。首次检查自动准备镜像。不进入默认项目随机组卷。',
        'evaluationRubric': ['程序通过/失败独立展示；AI 质量意见不改变程序结果。', '桌面适配不是官方 pass@k；短函数用于流程开销对照，不代表完整项目能力。'],
        'sourceNote': f'HumanEval+ {row["task_id"]}，固定提交 {COMMIT}；保留原题面和扩展断言，隐藏测试及参考解不进入工作区。',
        'fixedSuite': {'version': VERSION, 'task': index, 'testSha256': hashlib.sha256(row['test'].encode()).hexdigest(), 'inputCount': input_count(row['test'])}}


def install(app):
    rows = dataset(app)
    existing = {t['id'] for t in app.db.list('task') + app.db.list('task', True)}
    added = 0
    for row in rows:
        if row['task_id'] in EXCLUDED:continue
        index = row['task_id'].split('/')[1]
        if 'evalplus-' + index in existing:
            continue
        folder = app.local / 'public-sources' / 'evalplus-starters' / index
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'solution.py').write_text(row['prompt'] + '    pass\n', encoding='utf-8')
        baseline = app.import_files('baseline', {'path': str(folder), 'name': row['task_id'] + ' 函数起点'})
        app.save_task(task_definition(row, baseline['id']))
        added += 1
    return {'added': added, 'total': len(rows)-len(EXCLUDED), 'indexed': len(rows), 'excluded': sorted(EXCLUDED),
            'commit': COMMIT, 'sha256': SHA256, 'officialLeaderboard': False}


def prepare(app, task, image):
    if task.get('sourceKind') != 'evalplus-local' or image != IMAGE:
        return False
    rows = dataset(app)
    folder = app.local / 'verifier-builds' / VERSION
    folder.mkdir(parents=True, exist_ok=True)
    # Only the verifier context contains expected outputs, never a starter.
    tests = {r['task_id'].split('/')[1]: {k: r[k] for k in ('entry_point', 'test')} for r in rows if r['task_id'] not in EXCLUDED}
    (folder / 'tests.json').write_text(json.dumps(tests), encoding='utf-8')
    for name in ('Dockerfile', 'verify.py'):
        shutil.copyfile(app.root / 'tasks/evalplus-v1/tests' / name, folder / name)
    result = subprocess.run(['docker', 'build', '-t', IMAGE, str(folder)], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=900)
    if result.returncode:
        raise ValueError('HumanEval+ 验收镜像准备失败：' + result.stderr[-800:])
    return True
