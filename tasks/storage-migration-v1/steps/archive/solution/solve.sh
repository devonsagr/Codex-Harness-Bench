#!/bin/bash
set -euo pipefail
cat >> /app/legacy_store.py <<'PY'

    def archive(self, note_id, archived=True):
        rows = self.list(True)
        for row in rows:
            if row["id"] == note_id:
                row["archived"] = bool(archived)
                self.path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
                return
        raise KeyError(note_id)
PY
cat >> /app/README.md <<'MD'

Use archive(note_id, archived=True) to archive; pass False to restore. list(True) includes archived notes.
MD
