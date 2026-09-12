"""No model calls: baseline must fail and the oracle must pass in Harbor."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import uuid

import toml

from chb.cli import ROOT, IMAGE, VERIFIER_IMAGE, image_id
from chb.profiles import freeze, read_json, write_json


directory = ROOT / ".local" / "validation" / uuid.uuid4().hex[:12]
task = directory / "task"
freeze(ROOT / "tasks/search-notes-v1", task)
image = subprocess.check_output(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"], text=True).strip()
config = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
config["environment"]["docker_image"] = image
config["verifier"]["environment"]["docker_image"] = image_id(VERIFIER_IMAGE)
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
    results.append({"agent": agent, "expected": expected, "reward": reward, "error": error,
                    "result": str(files[0]), "cli_exit_code": result.returncode})
    write_json(directory / "receipt.json", {"image_id": image, "results": results})
    print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    if error or reward != expected:
        raise RuntimeError(f"Task validation failed for {agent}; see {directory}")
print(f"PASS: baseline rejected, oracle accepted. Receipt: {directory / 'receipt.json'}")
