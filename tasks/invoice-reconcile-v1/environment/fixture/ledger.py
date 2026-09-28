"""Small ledger starter. Complete reconcile without changing public helpers."""
from decimal import Decimal, InvalidOperation


def parse_amount(value):
    if not isinstance(value, str):
        raise ValueError('amount must be text')
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('invalid amount') from exc
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise ValueError('invalid amount')
    return amount


def summarize(balances):
    return {name: f'{value:.2f}' for name, value in sorted(balances.items())}


def reconcile(rows):
    """Return balances and ordered exceptions for charge/refund rows."""
    raise NotImplementedError('Implement the business reconciliation rules')
