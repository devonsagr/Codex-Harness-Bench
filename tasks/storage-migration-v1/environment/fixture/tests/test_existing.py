from pathlib import Path
import tempfile
import unittest

from notes import Store


class ExistingTests(unittest.TestCase):
    def test_add_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.data"
            store = Store(path)
            note = store.add("  笔记  ")
            self.assertEqual(note, {"id": 1, "title": "笔记", "archived": False})
            self.assertEqual(Store(path).list(), [note])


if __name__ == "__main__":
    unittest.main()
