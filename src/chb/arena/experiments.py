"""Frozen, within-model Harness experiments and evidence-first paired reports.

Reports never treat a subjective quality grade as an independent success oracle.
Every planned attempt remains in the denominator, including missing/failed runs.
"""
import copy
import math
from statistics import mean, median

from .files import fingerprint


VERSION = 'harness-paired-v1'
HARNESS_FIELDS = ('agentsPrompt', 'customConstraints', 'skills', 'skillMode',
                  'interactiveMode', 'nativeSettings', 'integrations')


def plan(data, configs, tasks, policy):
    value = data.get('experiment')
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {'hypothesis', 'repeats', 'activeMinutes', 'maxTokens'}:
        raise ValueError('对照实验设置无效。')
    if len(configs) != 2:
        raise ValueError('Harness 对照需要两套不同配置。')
    if len({(c['baseModel'], c['reasoning'], c.get('serviceTier', '')) for c in configs}) != 1:
        raise ValueError('Harness 对照必须使用相同模型、思考档位和速度。')
    if all(configs[0].get(k) == configs[1].get(k) for k in HARNESS_FIELDS):
        raise ValueError('两套配置内容相同，请选择确有规则、技能或流程差异的配置。')
    hypothesis = value.get('hypothesis', '')
    if not isinstance(hypothesis, str) or not 5 <= len(hypothesis.strip()) <= 1000:
        raise ValueError('请用 5–1000 字说明要验证的 Harness 改动。')
    repeats = value.get('repeats', 2)
    minutes = value.get('activeMinutes', 30)
    tokens = value.get('maxTokens')
    if type(repeats) is not int or not 1 <= repeats <= 5 or len(tasks)*repeats*2 > 60:
        raise ValueError('每题重复 1–5 次，总工作区数不得超过 60。')
    if type(minutes) is not int or not 5 <= minutes <= 240:
        raise ValueError('每次活动时间预算应为 5–240 分钟。')
    if tokens is not None and (type(tokens) is not int or not 1000 <= tokens <= 100_000_000):
        raise ValueError('Token 预算须为 1000–100000000，或留空。')
    result = {'version': VERSION, 'hypothesis': hypothesis.strip(), 'repeats': repeats,
              'activeMinutes': minutes, 'maxTokens': tokens, 'configIds': [c['id'] for c in configs],
              'taskIds': [t['id'] for t in tasks], 'primaryOutcome': 'verified-delivery',
              'changedFields': [k for k in HARNESS_FIELDS if configs[0].get(k) != configs[1].get(k)],
              'configHashes': [fingerprint(c) for c in configs], 'taskHashes': [fingerprint(t) for t in tasks],
              'policyHash': fingerprint(policy), 'budgetEnforcement': 'observed-not-desktop-kill',
              'order': 'alternating-pairs', 'plannedTrials': len(tasks)*repeats*2}
    return {**result, 'sha256': fingerprint(result)}


def schedule(tasks, configs, experiment):
    """AB/BA pairs with independent workspaces; repeats never reuse sessions."""
    for repeat in range(experiment['repeats'] if experiment else 1):
        for index, task in enumerate(tasks):
            order = list(enumerate(configs))
            if experiment and (repeat + index) % 2:
                order.reverse()
            for arm, config in order:
                yield task, config, ({'pairId': f'{task["id"]}:{repeat+1}', 'repeat': repeat+1,
                                      'arm': 'AB'[arm]} if experiment else {})


