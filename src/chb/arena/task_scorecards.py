"""Versioned local scores for the five verified DeepSWE task packages.

The upstream reward stays untouched. Each target group represents a behavior,
not a count of tests. A missing case report or quality review is unknown.
"""
import json
from pathlib import Path


VERSION = 'deepswe-local-v1'
PROJECT_POLICY_VERSION = 'project-policy-v1'
AUTO_PROJECT_VERSION = 'project-tasktype-v3'

# The expected F2P totals pin this retrospective card to the inspected v1.1
# packages. New or changed packages need a reviewed card, not a silent fallback.
CARDS = {
    'adaptix-name-mapping-aliases': (44, [
        ('别名读取与优先级', 20, lambda n: not any(s in n for s in ('conflict', 'collision', 'error', 'style', 'trail', 'schema', 'dump', 'extra'))),
        ('冲突与非法映射', 20, lambda n: not any(s in n for s in ('style', 'trail', 'schema', 'dump', 'extra')) and any(s in n for s in ('conflict', 'collision', 'error'))),
        ('命名风格', 15, lambda n: 'style' in n),
        ('调试轨迹、输出兼容', 15, lambda n: 'style' not in n and any(s in n for s in ('trail', 'schema', 'dump', 'extra'))),
    ]),
    'anko-default-function-arguments': (2, [
        ('默认参数加载', 35, lambda n: 'TestLoadDefaultArguments' in n),
        ('默认参数语法与调用可见性', 35, lambda n: 'TestDefaultArgumentsVisible' in n),
    ]),
    'aiomonitor-task-snapshots-diff': (53, [
        ('快照创建、保留与删除', 25, lambda n: not any(s in n for s in ('diff', 'cli_', 'webui_', 'task_', 'stack', 'timing'))),
        ('快照差异', 15, lambda n: 'diff' in n and not any(s in n for s in ('cli_', 'webui_'))),
        ('命令行与网页入口', 20, lambda n: any(s in n for s in ('cli_', 'webui_'))),
        ('任务与调用栈呈现', 10, lambda n: any(s in n for s in ('task_', 'stack', 'timing')) and not any(s in n for s in ('cli_', 'webui_', 'diff'))),
    ]),
    'actionlint-action-pinning-lint': (55, [
        ('固定版本规则', 20, lambda n: any(s in n for s in ('CommitSHA', 'Semver', 'DynamicRef')) and not any(s in n for s in ('Config', 'PerPath', 'ReusableWorkflow'))),
        ('配置与路径例外', 20, lambda n: any(s in n for s in ('Config', 'PerPath'))),
        ('可复用工作流', 15, lambda n: 'ReusableWorkflow' in n and not any(s in n for s in ('Config', 'PerPath'))),
        ('规则组合与诊断', 15, lambda n: not any(s in n for s in ('CommitSHA', 'Semver', 'DynamicRef', 'Config', 'PerPath', 'ReusableWorkflow'))),
    ]),
    'abs-stepped-slices': (6, [
        ('数组步长切片', 20, lambda n: 'ArrayStepped' in n),
        ('字符串步长切片', 15, lambda n: 'StringStepped' in n),
        ('切片赋值', 15, lambda n: 'AssignIndexRange' in n),
        ('表达式解析', 10, lambda n: 'ParsingIndexRange' in n),
        ('旧两段范围语义', 10, lambda n: 'TwoPartRange' in n),
    ]),
}


def _cases(native):
    rows = native.get('f2pCases')
    if rows is None:
        # Old immutable reports predate f2pCases; read their saved local CTRF.
        log = native.get('logDirectory')
        path = Path(log) / 'verifier' / 'ctrf.json' if isinstance(log, str) else None
        if path is None or not path.is_file() or path.stat().st_size > 10_000_000:
            return None
        try:
            rows = [{'name': row.get('name'), 'status': row.get('status')}
                    for row in json.loads(path.read_text(encoding='utf-8')).get('results', {}).get('tests', [])
                    if isinstance(row, dict) and str(row.get('name', '')).startswith('[f2p] ')]
        except (OSError, ValueError, AttributeError, TypeError):
            return None
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get('name'), str)
                                         or row.get('status') not in {'passed', 'failed'} for row in rows):
        return None
    return rows


