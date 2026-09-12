import argparse
import asyncio
from datetime import datetime, timezone
import difflib
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import uuid

from chb.profiles import digest, files_in, freeze, read_json, validate_profile, verify_frozen, write_json
from chb.report import render

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "chb-smoke:codex-0.154.0"
VERIFIER_IMAGE = "chb-verifier:search-notes-v1"
CODEX_VERSION = "0.154.0"


def command(args, **kwargs):
    return subprocess.run(args, check=True, text=True, encoding="utf-8", errors="replace", **kwargs)


def image_id(image=IMAGE):
    return command(["docker", "image", "inspect", image, "--format", "{{.Id}}"], capture_output=True, timeout=20).stdout.strip()


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


def make_plan(args):
    paths = [ROOT / "profiles" / name for name in args.profiles.split(",")]
    if len(paths) != 2 or paths[0] == paths[1]:
        raise ValueError("This MVP compares exactly two different profiles")
    profiles = [validate_profile(path) for path in paths]
    if profiles[0][1] != profiles[1][1]:
        raise ValueError("Native config differs: this protocol fixes reasoning and web search")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", args.model):
        raise ValueError("Invalid model identifier")
    image = image_id()
    verifier_image = image_id(VERIFIER_IMAGE)
    exp_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    directory = ROOT / "runs" / exp_id
    directory.mkdir(parents=True)
    snapshots = {}
    for path, (metadata, _) in zip(paths, profiles):
        name = metadata["name"]
        snapshots[name] = freeze(path, directory / "inputs" / "profiles" / name)
    task_input = directory / "inputs" / "task"
    freeze(ROOT / "tasks" / "search-notes-v1", task_input)
    import toml
    task = tomllib.loads((task_input / "task.toml").read_text(encoding="utf-8"))
    task["environment"]["docker_image"] = image
    task["verifier"]["environment"]["docker_image"] = verifier_image
    (task_input / "task.toml").write_text(toml.dumps(task), encoding="utf-8")
    task_hash, task_manifest = digest(files_in(task_input))
    names = [entry[0]["name"] for entry in profiles]
    trials = []
    for repeat in range(args.repeat):
        order = names if repeat % 2 == 0 else list(reversed(names))
        for name in order:
            trials.append({"id": f"trial-{len(trials)+1:03d}", "profile": name, "repeat": repeat})
    plan = {
        "schema": 1, "id": exp_id, "kind": "local-pipeline-smoke", "model": args.model,
        "codex_version": CODEX_VERSION, "harbor_version": version("harbor"),
        "image_id": image, "verifier_image_id": verifier_image, "repeat": args.repeat, "independent_task_groups": 1,
        "profiles": snapshots, "task": {"sha256": task_hash, "files": task_manifest},
        "runner_sha256": digest(files_in(ROOT / "src" / "chb"))[0],
        "native_config": profiles[0][1], "trials": trials,
        "max_agent_seconds_per_trial": 300, "max_total_agent_seconds": 300 * len(trials),
        "auth": "runtime-only: ChatGPT auth.json or OPENAI_API_KEY; no credentials in snapshots",
        "network": "agent allowlist chatgpt.com and *.openai.com; verifier no network",
        "verifier": "separate fresh container; no intermediate feedback",
        "source_publication": "local original fixture, pending GitHub publication",
        "statistical_claim": "none: one independent task group is insufficient",
        "retry": "none; a new plan preserves previous attempts",
    }
    write_json(directory / "plan.json", plan)
    (directory / "profile-diff.txt").write_text(profile_diff(*paths), encoding="utf-8")
    render(directory)
    print(json.dumps({"experiment": str(directory), "trials": len(trials), "model": args.model,
                      "max_total_agent_seconds": plan["max_total_agent_seconds"], "model_calls_started": 0}, ensure_ascii=False, indent=2))


def phase_seconds(raw, name):
    timing = raw.get(name) or {}
    if not timing.get("started_at") or not timing.get("finished_at"):
        return None
    return round((datetime.fromisoformat(timing["finished_at"]) - datetime.fromisoformat(timing["started_at"])).total_seconds(), 3)


