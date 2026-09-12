import json
from pathlib import Path

from contracts import normalize_title


class Store:
    def __init__(self, path):
        self.path = Path(path)

    def list(self, include_archived=False):
        rows = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
        return [dict(row) for row in rows if include_archived or not row["archived"]]

    def add(self, title):
        title = normalize_title(title)
        rows = self.list(include_archived=True)
        row = {"id": max((row["id"] for row in rows), default=0) + 1, "title": title, "archived": False}
        rows.append(row)
        self.path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return dict(row)