def score_public(task, native, quality, review_id, retrospective=True):
    """Return one evidence-linked local card, or a card with no final score."""
    task_id = (task.get('publicSource') or {}).get('id')
    if task_id not in CARDS or native is None:
        return None
    expected, groups = CARDS[task_id]
    cases = _cases(native)
    items = []
    complete = (cases is not None and len(cases) == expected == native.get('f2p_total')
                and len({case['name'] for case in cases}) == expected
                and all(case['name'].startswith('[f2p] ') for case in cases)
                and sum(case['status'] == 'passed' for case in cases) == native.get('f2p_passed'))
    if complete:
        assignments = [[group[2](case['name']) for group in groups] for case in cases]
        complete = all(sum(flags) == 1 for flags in assignments)
    for index, (label, weight, _) in enumerate(groups):
        members = [case for case, flags in zip(cases or [], assignments if complete else []) if flags[index]]
        status = None if not complete or not members else int(all(case['status'] == 'passed' for case in members))
        items.append({'label': label, 'weight': weight, 'ratio': status, 'points': weight * status if status is not None else None,
                      'evidence': 'F2P 语义组：' + '、'.join(case['name'] for case in members) if members else '缺少可核对的 F2P 测试明细'})
    p2p_total, p2p_passed = native.get('p2p_total'), native.get('p2p_passed')
    regression = (int(p2p_passed == p2p_total)
                  if type(p2p_total) is int and p2p_total > 0 and type(p2p_passed) is int
                  and 0 <= p2p_passed <= p2p_total else None)
    items.append({'label': '旧功能与边界回归', 'weight': 20, 'ratio': regression,
                  'points': 20 * regression if regression is not None else None,
                  'evidence': f"P2P {native.get('p2p_passed')}/{native.get('p2p_total')}；整组通过才得分"})
    quality = quality if type(quality) in (int, float) and 0 <= quality <= 100 and review_id else None
    items.append({'label': '工程可维护性', 'weight': 10, 'ratio': quality / 100 if quality is not None else None,
                  'points': round(quality / 10, 1) if quality is not None else None,
                  'evidence': f'独立 AI 审查 {review_id} 的可维护性分项；可人工复核' if quality is not None else '尚无有效的可维护性审查'})
    total = round(sum(item['points'] for item in items), 1) if all(item['points'] is not None for item in items) else None
    return {'version': VERSION, 'retrospective': retrospective, 'overall': total, 'items': items,
            'nativeVerificationId': native['id'], 'qualityReviewId': review_id,
            'note': '本地追溯评分，不是 DeepSWE 官方 reward；语义组全通过才记该组分，旧功能回归单列。'}


def score_project(task, trial, scores, review_id):
    """Apply the approved 60/25/15 local card to a completed open project."""
    latest = trial.get('captures', [])[-1] if trial.get('captures') else None
    measured = dict(scores)
    if task.get('checks') and latest:
        checks = latest.get('checks', [])
        if not checks or any(row.get('status') not in {'passed', 'failed'} for row in checks):
            measured['verification'] = None
        elif any(row['status'] == 'failed' for row in checks):
            measured['verification'] = 0
    reliability = [('verification', 10), ('robustness', 5), ('ux', 10)] if task.get('hasFrontendUI') else [('verification', 10), ('robustness', 15)]
    groups = [('用户目标与范围', [('intent', 50), ('instruction', 10)]),
              ('实际使用与可靠性', reliability),
              ('交付与可维护性', [('maintainability', 10), ('handoff', 5)])]
    items = []
    for label, dimensions in groups:
        weight = sum(points for _, points in dimensions)
        known = all(type(measured.get(key)) in (int, float) for key, _ in dimensions)
        earned = round(sum(measured[key] * points / 100 for key, points in dimensions), 2) if known else None
        items.append({'label': label, 'weight': weight, 'ratio': earned / weight if earned is not None else None,
                      'points': earned, 'evidence': '；'.join(f'{key}={measured.get(key) if measured.get(key) is not None else "未验证"}' for key, _ in dimensions)})
    total = round(sum(row['points'] for row in items), 1) if review_id and all(row['points'] is not None for row in items) else None
    return {'version': VERSION, 'retrospective': False, 'overall': total, 'items': items,
            'nativeVerificationId': None, 'qualityReviewId': review_id,
            'note': '本地开放项目评分：目标 60、使用与可靠性 25、交付维护 15；有配置的程序检查失败会限制验证项。'}


