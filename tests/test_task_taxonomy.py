import unittest

from chb.arena.taxonomy import classify


class TaskTaxonomyTests(unittest.TestCase):
    def test_public_source_categories_remain_distinct(self):
        expected = {
            'bugfix': 'swe-bugfix',
            'feature_request': 'swe-feature',
            'enhancement': 'architecture-engineering',
        }
        for category, family in expected.items():
            with self.subTest(category=category):
                self.assertEqual(classify({'id': 'public-task', 'publicSource': {'category': category}})[0], family)


if __name__ == '__main__':
    unittest.main()
