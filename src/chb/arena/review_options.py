"""Explicit reviewer budgets, separate from candidate task success/failure."""
DEFAULT_TIMEOUT=3600

class ReviewBudgetExceeded(ValueError):
    pass

def timeout_seconds(data):
    value=data.get('timeoutSeconds',DEFAULT_TIMEOUT)
    if type(value) is not int or not 60<=value<=28800:
        raise ValueError('审查时间预算须为 1 分钟至 8 小时；到时仅标记未完成，不判产物失败。')
    return value
