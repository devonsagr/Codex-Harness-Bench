import unittest

from notes import search_notes
from text_utils import normalize_text


class ExistingBehavior(unittest.TestCase):
    def test_basic_search(self):
        note = {"title": "apples"}
        self.assertEqual(search_notes([note], "apple"), [note])

    def test_normalization(self):
        self.assertEqual(normalize_text(" Straße "), "strasse")


if __name__ == "__main__":
    unittest.main()
