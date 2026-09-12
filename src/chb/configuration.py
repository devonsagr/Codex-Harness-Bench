"""Explicit private profile operations. Never write back to the user's Codex home."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tomllib
import uuid

from chb.profiles import digest, files_in, read_json, validate_profile, verify_frozen, write_json


def resolve_profile(root, name):
    candidate = Path(name)
    if candidate.is_absolute() or len(candidate.parts) > 1:
        return candidate.absolute()
    matches = [base / name for base in (root / "profiles", root / ".local/profiles") if (base / name).is_dir()]
    if len(matches) != 1:
        raise ValueError(f"Profile {name!r} is missing or ambiguous; use its explicit path")
    return matches[0]


def save_private(root, name, files, provenance):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", name):
        raise ValueError("Use a short lowercase profile name")
    destination = root / ".local/profiles" / name
    if destination.exists() or (root / "profiles" / name).exists():
        raise ValueError(f"Profile already exists: {name}; choose a new name")
    # Validate the complete staged profile before exposing it for selection.
    staging = root / ".local/staging" / uuid.uuid4().hex
    staging.mkdir(parents=True)
    for relative, data in files.items():
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    validate_profile(staging)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging.rename(destination)
    receipt = root / ".local/provenance" / f"{name}.json"
    write_json(receipt, {**provenance, "destination": str(destination),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "snapshot": {"sha256": digest(files_in(destination))[0],
                                     "files": digest(files_in(destination))[1]},
                        "host_configuration_modified": False})
    return {"profile": str(destination), "receipt": str(receipt)}


def import_current(root, name, home=None, reasoning=None):
    home = Path(home) if home is not None else Path.home() / ".codex"
    # Read only these explicit files. No home traversal or credential access.
    source = home / "AGENTS.override.md"
    if not source.is_file() or not source.read_bytes().strip():
        source = home / "AGENTS.md"
    config_path = home / "config.toml"
    for path in (source, config_path):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Linked configuration sources are not supported")
    native = tomllib.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.exists() else {}
    effort = reasoning or native.get("model_reasoning_effort") or "medium"
    normalized = {"model_reasoning_effort": effort, "web_search": "disabled"}
    instructions = source.read_bytes()
    config = f'model_reasoning_effort = "{effort}"\nweb_search = "disabled"\n'
    files = {"profile.json": json.dumps({"name": name, "description": "Private partial import of current global instructions"}).encode(),
             "AGENTS.md": instructions, "config.toml": config.encode()}
    return save_private(root, name, files, {
        "operation": "partial-import-current", "instructions_source": str(source),
        "instructions_sha256": hashlib.sha256(instructions).hexdigest(),
        "normalizations": {key: {"source": native.get(key), "effective": value}
                           for key, value in normalized.items() if native.get(key) != value},
        "omitted_setting_names": sorted(set(native) - set(normalized)),
        "not_imported": ["credentials", "skills (explicit selection required)", "MCP", "plugins", "project trust", "other native settings"],
        "claim": "Partial import only; not a reproduction of the complete personal harness",
    })


def clone_profile(root, source, name, skills=()):
    source = resolve_profile(root, source)
    metadata, _ = validate_profile(source)
    files = files_in(source)
    metadata["name"] = name
    files["profile.json"] = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
    sources = []
    for skill in skills:
        skill = Path(skill)
        contents = files_in(skill)
        if "SKILL.md" not in contents:
            raise ValueError(f"Missing SKILL.md: {skill}")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", skill.name):
            raise ValueError("Skill directory names must be portable")
        if any(key.startswith(f"skills/{skill.name}/") for key in files):
            raise ValueError(f"Skill already present: {skill.name}")
        for key, value in contents.items():
            files[f"skills/{skill.name}/{key}"] = value
        sources.append({"source": str(skill.resolve()), "sha256": digest(contents)[0]})
    return save_private(root, name, files, {"operation": "clone", "source": str(source),
                                          "source_sha256": digest(files_in(source))[0], "skills_added": sources})


def restore_profile(root, experiment, profile, name):
    experiment = Path(experiment).resolve()
    plan = read_json(experiment / "plan.json")
    if profile not in plan["profiles"] or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", profile):
        raise ValueError("Profile is not in the frozen experiment")
    source = experiment / "inputs/profiles" / profile
    verify_frozen(source, plan["profiles"][profile])
    metadata, _ = validate_profile(source)
    files = files_in(source)
    # Restoring creates a new selectable copy; instructions/config/skills stay byte-identical.
    metadata["name"] = name
    files["profile.json"] = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
    return save_private(root, name, files, {"operation": "restore-copy", "experiment": str(experiment),
                                          "source_profile": profile, "source_snapshot": plan["profiles"][profile],
                                          "changed_files": ["profile.json (new selectable name)"]})
