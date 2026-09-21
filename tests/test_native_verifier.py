import json
from pathlib import Path
import shutil
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

from chb.cli import ROOT
from chb.arena.service import Arena
from chb.arena.jobs import start_job
from chb.arena.native_verifier import grade, supported, prepare_environment, TASK_ID, REVISION
from chb.arena.scoring import MACHINE_POLICY


class NativeVerifierTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'.local/qa';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.temp.name)
        shutil.copytree(ROOT/'profiles',self.root/'profiles');(self.root/'catalog').mkdir()
        (self.root/'catalog/arena-tasks.json').write_text('[]')
        self.app=Arena(self.root)

    def tearDown(self):self.temp.cleanup()

    def log(self,name,events):
        p=self.root/name;p.write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8');return p

    def test_whitelist_counts_missing_skipped_and_duplicate_failure(self):
        p=self.log('suite.jsonl',[{'Package':'p','Test':'a','Action':'pass'},{'Package':'p','Test':'a','Action':'fail'},
                                 {'Package':'p','Test':'b','Action':'pass'},{'Package':'p','Test':'c','Action':'skip'}])
        result=grade({'f2p_node_ids':['p.a','p.c','p.missing'],'p2p_node_ids':['p.b']},[p])
        self.assertEqual((result['reward'],result['f2p_passed'],result['p2p_passed']),(0,0,1))
        self.assertEqual(result['partial'],.25)

    def test_environment_error_in_any_suite_is_unknown_not_zero(self):
        good=self.log('good.jsonl',[{'Action':'pass','Package':'p','Test':'a'}]);bad=self.root/'bad.log';bad.write_text('sandbox failed')
        with self.assertRaises(ValueError):grade({'f2p_node_ids':['p.a'],'p2p_node_ids':[]},[good,bad])
        with self.assertRaises(ValueError):grade({'f2p_node_ids':[],'p2p_node_ids':[]},[])

    def task(self):
        source=self.root/'source';source.mkdir();(source/'go.mod').write_text('module example\ngo 1.13\n')
        baseline=self.app.import_files('baseline',{'path':str(source),'name':'fixture'})
        return self.app.save_task({'id':'native-fixture','title':'Verifier fixture','inputPrompt':'Fix it','taskParadigm':'deterministic-bugfix',
            'channel':'deepswe-core','hasFrontendUI':False,'baselineId':baseline['id'],'checks':[],
            'publicSource':{'id':TASK_ID,'revision':REVISION}})

    def settled(self,rid):
        for _ in range(200):
            run=self.app.db.get('run',rid)
            if run['trials'][0].get('nativeExecution',{}).get('status')!='running':return run
            time.sleep(.01)
        self.fail('worker did not finish')

    def test_background_verifier_keeps_history_separate_from_ai_and_handles_failure(self):
        task=self.task();run=self.app.prepare({'requestId':'native','configIds':['minimal'],'taskIds':[task['id']]})
        tid=run['trials'][0]['id'];run=self.app.mutate(run['id'],tid,'capture',{});capture=run['trials'][0]['captures'][0]
        with patch('chb.arena.native_verifier.run',return_value={'id':'native-one','reward':0}):
            start_job(self.app,run['id'],tid,'native',{'captureId':capture['id']});current=self.settled(run['id'])
        self.assertEqual(current['trials'][0]['state'],'captured')
        self.assertEqual(current['trials'][0]['reviews'],[])
        self.assertEqual(current['trials'][0]['captures'][0]['nativeVerifications'],[{'id':'native-one','reward':0}])
        with patch('chb.arena.native_verifier.run',side_effect=ValueError('环境异常，未知分数')):
            start_job(self.app,run['id'],tid,'native',{'captureId':capture['id']});current=self.settled(run['id'])
        self.assertEqual(len(current['trials'][0]['captures'][0]['nativeVerifications']),1)
        self.assertEqual(current['trials'][0]['nativeExecution']['status'],'failed')

    def test_environment_readiness_requires_valid_failure_baseline_and_no_reference_leak(self):
        task=self.task();self.assertTrue(supported(task))
        with patch('chb.arena.native_verifier.run',return_value={'p2p':1,'f2p':0}):
            ready=prepare_environment(self.app,task)
        self.assertEqual(ready['publicSource']['environmentStatus'],'ready-windows')
        self.assertEqual(ready['inputPrompt'],'Fix it')
        with patch('chb.arena.native_verifier.run',return_value={'p2p':0,'f2p':0}):
            with self.assertRaises(ValueError):prepare_environment(self.app,ready)
        self.assertFalse(supported({'publicSource':{'id':TASK_ID,'revision':'different'}}))

    def test_cancel_does_not_publish_result_or_clear_other_checks(self):
        task=self.task();run=self.app.prepare({'requestId':'cancel','configIds':['minimal'],'taskIds':[task['id']],'policy':MACHINE_POLICY})
        tid=run['trials'][0]['id'];self.app.mutate(run['id'],tid,'capture',{})
        run=self.app.db.get('run',run['id']);capture=run['trials'][0]['captures'][0]
        capture['checks']=[{'id':'existing','status':'passed','weight':1}]
        self.app.db.save('run',run,run['revision'])
        def cancelled(*args):
            args[5]['stop'].set()
            return {'id':'cancelled','reward':1}
        with patch('chb.arena.jobs.applicable_checks',return_value=[{'id':'existing'}]),patch('chb.arena.native_verifier.run',side_effect=cancelled):
            start_job(self.app,run['id'],tid,'native',{'captureId':capture['id']});current=self.settled(run['id'])
        trial=current['trials'][0]
        self.assertEqual(trial['nativeExecution']['status'],'cancelled')
        self.assertFalse(trial['captures'][0].get('nativeVerifications'))
        self.assertEqual(trial['captures'][0]['checks'],capture['checks'])
        current=self.app.db.archive('run',current['id'],True,current['revision'])
        with self.assertRaises(ValueError):start_job(self.app,current['id'],tid,'native',{'captureId':capture['id']})

    def test_changed_baseline_is_rejected_before_toolchain_or_tests_run(self):
        from chb.arena.native_verifier import run
        task=self.task();base=self.app.db.get('baseline',task['baselineId'])
        source=self.app.local/'baselines'/base['id']/'files'
        fixed={'tasks':[{'id':TASK_ID,'baseCommit':'original','repositoryUrl':'https://github.com/d5/tengo'}]}
        with patch('chb.arena.native_verifier.catalog',return_value=fixed),patch('chb.arena.native_verifier.ensure_runtime') as runtime:
            with self.assertRaisesRegex(ValueError,'源码起点已更换'):
                run(self.app,task,source,base['manifest'],self.root/'result',{'stop':threading.Event()})
            runtime.assert_not_called()


if __name__=='__main__':unittest.main()
