import json
from pathlib import Path
import tempfile
import unittest

from chb.usage import reconcile_usage


def record(input_tokens, cached, output, stamp):
    return {"timestamp": stamp, "type": "event_msg", "payload": {"type": "token_count", "info": {
        "total_token_usage": {"input_tokens": input_tokens, "cached_input_tokens": cached,
                              "output_tokens": output, "total_tokens": input_tokens + output}}}}


class UsageTests(unittest.TestCase):
    def fixture(self, root):
        first = record(100, 20, 10, "one")
        second = record(250, 100, 30, "two")
        dirs, steps = [], []
        for index, records in enumerate(([first], [first, second])):
            directory = root / str(index)
            path = directory / "sessions/session.jsonl"
            path.parent.mkdir(parents=True)
            events = [{"type": "session_meta", "payload": {"id": "session", "cli_version": "0.154.0"}}, *records]
            path.write_text("\n".join(json.dumps(event) for event in events))
            dirs.append(directory)
            steps.append({"status": "completed", "session_id": "session",
                          "reported_usage": records[-1]["payload"]["info"]["total_token_usage"].copy()})
        return steps, dirs

    def test_verified_differences_do_not_sum_cumulative_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            steps, dirs = self.fixture(Path(tmp))
            result = reconcile_usage(steps, dirs, 2)
            self.assertEqual(result["status"], "verified_cumulative")
            self.assertEqual(result["totals"], {"input_tokens": 250, "cached_input_tokens": 100, "output_tokens": 30})
            self.assertEqual(result["turn_deltas"][1], {"input_tokens": 150, "cached_input_tokens": 80, "output_tokens": 20})
            self.assertEqual(steps[1]["reported_usage"]["input_tokens"], 250)

    def test_disagreement_missing_fields_and_incomplete_steps_are_unavailable(self):
        for case, reason in [("disagreement", "cli_and_native_totals_disagree"),
                             ("missing", "missing_or_invalid_counters"),
                             ("bool", "missing_or_invalid_counters"),
                             ("incomplete", "incomplete_turn_sequence"),
                             ("failed", "turn_not_completed"),
                             ("identity", "session_not_continuous")]:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                steps, dirs = self.fixture(Path(tmp))
                if case == "disagreement": steps[1]["reported_usage"]["input_tokens"] += 1; steps[1]["reported_usage"].pop("total_tokens")
                if case == "missing": steps[1]["reported_usage"].pop("cached_input_tokens")
                if case == "bool": steps[1]["reported_usage"]["output_tokens"] = True
                if case == "incomplete": steps.pop(); dirs.pop()
                if case == "failed": steps[1]["status"] = "timeout"
                if case == "identity": steps[1]["session_id"] = "other"
                result = reconcile_usage(steps, dirs, 2)
                self.assertEqual(result["reason"], reason)
                self.assertIsNone(result["totals"]["input_tokens"])

    def test_native_reset_rewrite_unknown_version_and_corruption_are_rejected(self):
        for case, reason in [("reset", "native_counter_reset"), ("rewrite", "native_history_not_extended"),
                             ("version", "unverified_native_cli_version"), ("id", "native_session_identity_mismatch"),
                             ("corrupt", "malformed_native_session"), ("ambiguous", "missing_or_ambiguous_native_session")]:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                steps, dirs = self.fixture(Path(tmp))
                path = dirs[1] / "sessions/session.jsonl"
                events = [json.loads(line) for line in path.read_text().splitlines()]
                if case == "reset": events[-1] = record(50, 10, 5, "reset")
                if case == "rewrite": events[1]["timestamp"] = "rewritten"
                if case == "version": events[0]["payload"]["cli_version"] = "future"
                if case == "id": events[0]["payload"]["id"] = "wrong"
                path.write_text("\n".join(json.dumps(event) for event in events))
                if case == "corrupt": path.write_text(path.read_text() + "\n{broken")
                if case == "ambiguous": (path.parent / "extra.jsonl").write_text(path.read_text())
                self.assertEqual(reconcile_usage(steps, dirs, 2)["reason"], reason)


if __name__ == "__main__":
    unittest.main()
