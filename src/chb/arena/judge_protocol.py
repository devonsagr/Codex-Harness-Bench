"""One anchored assessment contract for every machine-reviewed task.

The model supplies ordinal observations; arithmetic and evidence gates are code.
This is a reproducible rubric, not empirical calibration or an official reward.
"""
import re
from .files import fingerprint

VERSION = 'anchored-observations-v1'
FACETS = {
    'coverage': '本维度涉及的题面要求是否完整落实；逐条对照，额外功能不加分。',
    'quality': '已实现部分是否正确且可实际使用；列预期结果和观察结果。',
    'resilience': '针对本维度主动寻找反例、遗漏或不一致，并给出检查结果；不得凭未发现问题推断无缺陷。',
}
ANCHORS = {
    '0': '有证据的核心失败或完全不满足。',
    '1': '有实现但存在重大缺口，主要目标不能成立。',
    '2': '部分成立，仍有实质缺陷或需求遗漏。',
    '3': '适用要求成立且有直接证据，仍存在明确的次要问题。',
    '4': '适用要求完整成立；主动反例检查也有直接证据，未发现本项缺陷。不是额外功能奖励。',
    'null': '证据不足、环境不可用或本次无法判断；不记零分也不按满分。',
}


def contract(packet=None):
    value = {'version': VERSION, 'facets': FACETS, 'anchors': ANCHORS,
             'formula': '每维度 = 25 × 三项等级均值；缺一项则该维度为null。总分仍使用冻结权重，无extra/bonus。',
             'calibrated': False}
    if packet:
        task = packet['task']
        prompts = ([] if packet.get('evaluationScope', {}).get('kind') == 'stage' else [task.get('inputPrompt', '')])
        prompts += [s.get('prompt', '') for s in task.get('stages', [])]
        prompts = list(dict.fromkeys(p.strip() for p in prompts if p.strip()))
        clauses = []
        for prompt in prompts:
            # Split prose conservatively; preserve code blocks as one unit.
            for index, part in enumerate(re.split(r'(```[\s\S]*?```)', prompt)):
                chunks = [part] if index % 2 else re.split(r'(?<=[。；])|(?<=\.)\s+(?=[A-Z])|\n+', part)
                clauses.extend(chunk.strip() for chunk in chunks if chunk.strip())
        clauses = list(dict.fromkeys(clauses))
        # Bound response size without dropping any source clause.
        size = max(1, (len(clauses) + 47) // 48)
        value['requirements'] = {f'R{index//size+1:03}': '\n'.join(clauses[index:index+size])
                                 for index in range(0, len(clauses), size)}
    return {**value, 'sha256': fingerprint(value)}


INSTRUCTION = (
    '采用scoringContract的统一等级协议，不直接猜0–100分。每个ratings维度返回checks对象，'
    '恰好包含coverage、quality、resilience。每项返回level(0/1/2/3/4/null)、method、reason、evidence。'
    'reason写明本项检查的题面要求、预期结果、实际结果与缺口。不得用额外功能、代码量、漂亮描述或裁判对模型的印象加分。'
    '等级4必须给出counterEvidence数组，引用本项主动尝试的反例或边界检查记录；普通正例不能充当反例。'
    '动态功能的反例必须实际运行；静态质量允许引用具体源码对照。无适用边界时改查遗漏/不一致，不能发明题外要求。'
    '缺少证据时返回null；部分完成要给1或2，不能因为可启动就给3或4。'
    '检查所有task.criteria；intent的coverage和quality不得高于这些已验证需求的完成比例。'
    '最终ratings示例：{"intent":{"checks":{"coverage":{"level":2,"method":"runtime","reason":"预期/观察/缺口","evidence":[{"command":"实际命令","quote":"实际输出"}],"counterEvidence":[]},'
    '"quality":{"level":null,"method":"unverified","reason":"缺证据","evidence":[]},'
    '"resilience":{"level":null,"method":"unverified","reason":"未检查","evidence":[]}}}}。'
    'summary、findings、criteria仍按约定返回。所有维度使用同一格式；总分由程序计算，不要输出extra或bonus。'
    '另返回requirementChecks，键恰好等于scoringContract.requirements；每项沿用criteria的status/notes/evidence格式。'
    '这是程序从原始题面抽取的全部条款，不是新的需求。必须逐条判断；一条含多个条件时只有全部成立才能met。'
)


def validate(value, packet, commands):
    """Reuse the existing citation validator for each individual observation."""
    from .machine import dimensions, validate_machine
    from .scoring import UI_RUBRIC_KEYS
    expected = dimensions(packet['policy'], packet['task'])
    supplied = value.get('ratings')
    if not isinstance(supplied, dict) or set(supplied) != set(expected):
        raise ValueError('机器评分必须逐项覆盖冻结的评分维度。')
    flat, mapping, unknown = {}, {}, []
    runtime = UI_RUBRIC_KEYS | {'performance', 'verification', 'robustness', 'intent', 'handoff'}
    if packet['task'].get('taskFamily') == 'collaboration-planning' and not packet['task'].get('hasFrontendUI'):
        # A planning deliverable is examined directly; inventing an executable
        # acceptance command would not make its evidence more objective.
        runtime = runtime - {'intent', 'handoff', 'robustness'}
    for dim in expected:
        row = supplied[dim]
        checks = row.get('checks') if isinstance(row, dict) else None
        # A missing observation is recoverable evidence absence, not a reason to
        # discard every other valid result or silently use the model's score.
        if checks is None:
            checks = {}
        if not isinstance(checks, dict) or set(checks) - set(FACETS):
            raise ValueError('统一评分细项必须为coverage、quality、resilience。')
        for facet in FACETS:
            key = f'{dim}__{facet}'
            item = checks.get(facet)
            if item is None:
                item = {'level': None, 'method': 'unverified', 'reason': '裁判遗漏此细项。', 'evidence': []}
                unknown.append(key)
            if not isinstance(item, dict):
                raise ValueError('统一评分细项格式无效。')
            level = item.get('level')
            if level is not None and (type(level) is not int or level not in range(5)):
                raise ValueError('统一评分等级只能为0、1、2、3、4或null。')
            evidence = item.get('evidence', [])
            counter = item.get('counterEvidence', [])
            if not isinstance(counter, list):
                raise ValueError('反例证据必须是数组。')
            mapping[key] = (dim, facet, item)
            flat[key] = {'score': None if level is None else level * 25,
                         'method': item.get('method'), 'reason': item.get('reason'), 'evidence': evidence}
            if level == 4:
                flat[key + '__counter'] = {'score': 100 if counter else None,
                    'method': item.get('method') if counter else 'unverified',
                    'reason': '最高等级需要可核对的主动反例检查。', 'evidence': counter}
    clean_packet = {**packet, 'policy': {'dimensions': {key: 1 for key in flat}},
                    'task': {**packet['task'], 'hasFrontendUI': True}}
    clean_packet.pop('scoringContract', None)
    requirements = packet['scoringContract'].get('requirements', {})
    claims = value.get('requirementChecks', {})
    if not isinstance(claims, dict) or set(claims) - set(requirements):
        raise ValueError('需求检查编号不属于冻结原题条款。')
    original_criteria = clean_packet['task'].get('criteria', [])
    extra_criteria = [{'id': '__prompt_' + key} for key in requirements]
    clean_packet['task'] = {**clean_packet['task'], 'criteria': original_criteria + extra_criteria}
    reported_criteria = value.get('criteria', {})
    if not isinstance(reported_criteria, dict):
        raise ValueError('需求验收格式无效。')
    combined = {**reported_criteria, **{'__prompt_' + key: claims.get(key, {
        'status': 'unverified', 'notes': '裁判遗漏原题条款。', 'evidence': []}) for key in requirements}}
    result = validate_machine({**value, 'ratings': flat, 'criteria': combined}, clean_packet, commands)
    requirement_checks = {key: {**result['criteria'].pop('__prompt_' + key), 'source': source}
                          for key, source in requirements.items()}
    rows, warnings = {}, result['validationWarnings']
    def observe(key, dim):
        item = result['ratings'][key]
        if item['score'] is not None and dim in runtime and item['method'] != 'runtime':
            item = {**item, 'score': None, 'method': 'unverified', 'reason': '本项需要真实运行证据；静态阅读不足以判断。'}
        return item
    for dim in expected:
        checks = {}
        for facet in FACETS:
            key = f'{dim}__{facet}'
            item = observe(key, dim)
            counter = observe(key + '__counter', dim) if key + '__counter' in result['ratings'] else None
            positive_refs = {fingerprint(ref) for ref in item['evidence']}
            distinct_counter = counter and any(fingerprint(ref) not in positive_refs for ref in counter['evidence'])
            if item['score'] == 100 and (not counter or counter['score'] is None or not distinct_counter):
                item = {**item, 'score': None, 'method': 'unverified', 'reason': '最高等级缺少有效反例证据，暂不计分。'}
                warnings.append({'section': 'ratings', 'key': dim, 'message': facet + '：等级4的反例证据不足。'})
            checks[facet] = {**item, 'level': None if item['score'] is None else item['score'] / 25,
                              'label': FACETS[facet], 'counterEvidence': counter['evidence'] if counter else []}
        # Universal contradiction guard: low/unknown requirement completion
        # cannot coexist with a near-perfect goal score. No bonus compensation.
        criteria = result['criteria']
        groups = [[row['status'] for row in group.values()] for group in (criteria, requirement_checks) if group]
        if dim == 'intent' and groups:
            # Original UI criteria and source clauses overlap. Do not let many
            # easy clauses dilute a failed explicit acceptance requirement.
            cap = None if any('unverified' in group for group in groups) else min(
                100 * sum({'met': 1, 'partial': .5, 'unmet': 0}[s] for s in group) / len(group)
                for group in groups)
            for facet in ('coverage', 'quality'):
                if checks[facet]['score'] is not None and (cap is None or checks[facet]['score'] > cap):
                    checks[facet].update(score=cap,
                        constraint='受逐条需求完成比例限制；未验证需求不视作通过。')
        known = [item['score'] for item in checks.values() if item['score'] is not None]
        rows[dim] = {'score': round(sum(known) / 3, 2) if len(known) == 3 else None,
            'method': 'unverified' if len(known) < 3 else 'runtime' if all(c['method'] == 'runtime' for c in checks.values()) else 'static',
            'reason': '统一协议：覆盖、质量、反例检查三项等权；不奖励题外功能。',
            'evidence': [ref for c in checks.values() for ref in c['evidence']], 'checks': checks}
    warnings.extend({'section': 'ratings', 'key': key, 'message': '细项缺失，保留其他分项。'} for key in unknown)
    result.update(ratings=rows, scores={key: row['score'] for key, row in rows.items() if row['score'] is not None},
        scoringProtocol=VERSION, scoringContractSha256=packet['scoringContract']['sha256'],
        requirementChecks=requirement_checks, calibrated=False,
        note='等级与引用由AI判断，程序按统一规则计算；协议一致不等于已完成人工校准。')
    return result
