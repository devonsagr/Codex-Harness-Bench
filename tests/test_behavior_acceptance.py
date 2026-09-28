import copy
import json
from pathlib import Path
import unittest
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch
from chb.arena.behavior import VERSION, PROBES, COMMON, task_key, check_definition, summarize, screenshot
from chb.arena.builtin_tasks import creative_web_catalog, creative_prompt
from chb.arena.files import fingerprint

ROOT=Path(__file__).resolve().parents[1]


class BehaviorAcceptanceTests(unittest.TestCase):
    def setUp(self):
        entry=next(e for e in creative_web_catalog(ROOT) if e['id']=='pixel-postcard-v1')
        self.task={'id':'original-creative-'+entry['id'],'revision':1,'sourceKind':'repository-original',
                   'inputPrompt':creative_prompt(entry),'stages':[{'prompt':creative_prompt(entry)}],'checks':[]}
        self.capture={'id':'capture-fixture','manifest':{'sha256':'fixture'},'checks':[]}

    def report(self):
        body={'version':VERSION,'task':'pixel-postcard-v1','rows':[
            {'id':key,'status':'passed','detail':'observed','evidence':{'before':'a','after':'b'}}
            for key in {**PROBES['pixel-postcard-v1'],**COMMON}]}
        report={'captureHash':'fixture','taskHash':fingerprint(self.task),'imageId':'sha256:fixed',
                'status':'passed','output':json.dumps(body),'at':'fixture'}
        self.capture['behaviorChecks']=[report]
        return body,report

    def test_only_unchanged_known_task_contract_is_eligible(self):
        self.assertEqual(task_key(self.task,ROOT),'pixel-postcard-v1')
        for changes in [{'revision':2},{'sourceKind':'custom'},{'inputPrompt':'other'},
                        {'stages':[{'prompt':'other'}]},{'stages':[]},{'inputPrompt':self.task['inputPrompt']+' extra'}]:
            self.assertIsNone(check_definition({**self.task,**changes},ROOT))

    def test_no_report_is_unknown_not_zero(self):
        r=summarize(self.task,self.capture,ROOT)
        self.assertEqual((r['status'],r['passed'],r['failed'],r['unverified']),('incomplete',0,0,7))
        self.assertNotIn('score',r)

    def test_failed_probe_cannot_be_diluted_by_other_passes(self):
        body,report=self.report();body['rows'][0]['status']='failed';report['output']=json.dumps(body)
        r=summarize(self.task,self.capture,ROOT)
        self.assertEqual((r['status'],r['failed'],r['passed']),('failed',1,6))
        self.assertEqual(r['coverage'],100)

    def test_positive_suite_is_not_full_task_score(self):
        self.report();r=summarize(self.task,self.capture,ROOT)
        self.assertEqual(r['status'],'passed');self.assertTrue(r['uncovered'])
        self.assertNotIn('score',r)

    def test_snapshot_and_contract_mismatch_invalidate_all_rows(self):
        _,report=self.report()
        for key in ['captureHash','taskHash']:
            original=report[key];report[key]='other'
            self.assertEqual(summarize(self.task,self.capture,ROOT)['unverified'],7)
            report[key]=original

    def test_environment_failure_truncation_and_missing_rows_never_pass(self):
        body,report=self.report()
        for status in ['failed','timeout','cancelled','error']:
            report['status']=status
            self.assertEqual(summarize(self.task,self.capture,ROOT)['unverified'],7)
        report['status']='passed';report['outputTruncated']=True
        self.assertEqual(summarize(self.task,self.capture,ROOT)['unverified'],7)
        report.pop('outputTruncated');body['rows'].pop();report['output']=json.dumps(body)
        self.assertEqual(summarize(self.task,self.capture,ROOT)['unverified'],7)

    def test_duplicate_ids_unknown_protocol_and_invalid_json_rejected(self):
        body,report=self.report()
        bad=copy.deepcopy(body);bad['rows'][-1]=bad['rows'][0]
        for output in ['{',json.dumps(bad),json.dumps({**body,'version':'other'}),json.dumps({**body,'rows':[None]*7})]:
            report['output']=output
            self.assertEqual(summarize(self.task,self.capture,ROOT)['unverified'],7)

    def test_reading_supplement_does_not_mutate_frozen_reports(self):
        self.report();before=copy.deepcopy((self.task,self.capture))
        summarize(self.task,self.capture,ROOT)
        self.assertEqual(before,(self.task,self.capture))

    def test_container_execution_appends_separate_evidence_and_preserves_ai(self):
        from chb.arena.database import Database
        from chb.arena.jobs import run_checks
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'db.sqlite3')
            capture={**copy.deepcopy(self.capture),'stageIndex':0,'checks':[{'id':'old','status':'passed'}],
                     'behaviorImages':{VERSION:'sha256:fixed'}}
            run=db.save('run',{'id':'r','trials':[{'id':'t','captures':[capture],'reviews':[{'id':'old-ai','score':95}]}]})
            def trial(rid,tid):
                r=db.get('run',rid);return r,r['trials'][0]
            app=SimpleNamespace(root=ROOT,local=Path(tmp),lock=threading.RLock(),db=db,trial=trial,event=lambda *args:None)
            commands=[]
            def shell(args,**kwargs):
                commands.append(args)
                return SimpleNamespace(returncode=0,stdout='container-id' if args[1]=='create' else '0')
            def popen(args,**kwargs):
                kwargs['stdout'].write(b'{"rows":[]}')
                return SimpleNamespace(wait=lambda **kwargs:0,poll=lambda:0)
            control={'stop':threading.Event(),'containers':set()}
            with patch('chb.arena.jobs.verify_snapshot'),patch('chb.arena.jobs.shell',side_effect=shell),patch('chb.cli.pin_image',return_value='sha256:fixed'),patch('chb.arena.jobs.subprocess.Popen',side_effect=popen):
                run_checks(app,'r','t',capture,self.task,control,behavior=True)
                run_checks(app,'r','t',capture,self.task,control,behavior=True)
            saved=db.get('run','r')['trials'][0]
            self.assertEqual(saved['reviews'],[{'id':'old-ai','score':95}])
            self.assertEqual(saved['captures'][0]['checks'],[{'id':'old','status':'passed'}])
            self.assertEqual(len(saved['captures'][0]['behaviorAttempts']),1)
            self.assertEqual(saved['captures'][0]['behaviorChecks'][0]['captureHash'],'fixture')
            self.assertEqual(saved['ownedContainers'],[])
            create=next(args for args in commands if args[1]=='create')
            self.assertEqual(create[create.index('--network')+1],'none')
            self.assertTrue(create[create.index('--mount')+1].endswith('target=/candidate,readonly'))
            self.assertNotIn(str(ROOT),create[create.index('--mount')+1])
            with patch('chb.arena.jobs.verify_snapshot'),patch('chb.cli.pin_image',side_effect=ValueError('missing')):
                with self.assertRaises(ValueError):run_checks(app,'r','t',capture,self.task,control,behavior=True)
            saved=db.get('run','r')['trials'][0]['captures'][0]
            self.assertEqual(saved['behaviorChecks'],[])
            self.assertEqual(len(saved['behaviorAttempts']),2)
            self.assertEqual(summarize(self.task,saved,ROOT)['unverified'],7)

    def test_screenshot_requires_owned_attempt_whitelist_and_matching_content(self):
        import base64
        from chb.arena.files import hash_bytes
        with tempfile.TemporaryDirectory() as tmp:
            raw=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aMioAAAAASUVORK5CYII=')
            name=hash_bytes(raw)+'.png'
            folder=Path(tmp)/'runs/r/t/behavior-checks/behavior-test/artifacts';folder.mkdir(parents=True)
            (folder/name).write_bytes(raw)
            row={'attemptId':'behavior-test','images':[name]}
            app=SimpleNamespace(local=Path(tmp),trial=lambda *args:({}, {'captures':[{'behaviorChecks':[row]}]}))
            data={'attemptId':'behavior-test','path':name}
            self.assertTrue(screenshot(app,'r','t',data)['image'].startswith('data:image/png;base64,'))
            for bad in [{**data,'path':'../../secret'},{**data,'attemptId':'other'}]:
                with self.assertRaises(ValueError):screenshot(app,'r','t',bad)
            (folder/name).write_bytes(raw+b'changed')
            with self.assertRaisesRegex(ValueError,'哈希'):screenshot(app,'r','t',data)


if __name__=='__main__':unittest.main()
