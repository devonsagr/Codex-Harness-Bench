import argparse
import asyncio
from datetime import datetime, timezone
import difflib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import uuid

from chb.profiles import digest, files_in, freeze, read_json, validate_profile, verify_frozen, write_json
from chb.report import render
from chb.configuration import clone_profile, import_current, resolve_profile, restore_profile
from chb.results import summarize_trial
from chb.analysis import analyze_experiment
from chb.experiments import arrange_trials, planned_tasks, task_for_trial, task_path, verify_task_inputs

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "chb-smoke:codex-0.154.0"
VERIFIER_IMAGE = "chb-verifier:search-notes-v1"
CODEX_VERSION = "0.154.0"


def task_settings(name, root=None):
    if name not in {"search-notes-v1", "storage-migration-v1", "csv-catalog-v1"}:
        raise ValueError("Unknown task")
    image = IMAGE if name == "search-notes-v1" else f"chb-{name}:codex-{CODEX_VERSION}"
    return (root or ROOT) / "tasks" / name, image, f"chb-verifier:{name}"


def command(args, **kwargs):
    return subprocess.run(args, check=True, text=True, encoding="utf-8", errors="replace", **kwargs)


def image_id(image=IMAGE):
    return command(["docker", "image", "inspect", image, "--format", "{{.Id}}"], capture_output=True, timeout=20).stdout.strip()


