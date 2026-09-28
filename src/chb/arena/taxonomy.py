"""Stable task-type labels; source and capability remain separate axes."""

FAMILIES = {
    'swe-bugfix', 'swe-feature', 'web-interface', 'fullstack-product',
    'business-workflow', 'data-analysis', 'long-horizon',
    'architecture-engineering', 'collaboration-planning',
    'security-reliability', 'performance', 'other',
}
CAPABILITIES = {
    'coding', 'debugging', 'frontend', 'browser', 'api', 'data', 'reasoning',
    'requirements', 'architecture', 'security', 'performance', 'reliability',
    'long-context', 'collaboration', 'communication', 'maintainability',
}


def classify(task):
    """Classify legacy tasks without editing their saved original revisions."""
    source = task.get('publicSource') or {}
    identifier = task.get('id') or ''
    if source:
        family = {'bugfix': 'swe-bugfix', 'enhancement': 'architecture-engineering'}.get(source.get('category'), 'swe-feature')
    elif identifier in {'original-storage-migration-v1'}:
        family = 'long-horizon'
    elif identifier in {'original-csv-catalog-v1'}:
        family = 'data-analysis'
    elif identifier.startswith(('original-search-', 'swe-', 'bug-')):
        family = 'swe-bugfix'
    elif identifier.startswith('ui-') or identifier == 'proj-06-audio-waveform':
        family = 'web-interface'
    elif identifier == 'proj-02-brainstorm-spec-bi':
        family = 'business-workflow'
    elif identifier == 'proj-04-auth-rbac-dashboard' or identifier == 'inter-04-safe-execution-gate':
        family = 'security-reliability'
    elif identifier.startswith('proj-'):
        family = 'fullstack-product'
    elif identifier.startswith('arch-'):
        family = 'architecture-engineering'
    elif identifier.startswith('inter-'):
        family = 'collaboration-planning'
    elif identifier.startswith('perf-'):
        family = 'performance'
    elif task.get('hasFrontendUI'):
        family = 'web-interface'
    elif task.get('taskParadigm') == 'deterministic-bugfix':
        family = 'swe-bugfix'
    else:
        family = 'business-workflow'
    family = task.get('taskFamily', family)
    if family not in FAMILIES:
        raise ValueError('题目类型无效。')
    inferred = {'coding'}
    if family in {'swe-bugfix', 'swe-feature'}: inferred |= {'debugging', 'maintainability'}
    if family in {'web-interface', 'fullstack-product'}: inferred |= {'frontend', 'browser'}
    if family in {'business-workflow', 'data-analysis'}: inferred |= {'data', 'reasoning'}
    if family in {'business-workflow', 'collaboration-planning'}: inferred |= {'requirements', 'communication'}
    if family == 'long-horizon': inferred |= {'long-context', 'reliability', 'maintainability'}
    if family == 'architecture-engineering': inferred |= {'architecture', 'maintainability'}
    if family == 'security-reliability': inferred |= {'security', 'reliability'}
    if family == 'performance': inferred.add('performance')
    tags = task.get('capabilityTags', sorted(inferred))
    if not isinstance(tags, list) or len(tags) > 16 or len(set(tags)) != len(tags) or any(tag not in CAPABILITIES for tag in tags):
        raise ValueError('能力标签无效。')
    return family, tags
