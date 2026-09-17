import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from chb.arena.service import Arena
from chb.arena.scoring import policy, DESKTOP_POLICY, validate_review


class ScoreDecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'catalog').mkdir();(self.root/'catalog/arena-tasks.json').write_text('[]')
        (self.root/'home').mkdir();self.env=patch.dict(os.environ,{'CODEX_HOME':str(self.root/'home')});self.env.start()
        self.app=Arena(self.root)
        self.config=self.app.save_config({'name':'test','agentsPrompt':'','baseModel':'test','reasoning':'low','interactiveMode':'adaptive','skills':[]})
        self.task=self.app.save_task({'title':'Fixture','inputPrompt':'test','taskParadigm':'open-ended-project','channel':'deepswe-core',
            'schemaVersion':2,'hasFrontendUI':False,'stages':[{'title':'test','prompt':'test'}],
            'criteria':[{'id':'must','label':'Necessary behavior','required':True,'dimension':'intent'}],
            'checks':[{'id':'check','label':'Synthetic failure fixture','image':'fixture-only','argv':['false'],'weight':1,'criterionIds':['must']}]})
        self.policy={**copy.deepcopy(DESKTOP_POLICY),'dimensionUnit':'percent','requireDimensionEvidence':True,
                     'objectiveWeight':100,'humanWeight':0,'dimensions':{'intent':100},
                     'rubrics':{'intent':{'label':'Intent','description':'Check the required behavior.'}}}
        self.run=self.app.prepare({'requestId':'test','configIds':[self.config['id']],'taskIds':[self.task['id']],'policy':self.policy})
        self.rid=self.run['id'];self.tid=self.run['trials'][0]['id']
        self.app.mutate(self.rid,self.tid,'capture',{})
        run=self.app.db.get('run',self.rid)
        run['trials'][0]['captures'][0]['checks']=[{'id':'check','label':'Synthetic failure fixture','status':'failed','exitCode':1,'output':'fixture','seconds':1,'imageId':'fixture-only'}]
        self.app.db.save('run',run,run['revision'])
        self.app.mutate(self.rid,self.tid,'complete',{})
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def current(self):return self.app.present_run(self.app.db.get('run',self.rid))['trials'][0]
    def decision(self,score=80,**kwargs):
        trial=self.current()
        return self.app.mutate(self.rid,self.tid,'objective-review',{'captureId':trial['captures'][-1]['id'],
            'evidenceKey':trial['score']['objectiveEvidenceKey'],'score':score,'reason':'Verifier misses allowed implementation',
            'evidence':'Synthetic fixture check output and documented reproduction',**kwargs})['trials'][0]

    def test_correction_never_overwrites_automatic_or_required_verdict(self):
        t=self.decision(80)
        self.assertEqual(t['score']['objective'],0);self.assertEqual(t['score']['overall'],0)
        self.assertEqual(t['score']['adjudicatedObjective'],80);self.assertEqual(t['score']['adjudicatedOverall'],80)
        self.assertEqual(t['score']['acceptance']['status'],'not_met')
        self.assertEqual(t['captures'][0]['checks'][0]['status'],'failed')

    def test_zero_and_withdraw_are_distinct_and_history_remains(self):
        t=self.decision(0);self.assertEqual(t['score']['adjudicatedObjective'],0)
        t=self.decision(None);self.assertIsNone(t['score']['adjudicatedObjective'])
        self.assertEqual(len(t['objectiveReviews']),2)

    def test_reexecution_invalidates_old_decision_and_stale_submission(self):
        t=self.decision();key=t['score']['objectiveEvidenceKey']
        run=self.app.db.get('run',self.rid);run['trials'][0]['captures'][0]['checks'][0]['output']='rerun result'
        self.app.db.save('run',run,run['revision'])
        self.assertIsNone(self.current()['score']['adjudicatedObjective'])
        with self.assertRaisesRegex(ValueError,'证据已变化'):self.decision(evidenceKey=key)

    def test_new_capture_has_no_inherited_correction_and_unknown_is_not_filled(self):
        self.decision();self.app.mutate(self.rid,self.tid,'capture',{})
        self.assertIsNone(self.current()['score']['adjudicatedObjective'])
        with self.assertRaisesRegex(ValueError,'完整原分'):self.decision()

    def test_correction_requires_reason_evidence_and_finished_checks(self):
        for field in ['reason','evidence']:
            with self.assertRaises(ValueError):self.decision(**{field:''})
        run=self.app.db.get('run',self.rid);run['trials'][0]['state']='checking';self.app.db.save('run',run,run['revision'])
        with self.assertRaisesRegex(ValueError,'结束后台检查'):self.decision()

    def test_percent_contract_and_per_dimension_evidence(self):
        self.assertEqual(policy(self.policy)['dimensionUnit'],'percent')
        with self.assertRaisesRegex(ValueError,'100%'):policy({**self.policy,'dimensions':{'intent':1}})
        data={'scores':{'intent':0},'notes':'manual zero fixture','readiness':'rejected','constraints':{}}
        task={'hasFrontendUI':False}
        with self.assertRaisesRegex(ValueError,'每个计分维度'):validate_review(data,task,[],scoring_policy=self.policy)
        result=validate_review({**data,'dimensionEvidence':{'intent':'Required flow reproduced a failure.'}},task,[],scoring_policy=self.policy)
        self.assertEqual(result['scores']['intent'],0)
        legacy={**self.policy};legacy.pop('requireDimensionEvidence')
        self.assertNotIn('dimensionEvidence',validate_review(data,task,[],scoring_policy=legacy))

    def test_unconfigured_objective_requires_explicit_manual_policy(self):
        plain=self.app.save_task({**self.task,'id':None,'revision':None,'checks':[]})
        with self.assertRaisesRegex(ValueError,'没有自动检查'):
            self.app.prepare({'requestId':'missing-checks','configIds':[self.config['id']],'taskIds':[plain['id']],'policy':self.policy})
