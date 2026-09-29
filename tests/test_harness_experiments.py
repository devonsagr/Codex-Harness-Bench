import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from chb.arena.experiments import plan, schedule, report, delivery, minimal_copy
from chb.arena.service import Arena
from chb.arena.api import export
from chb.arena.telemetry import read_trace
from chb.cli import ROOT


class PairedReportTests(unittest.TestCase):
    def fixture(self, outcomes=(1, 0, 0, 1)):
        configs = [{'id': 'a', 'name': 'Full', 'baseModel': 'model', 'reasoning': 'max', 'serviceTier': 'standard', 'agentsPrompt': 'full'},
                   {'id': 'b', 'name': 'Lean', 'baseModel': 'model', 'reasoning': 'max', 'serviceTier': 'standard', 'agentsPrompt': 'lean'}]
        task = {'id': 'task', 'title': 'Task', 'revision': 1, 'stages': [{}], 'checks': []}
        experiment = plan({'experiment': {'hypothesis': 'Remove redundant reviews', 'repeats': 2, 'activeMinutes': 5}}, configs, [task], {})
        trials = []
        for i, (_, config, pair) in enumerate(schedule([task], configs, experiment)):
            capture = {'id': 'capture', 'manifest': {'sha256': 'hash'}, 'checks': [], 'harnessUnchanged': True, 'hostUnchanged': True,
                       'nativeVerifications': [{'id': 'n', 'reward': outcomes[i], 'captureHash': 'hash', 'adapter': 'fixture', 'imageId': 'sha256:fixed'}]}
            trials.append({'id': f't{i}', 'taskId': 'task', 'configId': config['id'], 'state': 'completed', 'captures': [capture],
                           'experimentArm': pair['arm'], 'pairId': pair['pairId'], 'repeat': pair['repeat'], 'reviews': [], 'observations': [],
                           'usage': {'sessionId': f's{i}', 'models': ['model'], 'reasoningLevels': ['max'], 'serviceTiers': ['standard'],
                                     'totalTokens': 100 if pair['arm'] == 'A' else 80, 'activeSeconds': 60}})
        return {'configs': configs, 'tasks': [task], 'trials': trials, 'experiment': experiment, 'hostFingerprint': {'host': 'fixed'}}

    def test_native_pass_does_not_require_any_ai_review_or_quality_score(self):
        run = self.fixture((1, 1, 1, 1))
        result = report(run)
        self.assertEqual(result['status'], 'observed')
        self.assertEqual(result['verifiedPairs'], 2)
        self.assertEqual(result['arms'][0]['rate'], 1)
        self.assertEqual(result['successDelta'], 0)

    def test_failures_included_in_denominator_and_cost_per_success(self):
        run = self.fixture((1, 0, 1, 0))
        result = report(run)
        self.assertEqual([a['rate'] for a in result['arms']], [.5, .5])
        self.assertEqual(result['arms'][0]['metrics']['tokens']['perSuccess'], 200)
        self.assertEqual(result['arms'][1]['metrics']['tokens']['perSuccess'], 160)
        self.assertEqual([p['successDelta'] for p in result['pairs']], [-1, 1])

    def test_missing_evidence_is_unknown_and_never_partial_success_rate(self):
        run = self.fixture((1, 1, 1, 1))
        run['trials'][0]['captures'] = []
        result = report(run)
        self.assertIsNone(result['arms'][0]['rate'])
        self.assertEqual(result['arms'][0]['bounds'], [.5, 1])
        self.assertIsNone(result['successDelta'])
        self.assertIsNone(result['arms'][0]['metrics']['tokens']['perSuccess'])

    def test_high_ai_grade_and_smoke_check_are_not_verified_delivery(self):
        run = self.fixture()
        trial = run['trials'][0]
        trial['captures'][0]['nativeVerifications'] = []
        trial['score'] = {'overall': 100, 'assurance': 'task-check-pass'}
        trial['captures'][0]['checks'] = [{'id': 'smoke', 'status': 'passed'}]
        self.assertEqual(delivery(run['tasks'][0], trial)['status'], 'unknown')

    def test_latest_capture_invalidates_old_native_results(self):
        run = self.fixture()
        run['trials'][0]['captures'][0]['manifest']['sha256'] = 'changed'
        self.assertEqual(report(run)['arms'][0]['unknown'], 1)

    def test_budget_is_same_for_both_arms_and_success_cannot_hide_overrun(self):
        run = self.fixture((1, 1, 1, 1))
        run['trials'][1]['usage']['activeSeconds'] = 301
        result = report(run)
        self.assertEqual(result['arms'][1]['overBudget'], 1)
        self.assertEqual(result['arms'][1]['failed'], 1)
        self.assertEqual(result['successDelta'], -.5)

    def test_missing_usage_not_zero_and_unknown_budget_does_not_pass(self):
        run = self.fixture((1, 1, 1, 1))
        run['trials'][0]['usage']['totalTokens'] = None
        run['trials'][0]['usage']['activeSeconds'] = None
        result = report(run)
        self.assertIsNone(result['arms'][0]['metrics']['tokens']['total'])
        self.assertEqual(result['arms'][0]['metrics']['tokens']['observedTotal'], 100)
        self.assertEqual(result['arms'][0]['unknown'], 1)

    def test_token_budget_nan_protocol_changes_and_pending_native_retry(self):
        run=self.fixture((1,1,1,1));run['experiment']['maxTokens']=1000
        run['trials'][0]['usage']['totalTokens']=1001
        self.assertTrue(report(run)['pairs'][0]['a']['overBudget'])
        run['trials'][0]['usage']['totalTokens']=float('nan')
        self.assertEqual(report(run)['pairs'][0]['a']['outcome'],'unknown')
        run['trials'][1]['captures'][0]['nativeVerifications'][0]['imageId']='different'
        self.assertFalse(report(run)['pairs'][0]['matched'])
        run['trials'][2]['nativeExecution']={'captureId':'capture','status':'running'}
        self.assertEqual(report(run)['pairs'][1]['b']['delivery']['status'],'unknown')

    def test_trust_registration_is_not_a_new_host_but_semantic_changes_are(self):
        run=self.fixture((1,1,1,1))
        run['trials'][0]['appliedHostFingerprint']={'config.toml':'a','configSemantic':'same'}
        run['trials'][1]['appliedHostFingerprint']={'config.toml':'b','configSemantic':'same'}
        self.assertTrue(report(run)['pairs'][0]['matched'])
        run['trials'][1]['appliedHostFingerprint']['configSemantic']='different'
        self.assertFalse(report(run)['pairs'][0]['matched'])
        self.assertEqual(report(run)['observedSuccessDelta'],0)

    def test_all_frozen_requirement_statuses_are_shown_separately_from_success(self):
        run=self.fixture()
        run['trials'][0]['reviews']=[{'captureId':'old','kind':'ai','requirementChecks':{'old':{'status':'met'}}},
          {'captureId':'capture','kind':'ai','requirementChecks':{'a':{'status':'met'},'b':{'status':'unmet'},'c':{'status':'partial'},'d':{'status':'unverified'}}}]
        result=report(run)['pairs'][0]['a']['assessment']
        self.assertEqual([result[k] for k in ('requirements','met','notMet','unknown')],[4,1,2,1])
        self.assertFalse(result['calibrated'])

    def test_condition_mismatch_keeps_attempt_but_blocks_attribution(self):
        for key, value in [('models', ['other']), ('reasoningLevels', []), ('serviceTiers', [])]:
            run = self.fixture((1, 1, 1, 1));run['trials'][0]['usage'][key] = value
            result = report(run)
            self.assertEqual(result['arms'][0]['passed'], 2)
            self.assertEqual(result['matchedPairs'], 1)
            self.assertIsNone(result['successDelta'])

    def test_shared_session_and_changed_host_are_visible(self):
        run = self.fixture((1, 1, 1, 1))
        run['trials'][1]['usage']['sessionId'] = 's0'
        run['trials'][3]['appliedHostFingerprint'] = {'host': 'other'}
        result = report(run)
        self.assertEqual(result['matchedPairs'], 0)
        self.assertIn('同一会话', ' '.join(result['pairs'][0]['conditions']))
        self.assertIn('宿主', ' '.join(result['pairs'][1]['conditions']))

    def test_interrupted_with_no_result_is_visible_not_zero(self):
        run = self.fixture();run['trials'][0].update(state='interrupted', captures=[])
        result = report(run)
        self.assertEqual(result['arms'][0]['interrupted'], 1)
        self.assertEqual(result['arms'][0]['unknown'], 1)

    def test_report_is_readonly_and_legacy_runs_are_unchanged(self):
        run = self.fixture();before = copy.deepcopy(run)
        report(run);self.assertEqual(run, before)
        del run['experiment'];self.assertIsNone(report(run))

    def test_invalid_plan_is_rejected_before_workspace_creation(self):
        run = self.fixture()
        for change in [{'repeats': True}, {'repeats': 9}, {'activeMinutes': 0}, {'maxTokens': -1}, {'hypothesis': ''}, {'unknown': 'x'}]:
            with self.assertRaises(ValueError):
                plan({'experiment': {'hypothesis': 'Validate a change', **change}}, run['configs'], run['tasks'], {})
        run['configs'][1]['baseModel'] = 'different'
        with self.assertRaisesRegex(ValueError, '相同模型'):
            plan({'experiment': {'hypothesis': 'Validate a change'}}, run['configs'], run['tasks'], {})


class ExperimentIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.root = Path(self.tmp.name)
        shutil.copytree(ROOT/'profiles', self.root/'profiles');(self.root/'catalog').mkdir()
        (self.root/'catalog/arena-tasks.json').write_text('[]')
        self.app = Arena(self.root)
        self.task = self.app.save_task({'id': 'qa', 'title': 'Small project', 'inputPrompt': 'Build a small calculator.',
            'taskParadigm': 'open-ended-project', 'channel': 'deepswe-core', 'hasFrontendUI': False,
            'stages': [{'title': 'Build', 'prompt': 'Build a calculator.'}], 'checks': []})

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_prepare_independent_repeats_frozen_plan_export_and_idempotency(self):
        config = self.app.db.get('config', 'minimal')
        lean = minimal_copy(self.app, {'configId': config['id'], 'revision': config['revision']})
        data = {'requestId': 'paired', 'configIds': [config['id'], lean['id']], 'taskIds': [self.task['id']],
                'experiment': {'hypothesis': 'Remove selected rules and compare', 'repeats': 2, 'activeMinutes': 15}}
        run = self.app.prepare(data)
        self.assertEqual([t['experimentArm'] for t in run['trials']], ['A', 'B', 'B', 'A'])
        self.assertEqual(len({t['workspacePath'] for t in run['trials']}), 4)
        self.assertEqual(run['experimentReport']['arms'][0]['unknown'], 2)
        self.assertEqual(run['experiment']['plannedTrials'], 4)
        self.assertEqual(self.app.prepare(data)['id'], run['id'])
        config['agentsPrompt'] += '\nnew rule';self.app.save_config(config)
        self.assertEqual(self.app.present_run(self.app.db.get('run', run['id']))['experiment'], run['experiment'])
        import io, zipfile
        with zipfile.ZipFile(io.BytesIO(export(self.app, run['id']))) as archive:
            stored = json.loads(archive.read('record.json'))
            self.assertEqual(stored['experimentReport'], run['experimentReport'])

    def test_minimal_copy_does_not_modify_source_or_host(self):
        source = self.app.db.get('config', 'minimal');host = self.app.host_fingerprint()
        lean = minimal_copy(self.app, {'configId': source['id'], 'revision': source['revision']})
        self.assertEqual(lean['baseModel'], source['baseModel'])
        self.assertEqual(lean['agentsPrompt'], '')
        self.assertEqual(lean['skills'], [])
        self.assertEqual(self.app.db.get('config', source['id']), source)
        self.assertEqual(self.app.host_fingerprint(), host)

    def test_trace_reads_only_explicit_speed_never_infers_default(self):
        rows = [{'type': 'session_meta', 'payload': {'id': 's', 'cwd': str(self.root)}},
                {'type': 'turn_context', 'payload': {'model': 'm', 'effort': 'max', 'service_tier': 'default'}}]
        self.assertEqual(read_trace('\n'.join(map(json.dumps, rows)), self.root)['serviceTiers'], ['standard'])
        del rows[1]['payload']['service_tier']
        self.assertEqual(read_trace('\n'.join(map(json.dumps, rows)), self.root)['serviceTiers'], [])

    def test_explicit_profile_switch_keeps_inherited_context_and_detects_unrelated_changes(self):
        import os
        from unittest.mock import patch
        from chb.arena.api import post
        from chb.arena.experiments import comparison_host
        home=self.root/'isolated-home';home.mkdir()
        (home/'models_cache.json').write_text(json.dumps({'models':[{'slug':'test-model','supported_reasoning_levels':[{'effort':'high'}]}]}))
        (home/'config.toml').write_text('model="old"\n[private]\nsetting="fixed"\n')
        (home/'AGENTS.override.md').write_text('inherited')
        with patch.dict(os.environ,{'CODEX_HOME':str(home)}):
            a=self.app.save_config({'name':'A','agentsPrompt':'extra rules','baseModel':'test-model','reasoning':'high','interactiveMode':'adaptive','skills':[]})
            b=minimal_copy(self.app,{'configId':a['id'],'revision':a['revision']})
            run=self.app.prepare({'requestId':'switch','configIds':[a['id'],b['id']],'taskIds':[self.task['id']],
                                 'experiment':{'hypothesis':'Compare extra rules','repeats':1}})
            contexts=[]
            for trial in run['trials']:
                post(self.app,f"/api/arena/runs/{run['id']}/trials/{trial['id']}/apply-config",{})
                current=self.app.db.get('run',run['id'])
                stored=next(t for t in current['trials'] if t['id']==trial['id'])
                contexts.append(stored['experimentHostContext'])
            self.assertEqual(contexts[0],contexts[1])
            path=home/'config.toml';path.write_text(path.read_text().replace('fixed','changed'))
            self.assertNotEqual(contexts[1],comparison_host(self.app,current,stored))
