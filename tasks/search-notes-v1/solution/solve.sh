#!/bin/bash
set -euo pipefail
cat > /app/notes.py <<'PY'
from text_utils import normalize_text


def search_notes(notes, query, include_archived=False):
    normalized = normalize_text(query)
    return [
        note for note in notes
        if (include_archived or not note.get("archived", False))
        and (
            not normalized
            or normalized in normalize_text(note.get("title", ""))
            or any(normalized in normalize_text(tag) for tag in note.get("tags", []))
        )
    ]
PY
