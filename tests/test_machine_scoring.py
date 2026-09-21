import copy
import json
import os
from pathlib import Path
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

from chb.arena.service import Arena
from chb.arena.scoring import MACHINE_POLICY, policy
from chb.arena.machine import evidence_key, validate_machine
from chb.arena.jobs import start_job


class MachineScoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'catalog').mkdir();(self.root/'catalog/arena-tasks.json').write_text('[]')
        (self.root/'home').mkdir();self.env=patch.dict(os.environ,{'CODEX_HOME':str(self.root/'home')});self.env.start()
        self.app=Arena(self.root)
        c=self.app.save_config({'name':'Fixture','agentsPrompt':'','baseModel':'fixture','reasoning':'low','interactiveMode':'adaptive','skills':[]})
        self.task=self.app.save_task({'title':'No-script fixture','inputPrompt':'Print hello','schemaVersion':2,'hasFrontendUI':False,
            'taskParadigm':'open-ended-project','channel':'deepswe-core','stages':[{'title':'Deliver','prompt':'Print hello'}],
            'criteria':[{'id':'hello','label':'Print hello','required':True,'dimension':'intent'}],'checks':[]})
        self.policy={**copy.deepcopy(MACHINE_POLICY),'dimensions':{'intent':80,'handoff':20},
                     'rubrics':{k:MACHINE_POLICY['rubrics'][k] for k in ['intent','handoff']}}
        self.run=self.app.prepare({'requestId':'machine','configIds':[c['id']],'taskIds':[self.task['id']],'policy':self.policy})
        self.rid=self.run['id'];self.tid=self.run['trials'][0]['id']
        Path(self.run['trials'][0]['workspacePath'],'main.py').write_text('print("hello")\n')
        self.app.mutate(self.rid,self.tid,'capture',{});self.app.mutate(self.rid,self.tid,'complete',{})
        self.capture=self.current()['captures'][-1]
        self.packet={'policy':self.policy,'task':self.task,'files':{'main.py':'print("hello")\n'},'checks':[],
                     'evidenceKey':evidence_key(self.capture)}
        self.commands=[{'id':'cmd1','command':'python3 main.py','output':'hello\n','exitCode':0}]
        self.value={'summary':'Fixture report','findings':[],
            'ratings':{k:{'score':80,'method':'runtime','reason':'Observed hello output','evidence':[{'command':'python3 main.py','quote':'hello'}]} for k in ['intent','handoff']},
            'criteria':{'hello':{'status':'met','notes':'Executed','evidence':[{'command':'python3 main.py','quote':'hello'}]}}}

    def tearDown(self):self.env.stop();self.tmp.cleanup()

    def test_judge_unsupported_tier_does_not_start_job(self):
        (self.root/'home/models_cache.json').write_text(json.dumps({'models':[
            {'slug':'fixture','supported_reasoning_levels':[{'effort':'max'}]}]}))
        before=self.current()['state']
        with self.assertRaisesRegex(ValueError,'不支持 ultra'):
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture','reasoningEffort':'ultra'})
        self.assertEqual(self.current()['state'],before)
        self.assertFalse(self.app.jobs)

    def test_progress_tracks_commands_not_reasoning_and_redacts_credentials(self):
        from chb.arena.api import post
        folder=self.app.local/'runs'/self.rid/self.tid/'reviews/job-fixture'
        folder.mkdir(parents=True)
        events=[{'type':'item.started','item':{'id':'cmd1','type':'command_execution','command':'run tests'}},
                {'type':'item.completed','item':{'id':'cmd1','type':'command_execution','command':'run tests',
                    'aggregated_output':'passed api_key=secret Bearer abc123','exit_code':0}},
                {'type':'item.completed','item':{'id':'thought','type':'reasoning','text':'private reasoning'}}]
        (folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n{"unfinished":')
        route=f'/api/arena/runs/{self.rid}/trials/{self.tid}/judge-progress'
        result=post(self.app,route,{})
        self.assertEqual(len(result['commands']),1)
        self.assertEqual(result['commands'][0]['status'],'completed')
        serialized=json.dumps(result)
        for value in ['secret','abc123','private reasoning']:self.assertNotIn(value,serialized)
        self.assertIn('[redacted]',serialized)
        run=self.app.db.get('run',self.rid)
        run['trials'][0]['judgeExecution']={'status':'preparing'}
        self.app.db.save('run',run,run['revision'])
        self.assertEqual(post(self.app,route,{})['commands'],[])
        with self.assertRaises(ValueError):post(self.app,f'/api/arena/runs/{self.rid}/trials/not-owned/judge-progress',{})

    def test_interrupted_judge_never_remains_running_after_restart(self):
        run=self.app.db.get('run',self.rid)
        run['trials'][0].update(state='judging',judgeExecution={'status':'running','jobId':'job-fixture'})
        self.app.db.save('run',run,run['revision'])
        restarted=Arena(self.root)
        trial=restarted.db.get('run',self.rid)['trials'][0]
        self.assertEqual(trial['judgeExecution']['status'],'interrupted')
        self.assertEqual(trial['state'],'captured')
    def current(self):return self.app.present_run(self.app.db.get('run',self.rid))['trials'][0]
    def report(self,identifier='ai-1',value=None):
        report=validate_machine(value or self.value,self.packet,self.commands)
        run=self.app.db.get('run',self.rid)
        run['trials'][0]['reviews'].append({'id':identifier,'kind':'ai','at':'fixture','captureId':self.capture['id'],**report})
        self.app.db.save('run',run,run['revision']);return self.current()
    def correct(self,score=90,**patches):
        score_data=self.current()['score']
        return self.app.mutate(self.rid,self.tid,'machine-correction',{'reviewId':score_data['machineReviewId'],
            'evidenceKey':score_data['machineEvidenceKey'],'changes':{'intent':{'score':score,'reason':'Manual reproduction fixture'}},**patches})['trials'][0]

    def test_no_script_machine_score_and_no_mandatory_human(self):
        self.assertEqual(policy(self.policy)['version'],'arena-machine-v1')
        t=self.report();self.assertEqual(t['score']['overall'],80);self.assertIsNone(t['score']['human'])
        self.assertEqual(t['score']['machineCoverage'],100);self.assertEqual(t['score']['acceptance']['status'],'met')

    def test_zero_is_score_unknown_is_partial_and_completion_required(self):
        value=copy.deepcopy(self.value);value['ratings']['intent']['score']=0
        value['ratings']['handoff']={'score':None,'method':'unverified','reason':'Missing evidence','evidence':[]}
        t=self.report(value=value);self.assertEqual(t['score']['machine'],0);self.assertEqual(t['score']['machineCoverage'],80)
        self.assertIsNone(t['score']['overall'])
        self.report('ai-2')
        run=self.app.db.get('run',self.rid);run['trials'][0]['state']='captured';self.app.db.save('run',run,run['revision'])
        self.assertIsNone(self.current()['score']['overall'])

    def test_correction_preserves_machine_and_undo(self):
        self.report();t=self.correct(100)
        self.assertEqual(t['score']['overall'],96);self.assertEqual(t['score']['machine'],80)
        self.assertEqual(t['reviews'][-1]['ratings']['intent']['score'],80)
        t=self.correct(None);self.assertEqual(t['score']['overall'],80);self.assertEqual(len(t['machineCorrections']),2)

    def test_partial_unknown_can_be_manually_reviewed_without_faking_machine_coverage(self):
        value=copy.deepcopy(self.value);value['ratings']['intent']={'score':None,'method':'unverified','reason':'Not run','evidence':[]}
        self.report(value=value);t=self.correct(100)
        self.assertEqual(t['score']['overall'],96);self.assertEqual(t['score']['machineCoverage'],20)

    def test_rejudge_invalidates_corrections_and_stale_submission(self):
        self.report();self.correct();t=self.report('ai-2')
        self.assertEqual(t['score']['overall'],80);self.assertEqual(t['score']['machineOverrides'],{})
        with self.assertRaisesRegex(ValueError,'已变化'):self.correct(reviewId='ai-1')

    def test_new_capture_and_rerun_checks_invalidate_machine_evidence(self):
        self.report();self.correct()
        run=self.app.db.get('run',self.rid);run['trials'][0]['captures'][-1]['checks']=[{'id':'new','status':'passed'}]
        self.app.db.save('run',run,run['revision']);self.assertIsNone(self.current()['score']['machine'])
        self.app.mutate(self.rid,self.tid,'capture',{});self.assertIsNone(self.current()['score']['machine'])

    def test_invalid_score_evidence_and_missing_dimensions_rejected(self):
        for field,bad in [('score',float('nan')),('score',True),('score',101),('evidence',[]),('method','unverified')]:
            value=copy.deepcopy(self.value);value['ratings']['intent'][field]=bad
            with self.assertRaises(ValueError):validate_machine(value,self.packet,self.commands)
        value=copy.deepcopy(self.value);del value['ratings']['handoff']
        with self.assertRaises(ValueError):validate_machine(value,self.packet,self.commands)

    def test_fabricated_command_and_source_citations_rejected(self):
        for ref in [{'command':'pytest','quote':'hello'},{'command':'python3 main.py','quote':'all passed'},
                    {'path':'missing.py','line':1,'quote':'hello'},{'path':'main.py','line':2,'quote':'fabricated'}]:
            value=copy.deepcopy(self.value);value['ratings']['intent']['evidence']=[ref]
            report=validate_machine(value,self.packet,self.commands)
            self.assertIsNone(report['ratings']['intent']['score'])
            self.assertEqual(report['ratings']['handoff']['score'],80)
            self.assertEqual(len(report['validationWarnings']),1)

    def test_visual_score_requires_execution_evidence(self):
        packet=copy.deepcopy(self.packet);packet['task']['hasFrontendUI']=True
        packet['policy']['dimensions']={'ux':100}
        value=copy.deepcopy(self.value);value['ratings']={'ux':{'score':80,'method':'static','reason':'Read code','evidence':[{'path':'main.py','line':1,'quote':'hello'}]}}
        with self.assertRaisesRegex(ValueError,'实际运行'):validate_machine(value,packet,self.commands)

    def test_correction_requires_reason_and_rejects_busy(self):
        self.report()
        with self.assertRaises(ValueError):self.correct(changes={'intent':{'score':90,'reason':''}})
        run=self.app.db.get('run',self.rid);run['trials'][0]['state']='judging';self.app.db.save('run',run,run['revision'])
        with self.assertRaises(ValueError):self.correct()

    def test_job_no_scripts_uses_judge_and_saves_machine_report(self):
        report=validate_machine(self.value,self.packet,self.commands)
        with patch('chb.arena.jobs.run_judge',return_value=report) as judge,patch('chb.arena.jobs.run_checks') as checks:
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture'})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
            judge.assert_called_once();checks.assert_not_called()
        self.assertFalse(self.app.jobs);self.assertEqual(self.current()['score']['overall'],80)

    def test_failed_judge_does_not_invent_score(self):
        with patch('chb.arena.jobs.run_judge',side_effect=ValueError('机器环境未就绪')):
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture'})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
        t=self.current();self.assertIsNone(t['score']['overall']);self.assertEqual(t['state'],'completed')
        self.assertIn('未就绪',t['lastJobError']['message'])

    def test_harbor_packet_and_real_event_parser_without_model_call(self):
        from chb.arena.jobs import run_judge
        test=self
        class JobFixture:
            async def run(self):
                pass
        async def create(cfg):
            import tomllib
            source=Path(cfg.tasks[0].path)
            definition=tomllib.loads((source/'task.toml').read_text(encoding='utf-8'))
            test.assertEqual(definition['environment']['docker_image'],'sha256:fixture')
            test.assertEqual(definition['environment']['workdir'],'/app')
            test.assertEqual(definition['agent']['timeout_sec'],480)
            test.assertEqual((source/'environment/candidate/main.py').read_text(),'print("hello")\n')
            test.assertFalse((source/'environment/Dockerfile').exists())
            test.assertIn('ratings',(source/'instruction.md').read_text(encoding='utf-8'))
            line_map=json.loads((source/'environment/source-lines.json').read_text(encoding='utf-8'))
            test.assertEqual(line_map['main.py'],[{'line':1,'text':'print("hello")'}])
            test.assertIn('/app/source-lines.json',(source/'instruction.md').read_text(encoding='utf-8'))
            logs=Path(cfg.jobs_dir)/'fixture/agent';logs.mkdir(parents=True)
            events=[{'type':'item.completed','item':{'id':'cmd1','type':'command_execution','command':'python3 main.py','aggregated_output':'hello\n','exit_code':0}},
                    {'type':'item.completed','item':{'type':'agent_message','text':json.dumps(test.value)}}]
            (logs/'codex.txt').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
            return JobFixture()
        with patch('chb.cli.pin_image',return_value='sha256:fixture'),patch('harbor.job.Job.create',side_effect=create):
            report=run_judge(self.app,self.rid,self.tid,self.capture,self.task,{'model':'fixture'},{'stop':threading.Event()})
        self.assertEqual(report['scoreSchema'],'arena-machine-v1');self.assertEqual(report['scores']['intent'],80)
        self.assertEqual(report['commands'][0]['output'],'hello\n')

    def test_missing_optional_verifier_still_allows_machine_review(self):
        run=self.app.db.get('run',self.rid);run['tasks'][0]['checks']=[{'id':'c','label':'optional','image':'fixture','argv':['true'],'weight':1}]
        self.app.db.save('run',run,run['revision'])
        report=validate_machine(self.value,self.packet,self.commands)
        with patch('chb.arena.jobs.run_checks',side_effect=ValueError('无法读取检查镜像')),patch('chb.arena.jobs.run_judge',return_value=report) as judge:
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture'})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
            judge.assert_called_once()
        self.assertEqual(self.current()['score']['machine'],80)

    def test_windows_newlines_match_but_fabricated_text_still_fails(self):
        commands=[{'id':'x','command':'python3 main.py','output':'hello\r\nexit=0\r\n','exitCode':0}]
        value=copy.deepcopy(self.value)
        value['ratings']['intent']['evidence']=[{'command':'python3 main.py','quote':'hello\nexit=0'}]
        self.assertEqual(validate_machine(value,self.packet,commands)['ratings']['intent']['score'],80)
        value['ratings']['intent']['evidence'][0]['quote']='hello\nexit=1'
        self.assertIsNone(validate_machine(value,self.packet,commands)['ratings']['intent']['score'])

    def test_local_judge_never_runs_docker_checks(self):
        run=self.app.db.get('run',self.rid);run['tasks'][0]['checks']=[{'id':'c','label':'check','image':'fixture','argv':['true'],'weight':1}]
        self.app.db.save('run',run,run['revision'])
        with patch('chb.arena.jobs.run_checks') as checks,patch('chb.arena.jobs.run_judge',return_value=validate_machine(self.value,self.packet,self.commands)):
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture','environment':'local'})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
            checks.assert_not_called()

    def test_review_packet_only_contains_captured_stage_prompts(self):
        from chb.arena.jobs import review_packet
        task={**self.task,'stages':[{'title':'Now','prompt':'now'},{'title':'Future','prompt':'future'}],
              'promptSnapshots':[{'text':'sent'},{'text':'not yet sent'}]}
        run=self.app.db.get('run',self.rid);run['trials'][0].pop('finalCaptureId',None);self.app.db.save('run',run,run['revision'])
        packet=review_packet(self.app,self.rid,self.tid,{**self.capture,'stageIndex':0},task)
        self.assertEqual(packet['stageIndex'],0)
        self.assertEqual(packet['evaluationScope'],{'kind':'stage','stageIndex':0,'totalStages':2,'stageTitle':task['stages'][0].get('title')})
        self.assertEqual(packet['task']['promptSnapshots'],[{'text':'sent'}])
        self.assertEqual(len(task['stages']),2)

    def test_wrong_line_resolves_only_exact_unique_quote_and_keeps_original(self):
        value=copy.deepcopy(self.value)
        value['ratings']['intent']['method']='static'
        value['ratings']['intent']['evidence']=[{'path':'main.py','line':124,'quote':'hello'}]
        report=validate_machine(value,self.packet,self.commands)
        ref=report['ratings']['intent']['evidence'][0]
        self.assertEqual((ref['line'],ref['reportedLine']),(1,124))
        packet=copy.deepcopy(self.packet);packet['files']['main.py']+='print("hello")\n'
        report=validate_machine(value,packet,self.commands)
        self.assertIsNone(report['ratings']['intent']['score'])
        self.assertIn('唯一定位',report['validationWarnings'][0]['message'])

    def test_early_completion_requires_fresh_full_scope_and_keeps_history(self):
        from chb.arena.jobs import review_packet
        run=self.app.db.get('run',self.rid)
        run['tasks'][0]['stages'].append({'id':'second','title':'Extra','prompt':'extra'})
        run['tasks'][0]['promptSnapshots'].append({'text':'not sent'})
        trial=run['trials'][0];trial['state']='captured';trial.pop('finalCaptureId',None)
        self.app.db.save('run',run,run['revision'])
        self.report();self.assertEqual(self.current()['score']['machine'],80)
        result=self.app.mutate(self.rid,self.tid,'complete',{})
        trial=result['trials'][0]
        self.assertEqual(trial['stageIndex'],0)
        self.assertEqual(len(trial['reviews']),1)
        self.assertIsNone(trial['score']['overall'])
        self.assertIsNone(trial['score']['machineReviewId'])
        packet=review_packet(self.app,self.rid,self.tid,self.capture,result['tasks'][0])
        self.assertEqual(packet['evaluationScope']['kind'],'final')
        self.assertEqual(len(packet['task']['promptSnapshots']),1)
        report=validate_machine(self.value,self.packet,self.commands)
        report['evaluationScope']=packet['evaluationScope']
        with patch('chb.arena.jobs.run_judge',return_value=report):
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture','environment':'local'})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(self.current()['score']['overall'],80)
        self.app.mutate(self.rid,self.tid,'capture',{})
        self.assertNotIn('finalCaptureId',self.current())
        self.assertIsNone(self.current()['score']['overall'])

    def test_intermediate_review_does_not_create_final_score(self):
        run=self.app.db.get('run',self.rid)
        run['tasks'][0]['stages'].append({'id':'stage-2','title':'Next','prompt':'Future requirement'})
        run['trials'][0]['state']='captured';run['trials'][0].pop('finalCaptureId',None)
        self.app.db.save('run',run,run['revision'])
        self.report()
        self.assertEqual(self.current()['score']['machine'],80)
        self.assertIsNone(self.current()['score']['overall'])
