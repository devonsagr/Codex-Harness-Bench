"""Versioned task contracts and frozen desktop prompts, without changing old runs."""
import copy
import hashlib
import json
import re

CONTRACT_VERSION = 2
SPEC_LISTS = {'userStories': '用户故事', 'apiEndpoints': '接口约定', 'dataModel': '数据模型', 'acceptanceCriteria': '验收标准'}
DIMENSIONS = {'intent', 'maintainability', 'robustness', 'ux'}
SCOPES = {'frontend-only', 'fullstack-node', 'fullstack-sqlite', 'frontend-mockapi'}


def string(value, label, limit=8000, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f'{label}必须是{limit}字符以内的文本' + ('且不能为空。' if required else '。'))
    return value


def stable_id(prefix, value):
    return prefix + '-' + hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]


def validate_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,89}', value):
        raise ValueError('契约条目编号无效。')
    return value


def normalize_contract(task):
    """Return a copy; callers decide whether to save a new revision or freeze a new run."""
    result = copy.deepcopy(task)
    result.setdefault('difficulty', '未标注')
    version = result.get('schemaVersion', 1)
    if type(version) is not int or version not in {1, CONTRACT_VERSION}:
        raise ValueError('不支持此题目格式版本，请使用版本1或2。')
    spec = result.get('projectSpec')
    if spec is not None:
        if not isinstance(spec, dict):
            raise ValueError('项目契约必须是对象。')
        for key, label in SPEC_LISTS.items():
            rows = spec.get(key, [])
            if not isinstance(rows, list) or len(rows) > 80:
                raise ValueError(f'{label}必须是最多80条文本的数组。')
            spec[key] = [string(row, label, required=True) for row in rows]
        spec['techStack'] = string(spec.get('techStack', ''), '技术边界')
    scope = result.get('fullstackScope')
    if scope is not None and scope not in SCOPES:
        raise ValueError('项目范围无效。')
    for key in ['evaluationRubric', 'customChecklist', 'rubrics']:
        rows = result.get(key, [])
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError('原题评分细则必须是最多100项的数组。')
        for row in rows:
            if key == 'evaluationRubric':
                string(row, '原题评分说明', required=True)
            elif not isinstance(row, dict):
                raise ValueError('原题评分条目必须是对象。')
            else:
                string(row.get('label'), '原题评分条目', required=True)
                if 'desc' in row:
                    string(row['desc'], '原题评分说明')
    # One-time, deterministic conversion. In v2, removing a criterion is intentional.
    if 'criteria' not in result:
        rows = []
        seen = set()
        sources = [('projectSpec.userStories', (spec or {}).get('userStories', [])),
                   ('projectSpec.acceptanceCriteria', (spec or {}).get('acceptanceCriteria', [])),
                   ('customChecklist', result.get('customChecklist', [])),
                   ('rubrics', result.get('rubrics', [])),
                   ('evaluationRubric', result.get('evaluationRubric', []))]
        for source, items in sources:
            for item in items:
                label = item if isinstance(item, str) else item['label']
                if label.strip() in seen:
                    continue
                seen.add(label.strip())
                row = {'id': stable_id('criterion', source + ':' + label), 'label': label,
                       'description': item.get('desc', '') if isinstance(item, dict) else '',
                       'required': False, 'dimension': 'intent', 'source': source}
                if isinstance(item, dict) and ('points' in item or 'maxPoints' in item):
                    row['legacyPoints'] = item.get('points', item.get('maxPoints'))
                rows.append(row)
        result['criteria'] = rows
    criteria = result['criteria']
    if not isinstance(criteria, list) or len(criteria) > 200:
        raise ValueError('验收条目最多200项。')
    ids = set()
    for row in criteria:
        if not isinstance(row, dict):
            raise ValueError('验收条目必须是对象。')
        cid = validate_id(row.get('id'))
        if cid in ids:
            raise ValueError('验收条目编号重复。')
        ids.add(cid)
        string(row.get('label'), '验收条目', required=True)
        row['description'] = string(row.get('description', ''), '验收说明')
        if type(row.get('required', False)) is not bool:
            raise ValueError('必要项标记必须是布尔值。')
        row.setdefault('required', False)
        row.setdefault('dimension', 'intent')
        if row['dimension'] not in DIMENSIONS:
            raise ValueError('验收条目关联的评分维度无效。')
        row['source'] = string(row.get('source', 'user-authored'), '条目来源', 200)
    stages = result.get('stages', [])
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            raise ValueError('阶段必须是对象。')
        stage.setdefault('id', stable_id('stage', str(index) + ':' + stage['title']))
        validate_id(stage['id'])
    if len({s['id'] for s in stages}) != len(stages):
        raise ValueError('阶段编号重复。')
    for check in result.get('checks', []):
        check.setdefault('kind', 'other')
        if check['kind'] not in {'functional', 'build', 'rule', 'other'}:
            raise ValueError('检查类别无效。')
        refs = check.get('criterionIds', [])
        if not isinstance(refs, list) or any(not isinstance(cid, str) for cid in refs) or len(set(refs)) != len(refs) or not set(refs) <= ids:
            raise ValueError('检查引用了不存在或重复的验收条目。')
        check['criterionIds'] = refs
        if type(check.get('runOnFinal', False)) is not bool:
            raise ValueError('最终回归标记必须是布尔值。')
        check.setdefault('runOnFinal', False)
    result['schemaVersion'] = CONTRACT_VERSION
    return result


