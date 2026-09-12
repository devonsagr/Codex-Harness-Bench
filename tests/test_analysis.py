import json
from pathlib import Path
import tempfile
import unittest

from chb.analysis import analyze_experiment, source_manifest
from chb.cli import ROOT
from chb.profiles import files_in, freeze, read_json, write_json
from chb.report import render


class AnalysisTests(unittest.TestCase):
    def test_reanalysis_is_append_only_and_keeps_source_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/chb").mkdir(parents=True)
            (root / "src/chb/fixture.py").write_text("# analyzer fixture\n")
            experiment = root / "runs/old"
            profile = freeze(ROOT / "profiles/minimal", experiment / "inputs/profiles/minimal")
            task = freeze(ROOT / "tasks/search-notes-v1", experiment / "inputs/task")
            write_json(experiment / "plan.json", {"id": "old", "model": "model", "repeat": 1,
                       "codex_version": "0.154.0", "harbor_version": "0.23.0", "task": task,
                       "profiles": {"minimal": profile}, "trials": [{"id": "trial-001", "profile": "minimal"}]})
            (experiment / "profile-diff.txt").write_text("difference")
            write_json(experiment / "trial-001/result.json", {"status": "completed", "accepted": True})
            harbor = experiment / "trial-001/harbor/job/task"
            write_json(harbor / "result.json", {"trial_name": "task", "verifier_result": {"rewards": {"reward": 1}}})
            (harbor / "agent").mkdir()
            (harbor / "agent/codex.txt").write_text('{"type":"turn.completed","usage":{"input_tokens":20,"cached_input_tokens":0,"output_tokens":5}}\n')
            render(experiment)
            before = files_in(experiment)
            output = analyze_experiment(root, experiment)
            metadata = read_json(output / "analysis.json")
            self.assertTrue(metadata["historical_verdicts_preserved"])
            self.assertEqual(metadata["model_calls_started"], 0)
            self.assertEqual(before, files_in(experiment))
            self.assertEqual(metadata["source_manifest"], source_manifest(experiment))
            self.assertEqual(read_json(output / "trial-001/result.json")["input_tokens"], 20)
            report = (output / "report.html").read_text(encoding="utf-8")
            self.assertIn("已有日志的重新分析", report)
            self.assertIn("../../../runs/old/", report)
            again = analyze_experiment(root, experiment)
            self.assertNotEqual(output, again)
            self.assertEqual(before, files_in(experiment))
            write_json(experiment / "trial-001/result.json", {"status": "completed", "accepted": False})
            with self.assertRaisesRegex(ValueError, "historical verdict"):
                analyze_experiment(root, experiment)


if __name__ == "__main__":
    unittest.main()
