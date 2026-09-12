"""Observable evidence only: accepted behavior, session continuity, and skill read output."""
from datetime import datetime
import json
from pathlib import Path

from chb.profiles import read_json
from chb.usage import reconcile_usage
from chb.experiments import task_for_trial


def phase_seconds(raw, name):
    timing = raw.get(name) or {}
    if not timing.get("started_at") or not timing.get("finished_at"):
        return None
    return round((datetime.fromisoformat(timing["finished_at"]) - datetime.fromisoformat(timing["started_at"])).total_seconds(), 3)


def events_from(path):
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def summarize_step(raw, agent_dir, profile, profile_dir=None):
    events = events_from(agent_dir / "codex.txt")
    terminals = [event for event in events if event.get("type") in {"turn.completed", "turn.failed"}]
    terminal = terminals[-1] if terminals else {}
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
    elif terminal.get("type") == "turn.failed":
        status = "execution_error"
        error = terminal.get("error")
    elif rewards is None or "reward" not in rewards:
        status = "verifier_error"
    elif not terminals:
        status = "execution_error"
        error = {"reason": "Missing Codex terminal event; verifier reward alone is insufficient"}
    accepted = bool(rewards["reward"] == 1) if status == "completed" else None
    usage = terminal.get("usage") or {}
    messages = [event["item"].get("text", "") for event in events
                if event.get("type") == "item.completed" and (event.get("item") or {}).get("type") == "agent_message"]
    evidence_path = agent_dir / "effective-profile.json"
    evidence = read_json(evidence_path) if evidence_path.is_file() else None
    reads = []
    if profile_dir is not None:
        for skill in sorted((Path(profile_dir) / "skills").glob("*/SKILL.md")):
            expected = skill.read_text(encoding="utf-8").strip()
            matches = []
            for event in events:
                item = event.get("item") or {}
                if (event.get("type") == "item.completed" and item.get("type") == "command_execution"
                        and item.get("exit_code") == 0 and f"{skill.parent.name}/SKILL.md" in item.get("command", "")
                        and expected in item.get("aggregated_output", "").replace("\r\n", "\n")):
                    matches.append(item.get("id"))
            reads.append({"skill": skill.parent.name, "complete_read_output_observed": bool(matches), "event_ids": matches})
    threads = [event.get("thread_id") for event in events if event.get("type") == "thread.started"]
    return {"status": status, "accepted": accepted, "reward": (rewards or {}).get("reward"),
            "agent_seconds": phase_seconds(raw, "agent_execution"), "evaluation_seconds": phase_seconds(raw, "verifier"),
            "profile_marker_observed": any(f"CHB_PROFILE={profile}" in message for message in messages),
            "effective_profile_evidence": evidence is not None, "profile_load_index": (evidence or {}).get("load_index"),
            "loaded_skills": sorted((evidence or {}).get("skills", {})), "skill_reads": reads,
            "skill_read_definition": "A read requires successful output containing the complete SKILL.md; reading does not prove internal compliance",
            "session_id": threads[-1] if threads else None, "reported_usage": usage,
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
            "cached_input_tokens": usage.get("cached_input_tokens"), "error": error}


def complete_sum(steps, field):
    values = [step.get(field) for step in steps]
    return round(sum(values), 3) if values and all(value is not None for value in values) else None


def summarize_trial(directory, profile):
    directory = Path(directory)
    paths = [p for p in directory.glob("harbor/*/*/result.json") if "trial_name" in read_json(p)]
    if len(paths) != 1:
        return {"status": "infrastructure_error", "accepted": None, "reason": "Missing unique Harbor trial result", "cost_usd": None}
    raw = read_json(paths[0])
    trial_dir = paths[0].parent
    plan_file = directory.parent / "plan.json"
    plan = read_json(plan_file) if plan_file.is_file() else {}
    profile_dir = directory.parent / "inputs/profiles" / profile
    planned_trial = next((trial for trial in plan.get("trials", []) if trial["id"] == directory.name), {})
    task_name, task = task_for_trial(plan, planned_trial)
    configured_steps = task["step_names"]
    raw_steps = raw.get("step_results") or []
    if raw_steps or configured_steps:
        steps, agent_dirs = [], []
        for step in raw_steps:
            name = step["step_name"]
            result = summarize_step(step, trial_dir / "steps" / name / "agent", profile, profile_dir)
            result["name"] = name
            result["evidence_path"] = (trial_dir / "steps" / name).relative_to(directory).as_posix()
            steps.append(result)
            agent_dirs.append(trial_dir / "steps" / name / "agent")
        expected = configured_steps or [step["name"] for step in steps]
        complete = [step["name"] for step in steps] == expected and bool(steps)
        status = next((step["status"] for step in steps if step["status"] != "completed"), "completed")
        if not complete or raw.get("exception_info"):
            status = "execution_error"
        ids = [step["session_id"] for step in steps]
        continuity = complete and all(ids) and len(set(ids)) == 1
        if status == "completed" and not continuity:
            status = "protocol_error"
        accounting = reconcile_usage(steps, agent_dirs, len(expected))
        for index, step in enumerate(steps):
            # Original CLI values remain in reported_usage; public per-step values
            # now mean increments, and never silently fall back to cumulative.
            delta = accounting["turn_deltas"][index] if accounting["status"] == "verified_cumulative" else {}
            for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
                step[key] = delta.get(key)
            step["usage_kind"] = "verified_increment" if delta else "unavailable"
        result = {"status": status, "accepted": all(step["accepted"] is True for step in steps) if status == "completed" else None,
                  "steps": steps, "expected_steps": expected, "completed_steps": len(steps),
                  "session_continuity_observed": continuity,
                  "agent_seconds": complete_sum(steps, "agent_seconds"),
                  "evaluation_seconds": complete_sum(steps, "evaluation_seconds"),
                  "effective_profile_evidence": complete and all(step["effective_profile_evidence"] for step in steps),
                  "profile_marker_observed": complete and all(step["profile_marker_observed"] for step in steps),
                  "error": raw.get("exception_info"),
                  **accounting["totals"], "usage_accounting": accounting,
                  "usage_note": "Raw cumulative values remain in reported_usage; verified per-turn values are adjacent differences",
                  "verifier_environment_mode": "separate" if plan.get("verifier", "").startswith("separate") else None,
                  "verifier_mode_evidence": "frozen task protocol; per-step verifier logs in evidence_path"}
    else:
        result = summarize_step(raw, trial_dir / "agent", profile, profile_dir)
        result["verifier_environment_mode"] = raw.get("verifier_environment_mode")
    result.update({"task": task_name, "task_group": task["group"],
                   "environment_seconds": phase_seconds(raw, "environment_setup"),
                   "agent_setup_seconds": phase_seconds(raw, "agent_setup"),
                   "cost_usd": None, "cost_kind": "unavailable; subscription usage is not an API bill",
                   "harbor_result": paths[0].relative_to(directory).as_posix()})
    return result
