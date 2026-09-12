"""Frozen task routing and descriptive comparisons, including legacy single-task plans."""
from collections import Counter
import re
import tomllib

from chb.profiles import verify_frozen


def planned_tasks(plan):
    if plan.get("schema", 1) >= 3:
        tasks = plan["tasks"]
        if not tasks or any(not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name) for name in tasks):
            raise ValueError("Invalid task names in plan")
        return tasks
    name = plan.get("task_name", "search-notes-v1")
    return {name: {"group": plan.get("task_group", name), "snapshot": plan.get("task"),
                   "step_names": plan.get("step_names", []),
                   "image_id": plan.get("image_id"), "verifier_image_id": plan.get("verifier_image_id")}}


def task_for_trial(plan, trial):
    tasks = planned_tasks(plan)
    name = trial["task"] if plan.get("schema", 1) >= 3 else next(iter(tasks))
    if name not in tasks:
        raise ValueError("Trial refers to an unknown frozen task")
    return name, tasks[name]


def task_path(experiment, plan, name):
    return experiment / "inputs" / "tasks" / name if plan.get("schema", 1) >= 3 else experiment / "inputs/task"


def arrange_trials(tasks, profiles, repeats):
    trials = []
    for repeat in range(repeats):
        for index, (task, spec) in enumerate(tasks.items()):
            order = profiles if (index + repeat) % 2 == 0 else list(reversed(profiles))
            for profile in order:
                trials.append({"id": f"trial-{len(trials) + 1:03d}", "task": task,
                               "profile": profile, "repeat": repeat,
                               "max_agent_seconds": 300 * max(1, len(spec["step_names"]))})
    return trials


def verify_task_inputs(experiment, plan):
    tasks = planned_tasks(plan)
    for name, spec in tasks.items():
        path = task_path(experiment, plan, name)
        verify_frozen(path, spec["snapshot"])
        if plan.get("schema", 1) >= 3:
            task = tomllib.loads((path / "task.toml").read_text(encoding="utf-8"))
            if (task["metadata"]["name"] != name or task["metadata"]["group"] != spec["group"]
                    or [step["name"] for step in task.get("steps", [])] != spec["step_names"]
                    or task["environment"]["docker_image"] != spec["image_id"]
                    or task["verifier"]["environment"]["docker_image"] != spec["verifier_image_id"]):
                raise ValueError("Task routing metadata differs from frozen definition")
    if plan.get("schema", 1) >= 3:
        expected = arrange_trials(tasks, list(plan["profiles"]), plan["repeat"])
        if expected != plan["trials"]:
            raise ValueError("Trial coverage or order differs from frozen protocol")
        turns = sum(trial["max_agent_seconds"] // 300 for trial in expected)
        if plan["planned_agent_turns"] != turns or plan["max_total_agent_seconds"] != turns * 300:
            raise ValueError("Plan budget differs from task coverage")


def complete_total(results, field):
    values = [result.get(field) for result in results]
    return round(sum(values), 3) if values and all(value is not None for value in values) else None


def group_comparisons(plan, results):
    """Only pair the same task/repeat with both profiles accepted. Missing is never zero."""
    grouped = {}
    profiles = list(plan.get("profiles", {})) or list(dict.fromkeys(t["profile"] for t in plan["trials"]))
    for trial in plan["trials"]:
        name, task = task_for_trial(plan, trial)
        group = grouped.setdefault(task["group"], {"tasks": set(), "pairs": {}, "trials": []})
        group["tasks"].add(name)
        key = (name, trial.get("repeat", 0))
        pair = group["pairs"].setdefault(key, {})
        if trial["profile"] in pair:
            raise ValueError("Duplicate task/profile/repeat in plan")
        result = results.get(trial["id"], {"status": "not_run"})
        pair[trial["profile"]] = result
        group["trials"].append((trial["profile"], result))
    summary = []
    for name, group in grouped.items():
        paired = [pair for pair in group["pairs"].values() if len(profiles) == 2 and
                  all(pair.get(p, {}).get("status") == "completed" and pair[p].get("accepted") is True for p in profiles)]
        rows = {}
        for profile in profiles:
            own = [result for p, result in group["trials"] if p == profile]
            counts = Counter("pending" if r.get("status") in {None, "not_run", "running"} else
                             "accepted" if r.get("status") == "completed" and r.get("accepted") is True else
                             "failed" if r.get("status") == "completed" and r.get("accepted") is False else "error" for r in own)
            rows[profile] = {"planned": len(own), **{k: counts[k] for k in ("accepted", "failed", "error", "pending")},
                             "paired_agent_seconds": complete_total([pair[profile] for pair in paired], "agent_seconds")}
        summary.append({"group": name, "tasks": sorted(group["tasks"]), "planned_pairs": len(group["pairs"]),
                        "accepted_pairs": len(paired), "profiles": rows})
    return summary
