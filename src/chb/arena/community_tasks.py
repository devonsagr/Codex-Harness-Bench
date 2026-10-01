"""Small community-inspired projects with fixed, reusable core contracts."""
import hashlib
import json

VERSION = 'community-engine-v1'
IMAGE = 'chb-verifier:' + VERSION


def catalog(root):
    path = root / 'tasks/community-web-v1/catalog.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []


def install(app):
    saved = []
    existing = {t['id'] for t in app.db.list('task') + app.db.list('task', True)}
    for entry in catalog(app.root):
        if 'community-' + entry['id'] in existing:continue
        folder = app.local / 'public-sources/community-starters' / entry['id']
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>任务起点</title><body></body></html>', encoding='utf-8')
        (folder / 'model.js').write_text('// 按题面实现功能核心；这里不包含参考解。\nglobalThis.CHBCore = {};\n', encoding='utf-8')
        baseline = app.import_files('baseline', {'path': str(folder), 'name': entry['title'] + ' 空白起点'})
        checks = [{'id': 'suite', 'label': f'功能核心 · {len(entry["caseIds"])} 个固定用例', 'image': IMAGE,
                   'argv': ['node', '/tests/verify.cjs', '/app', entry['id']], 'weight': 1, 'timeout': 35, 'kind': 'functional'},
                  {'id': 'ui', 'label': '页面运行、控制和核心连接检查', 'image': IMAGE,
                   'argv': ['node', '/tests/verify-ui.cjs', '/app', entry['id']], 'weight': 1, 'timeout': 60, 'kind': 'functional'}]
        saved.append(app.save_task({'id': 'community-' + entry['id'], 'title': entry['title'],
            'description': '社区实践 · ' + entry['id'], 'inputPrompt': entry['prompt'],
            'stages': [{'title': '实现页面与功能核心', 'prompt': entry['prompt']}], 'checks': checks,
            'criteria': [{'id': 'engine', 'label': '固定功能核心测试', 'required': True, 'dimension': 'intent'},
                         {'id': 'interface', 'label': '实际使用核心、可操作的页面', 'required': True, 'dimension': 'ux'},
                         {'id': 'visual', 'label': '题面场景与视觉表达', 'required': True, 'dimension': 'ux'}],
            'baselineId': baseline['id'], 'requiresBaseline': True, 'hasFrontendUI': True,
            'taskFamily': 'web-interface', 'capabilityTags': entry['tags'], 'language': 'HTML/CSS/JavaScript',
            'taskParadigm': 'open-ended-project', 'channel': 'frontend-ui', 'difficulty': entry['difficulty'],
            'sourceKind': 'community-adapted', 'referenceUrl': entry['referenceUrl'], 'license': '本项目原创适配 MIT；未复制上游代码或整份提示词',
            'environmentNote': '离线单页、小型功能核心；固定测试不评审美。首次检查自动准备容器。不同实现共享同一接口与验收，禁止用测试覆盖数量冒充完整视觉验收。',
            'sourceNote': '借鉴社区项目的任务机制，已缩小规模并新增固定接口/验收。这是 CHB 改编题，不是上游原题或官方成绩。',
            'evaluationRubric': ['核心用例逐项判定；程序与AI意见分存。', '页面须实际使用核心；视觉、连续碰撞和完整游戏流程仍需运行取证，不由核心通过自动认证。'],
            'fixedSuite': {'version': VERSION, 'task': entry['id'], 'testSha256': entry['testSha256'], 'caseIds': entry['caseIds']}}))
    return saved
