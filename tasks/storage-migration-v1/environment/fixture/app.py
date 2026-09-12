import json
from pathlib import Path

from notes import Store


def load_store(root):
    root = Path(root)
    config = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    if config["backend"] != "json":
        raise ValueError("unsupported backend")
    return Store(root / config["path"])
