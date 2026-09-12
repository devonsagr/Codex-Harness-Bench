import json
from pathlib import Path
import shutil
import tempfile
import unittest

from chb.cli import ROOT, summarize_trial
from chb.profiles import digest, files_in, freeze, validate_profile, verify_frozen, write_json
from chb.report import render
from chb.adapter import ProfileCodex


class CoreTests(unittest.TestCase):
    def test_harbor_custom_profile_option_is_declared(self):
        options = ProfileCodex.parse_options({"profile_path": "profiles/minimal", "version": "0.154.0"})
        self.assertEqual(options.profile_path, "profiles/minimal")

    def test_real_event_usage_and_instruction_marker_are_observed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            trial = directory / "harbor/job/task-1"
            write_json(trial / "result.json", {"trial_name": "task-1", "verifier_result": {"rewards": {"reward": 1}}})
            (trial / "agent").mkdir()
            events = [
                {"type": "item.completed", "item": {"type": "agent_message", "text": "Done.\nCHB_PROFILE=minimal"}},
                {"type": "turn.completed", "usage": {"input_tokens": 800, "output_tokens": 120, "cached_input_tokens": 0}},
            ]
            (trial / "agent/codex.txt").write_text("\n".join(json.dumps(event) for event in events))
            result = summarize_trial(directory, "minimal")
            self.assertTrue(result["accepted"])
            self.assertTrue(result["profile_marker_observed"])
            self.assertEqual(result["cached_input_tokens"], 0)
            self.assertEqual(result["input_tokens"], 800)

    def test_frozen_history_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "profile"
            shutil.copytree(ROOT / "profiles/minimal", source)
            snapshot = freeze(source, base / "snapshot")
            (source / "AGENTS.md").write_text("new instructions")
            verify_frozen(base / "snapshot", snapshot)
            (base / "snapshot/AGENTS.md").write_text("tampered")
            with self.assertRaises(ValueError):
                verify_frozen(base / "snapshot", snapshot)

    def test_digest_ignores_enumeration_order(self):
        self.assertEqual(digest({"b": b"2", "a": b"1"}), digest({"a": b"1", "b": b"2"}))
        self.assertNotEqual(digest({"a": b"1"})[0], digest({"a": b"2"})[0])

    def test_unknown_config_and_secret_file_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "profile"
            shutil.copytree(ROOT / "profiles/minimal", profile)
            with (profile / "config.toml").open("a") as out:
                out.write('\nmade_up_planner = true\n')
            with self.assertRaisesRegex(ValueError, "Unsupported Codex"):
                validate_profile(profile)
            (profile / "auth.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Credential"):
                files_in(profile)

    def test_missing_usage_is_not_free_usage(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_json(directory / "harbor/job/task-1/result.json", {
                "trial_name": "task-1", "verifier_result": {"rewards": {"reward": 0}},
            })
            result = summarize_trial(directory, "minimal")
            self.assertFalse(result["accepted"])
            self.assertIsNone(result["input_tokens"])
            self.assertIsNone(result["cost_usd"])

    def test_timeout_and_verifier_errors_are_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            result_file = directory / "harbor/job/task-1/result.json"
            for error, status in [("AgentTimeoutError", "timeout"), ("VerifierError", "verifier_error")]:
                write_json(result_file, {"trial_name": "task-1", "agent_execution": {"started_at": "2026-09-12T00:00:00Z"},
                                        "exception_info": {"exception_type": error}})
                self.assertEqual(summarize_trial(directory, "minimal")["status"], status)

    def test_report_escapes_untrusted_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_json(directory / "plan.json", {
                "id": "<script>alert(1)</script>", "model": "model", "repeat": 1,
                "codex_version": "0.154.0", "harbor_version": "0.23.0",
                "trials": [{"id": "trial-001", "profile": "<img src=x onerror=alert(1)>"}],
            })
            report = render(directory).read_text(encoding="utf-8")
            self.assertNotIn("<script>", report)
            self.assertNotIn("<img ", report)
            self.assertIn("&lt;script&gt;", report)


if __name__ == "__main__":
    unittest.main()