def summarize_trial(directory, profile):
    paths = [p for p in directory.glob("harbor/*/*/result.json") if "trial_name" in read_json(p)]
    if len(paths) != 1:
        return {"status": "infrastructure_error", "accepted": None, "reason": "Missing unique Harbor trial result", "cost_usd": None}
    raw = read_json(paths[0])
    trial_dir = paths[0].parent
    error = raw.get("exception_info")
    rewards = (raw.get("verifier_result") or {}).get("rewards")
    status = "completed"
    if error:
        kind = error["exception_type"]
        status = "timeout" if "Timeout" in kind else "execution_error"
        if not raw.get("agent_execution"):
            status = "infrastructure_error"
        elif "Verif" in kind or "Reward" in kind:
            status = "verifier_error"
    accepted = bool(rewards and rewards.get("reward") == 1) if rewards is not None and not error else None
    if accepted is None and status == "completed":
        status = "verifier_error"
    events = trial_dir / "agent" / "codex.txt"
    usage, final_messages = {}, []
    if events.is_file():
        for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "turn.completed":
                usage = event.get("usage") or {}
            item = event.get("item") or {}
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                final_messages.append(item.get("text", ""))
    marker = any(f"CHB_PROFILE={profile}" in message for message in final_messages)
    return {
        "status": status, "accepted": accepted,
        "profile_marker_observed": marker,
        "effective_profile_evidence": (trial_dir / "agent" / "effective-profile.json").is_file(),
        "agent_seconds": phase_seconds(raw, "agent_execution"),
        "environment_seconds": phase_seconds(raw, "environment_setup"),
        "agent_setup_seconds": phase_seconds(raw, "agent_setup"),
        "evaluation_seconds": phase_seconds(raw, "verifier"),
        "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
        "cached_input_tokens": usage.get("cached_input_tokens"),
        "cost_usd": None, "cost_kind": "unavailable; subscription usage is not an API bill",
        "error": error, "harbor_result": str(paths[0].relative_to(directory)),
        "verifier_environment_mode": raw.get("verifier_environment_mode"),
    }


async def execute_plan(directory):
    from harbor.job import Job
    from harbor.models.job.config import JobConfig
    directory = Path(directory).resolve()
    plan = read_json(directory / "plan.json")
    if version("harbor") != plan["harbor_version"]:
        raise ValueError("Harbor version changed; create a new plan")
    if digest(files_in(ROOT / "src" / "chb"))[0] != plan["runner_sha256"]:
        raise ValueError("Runner changed; create a new plan")
    verify_frozen(directory / "inputs" / "task", plan["task"])
    for name, snapshot in plan["profiles"].items():
        verify_frozen(directory / "inputs" / "profiles" / name, snapshot)
    # Resolve the pinned image itself, not the mutable convenience tag.
    command(["docker", "image", "inspect", plan["image_id"]], capture_output=True, timeout=20)
    command(["docker", "image", "inspect", plan["verifier_image_id"]], capture_output=True, timeout=20)
    auth_path = Path.home() / ".codex" / "auth.json"
    if not auth_path.is_file() and not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("Authenticate Codex first or set OPENAI_API_KEY")
    for trial in plan["trials"]:
        output = directory / trial["id"]
        if output.exists():
            raise ValueError(f"Attempt already exists: {output}. Make a new plan; history is not overwritten.")
        output.mkdir()
        write_json(output / "result.json", {"status": "running", "accepted": None})
        print(f"Running {trial['id']} / {trial['profile']} (300s agent limit)", flush=True)
        agent = {
            "import_path": "chb.adapter:ProfileCodex", "model_name": plan["model"],
            "kwargs": {"version": plan["codex_version"], "profile_path": str(directory / "inputs" / "profiles" / trial["profile"])},
            "env": {"CODEX_AUTH_JSON_PATH": str(auth_path)} if auth_path.is_file() else {},
            "override_timeout_sec": 300, "override_setup_timeout_sec": 120,
        }
        config = JobConfig.model_validate({
            "job_name": "job", "jobs_dir": str(output / "harbor"),
            "n_concurrent_trials": 1, "n_attempts": 1,
            "retry": {"max_retries": 0}, "quiet": True,
            "agents": [agent], "tasks": [{"path": str(directory / "inputs" / "task")}],
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
    sub.add_parser("prepare", help="Build the fixed Codex smoke image; no model call")
    sub.add_parser("profiles")
    diff = sub.add_parser("diff")
    diff.add_argument("left")
    diff.add_argument("right")
    plan = sub.add_parser("plan", help="Freeze inputs and show run count; no model call")
    plan.add_argument("--profiles", default="minimal,focused")
    plan.add_argument("--model", required=True)
    plan.add_argument("--repeat", type=int, choices=range(1, 6), default=1)
    run = sub.add_parser("run", help="Execute one previously frozen plan using real Codex calls")
    run.add_argument("experiment", type=Path)
    report = sub.add_parser("report")
    report.add_argument("experiment", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            doctor()
        elif args.command == "prepare":
            command(["docker", "build", "-t", IMAGE, str(ROOT / "tasks/search-notes-v1/environment")])
            command(["docker", "build", "-t", VERIFIER_IMAGE, str(ROOT / "tasks/search-notes-v1/tests")])
        elif args.command == "profiles":
            for path in sorted((ROOT / "profiles").iterdir()):
                print(json.dumps(validate_profile(path)[0], ensure_ascii=False))
        elif args.command == "diff":
            print(profile_diff(ROOT / "profiles" / args.left, ROOT / "profiles" / args.right))
        elif args.command == "plan":
            make_plan(args)
        elif args.command == "run":
            if not asyncio.run(execute_plan(args.experiment)):
                return 1
        elif args.command == "report":
            print(render(args.experiment))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
