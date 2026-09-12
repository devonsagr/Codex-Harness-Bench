"""External behavior and cleanup acceptance; never present during agent execution."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(sys.argv.pop(1))
sys.path.insert(0, str(ROOT))
from notes import Store

SQLITE = os.environ.get("CHB_STAGE") == "sqlite"


class BehaviorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "notes.data"
        self.store = Store(self.path)

    def test_archive_survives_reopen(self):
        a, b = self.store.add("第一条"), self.store.add("second")
        self.store.archive(a["id"])
        reopened = Store(self.path)
        self.assertEqual(reopened.list(), [b])
        self.assertEqual(reopened.list(True), [{**a, "archived": True}, b])
        reopened.archive(a["id"], False)
        self.assertEqual(Store(self.path).list(), [a, b])

    def test_missing_id_does_not_change_notes(self):
        a = self.store.add("keep")
        with self.assertRaises(KeyError):
            self.store.archive(98)
        self.assertEqual(self.store.list(True), [a])

    def test_validation_and_copies(self):
        for bad in ("", " \t", None, 6):
            with self.assertRaises(ValueError):
                self.store.add(bad)
        a = self.store.add("  Mixed 文本  ")
        self.assertEqual(a["title"], "Mixed 文本")
        a["title"] = "outside"
        rows = self.store.list(True)
        rows[0]["archived"] = True
        rows.clear()
        self.assertEqual(Store(self.path).list(), [{"id": 1, "title": "Mixed 文本", "archived": False}])

    def test_public_regression_tests(self):
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                                cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_protected_contract_and_helper_reuse(self):
        for name, expected in json.loads(Path("/tests/protected.json").read_text()).items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)
        import contracts
        calls = []
        def observe(frame, event, arg):
            if event == "call" and frame.f_code == contracts.normalize_title.__code__:
                calls.append(True)
        previous = sys.getprofile()
        try:
            sys.setprofile(observe)
            self.store.add("helper probe")
        finally:
            sys.setprofile(previous)
        self.assertTrue(calls, "add must reuse the existing normalization helper")

    def test_archive_is_documented(self):
        self.assertIn("archive", (ROOT / "README.md").read_text().lower())

    @unittest.skipIf(SQLITE, "first-turn backend only")
    def test_json_is_current_storage_in_first_turn(self):
        note = self.store.add("current")
        self.store.archive(note["id"])
        self.assertEqual(json.loads(self.path.read_text()), [{**note, "archived": True}])


@unittest.skipUnless(SQLITE, "second-turn acceptance")
class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "notes.db"
        self.legacy = self.root / "user-notes.json"

    def test_import_retains_ids_archive_and_source(self):
        rows = [{"id": 8, "title": "中文", "archived": True}, {"id": 3, "title": "keep", "archived": False}]
        self.legacy.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        before = self.legacy.read_bytes()
        store = Store(self.path, legacy_path=self.legacy)
        self.assertEqual(store.list(True), list(reversed(rows)))
        self.assertEqual(self.legacy.read_bytes(), before)
        self.assertEqual(store.add("next")["id"], 9)
        store.archive(8, False)
        self.assertEqual(len(Store(self.path, legacy_path=self.legacy).list()), 3)
        self.assertEqual(self.path.read_bytes()[:16], b"SQLite format 3\x00")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_nonempty_database_ignores_legacy(self):
        Store(self.path).add("existing")
        self.legacy.write_text("not json")
        self.assertEqual(Store(self.path, self.legacy).list()[0]["title"], "existing")

    def test_invalid_import_is_atomic(self):
        good = {"id": 1, "title": "ok", "archived": False}
        invalid = ["not json", "{}", json.dumps([good, good]),
                   json.dumps([good, {"id": 2}]),
                   json.dumps([good, {"id": 2, "title": " ", "archived": False}]),
                   json.dumps([good, {"id": True, "title": "x", "archived": False}]),
                   json.dumps([good, {"id": 2, "title": "x", "archived": "false"}])]
        for index, value in enumerate(invalid):
            with self.subTest(index=index):
                path = self.root / f"invalid-{index}.db"
                self.legacy.write_text(value)
                with self.assertRaises(ValueError):
                    Store(path, self.legacy)
                self.assertEqual(Store(path).list(True), [])
                self.assertEqual(self.legacy.read_text(), value)

    def test_settings_and_entry_point_use_sqlite(self):
        config = json.loads((ROOT / "settings.json").read_text())
        self.assertEqual(config, {"database_path": "notes.db"})
        (self.root / "settings.json").write_text(json.dumps(config))
        from app import load_store
        store = load_store(self.root)
        note = store.add("entry point")
        store.archive(note["id"])
        self.assertEqual(load_store(self.root).list(), [])
        self.assertEqual(self.path.read_bytes()[:16], b"SQLite format 3\x00")

    def test_old_module_removed_and_documentation_current(self):
        self.assertFalse((ROOT / "legacy_store.py").exists(), "old implementation must be removed")
        for source in ROOT.glob("*.py"):
            self.assertNotIn("legacy_store", source.read_text(), str(source))
        text = (ROOT / "README.md").read_text().lower()
        for required in ("sqlite", "legacy_path", "archive", "unittest"):
            self.assertIn(required, text)
        for stale in ("backend=json", '"backend"', "json is the storage backend"):
            self.assertNotIn(stale, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