def task_view(task):
    value = normalize_contract(task)
    value['contractUpgradePending'] = task.get('schemaVersion', 1) != CONTRACT_VERSION
    return value


def contract_text(task):
    parts = []
    if task.get('fullstackScope'):
        parts.append('项目范围：' + task['fullstackScope'])
    spec = task.get('projectSpec') or {}
    if spec.get('techStack'):
        parts.append('技术边界：\n' + spec['techStack'])
    for key, label in SPEC_LISTS.items():
        if spec.get(key):
            parts.append(label + '：\n' + '\n'.join('- ' + row for row in spec[key]))
    if task.get('criteria'):
        parts.append('逐项验收约定（编号供回收后核对，不能由执行者自行改写）：\n' + '\n'.join(
            f"- [{c['id']}] {'必要项' if c['required'] else '验收观察项'}：{c['label']}" +
            ('\n  ' + c['description'] if c.get('description') else '') for c in task['criteria']))
    return '\n\n'.join(parts)


def freeze_prompts(task):
    """Freeze every stage now; later frontend edits cannot change what was prepared."""
    value = copy.deepcopy(task)
    prompts = []
    for index, stage in enumerate(value['stages']):
        text = f"总体需求：\n{value['inputPrompt']}"
        contract = contract_text(value)
        if contract:
            text += '\n\n项目契约：\n' + contract
        text += f"\n\n当前阶段 {index + 1}/{len(value['stages'])}：{stage['title']}\n{stage['prompt']}"
        prompts.append({'stageId': stage['id'], 'text': text, 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()})
    value['promptSnapshots'] = prompts
    return value


def stage_prompt(task, index):
    if 'promptSnapshots' in task:
        return {**task['promptSnapshots'][index], 'source': 'frozen-contract-v2'}
    stage = task['stages'][index]
    text = f"总体需求：\n{task['inputPrompt']}\n\n本轮任务：\n{stage['prompt']}" if index == 0 and stage['prompt'] != task['inputPrompt'] else stage['prompt']
    return {'text': text, 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'source': 'legacy-text-only'}


def applicable_checks(task, stage):
    last = len(task['stages']) - 1
    return [c for c in task['checks'] if c.get('stageIndex', last) == stage or
            (task.get('schemaVersion') == CONTRACT_VERSION and stage == last and c.get('runOnFinal'))]


def expected_checks(task):
    return [(stage, check) for stage in range(len(task['stages'])) for check in applicable_checks(task, stage)]


def import_document(document):
    if isinstance(document, dict) and 'tasks' in document:
        if type(document.get('schemaVersion', 2)) is not int or document.get('schemaVersion', 2) not in {1, 2}:
            raise ValueError('不支持此题包格式版本。')
        document = document['tasks']
    if isinstance(document, dict):
        document = [document]
    if not isinstance(document, list) or not 1 <= len(document) <= 50 or any(not isinstance(x, dict) for x in document):
        raise ValueError('题包应为一个题目对象或1–50道题目的数组。')
    # Same limit as the ordinary API; preview and commit must accept the same data.
    if len(json.dumps(document, ensure_ascii=False).encode('utf-8')) > 900000:
        raise ValueError('题包超过900 KB，请拆分导入。')
    return document