def minimal_copy(app, data):
    """Explicit library action; never writes the host's settings."""
    from .service import identifier
    source = app.db.get('config', identifier(data.get('configId')))
    if source.get('archived') or source['revision'] != data.get('revision'):
        raise ValueError('配置已变化或归档，请刷新后重试。')
    value = copy.deepcopy(source)
    for key in ('id', 'revision', 'archived', 'importSource'):
        value.pop(key, None)
    value.update(name=(source['name'][:90] + ' · 精简对照'), agentsPrompt='', skills=[],
                 customConstraints=[], skillMode='auto',
                 tagline='移除附加规则、个人约束和选用技能；保留模型、工具和交互设置，仍继承宿主。')
    return app.save_config(value)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def comparison_host(app, run, trial):
    """Separate the explicitly applied treatment from its inherited host context."""
    import base64
    import json
    from .files import safe_path, hash_bytes
    from .codex_apply import managed_paths, native
    aid = trial.get('codexApplicationId')
    if not aid:
        host = app.host_fingerprint()
        return {k: v for k, v in host.items() if k != 'config.toml' or not host.get('configSemantic')}
    receipt = json.loads(safe_path(app.local, f'codex-applications/{aid}/receipt.json').read_text(encoding='utf-8'))
    # Switch restores the original host before applying a different treatment.
    # Use that saved inherited instruction layer, never the treatment's own hash.
    before = receipt['files']['AGENTS.override.md'].get('before')
    _, doc, _ = native()
    values = doc.unwrap()
    values.pop('projects', None)
    for config in run['configs']:
        for path in managed_paths(config):
            parent = values
            for key in path[:-1]:
                parent = parent.get(key, {})
            parent.pop(path[-1], None)
    def compact(value):
        return {k: compact(v) if isinstance(v, dict) else v for k, v in value.items()
                if not isinstance(v, dict) or compact(v)}
    return {'configSemantic': fingerprint(compact(values)),
            'AGENTS.md': app.host_fingerprint().get('AGENTS.md'),
            'AGENTS.override.md': hash_bytes(base64.b64decode(before)) if before is not None else None,
            'applicationContext': 'explicit-application-v1'}


def delivery(task, trial):
    """Program success is independent of judge availability and quality points."""
    captures = trial.get('captures') or []
    if not captures:
        return {'status': 'unknown', 'reason': '尚未回收产物', 'source': 'none'}
    capture = captures[-1]
    from .fixed_suites import summary as fixed_summary
    program = fixed_summary(task, trial)
    if program and program['version']=='evalplus-originfmt-v1':
        return {'status': program['status'] if program['status'] in {'passed','failed'} else 'unknown',
                'reason': program['scope'], 'source': 'fixed-suite', 'protocol': program['protocol']}
    if len(task.get('stages', [])) > 1 and trial.get('finalCaptureId') != capture['id']:
        return {'status': 'unknown', 'reason': '尚未完成最终阶段验收', 'source': 'none'}
    native = next((v for v in reversed(capture.get('nativeVerifications', []))
                   if v.get('captureHash') == capture['manifest']['sha256']
                   and type(v.get('reward')) is int and v['reward'] in (0, 1)), None)
    execution = trial.get('nativeExecution') or {}
    if native and execution.get('captureId') == capture['id'] and execution.get('status') in {'running', 'failed', 'interrupted'}:
        return {'status': 'unknown', 'reason': '本快照原验收重试尚未完成', 'source': 'native'}
    if native:
        return {'status': 'passed' if native['reward'] else 'failed', 'reason': '原题程序验收',
                'source': 'native', 'evidenceId': native['id'],
                'protocol': fingerprint({k: native.get(k) for k in ('adapter', 'imageId', 'goVersion', 'sourceRevision')})}
    checks = capture.get('checks') or []
    configured = {c['id'] for c in task.get('checks', []) if c.get('id')}
    if any(c.get('status') == 'failed' and c.get('id') in configured for c in checks):
        return {'status': 'failed', 'reason': '任务程序检查有明确失败', 'source': 'program',
                'protocol': fingerprint(sorted((c.get('id'), c.get('imageId')) for c in checks))}
    behavior = (trial.get('score') or {}).get('behaviorAcceptance') or {}
    if behavior.get('captureHash') == capture['manifest']['sha256'] and behavior.get('status') == 'failed':
        return {'status': 'failed', 'reason': '任务交互检查有明确失败', 'source': 'behavior'}
    from .machine import score_assurance
    assurance = score_assurance(task, trial)
    if assurance in {'task-check-pass', 'task-check-fail'}:
        return {'status': 'passed' if assurance == 'task-check-pass' else 'failed',
                'reason': '已验证的任务专属程序验收', 'source': 'program',
                'protocol': fingerprint(sorted((c.get('id'), c.get('imageId')) for c in checks))}
    return {'status': 'unknown', 'reason': '现有检查覆盖有限；AI 参考分不代替整题验收', 'source': 'limited'}


