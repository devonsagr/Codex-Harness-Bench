"""Independent business-rule verifier; this file is never in the candidate."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else '/app')
spec = importlib.util.spec_from_file_location('candidate_ledger', ROOT / 'ledger.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def row(id, customer, kind, amount, ref=None):
    result = {'id': id, 'customer': customer, 'kind': kind, 'amount': amount}
    if ref is not None: result['ref'] = ref
    return result


class LedgerAcceptance(unittest.TestCase):
    def test_partial_refunds_and_zero_balance(self):
        rows = [row('a', 'Lin', 'charge', '12.30'), row('b', 'Lin', 'refund', '2.30', 'a'),
                row('c', 'Lin', 'refund', '10.00', 'a')]
        self.assertEqual(candidate.reconcile(rows), {'balances': {'Lin': '0.00'}, 'exceptions': []})

    def test_duplicate_does_not_change_reference_or_balance(self):
        rows = [row('a', 'A', 'charge', '5'), row('a', 'A', 'charge', '20'),
                row('b', 'A', 'refund', '5', 'a')]
        self.assertEqual(candidate.reconcile(rows), {'balances': {'A': '0.00'},
                                                     'exceptions': [{'index': 1, 'code': 'DUPLICATE'}]})

    def test_invalid_and_future_reference(self):
        rows = [row('r', 'A', 'refund', '1', 'c'), row('c', 'A', 'charge', '1.001'),
                row('d', 'A', 'charge', '4'), row('e', 'A', 'refund', 'NaN', 'd')]
        self.assertEqual(candidate.reconcile(rows), {'balances': {'A': '4.00'}, 'exceptions': [
            {'index': 0, 'code': 'UNKNOWN_REFERENCE'}, {'index': 1, 'code': 'INVALID_AMOUNT'},
            {'index': 3, 'code': 'INVALID_AMOUNT'}]})

    def test_customer_and_cumulative_limit(self):
        rows = [row('a', 'A', 'charge', '10'), row('b', 'B', 'refund', '2', 'a'),
                row('c', 'A', 'refund', '6', 'a'), row('d', 'A', 'refund', '5', 'a')]
        self.assertEqual(candidate.reconcile(rows), {'balances': {'A': '4.00'}, 'exceptions': [
            {'index': 1, 'code': 'CUSTOMER_MISMATCH'}, {'index': 3, 'code': 'OVER_REFUND'}]})

    def test_decimal_order_and_no_mutation(self):
        rows = [row('a', 'Z', 'charge', '0.10'), row('b', 'A', 'charge', '0.20'),
                row('c', 'Z', 'charge', '0.20'), row('d', 'Z', 'refund', '0.10', 'c')]
        before = copy.deepcopy(rows)
        self.assertEqual(candidate.reconcile(rows), {'balances': {'A': '0.20', 'Z': '0.20'}, 'exceptions': []})
        self.assertEqual(rows, before)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
