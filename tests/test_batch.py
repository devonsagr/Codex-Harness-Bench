import argparse
import asyncio
from contextlib import redirect_stdout
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from chb import cli
from chb.analysis import analyze_experiment
from chb.experiments import group_comparisons, planned_tasks, task_for_trial, task_path, verify_task_inputs
from chb.profiles import files_in, read_json, write_json


TASKS = ["search-notes-v1", "storage-migration-v1", "csv-catalog-v1"]


class BatchTests(unittest.TestCase):
    def create_plan(self, root, repeat=1):
        shutil.copytree(cli.ROOT / "profiles", root / "profiles")
        shutil.copytree(cli.ROOT / "tasks", root / "tasks")
        (root / "src/chb").mkdir(parents=True)
        (root / "src/chb/fixture.py").write_text("# runner fixture\n")
        args = argparse.Namespace(profiles="minimal,focused", model="openai/test", task=None,
                                  tasks=",".join(TASKS), repeat=repeat)
        with patch.object(cli, "ROOT", root), patch.object(cli, "pin_image", side_effect=lambda tag: "sha256:" + tag), redirect_stdout(io.StringIO()):
            cli.make_plan(args)
        experiment = next((root / "runs").iterdir())
        return experiment, read_json(experiment / "plan.json")

    def test_frozen_coverage_order_budget_and_snapshot_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            experiment, plan = self.create_plan(root, repeat=2)
            self.assertEqual(plan["schema"], 3)
            self.assertEqual(len(plan["trials"]), 12)
            self.assertEqual(plan["planned_agent_turns"], 16)
            self.assertEqual(plan["max_total_agent_seconds"], 4800)
            self.assertEqual(plan["declared_task_groups"], 3)
            self.assertEqual([t["profile"] for t in plan["trials"]],
                             ["minimal", "focused", "focused", "minimal", "minimal", "focused",
                              "focused", "minimal", "minimal", "focused", "focused", "minimal"])
            self.assertEqual([t["max_agent_seconds"] for t in plan["trials"][:6]], [300, 300, 600, 600, 300, 300])
            (root / "tasks/csv-catalog-v1/instruction.md").write_text("changed after planning")
            verify_task_inputs(experiment, plan)
            changed = read_json(experiment / "plan.json")
            changed["trials"][0]["task"] = TASKS[1]
            with self.assertRaisesRegex(ValueError, "coverage or order"):
                verify_task_inputs(experiment, changed)
            changed = read_json(experiment / "plan.json")
            changed["max_total_agent_seconds"] = 600
            with self.assertRaisesRegex(ValueError, "budget"):
                verify_task_inputs(experiment, changed)

    def test_harbor_routes_each_task_and_reanalysis_preserves_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            experiment, plan = self.create_plan(root)
            configs = []

            async def create_job(config):
                configs.append(config)
                name = config.tasks[0].path.name
                agent = config.agents[0]
                expected = planned_tasks(plan)[name]
                self.assertEqual(agent.resume_trajectory, bool(expected["step_names"]))
                self.assertEqual(Path(agent.kwargs["profile_path"]).name, plan["trials"][len(configs) - 1]["profile"])
                self.assertEqual(agent.override_timeout_sec, 300)
                self.assertEqual(config.retry.max_retries, 0)
                harbor = Path(config.jobs_dir) / "job/task"
                raw = {"trial_name": "task", "verifier_result": {"rewards": {"reward": 1}}}
                if expected["step_names"]:
                    raw["step_results"] = [{"step_name": step, "verifier_result": {"rewards": {"reward": 1}}}
                                           for step in expected["step_names"]]
                    agents = [harbor / "steps" / step / "agent" for step in expected["step_names"]]
                else:
                    agents = [harbor / "agent"]
                write_json(harbor / "result.json", raw)
                for agent_dir in agents:
                    agent_dir.mkdir(parents=True)
                    (agent_dir / "codex.txt").write_text('{"type":"thread.started","thread_id":"fixture-session"}\n{"type":"turn.completed"}\n')
                class Job:
                    async def run(self):
                        return None
                return Job()

            with patch.object(cli, "ROOT", root), patch.object(cli, "command"), patch.dict("os.environ", {"OPENAI_API_KEY": "fixture"}), \
                    patch("harbor.job.Job.create", side_effect=create_job), redirect_stdout(io.StringIO()):
                self.assertTrue(asyncio.run(cli.execute_plan(experiment)))
                with self.assertRaisesRegex(ValueError, "Attempt already exists"):
                    asyncio.run(cli.execute_plan(experiment))
            self.assertEqual([c.tasks[0].path.name for c in configs], [t["task"] for t in plan["trials"]])
            self.assertEqual(len(configs), 6)
            for trial in plan["trials"]:
                result = read_json(experiment / trial["id"] / "result.json")
                self.assertEqual(result["task"], trial["task"])
                self.assertTrue(result["accepted"])
                self.assertEqual(len(result.get("steps", [])), 2 if trial["task"] == TASKS[1] else 0)
            before = files_in(experiment)
            analysis = analyze_experiment(root, experiment)
            self.assertEqual(files_in(experiment), before)
            self.assertEqual(len(read_json(analysis / "comparison.json")["groups"]), 3)
            self.assertIn("../../../runs/", (analysis / "report.html").read_text(encoding="utf-8"))

    def test_later_task_tamper_stops_before_any_model_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            experiment, plan = self.create_plan(root)
            (task_path(experiment, plan, TASKS[-1]) / "instruction.md").write_text("tamper")
            with patch.object(cli, "ROOT", root), patch("harbor.job.Job.create", new_callable=AsyncMock) as job:
                with self.assertRaisesRegex(ValueError, "Frozen inputs changed"):
                    asyncio.run(cli.execute_plan(experiment))
                job.assert_not_called()
            self.assertFalse(any(experiment.glob("trial-*")))

    def test_group_pairing_never_hides_failure_or_invents_missing_time(self):
        plan = {"schema": 3, "profiles": {"a": {}, "b": {}}, "tasks": {
            "task-one": {"group": "same-origin", "step_names": ["first", "second"]},
            "task-two": {"group": "same-origin", "step_names": []}}, "trials": []}
        results = {}
        states = [("completed", True, 10), ("completed", True, 12),
                  ("completed", True, 5), ("completed", False, 1),
                  ("timeout", None, 300), ("not_run", None, None),
                  ("completed", True, None), ("completed", True, 20)]
        for index, (status, accepted, seconds) in enumerate(states):
            trial_id = f"trial-{index + 1:03d}"
            plan["trials"].append({"id": trial_id, "profile": "a" if index % 2 == 0 else "b",
                                   "task": "task-one" if index < 4 else "task-two", "repeat": (index // 2) % 2})
            results[trial_id] = {"status": status, "accepted": accepted, "agent_seconds": seconds}
        group, = group_comparisons(plan, results)
        self.assertEqual(group["planned_pairs"], 4)
        self.assertEqual(group["accepted_pairs"], 2)
        self.assertEqual(group["profiles"]["a"]["error"], 1)
        self.assertEqual(group["profiles"]["b"]["failed"], 1)
        self.assertEqual(group["profiles"]["b"]["pending"], 1)
        self.assertIsNone(group["profiles"]["a"]["paired_agent_seconds"])
        self.assertEqual(group["profiles"]["b"]["paired_agent_seconds"], 32)
        results["trial-002"]["accepted"] = False
        results["trial-008"]["accepted"] = False
        group, = group_comparisons(plan, results)
        self.assertEqual(group["accepted_pairs"], 0)
        self.assertIsNone(group["profiles"]["b"]["paired_agent_seconds"])

    def test_legacy_single_task_routing_and_duplicate_selection(self):
        plan = {"schema": 2, "task_name": TASKS[1], "step_names": ["archive", "sqlite"]}
        name, task = task_for_trial(plan, {"profile": "a"})
        self.assertEqual(name, TASKS[1])
        self.assertEqual(task["step_names"], ["archive", "sqlite"])
        self.assertEqual(task_path(Path("old"), plan, name), Path("old/inputs/task"))
        args = argparse.Namespace(profiles="minimal,focused", model="test", task=None, repeat=1,
                                  tasks="search-notes-v1,search-notes-v1")
        with patch.object(cli, "pin_image") as pin:
            with self.assertRaisesRegex(ValueError, "Duplicate tasks"):
                cli.make_plan(args)
            pin.assert_not_called()


if __name__ == "__main__":
    unittest.main()