def conditions(run, trial, config):
    issues = []
    usage = trial.get('usage') or {}
    if usage.get('models') != [config['baseModel']]:
        issues.append('实际模型缺失或与冻结值不同')
    if not config.get('reasoning') or usage.get('reasoningLevels') != [config['reasoning']]:
        issues.append('实际思考档位缺失或与冻结值不同')
    tiers = usage.get('serviceTiers') or []
    if not config.get('serviceTier') or tiers != [config['serviceTier']]:
        issues.append('实际速度未由日志核对')
    if not usage.get('sessionId'):
        issues.append('未绑定独立原生会话')
    if any(not c.get('harnessUnchanged') or not c.get('hostUnchanged') for c in trial.get('captures', [])):
        issues.append('工作区或宿主设置发生变化')
    if trial.get('experimentHostContext') and any(c.get('experimentHostContext') != trial['experimentHostContext'] for c in trial.get('captures', [])):
        issues.append('未纳入实验变量的宿主设置发生变化')
    if trial.get('observations'):
        issues.append('有运行条件变动记录')
    host = trial.get('appliedHostFingerprint', run.get('hostFingerprint', {}))
    if not host:
        issues.append('宿主指纹缺失')
    return issues


def assessment(trial):
    """Expose coverage, not a fabricated absolute quality certification."""
    latest = (trial.get('captures') or [{}])[-1]
    reviews = [r for r in trial.get('reviews', []) if r.get('captureId') == latest.get('id') and r.get('kind') == 'ai']
    review = reviews[-1] if reviews else {}
    dialogue=latest.get('interactionEvidence') or {}
    interaction=review.get('interaction') or {}
    observed=interaction if dialogue.get('sha256') and interaction.get('evidenceSha256')==dialogue['sha256'] else None
    requirements = review.get('requirementChecks') or {}
    rows = list(requirements.values())
    return {'requirements': len(rows), 'met': sum(r.get('status') == 'met' for r in rows),
            'notMet': sum(r.get('status') in {'unmet', 'partial'} for r in rows),
            'unknown': sum(r.get('status') not in {'met', 'unmet', 'partial'} for r in rows),
            'referenceScore': (trial.get('score') or {}).get('overall'), 'calibrated': False,
            'interaction': {key:observed.get(key) for key in ('counts','totalTurns','omittedTurns','version')} if observed else None}