def pin_image(image):
    try:
        pinned = image_id(image)
    except subprocess.CalledProcessError:
        # Docker Desktop can list a tag whose name lookup is stale while its
        # content ID remains usable. Recover only that exact, unique mapping.
        listing = command(["docker", "image", "ls", "--no-trunc", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"],
                          capture_output=True, timeout=20).stdout.splitlines()
        candidates = {line.split()[1] for line in listing if len(line.split()) == 2 and line.split()[0] == image}
        if len(candidates) != 1:
            raise ValueError(f"Image is missing or ambiguous: {image}; prepare the task images")
        candidate = candidates.pop()
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", candidate) or image_id(candidate) != candidate:
            raise ValueError("Listed image content could not be verified")
        pinned = candidate
        command(["docker", "image", "tag", pinned, image], capture_output=True, timeout=20)
    # Docker Desktop's containerd store can discard an untagged manifest when a
    # convenience tag is rebuilt. Retain a content-derived tag for frozen runs.
    command(["docker", "image", "tag", pinned, "chb-frozen:" + pinned.removeprefix("sha256:")],
            capture_output=True, timeout=20)
    return pinned


def profile_diff(left, right):
    a, b = files_in(left), files_in(right)
    parts = []
    for name in sorted(a.keys() | b.keys()):
        if a.get(name) != b.get(name):
            parts.extend(difflib.unified_diff(
                a.get(name, b"").decode("utf-8", errors="replace").splitlines(True),
                b.get(name, b"").decode("utf-8", errors="replace").splitlines(True),
                fromfile=f"{Path(left).name}/{name}", tofile=f"{Path(right).name}/{name}"))
    return "".join(parts)


def doctor():
    checks = {"python": sys.version.split()[0], "harbor": version("harbor"), "codex_pinned": CODEX_VERSION}
    for name, args in {
        "docker": ["docker", "info", "--format", "{{.ServerVersion}}"],
        "host_codex": ["codex", "--version"],
    }.items():
        try:
            checks[name] = command(args, capture_output=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            checks[name] = f"unavailable: {type(exc).__name__}"
    checks["chatgpt_auth_file_present"] = (Path.home() / ".codex" / "auth.json").is_file()
    try:
        checks["image"] = image_id()
    except (OSError, subprocess.SubprocessError):
        checks["image"] = "not built; run chb prepare"
    print(json.dumps(checks, indent=2, ensure_ascii=False))


def make_plan(args, *, root=None, emit=True):
    root = root or ROOT
    paths = [resolve_profile(root, name.strip()) for name in args.profiles.split(",")]
    if len(paths) != 2 or paths[0] == paths[1]:
        raise ValueError("This MVP compares exactly two different profiles")
    profiles = [validate_profile(path) for path in paths]
    if profiles[0][0]["name"] == profiles[1][0]["name"]:
        raise ValueError("Profiles must have distinct metadata names")
    if profiles[0][1] != profiles[1][1]:
        raise ValueError("Native config differs: this protocol fixes reasoning and web search")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", args.model):
        raise ValueError("Invalid model identifier")
    selected = [name.strip() for name in (getattr(args, "tasks", None) or args.task or "search-notes-v1").split(",")]
    if len(set(selected)) != len(selected):
        raise ValueError("Duplicate tasks are not independent samples")
    sources = {name: task_settings(name, root) for name in selected}
    images = {name: (pin_image(agent), pin_image(verifier)) for name, (_, agent, verifier) in sources.items()}
    exp_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    directory = root / "runs" / exp_id
    directory.mkdir(parents=True)
    snapshots = {}
    for path, (metadata, _) in zip(paths, profiles):
        name = metadata["name"]
        snapshots[name] = freeze(path, directory / "inputs" / "profiles" / name)
    import toml
    tasks = {}
    for name, (source, _, _) in sources.items():
        task_input = directory / "inputs/tasks" / name
        freeze(source, task_input)
        task = tomllib.loads((task_input / "task.toml").read_text(encoding="utf-8"))
        image, verifier_image = images[name]
        task["environment"]["docker_image"] = image
        task["verifier"]["environment"]["docker_image"] = verifier_image
        (task_input / "task.toml").write_text(toml.dumps(task), encoding="utf-8")
        task_hash, task_manifest = digest(files_in(task_input))
        tasks[name] = {"group": task["metadata"]["group"], "step_names": [step["name"] for step in task.get("steps", [])],
                       "image_id": image, "verifier_image_id": verifier_image,
                       "snapshot": {"sha256": task_hash, "files": task_manifest}}
    names = [entry[0]["name"] for entry in profiles]
    trials = arrange_trials(tasks, names, args.repeat)
    turns = sum(trial["max_agent_seconds"] // 300 for trial in trials)
    plan = {
        "schema": 3, "id": exp_id, "kind": "local-pipeline-smoke", "model": args.model,
        "tasks": tasks,
        "codex_version": CODEX_VERSION, "harbor_version": version("harbor"),
        "repeat": args.repeat, "declared_task_groups": len({task["group"] for task in tasks.values()}),
        "profiles": snapshots,
        "runner_sha256": digest(files_in(root / "src" / "chb"))[0],
        "native_config": profiles[0][1], "trials": trials,
        "max_agent_seconds_per_turn": 300,
        "max_agent_seconds_per_trial": max(trial["max_agent_seconds"] for trial in trials),
        "max_total_agent_seconds": 300 * turns,
        "planned_agent_turns": turns,
        "order": "task order as selected; profile order reverses on adjacent tasks and repeats",
        "auth": "runtime-only: ChatGPT auth.json or OPENAI_API_KEY; no credentials in snapshots",
        "network": "agent allowlist chatgpt.com and *.openai.com; verifier no network",
        "verifier": "separate fresh container; no intermediate feedback",
        "source_publication": "project original fixture; distribution follows repository visibility",
        "statistical_claim": "none: descriptive small original suite; group independence is not established",
        "retry": "none; a new plan preserves previous attempts",
    }
    write_json(directory / "plan.json", plan)
    (directory / "profile-diff.txt").write_text(profile_diff(*paths), encoding="utf-8")
    render(directory)
    if emit:
        print(json.dumps({"experiment": str(directory), "trials": len(trials), "agent_turns": plan["planned_agent_turns"], "model": args.model,
                          "max_total_agent_seconds": plan["max_total_agent_seconds"], "model_calls_started": 0}, ensure_ascii=False, indent=2))
    return directory


async def execute_plan(directory):
    from harbor.job import Job
    from harbor.models.job.config import JobConfig
    directory = Path(directory).resolve()
    plan = read_json(directory / "plan.json")
    if version("harbor") != plan["harbor_version"]:
        raise ValueError("Harbor version changed; create a new plan")
    if digest(files_in(ROOT / "src" / "chb"))[0] != plan["runner_sha256"]:
        raise ValueError("Runner changed; create a new plan")
    verify_task_inputs(directory, plan)
    for name, snapshot in plan["profiles"].items():
        verify_frozen(directory / "inputs" / "profiles" / name, snapshot)
    # Resolve the pinned image itself, not the mutable convenience tag.
    for task in planned_tasks(plan).values():
        command(["docker", "image", "inspect", task["image_id"]], capture_output=True, timeout=20)
        command(["docker", "image", "inspect", task["verifier_image_id"]], capture_output=True, timeout=20)
    auth_path = Path.home() / ".codex" / "auth.json"
    if not auth_path.is_file() and not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("Authenticate Codex first or set OPENAI_API_KEY")
    if any((directory / trial["id"]).exists() for trial in plan["trials"]):
        raise ValueError("Attempt already exists. Make a new plan; history is not overwritten.")
    for trial in plan["trials"]:
        task_name, task = task_for_trial(plan, trial)
        output = directory / trial["id"]
        if output.exists():
            raise ValueError(f"Attempt already exists: {output}. Make a new plan; history is not overwritten.")
        output.mkdir()
        write_json(output / "result.json", {"status": "running", "accepted": None})
        print(f"Running {trial['id']} / {task_name} / {trial['profile']} (300s per user turn)", flush=True)
        agent = {
            "import_path": "chb.adapter:ProfileCodex", "model_name": plan["model"],
            "kwargs": {"version": plan["codex_version"], "profile_path": str(directory / "inputs" / "profiles" / trial["profile"])},
            "env": {"CODEX_AUTH_JSON_PATH": str(auth_path)} if auth_path.is_file() else {},
            "override_timeout_sec": 300, "override_setup_timeout_sec": 120,
            "resume_trajectory": bool(task["step_names"]),
        }
        config = JobConfig.model_validate({
            "job_name": "job", "jobs_dir": str(output / "harbor"),
            "n_concurrent_trials": 1, "n_attempts": 1,
            "retry": {"max_retries": 0}, "quiet": True,
            "agents": [agent], "tasks": [{"path": str(task_path(directory, plan, task_name))}],
            "environment": {"type": "docker", "delete": True},
        })
        try:
            job = await Job.create(config)
            await job.run()
            result = summarize_trial(output, trial["profile"])
        except Exception as exc:
            result = {"status": "infrastructure_error", "accepted": None, "reason": f"{type(exc).__name__}: {exc}", "cost_usd": None}
        write_json(output / "result.json", result)
        render(directory)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if result["status"] != "completed":
            print("Stopped before the next trial. Original attempt retained; correct the cause and create a new plan.")
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Local Codex profile comparisons; Harbor handles isolation and evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    ui = sub.add_parser("ui", help="Open the local configuration and experiment workbench; no model calls")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--no-browser", action="store_true")
    prepare = sub.add_parser("prepare", help="Build task and separate verifier images; no model call")
    prepare.add_argument("--task", default="search-notes-v1")
    sub.add_parser("profiles")
    diff = sub.add_parser("diff")
    diff.add_argument("left")
    diff.add_argument("right")
    plan = sub.add_parser("plan", help="Freeze inputs and show run count; no model call")
    plan.add_argument("--profiles", default="minimal,focused")
    selection = plan.add_mutually_exclusive_group()
    selection.add_argument("--task", help="One task; defaults to search-notes-v1")
    selection.add_argument("--tasks", help="Comma-separated tasks in the desired frozen order")
    plan.add_argument("--model", required=True)
    plan.add_argument("--repeat", type=int, choices=range(1, 6), default=1)
    run = sub.add_parser("run", help="Execute one previously frozen plan using real Codex calls")
    run.add_argument("experiment", type=Path)
    report = sub.add_parser("report")
    report.add_argument("experiment", type=Path)
    analyze = sub.add_parser("analyze", help="Reanalyze finished local logs into a new report; no model calls or history writes")
    analyze.add_argument("experiment", type=Path)
    config = sub.add_parser("config", help="Create private profiles without changing your Codex settings")
    operations = config.add_subparsers(dest="operation", required=True)
    current = operations.add_parser("import-current")
    current.add_argument("name")
    current.add_argument("--reasoning", choices=["low", "medium", "high", "xhigh"])
    clone = operations.add_parser("clone")
    clone.add_argument("source")
    clone.add_argument("name")
    clone.add_argument("--skill", action="append", type=Path, default=[])
    restore = operations.add_parser("restore")
    restore.add_argument("experiment", type=Path)
    restore.add_argument("profile")
    restore.add_argument("name")
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            doctor()
        elif args.command == "ui":
            from chb.webapp import serve
            serve(ROOT, args.port, open_browser=not args.no_browser)
        elif args.command == "prepare":
            task, agent_image, verifier_image = task_settings(args.task)
            command(["docker", "build", "-t", agent_image, str(task / "environment")])
            command(["docker", "build", "-t", verifier_image, str(task / "tests")])
        elif args.command == "profiles":
            for path in sorted(list((ROOT / "profiles").glob("*")) + list((ROOT / ".local/profiles").glob("*"))):
                print(json.dumps(validate_profile(path)[0], ensure_ascii=False))
        elif args.command == "diff":
            print(profile_diff(resolve_profile(ROOT, args.left), resolve_profile(ROOT, args.right)))
        elif args.command == "plan":
            make_plan(args)
        elif args.command == "run":
            if not asyncio.run(execute_plan(args.experiment)):
                return 1
        elif args.command == "report":
            print(render(args.experiment))
        elif args.command == "analyze":
            print(analyze_experiment(ROOT, args.experiment))
        elif args.command == "config":
            if args.operation == "import-current":
                result = import_current(ROOT, args.name, reasoning=args.reasoning)
            elif args.operation == "clone":
                result = clone_profile(ROOT, args.source, args.name, args.skill)
            else:
                result = restore_profile(ROOT, args.experiment, args.profile, args.name)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
