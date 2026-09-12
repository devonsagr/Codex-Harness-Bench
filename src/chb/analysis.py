"""Append-only reanalysis outside the original experiment. No model calls."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import uuid

from chb.profiles import freeze, read_json, verify_frozen, write_json
from chb.report import render
from chb.results import summarize_trial


def source_manifest(experiment):
    patterns = ["plan.json", "profile-diff.txt", "report.html", "inputs/**/*",
                "trial-*/result.json", "trial-*/harbor/*/*/result.json",
                "trial-*/harbor/*/*/agent/**/*", "trial-*/harbor/*/*/steps/*/agent/**/*"]
    paths = sorted({path for pattern in patterns for path in experiment.glob(pattern) if path.is_file()})
    manifest = {}
    for path in paths:
        if path.is_symlink() or path.is_junction():
            raise ValueError("Linked evidence is not supported")
        manifest[path.relative_to(experiment).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def analyze_experiment(root, experiment):
    root = Path(root).resolve()
    experiment = Path(experiment).resolve()
    plan = read_json(experiment / "plan.json")
    verify_frozen(experiment / "inputs/task", plan["task"])
    for name, snapshot in plan["profiles"].items():
        verify_frozen(experiment / "inputs/profiles" / name, snapshot)
    originals = {}
    for trial in plan["trials"]:
        original = read_json(experiment / trial["id"] / "result.json")
        if original.get("status") in {None, "running", "not_run"}:
            raise ValueError("Reanalysis requires finished trials")
        originals[trial["id"]] = original
    before = source_manifest(experiment)
    analysis_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    directory = root / ".local/analyses" / analysis_id
    directory.mkdir(parents=True, exist_ok=False)
    analyzer = freeze(root / "src/chb", directory / "analyzer")
    results = {}
    for trial in plan["trials"]:
        result = summarize_trial(experiment / trial["id"], trial["profile"])
        if any(result.get(key) != originals[trial["id"]].get(key) for key in ("accepted", "status")):
            raise ValueError("New parsing changes a historical verdict; investigate instead of silently replacing it")
        results[trial["id"]] = result
        write_json(directory / trial["id"] / "result.json", result)
    if before != source_manifest(experiment):
        raise ValueError("Source evidence changed during analysis; output is not verified")
    metadata = {"schema": 1, "id": analysis_id, "source_experiment": str(experiment),
                "source_experiment_id": plan["id"], "source_manifest": before,
                "analyzer": analyzer, "model_calls_started": 0,
                "historical_verdicts_preserved": True, "source_files_unchanged": True}
    write_json(directory / "analysis.json", metadata)
    render(experiment, results=results, output_dir=directory, analysis=metadata)
    return directory
