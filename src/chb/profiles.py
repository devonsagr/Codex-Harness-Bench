"""Explicit, content-addressed inputs; never import a personal Codex home."""
import hashlib
import json
import os
from pathlib import Path
import re
import tomllib


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def files_in(root):
    root = Path(root)
    if root.is_symlink() or root.is_junction():
        raise ValueError(f"Links are not allowed in frozen input: {root}")
    if not root.is_dir():
        raise ValueError(f"Input directory does not exist: {root}")
    root = root.resolve()
    result = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in {"__pycache__", ".git"})
        for name in dirs + sorted(names):
            path = Path(directory) / name
            if path.is_symlink() or path.is_junction():
                raise ValueError(f"Links are not allowed in frozen input: {path}")
        for name in sorted(names):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if path.name.lower() == "auth.json" or path.name.lower().startswith(".env") or path.suffix.lower() in {".pem", ".key"}:
                raise ValueError(f"Credential file cannot be frozen: {relative}")
            result[relative] = path.read_bytes()
    return result


def digest(files):
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
    revision = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return revision, manifest


def freeze(source, destination):
    data = files_in(source)
    revision, manifest = digest(data)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name, content in data.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return {"sha256": revision, "files": manifest}


def verify_frozen(directory, snapshot):
    if digest(files_in(directory))[0] != snapshot["sha256"]:
        raise ValueError(f"Frozen inputs changed: {directory}. Create a new experiment.")


def validate_profile(path):
    path = Path(path)
    metadata = read_json(path / "profile.json")
    if set(metadata) - {"name", "description"}:
        raise ValueError("Unsupported profile metadata")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", metadata.get("name", "")):
        raise ValueError("Profile names must be short lowercase slugs")
    files_in(path)  # Reject credential files and filesystem links before using content.
    config = tomllib.loads((path / "config.toml").read_text(encoding="utf-8"))
    allowed = {"model_reasoning_effort", "web_search"}
    if set(config) - allowed:
        raise ValueError(f"Unsupported Codex fields in this MVP: {set(config) - allowed}")
    if config.get("model_reasoning_effort") not in {"low", "medium", "high", "xhigh"}:
        raise ValueError("Explicit supported reasoning effort is required")
    if config.get("web_search") != "disabled":
        raise ValueError("This smoke protocol requires web_search = disabled")
    (path / "AGENTS.md").read_text(encoding="utf-8")
    for entry in path.iterdir():
        if entry.name not in {"profile.json", "config.toml", "AGENTS.md", "skills"}:
            raise ValueError(f"Unsupported profile input: {entry.name}")
    skills = path / "skills"
    if skills.exists():
        for skill in skills.iterdir():
            if not skill.is_dir() or not (skill / "SKILL.md").is_file():
                raise ValueError(f"Each skill must be a directory containing SKILL.md: {skill}")
    return metadata, config