def score_project_policy(task, trial, scores, review_id, policy):
    """Score a new open-project run using its frozen, selected rubric weights."""
    from .scoring import UI_RUBRIC_KEYS
    weights = {key:weight for key,weight in policy['dimensions'].items()
               if weight>0 and (key not in UI_RUBRIC_KEYS or task.get('hasFrontendUI'))}
    total_weight = sum(weights.values())
    latest = trial.get('captures', [])[-1] if trial.get('captures') else None
    measured = dict(scores)
    verification_note = None
    if 'verification' in weights and task.get('checks') and latest:
        checks = latest.get('checks', [])
        if not checks or any(row.get('status') not in {'passed', 'failed'} for row in checks):
            measured['verification'] = None
            verification_note = '已配置的程序检查尚无完整结果，验证项未计分'
        elif any(row['status'] == 'failed' for row in checks):
            measured['verification'] = 0
            verification_note = '已有程序检查失败，验证项限制为 0 分'
    items = []
    for key,weight in weights.items():
        value = measured.get(key)
        known = type(value) in (int, float)
        items.append({'key': key, 'label': policy['rubrics'][key]['label'],
                      'weight': round(weight / total_weight * 100, 2),
                      'ratio': value / 100 if known else None,
                      'points': round(value * weight / total_weight, 2) if known else None,
                      'evidence': verification_note if key=='verification' and verification_note else
                                  (f'冻结评分方案 {key}：{value} 分' if known else '缺少可核对的逐项证据')})
    complete = review_id and all(item['points'] is not None for item in items)
    total = round(sum(item['points'] for item in items), 2) if complete else None
    return {'version': PROJECT_POLICY_VERSION, 'retrospective': False, 'overall': total, 'items': items,
            'nativeVerificationId': None, 'qualityReviewId': review_id,
            'note': '本地开放项目分按创建评测时冻结的适用评分项与权重计算；未测项不当作零分。有配置的程序检查失败会限制验证项。'}


def score_project_auto(task, trial, scores, review_id, scorecard_version=AUTO_PROJECT_VERSION):
    """A frozen task-type card: one result, with three disjoint 60/25/15 groups."""
    from .scoring import AUTO_PROJECT_GROUPS, AUTO_PROJECT_GROUPS_V2, auto_profile, RUBRICS
    profile = auto_profile(task)
    groups = (AUTO_PROJECT_GROUPS if scorecard_version==AUTO_PROJECT_VERSION else AUTO_PROJECT_GROUPS_V2)[profile]
    latest = trial.get('captures', [])[-1] if trial.get('captures') else None
    measured = dict(scores)
    verification_note = None
    if 'verification' in measured and task.get('checks') and latest:
        checks = latest.get('checks', [])
        if not checks or any(row.get('status') not in {'passed', 'failed'} for row in checks):
            measured['verification'] = None
            verification_note = '已配置的程序检查尚无完整结果，验证项未计分'
        elif any(row['status'] == 'failed' for row in checks):
            measured['verification'] = 0
            verification_note = '已有程序检查失败，验证项限制为 0 分'
    items = []
    for label, dimensions in groups:
        weight = sum(points for _, points in dimensions)
        known = all(type(measured.get(key)) in (int, float) for key, _ in dimensions)
        earned = round(sum(measured[key] * points / 100 for key, points in dimensions), 2) if known else None
        evidence = '；'.join(f'{RUBRICS[key][0]} {points}%：{measured.get(key) if measured.get(key) is not None else "未验证"}'
                            for key, points in dimensions)
        if verification_note and any(key == 'verification' for key, _ in dimensions):
            evidence += '；' + verification_note
        items.append({'label': label, 'weight': weight, 'ratio': earned / weight if earned is not None else None,
                      'points': earned, 'evidence': evidence})
    complete = review_id and all(item['points'] is not None for item in items)
    total = round(sum(item['points'] for item in items), 2) if complete else None
    return {'version': scorecard_version, 'retrospective': False, 'overall': total, 'items': items,
            'nativeVerificationId': None, 'qualityReviewId': review_id,
            'note': '按冻结题型自动选三组评分项：目标 60、使用与可靠性 25、交付维护 15；规则约束在目标组计一次。缺证据留空，原题程序验收另列。'}
