"""Trusted external verifier, uploaded only to the fresh verifier container."""
import copy
import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/app")
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("candidate_notes", ROOT / "notes.py")
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
search = candidate.search_notes


class Acceptance(unittest.TestCase):
    def setUp(self):
        self.items = [
            {"title": " Straße ", "tags": ["Travel"]},
            {"title": "Food", "tags": ["  APPLE "]},
            {"title": "Apple old", "archived": True},
            {},
        ]

    def test_unicode_title(self):
        self.assertEqual(search(self.items, " STRASSE "), self.items[:1])

    def test_tag_match(self):
        self.assertEqual(search(self.items, "apple"), self.items[1:2])

    def test_archived_opt_in(self):
        self.assertEqual(search(self.items, " APPLE ", True), self.items[1:3])

    def test_empty_and_whitespace(self):
        for query in ("", "  ", "\t\n"):
            self.assertEqual(search(self.items, query), [self.items[0], self.items[1], self.items[3]])
            self.assertEqual(search(self.items, query, True), self.items)

    def test_generator_order_and_identity(self):
        result = search(iter(self.items), "", True)
        self.assertEqual(result, self.items)
        self.assertTrue(all(a is b for a, b in zip(result, self.items)))

    def test_missing_fields_and_no_result(self):
        self.assertEqual(search([{}, {"tags": []}], "x"), [])
        self.assertEqual(search([], ""), [])

    def test_no_mutation(self):
        before = copy.deepcopy(self.items)
        search(self.items, "a", True)
        self.assertEqual(self.items, before)

    def test_existing_helper_is_used(self):
        import text_utils
        original = text_utils.normalize_text
        with patch.object(text_utils, "normalize_text", wraps=original) as via_module:
            if hasattr(candidate, "normalize_text"):
                with patch.object(candidate, "normalize_text", wraps=original) as via_import:
                    search(self.items, "STRASSE")
                    self.assertGreater(via_import.call_count + via_module.call_count, 0)
            else:
                search(self.items, "STRASSE")
                self.assertGreater(via_module.call_count, 0)

    def test_frozen_files(self):
        self.assertEqual((ROOT / "text_utils.py").read_text(),
                         'def normalize_text(value):\n    return value.strip().casefold()\n')
        self.assertEqual((ROOT / "AGENTS.md").read_text(),
                         'This is a small Python project using only the standard library.\n'
                         'Run tests with `python -m unittest discover -s tests`.\n'
                         'Keep public signatures stable and reuse existing utilities.\n')


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=2)
