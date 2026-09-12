#!/bin/bash
set -euo pipefail
cat > /app/notes.py <<'PY'
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from contracts import normalize_title


class Store:
    def __init__(self, database_path, legacy_path=None):
        self.path = Path(database_path)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, archived INTEGER NOT NULL)")
            if legacy_path is not None and db.execute("SELECT count(*) FROM notes").fetchone()[0] == 0:
                try:
                    rows = json.loads(Path(legacy_path).read_text(encoding="utf-8"))
                except (ValueError, UnicodeError) as exc:
                    raise ValueError("invalid legacy JSON") from exc
                if not isinstance(rows, list):
                    raise ValueError("legacy data must be an array")
                seen = set()
                for row in rows:
                    if not isinstance(row, dict) or not {"id", "title", "archived"} <= row.keys():
                        raise ValueError("missing note fields")
                    if type(row["id"]) is not int or row["id"] <= 0 or row["id"] in seen or type(row["archived"]) is not bool:
                        raise ValueError("invalid ID or archive state")
                    normalize_title(row["title"])
                    seen.add(row["id"])
                db.executemany("INSERT INTO notes(id, title, archived) VALUES (?, ?, ?)",
                               [(row["id"], row["title"], int(row["archived"])) for row in rows])

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def add(self, title):
        title = normalize_title(title)
        with self._connect() as db:
            cursor = db.execute("INSERT INTO notes(title, archived) VALUES (?, 0)", (title,))
            return {"id": cursor.lastrowid, "title": title, "archived": False}

    def list(self, include_archived=False):
        with self._connect() as db:
            return [{"id": row[0], "title": row[1], "archived": bool(row[2])}
                    for row in db.execute("SELECT id, title, archived FROM notes WHERE ? OR archived=0 ORDER BY id", (include_archived,))]

    def archive(self, note_id, archived=True):
        with self._connect() as db:
            cursor = db.execute("UPDATE notes SET archived=? WHERE id=?", (int(bool(archived)), note_id))
            if cursor.rowcount == 0:
                raise KeyError(note_id)
PY
python - <<'PY'
from pathlib import Path
Path('/app/legacy_store.py').unlink()
PY
cat > /app/settings.json <<'JSON'
{"database_path": "notes.db"}
JSON
cat > /app/app.py <<'PY'
import json
from pathlib import Path
from notes import Store


def load_store(root):
    root = Path(root)
    config = json.loads((root / "settings.json").read_text())
    return Store(root / config["database_path"])
PY
cat > /app/README.md <<'MD'
# Notes

SQLite is the current storage. settings.json contains database_path, default notes.db.
Store(database_path, legacy_path=None) optionally imports a JSON array into an empty database once; the original source remains unchanged. JSON is only an import format.
add(title) creates notes; list() excludes archived notes, list(True) includes all.
archive(note_id, archived=True) archives a note; False restores it.
Run python -m unittest discover -s tests -v. Standard library only.
MD
