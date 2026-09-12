"""No model calls: baseline must fail and the oracle must pass in Harbor."""
import json
import argparse
from pathlib import Path
import subprocess
import sys
import tomllib
import uuid

import toml

from chb.cli import ROOT, task_settings, pin_image
from chb.profiles import freeze, read_json, write_json


parser = argparse.ArgumentParser()
parser.add_argument("--task", default="search-notes-v1")
args = parser.parse_args()
source, image_tag, verifier_tag = task_settings(args.task)
directory = ROOT / ".local" / "validation" / uuid.uuid4().hex[:12]
task = directory / "task"
freeze(source, task)
image = pin_image(image_tag)
config = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
config["environment"]["docker_image"] = image
config["verifier"]["environment"]["docker_image"] = pin_image(verifier_tag)
(task / "task.toml").write_text(toml.dumps(config), encoding="utf-8")
results = []
for agent, expected in [("nop", 0), ("oracle", 1)]:
    result = subprocess.run([
        sys.executable, "-X", "utf8", "-c", "from harbor.cli.main import app; app()",
        "run", "--path", str(task), "--agent", agent, "--n-concurrent", "1",
        "--job-name", agent, "--jobs-dir", str(directory / "jobs"), "--quiet",
    ], check=False)
    files = list((directory / "jobs" / agent).glob("*/result.json"))
    if len(files) != 1:
        raise RuntimeError(f"Missing result for {agent}; see {directory}")
    trial = read_json(files[0])
    reward = (trial.get("verifier_result") or {}).get("rewards", {}).get("reward")
    error = trial.get("exception_info")
    steps = trial.get("step_results") or []
    step_rewards = [{"step": step["step_name"], "reward": (step.get("verifier_result") or {}).get("rewards", {}).get("reward"),
                     "error": step.get("exception_info")} for step in steps]
    results.append({"agent": agent, "expected": expected, "reward": reward, "error": error,
                    "result": str(files[0]), "cli_exit_code": result.returncode, "steps": step_rewards})
    write_json(directory / "receipt.json", {"task": args.task, "image_id": image, "results": results})
    print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    if (error or reward != expected or result.returncode != 0
            or len(steps) != len(config.get("steps", []))
            or any(step["error"] or step["reward"] != expected for step in step_rewards)):
        raise RuntimeError(f"Task validation failed for {agent}; see {directory}")
print(f"PASS: baseline rejected, oracle accepted. Receipt: {directory / 'receipt.json'}")
