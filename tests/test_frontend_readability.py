import copy
import json
import unittest
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from chb.arena.frontend_readability import extract, VERSION, PREFIX, FOCUS, CHECK_ID, ARGV, check_definition
from chb.arena.files import fingerprint


class FrontendReadabilityTests(unittest.TestCase):
    def fixture(self):
        task={'checks':[{'id':'browser','image':'chb-verifier:creative-web-v1','argv':['node','/tests/verify.cjs','/app','form']}]}
        view={'version':VERSION,'viewport':{'width':390,'height':800},'sampledText':8,'sampledControls':3,
              'smallestBodyFont':8,'limited':False,'concerns':[{'kind':'small-text','text':'预约说明','selector':'p',
              'role':'body','fontSize':8,'bounds':{'x':24,'y':50,'width':250,'height':12}}]}
        checks=[{'id':'browser','imageId':'sha256:fixture','status':'passed','output':'PASS: browser foundation\n'+PREFIX+json.dumps(view)}]
        return task,checks,view

    def test_foundation_pass_does_not_remove_readability_risks_or_generate_a_grade(self):
        task,checks,_=self.fixture();before=copy.deepcopy(checks)
        result=extract(task,checks)
        self.assertEqual(result['views'][0]['smallestBodyFont'],8)
        self.assertEqual(result['views'][0]['concerns'][0]['kind'],'small-text')
        self.assertEqual(result['views'][0]['checkStatus'],'passed')
        self.assertNotIn('score',result);self.assertTrue(result['scoresAreAdvisory']);self.assertEqual(checks,before)

    def test_no_measurement_or_different_declared_checker_does_not_claim_good_readability(self):
        task,checks,_=self.fixture();checks[0]['output']='PASS: visible heading'
        self.assertIsNone(extract(task,checks))
        task,checks,_=self.fixture();task['checks'][0]['image']='unrelated:fixture'
        self.assertIsNone(extract(task,checks))

    def test_partial_measurements_remain_partial_and_failed_checks_stay_failed(self):
        task,checks,_=self.fixture();checks[0]['status']='failed';checks[0]['output']+='\n'+PREFIX+'{broken'
        result=extract(task,checks)
        self.assertEqual(len(result['views']),1);self.assertEqual(result['views'][0]['checkStatus'],'failed')

    def test_invalid_viewports_and_untrusted_display_values_are_rejected(self):
        for field,value in [('version','another'),('smallestBodyFont',True),('smallestBodyFont',float('nan')),
                            ('viewport',{'width':True,'height':800}),('sampledText',-1),('concerns',[{'kind':'small-text','text':{'not':'text'}}])]:
            with self.subTest(field=field,value=value):
                task,checks,view=self.fixture();view[field]=value;checks[0]['output']=PREFIX+json.dumps(view)
                self.assertIsNone(extract(task,checks))

    def test_frontend_focus_covers_the_users_actual_goal_without_new_weights(self):
        self.assertEqual(set(FOCUS),{'readable','plain_language','usable_flow','appropriate_scope'})
        self.assertIn('文件数',FOCUS['appropriate_scope'])

    def test_fixed_offline_measurement_requires_entry_point_and_bound_task_snapshot(self):
        task={'hasFrontendUI':True,'checks':[]}
        capture={'manifest':{'sha256':'capture-fixture','files':{'index.html':'hash'}}}
        definition=check_definition(task,capture)
        self.assertEqual(definition['argv'],ARGV);self.assertEqual(definition['weight'],0)
        self.assertIsNone(check_definition({**task,'hasFrontendUI':False},capture))
        self.assertIsNone(check_definition(task,{'manifest':{'files':{'app.tsx':'hash'}}}))
        _,checks,_=self.fixture()
        row={**checks[0],'id':CHECK_ID,'argv':ARGV,'captureHash':'capture-fixture','taskHash':fingerprint(task)}
        capture['readabilityChecks']=[row]
        self.assertEqual(extract(task,[],capture)['views'][0]['smallestBodyFont'],8)
        for field in ('captureHash','taskHash','argv'):
            with self.subTest(field=field):
                bad=copy.deepcopy(capture);bad['readabilityChecks'][0][field]='wrong'
                self.assertIsNone(extract(task,[],bad))
        # A configured row with the diagnostic ID is not a platform measurement.
        self.assertIsNone(extract(task,[row],{**capture,'readabilityChecks':[]}))

    def test_measurement_storage_is_separate_from_acceptance_and_old_ai_grades(self):
        from chb.arena.database import Database
        from chb.arena.jobs import run_checks
        with tempfile.TemporaryDirectory() as tmp:
            task={'id':'community-fixture','hasFrontendUI':True,'checks':[]}
            capture={'id':'c','stageIndex':0,'manifest':{'sha256':'hash','files':{'index.html':'file-hash'}},
                     'checks':[{'id':'core','status':'failed'}],'readabilityImages':{CHECK_ID:'sha256:fixed'}}
            db=Database(Path(tmp)/'db.sqlite3')
            db.save('run',{'id':'r','trials':[{'id':'t','captures':[capture],'reviews':[{'id':'old-ai','score':80}]}]})
            def trial(*args):
                r=db.get('run','r');return r,r['trials'][0]
            app=SimpleNamespace(root=Path(tmp),local=Path(tmp),lock=threading.RLock(),db=db,trial=trial,event=lambda *args:None)
            commands=[]
            def shell(args,**kwargs):
                commands.append(args);return SimpleNamespace(returncode=0,stdout='owned-container' if args[1]=='create' else '0')
            _,rows,_=self.fixture()
            def popen(args,**kwargs):
                kwargs['stdout'].write(rows[0]['output'].encode());return SimpleNamespace(wait=lambda **kwargs:0,poll=lambda:0)
            with patch('chb.arena.jobs.verify_snapshot'),patch('chb.arena.jobs.shell',side_effect=shell),patch('chb.cli.pin_image',return_value='sha256:fixed'),patch('chb.arena.jobs.subprocess.Popen',side_effect=popen):
                run_checks(app,'r','t',capture,task,{'stop':threading.Event(),'containers':set()},readability=True)
            saved=trial()[1]
            self.assertEqual(saved['reviews'],[{'id':'old-ai','score':80}])
            self.assertEqual(saved['captures'][0]['checks'],[{'id':'core','status':'failed'}])
            self.assertEqual(extract(task,[],saved['captures'][0])['views'][0]['smallestBodyFont'],8)
            self.assertEqual(saved['ownedContainers'],[])
            create=next(row for row in commands if row[1]=='create')
            self.assertEqual(create[-3:],ARGV);self.assertEqual(create[create.index('--network')+1],'none')
            self.assertTrue(create[create.index('--mount')+1].endswith('target=/candidate,readonly'))

    def test_one_assessment_collects_without_task_verifier_and_reuses_measurements(self):
        from chb.arena.assessment import run_assessment
        from chb.arena.database import Database
        with tempfile.TemporaryDirectory() as tmp:
            task={'id':'custom-fixture','hasFrontendUI':True,'checks':[],'stages':[{'title':'Deliver','prompt':'Build an offline page.'}]}
            capture={'id':'c','stageIndex':0,'manifest':{'sha256':'hash','files':{'index.html':'file-hash'}},'checks':[]}
            db=Database(Path(tmp)/'db.sqlite3')
            db.save('run',{'id':'r','trials':[{'id':'t','captures':[capture],'assessmentExecution':{'steps':[]}}]})
            def trial(*args):
                r=db.get('run','r');return r,r['trials'][0]
            app=SimpleNamespace(root=Path(tmp),local=Path(tmp),lock=threading.RLock(),db=db,trial=trial)
            def check(*args,**kwargs):
                self.assertTrue(kwargs['readability']);_,rows,_=self.fixture()
                capture['readabilityChecks']=[{**rows[0],'id':CHECK_ID,'argv':ARGV,'captureHash':'hash','taskHash':fingerprint(task)}]
            with patch('chb.arena.assessment.verify_snapshot'),patch('chb.arena.jobs.run_checks',side_effect=check) as checks,patch('chb.arena.jobs.run_judge',return_value={}) as judge:
                control={'stop':threading.Event()};data={'environment':'docker','timeoutSeconds':300}
                run_assessment(app,'r','t',capture,task,data,control)
                run_assessment(app,'r','t',capture,task,data,control)
            checks.assert_called_once();self.assertEqual(judge.call_count,2)
            self.assertEqual(capture['checks'],[])

    def test_high_opinion_cannot_ignore_a_measured_sample_but_is_not_auto_downgraded(self):
        from chb.arena.judge_repair import repair_issues
        task,checks,_=self.fixture()
        result={'frontendReadability':extract(task,checks),'ratings':{'ux':{'score':90,'evidence':[{'checkId':'browser','quote':'PASS: browser foundation'}]}}}
        before=copy.deepcopy(result)
        issues=repair_issues(result)
        self.assertEqual(len(issues),1);self.assertEqual(issues[0]['dimension'],'ux')
        self.assertIn('预约说明',issues[0]['reason']);self.assertEqual(result,before)
        result['ratings']['ux']['evidence'].append({'checkId':'browser','quote':'"kind":"small-text","text":"预约说明"'})
        self.assertEqual(repair_issues(result),[])
        result['ratings']['ux']['score']=25;result['ratings']['ux']['evidence']=[]
        self.assertEqual(repair_issues(result),[])


if __name__=='__main__':unittest.main()
