import unittest
from decimal import Decimal
from ledger import parse_amount, summarize


class ExistingTests(unittest.TestCase):
    def test_amount_and_summary(self):
        self.assertEqual(parse_amount('2.50'), Decimal('2.50'))
        self.assertEqual(summarize({'z': Decimal('1'), 'a': Decimal('2.5')}), {'a': '2.50', 'z': '1.00'})


if __name__ == '__main__':
    unittest.main()
