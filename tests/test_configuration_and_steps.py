import json
from pathlib import Path
import tempfile
import unittest

from chb.configuration import clone_profile, import_current, resolve_profile, restore_profile
from chb.profiles import files_in, freeze, read_json, validate_profile, write_json
from chb.results import summarize_trial


class ConfigurationTests(unittest.TestCase):
    def test_partial_import_clone_and_restore_preserve_private_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            (home / "AGENTS.md").write_text("user instructions", encoding="utf-8")
            (home / "AGENTS.override.md").write_text("effective instructions", encoding="utf-8")
            (home / "config.toml").write_text('model_reasoning_effort="xhigh"\nweb_search="live"\n[secrets]\nkey="do-not-copy"\n')
            (home / "auth.json").write_text("do-not-read")
            before = {p.name: p.read_bytes() for p in home.iterdir()}
            result = import_current(root, "current", home, reasoning="medium")
            profile = Path(result["profile"])
            self.assertEqual((profile / "AGENTS.md").read_text(), "effective instructions")
            self.assertEqual(validate_profile(profile)[1]["model_reasoning_effort"], "medium")
            self.assertNotIn(b"do-not-copy", b"".join(files_in(profile).values()) + Path(result["receipt"]).read_bytes())
            self.assertEqual(read_json(result["receipt"])["omitted_setting_names"], ["secrets"])
            skill = root / "source-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text("skill workflow")
            clone = Path(clone_profile(root, "current", "with-skill", [skill])["profile"])
            self.assertEqual((clone / "AGENTS.md").read_bytes(), (profile / "AGENTS.md").read_bytes())
            self.assertEqual(resolve_profile(root, "with-skill"), clone)
            experiment = root / "experiment"
            snapshot = freeze(clone, experiment / "inputs/profiles/with-skill")
            write_json(experiment / "plan.json", {"profiles": {"with-skill": snapshot}})
            (clone / "AGENTS.md").write_text("edited after experiment")
            restored = Path(restore_profile(root, experiment, "with-skill", "restored")["profile"])
            self.assertEqual((restored / "AGENTS.md").read_text(), "effective instructions")
            self.assertEqual((restored / "skills/source-skill/SKILL.md").read_text(), "skill workflow")
            self.assertEqual({p.name: p.read_bytes() for p in home.iterdir()}, before)
            with self.assertRaisesRegex(ValueError, "already exists"):
                import_current(root, "current", home)
            (experiment / "inputs/profiles/with-skill/AGENTS.md").write_text("tamper")
            with self.assertRaisesRegex(ValueError, "Frozen inputs changed"):
                restore_profile(root, experiment, "with-skill", "invalid")

    def test_linked_or_secret_skill_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            skill = Path(temporary) / "skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text("workflow")
            (skill / ".env.production").write_text("secret")
            with self.assertRaisesRegex(ValueError, "Credential"):
                files_in(skill)
            (skill / ".env.production").unlink()
            try:
                (skill / "linked").symlink_to(skill, target_is_directory=True)
            except OSError:
                self.skipTest("Symlink creation is unavailable")
            with self.assertRaisesRegex(ValueError, "Links"):
                files_in(skill)


class MultiStepTests(unittest.TestCase):
    def setup_experiment(self, root):
        directory = root / "trial-001"
        trial = directory / "harbor/job/task-1"
        write_json(root / "plan.json", {"step_names": ["archive", "sqlite"], "verifier": "separate fresh container"})
        skill = root / "inputs/profiles/current/skills/workflow/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("Read scope. Complete the task.")
        raw = {"trial_name": "task-1", "step_results": []}
        for name in ("archive", "sqlite"):
            raw["step_results"].append({"step_name": name, "verifier_result": {"rewards": {"reward": 1}}})
            agent = trial / "steps" / name / "agent"
            agent.mkdir(parents=True)
            events = [{"type": "thread.started", "thread_id": "same-session"},
                      {"type": "item.completed", "item": {"type": "command_execution", "id": "read1", "exit_code": 0,
                       "command": "cat /root/.agents/skills/workflow/SKILL.md", "aggregated_output": "Read scope. Complete the task.\n"}},
                      {"type": "turn.completed", "usage": {"input_tokens": 500, "output_tokens": 50}}]
            (agent / "codex.txt").write_text("\n".join(json.dumps(event) for event in events))
        write_json(trial / "result.json", raw)
        return directory, trial, raw

    def test_continuity_skill_read_and_no_cumulative_double_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory, trial, raw = self.setup_experiment(Path(temporary))
            result = summarize_trial(directory, "current")
            self.assertTrue(result["accepted"])
            self.assertTrue(result["session_continuity_observed"])
            self.assertIsNone(result["input_tokens"])
            self.assertTrue(result["steps"][0]["skill_reads"][0]["complete_read_output_observed"])
            log = trial / "steps/sqlite/agent/codex.txt"
            log.write_text(log.read_text().replace("same-session", "other-session"))
            self.assertEqual(summarize_trial(directory, "current")["status"], "protocol_error")

    def test_missing_round_cannot_be_accepted_by_mean_reward(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory, trial, raw = self.setup_experiment(Path(temporary))
            raw["step_results"].pop()
            raw["verifier_result"] = {"rewards": {"reward": 1}}
            write_json(trial / "result.json", raw)
            self.assertIsNone(summarize_trial(directory, "current")["accepted"])

    def test_failed_event_and_partial_read_are_not_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory, trial, raw = self.setup_experiment(Path(temporary))
            log = trial / "steps/archive/agent/codex.txt"
            log.write_text(log.read_text().replace('"turn.completed"', '"turn.failed"').replace('Read scope. Complete the task.\\n', 'Read scope.\\n'))
            result = summarize_trial(directory, "current")
            self.assertEqual(result["status"], "execution_error")
            self.assertIsNone(result["accepted"])
            self.assertFalse(result["steps"][0]["skill_reads"][0]["complete_read_output_observed"])


if __name__ == "__main__":
    unittest.main()