def report(run):
    experiment = run.get('experiment')
    if not experiment:
        return None
    tasks = {t['id']: t for t in run['tasks']}
    configs = {c['id']: c for c in run['configs']}
    rows = []
    sessions = [t.get('usage', {}).get('sessionId') for t in run['trials'] if t.get('usage')]
    for trial in run['trials']:
        result = delivery(tasks[trial['taskId']], trial)
        usage = trial.get('usage') or {}
        time = usage.get('activeSeconds')
        tokens = usage.get('totalTokens')
        over = (finite(time) and time > experiment['activeMinutes']*60) or (
            experiment.get('maxTokens') is not None and finite(tokens) and tokens > experiment['maxTokens'])
        budget_known = finite(time) and (experiment.get('maxTokens') is None or finite(tokens))
        issues = conditions(run, trial, configs[trial['configId']])
        if usage.get('sessionId') and sessions.count(usage['sessionId']) > 1:
            issues.append('同一会话被重复用于不同试次')
        finished = trial.get('state') == 'completed'
        outcome = 'failed' if over or result['status'] == 'failed' else (
            'passed' if result['status'] == 'passed' and finished and budget_known else 'unknown')
        rows.append({'trialId': trial['id'], 'taskId': trial['taskId'], 'title': tasks[trial['taskId']]['title'],
                     'arm': trial['experimentArm'], 'pairId': trial['pairId'], 'repeat': trial['repeat'],
                     'state': trial['state'], 'delivery': result, 'outcome': outcome,
                     'overBudget': bool(over), 'budgetKnown': bool(budget_known), 'conditions': issues,
                     'tokens': tokens if finite(tokens) else None, 'activeSeconds': time if finite(time) else None,
                     'assessment': assessment(trial)})
    pairs = []
    trials = {t['id']: t for t in run['trials']}
    for pair_id in dict.fromkeys(r['pairId'] for r in rows):
        a = next(r for r in rows if r['pairId'] == pair_id and r['arm'] == 'A')
        b = next(r for r in rows if r['pairId'] == pair_id and r['arm'] == 'B')
        problems = list(dict.fromkeys(a['conditions'] + b['conditions']))
        hosts = [trials[r['trialId']].get('experimentHostContext') or trials[r['trialId']].get('appliedHostFingerprint', run.get('hostFingerprint', {})) for r in (a, b)]
        hosts = [{k:v for k,v in host.items() if k!='config.toml' or not host.get('configSemantic')} for host in hosts]
        if hosts[0] != hosts[1]:
            problems.append('两次执行的宿主指纹不同')
        if a['delivery'].get('protocol') != b['delivery'].get('protocol'):
            problems.append('程序验收环境或协议不同/缺失')
        pairs.append({'pairId': pair_id, 'taskId': a['taskId'], 'repeat': a['repeat'], 'a': a, 'b': b,
                      'conditions': problems, 'matched': not problems,
                      'successDelta': (int(b['outcome'] == 'passed')-int(a['outcome'] == 'passed'))
                      if a['outcome'] != 'unknown' and b['outcome'] != 'unknown' else None,
                      'tokenDelta': b['tokens']-a['tokens'] if a['tokens'] is not None and b['tokens'] is not None else None,
                      'secondsDelta': b['activeSeconds']-a['activeSeconds'] if a['activeSeconds'] is not None and b['activeSeconds'] is not None else None})
    arms = []
    for arm, cid in zip('AB', experiment['configIds']):
        selected = [r for r in rows if r['arm'] == arm]
        counts = {s: sum(r['outcome'] == s for r in selected) for s in ('passed', 'failed', 'unknown')}
        n = len(selected)
        metrics = {}
        for key in ('tokens', 'activeSeconds'):
            known = [r[key] for r in selected if r[key] is not None]
            total = sum(known) if len(known) == n else None
            metrics[key] = {'total': total, 'observedTotal': sum(known), 'known': len(known), 'planned': n,
                            'perSuccess': total/counts['passed'] if total is not None and counts['passed'] and not counts['unknown'] else None}
        arms.append({'arm': arm, 'configId': cid, 'name': configs[cid]['name'], 'planned': n, **counts,
                     'interrupted': sum(r['state'] == 'interrupted' for r in selected),
                     'overBudget': sum(r['overBudget'] for r in selected),
                     'rate': counts['passed']/n if n and not counts['unknown'] else None,
                     'bounds': [counts['passed']/n, (counts['passed']+counts['unknown'])/n] if n else None,
                     'metrics': metrics})
    # Task means prevent future unequal repeats from silently overweighting a task.
    usable = [p for p in pairs if p['matched'] and p['successDelta'] is not None]
    differences = [mean(p['successDelta'] for p in usable if p['taskId'] == tid)
                   for tid in tasks if any(p['taskId'] == tid for p in usable)]
    complete = len(usable) == len(pairs) and bool(pairs)
    outcomes_complete = bool(pairs) and all(p['successDelta'] is not None for p in pairs)
    return {'version': VERSION, 'arms': arms, 'pairs': pairs, 'plannedPairs': len(pairs),
            'matchedPairs': sum(p['matched'] for p in pairs), 'verifiedPairs': len(usable),
            'successDelta': mean(differences) if complete else None,
            'observedSuccessDelta': mean(p['successDelta'] for p in pairs) if outcomes_complete else None,
            'medianTaskDelta': median(differences) if complete else None,
            'status': 'observed' if complete else 'incomplete',
            'conclusion': '配对结果已齐；这是本题集观测差异，尚未做独立确认实验。' if complete else '配对证据尚未齐全；各次结果保留，未验证项不算零分。',
            'limitations': ['预算按原生日志事后核对，不会自动停止桌面任务。',
                           '活动时间含工具与区间内等待，不是纯推理时间；裁判费用另计。',
                           '通过仅指冻结程序验收范围，不能证明所有视觉质量；AI 分数不参与通过率。',
                           '未知范围是缺失结果的上下界，不是置信区间；不自动宣布胜者。']}
