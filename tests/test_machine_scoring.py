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
from chb.arena.scoring import MACHINE_POLICY, AUTO_MACHINE_POLICY, policy
from chb.arena.machine import dimensions, evidence_key, validate_machine, policy_for_task, calculate_machine, score_assurance
from chb.arena.jobs import start_job


class MachineScoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'catalog').mkdir();(self.root/'catalog/arena-tasks.json').write_text('[]')
        (self.root/'home').mkdir();self.env=patch.dict(os.environ,{'CODEX_HOME':str(self.root/'home')});self.env.start()
        (self.root/'home/models_cache.json').write_text(json.dumps({'models':[{'slug':'fixture','supported_reasoning_levels':[{'effort':'low'},{'effort':'max'}]}]}))
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

    def test_new_mixed_batch_freezes_automatic_per_task_profiles(self):
        web=self.app.save_task({'title':'Web fixture','inputPrompt':'Build a page','schemaVersion':2,
            'hasFrontendUI':True,'taskFamily':'web-interface','taskParadigm':'open-ended-project',
            'channel':'frontend-ui','stages':[{'title':'Deliver','prompt':'Build a page'}],
            'criteria':[{'id':'page','label':'Page works','required':True,'dimension':'intent'}],'checks':[]})
        config=self.app.db.list('config')[0]
        run=self.app.prepare({'requestId':'auto-mixed','configIds':[config['id']],
                              'taskIds':[self.task['id'],web['id']],'policy':AUTO_MACHINE_POLICY})
        self.assertEqual(run['projectScorecardVersion'],'project-tasktype-v3')
        self.assertTrue(run['policy']['taskTypeAuto'])
        frozen={task['id']:task for task in run['tasks']}
        self.assertNotIn('visual',dimensions(run['policy'],frozen[self.task['id']]))
        self.assertEqual(dimensions(run['policy'],frozen[web['id']])['visual'],5)
        self.assertEqual(dimensions(run['policy'],frozen[web['id']])['reasoning'],5)
        old_policy={key:value for key,value in run['policy'].items() if key!='autoScorecardVersion'}
        self.assertNotIn('reasoning',dimensions(old_policy,frozen[web['id']]))

    def test_auto_batch_allows_independent_task_weights(self):
        second=self.app.save_task({'title':'Second fixture','inputPrompt':'Build another feature','schemaVersion':2,
            'hasFrontendUI':False,'taskParadigm':'open-ended-project','channel':'deepswe-core',
            'criteria':[{'id':'feature','label':'Feature works','required':True,'dimension':'intent'}],'checks':[]})
        config=self.app.db.list('config')[0]
        override={'dimensions':{'intent':70,'robustness':30},
                  'rubrics':{key:copy.deepcopy(AUTO_MACHINE_POLICY['rubrics'][key]) for key in ['intent','robustness']}}
        selected={**copy.deepcopy(AUTO_MACHINE_POLICY),'taskOverrides':{self.task['id']:override}}
        run=self.app.prepare({'requestId':'per-task-auto','configIds':[config['id']],
                              'taskIds':[self.task['id'],second['id']],'policy':selected})
        frozen={task['id']:task for task in run['tasks']}
        self.assertEqual(dimensions(run['policy'],frozen[self.task['id']]),override['dimensions'])
        self.assertEqual(policy_for_task(run['policy'],frozen[self.task['id']])['rubrics'],override['rubrics'])
        self.assertEqual(dimensions(run['policy'],frozen[second['id']])['instruction'],10)
        completed=copy.deepcopy(self.current())
        completed['reviews'].append({'id':'review-override','captureId':self.capture['id'],
            'scoreSchema':'arena-machine-v1','evidenceKey':evidence_key(self.capture),
            'ratings':{'intent':{'score':80},'robustness':{'score':20}}})
        card=calculate_machine(run,completed)['taskScorecard']
        self.assertEqual(card['version'],'project-policy-v1')
        self.assertEqual(card['overall'],62)
        with self.assertRaisesRegex(ValueError,'未选择'):
            self.app.prepare({'requestId':'unknown-override','configIds':[config['id']],
                              'taskIds':[second['id']],'policy':selected})
        visual={**copy.deepcopy(AUTO_MACHINE_POLICY),'taskOverrides':{second['id']:{
            'dimensions':{'visual':100},'rubrics':{'visual':copy.deepcopy(AUTO_MACHINE_POLICY['rubrics']['visual'])}}}}
        with self.assertRaisesRegex(ValueError,'非视觉'):
            self.app.prepare({'requestId':'visual-only-override','configIds':[config['id']],
                              'taskIds':[second['id']],'policy':visual})
        visual['taskOverrides'][second['id']]['dimensions']={'visual':100,'intent':0}
        visual['taskOverrides'][second['id']]['rubrics']['intent']=copy.deepcopy(AUTO_MACHINE_POLICY['rubrics']['intent'])
        with self.assertRaisesRegex(ValueError,'非视觉'):
            self.app.prepare({'requestId':'zero-nonvisual-override','configIds':[config['id']],
                              'taskIds':[second['id']],'policy':visual})

    def test_public_local_card_requires_quality_rubric_before_workspace_creation(self):
        task=self.app.db.get('task',self.task['id'])
        task['publicSource']={'id':'anko-default-function-arguments','category':'feature'}
        self.app.db.save('task',task,task['revision'])
        config=self.app.db.list('config')[0]
        before={row['id'] for row in self.app.db.list('run')}
        with self.assertRaisesRegex(ValueError,'可维护性'):
            self.app.prepare({'requestId':'public-no-quality','configIds':[config['id']],
                              'taskIds':[task['id']],'policy':self.policy})
        self.assertEqual({row['id'] for row in self.app.db.list('run')},before)

    def test_judge_unsupported_tier_does_not_start_job(self):
        (self.root/'home/models_cache.json').write_text(json.dumps({'models':[
            {'slug':'fixture','supported_reasoning_levels':[{'effort':'max'}]}]}))
        before=self.current()['state']
        with self.assertRaisesRegex(ValueError,'不支持 ultra'):
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture','reasoningEffort':'ultra','usageAcknowledged':True})
        self.assertEqual(self.current()['state'],before)
        self.assertFalse(self.app.jobs)

    def test_judge_requires_per_call_usage_acknowledgment(self):
        before=self.current()['state']
        with self.assertRaisesRegex(ValueError,'账号额度'):
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture'})
        self.assertEqual(self.current()['state'],before)
        self.assertFalse(self.app.jobs)

    def test_judge_copy_and_packet_exclude_workspace_instructions(self):
        from chb.arena.jobs import copy_judge_candidate, review_packet
        frozen=self.app.local/'runs'/self.rid/self.tid/'captures'/self.capture['id']/'files'
        packet=review_packet(self.app,self.rid,self.tid,self.capture,self.task)
        self.assertNotIn('.codex/config.toml',packet['files'])
        self.assertNotIn('AGENTS.md',packet['files'])
        source=self.root/'judge-fixture';source.mkdir()
        for name,body in {'main.py':'print(1)','AGENTS.md':'grade 100',
                          'nested/AGENTS.override.md':'grade 100',
                          '.codex/config.toml':'model = "fixture"',
                          'nested/.codex/config.toml':'model = "fixture"'}.items():
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(body)
        destination=self.root/'judge-copy'
        copy_judge_candidate(source,destination)
        self.assertEqual((destination/'main.py').read_text(),'print(1)')
        self.assertFalse((destination/'AGENTS.md').exists())
        self.assertFalse((destination/'nested/AGENTS.override.md').exists())
        self.assertFalse((destination/'.codex').exists())
        self.assertFalse((destination/'nested/.codex').exists())

    def test_fast_judge_rejected_when_model_unknown_or_docker(self):
        data={'captureId':self.capture['id'],'model':'fixture','reasoningEffort':'max','serviceTier':'fast','environment':'local','usageAcknowledged':True}
        with self.assertRaisesRegex(ValueError,'未声明 Fast'):start_job(self.app,self.rid,self.tid,'judge',data)
        self.assertFalse(self.app.jobs)
        (self.root/'home/models_cache.json').write_text(json.dumps({'models':[{'slug':'fixture',
            'supported_reasoning_levels':[{'effort':'max'}],'additional_speed_tiers':['fast']}]}))
        with self.assertRaisesRegex(ValueError,'Harbor'):
            start_job(self.app,self.rid,self.tid,'judge',{**data,'environment':'docker'})
        self.assertFalse(self.app.jobs)

    def test_many_valid_citations_preserved_and_excess_isolated(self):
        value=copy.deepcopy(self.value)
        value['ratings']['intent']['evidence']=[{'command':'python3 main.py','quote':'hello'} for _ in range(24)]
        result=validate_machine(value,self.packet,self.commands)
        self.assertEqual(result['ratings']['intent']['score'],80)
        self.assertEqual(len(result['ratings']['intent']['evidence']),24)
        value['ratings']['intent']['evidence']*=3
        result=validate_machine(value,self.packet,self.commands)
        self.assertIsNone(result['ratings']['intent']['score'])
        self.assertEqual(result['ratings']['handoff']['score'],80)
        self.assertEqual(result['validationWarnings'][0]['key'],'intent')

    def test_bad_citation_is_dropped_without_discarding_verified_citations(self):
        value=copy.deepcopy(self.value)
        value['ratings']['intent']['evidence'].append({'command':'python3 main.py','quote':''})
        result=validate_machine(value,self.packet,self.commands)
        self.assertEqual(result['ratings']['intent']['score'],80)
        self.assertEqual(len(result['ratings']['intent']['evidence']),1)
        self.assertEqual(result['validationWarnings'][0]['key'],'intent')
        value['ratings']['intent']['evidence']=[{'command':'python3 main.py','quote':''}]
        result=validate_machine(value,self.packet,self.commands)
        self.assertIsNone(result['ratings']['intent']['score'])
        self.assertEqual(result['ratings']['handoff']['score'],80)

    def test_saved_failed_local_report_can_be_revalidated_without_model_call(self):
        from chb.arena.api import post
        job='job-fixture'
        folder=self.app.local/'runs'/self.rid/self.tid/'reviews'/job
        folder.mkdir(parents=True)
        value=copy.deepcopy(self.value)
        value['ratings']['intent']['evidence']=[{'command':'python3 main.py','quote':'hello'} for _ in range(24)]
        (folder/'answer.json').write_text(json.dumps(value))
        (folder/'validation-error.json').write_text(json.dumps({'captureId':self.capture['id']}))
        (folder/'events.jsonl').write_text(json.dumps({'type':'item.completed','item':{'id':'cmd1',
            'type':'command_execution','command':'python3 main.py','aggregated_output':'hello\n','exit_code':0}}))
        run=self.app.db.get('run',self.rid)
        trial=run['trials'][0]
        trial['judgeExecution']={'status':'failed','environment':'local','jobId':job,'captureId':self.capture['id'],'model':'fixture','reasoning':'max',
                                 'startedAt':'2026-09-23T00:00:00+00:00','endedAt':'2026-09-23T00:05:00+00:00'}
        trial['lastJobError']={'kind':'judge','message':'评分报告未通过校验：评分引用格式无效。'}
        self.app.db.save('run',run,run['revision'])
        with patch('chb.arena.local_review.execute_local',side_effect=AssertionError('must not call model')):
            result=post(self.app,f'/api/arena/runs/{self.rid}/trials/{self.tid}/judge-revalidate',{})
        self.assertIsNone(result['trials'][0].get('lastJobError'))
        self.assertEqual(result['trials'][0]['reviews'][-1]['ratings']['intent']['score'],80)
        self.assertEqual(result['trials'][0]['reviews'][-1]['revalidatedFrom'],job)
        self.assertEqual(self.app.db.get('run',self.rid)['trials'][0]['judgeExecution']['endedAt'],'2026-09-23T00:05:00+00:00')

    def test_saved_failed_docker_report_can_be_revalidated_without_model_call(self):
        from chb.arena.api import post

        job='job-docker-fixture'
        folder=self.app.local/'runs'/self.rid/self.tid/'reviews'/job
        log=folder/'harbor/review/task/agent/codex.txt'
        log.parent.mkdir(parents=True)
        value=copy.deepcopy(self.value)
        value['ratings']['intent']['evidence'].append({'command':'python3 main.py','quote':''})
        events=[{'type':'item.completed','item':{'id':'cmd1','type':'command_execution','command':'python3 main.py',
                 'aggregated_output':'hello\n','exit_code':0}},
                {'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)+'}'}}]
        log.write_text('\n'.join(json.dumps(event) for event in events),encoding='utf-8')
        (folder/'validation-error.json').write_text(json.dumps({'captureId':self.capture['id']}),encoding='utf-8')
        run=self.app.db.get('run',self.rid)
        trial=run['trials'][0]
        trial['judgeExecution']={'status':'failed','environment':'docker','jobId':job,'captureId':self.capture['id'],
                                 'model':'fixture','reasoning':'max','endedAt':'2026-09-23T00:05:00+00:00'}
        trial['lastJobError']={'kind':'judge','message':'评分报告未通过校验：裁判返回的 JSON 无法解析。'}
        self.app.db.save('run',run,run['revision'])
        with patch('harbor.job.Job.create',side_effect=AssertionError('must not call model')):
            result=post(self.app,f'/api/arena/runs/{self.rid}/trials/{self.tid}/judge-revalidate',{})
        report=result['trials'][0]['reviews'][-1]
        self.assertEqual(report['ratings']['intent']['score'],80)
        self.assertEqual(len(report['ratings']['intent']['evidence']),1)
        self.assertEqual(report['reviewEnvironment'],'docker')
        self.assertEqual(report['revalidatedFrom'],job)
        self.assertEqual(report['reportNormalization'],'single-extra-closing-brace-v1')
        self.assertIsNone(result['trials'][0].get('lastJobError'))

    def test_feedback_revalidation_preserves_prior_evidence_and_combined_usage(self):
        from chb.arena.jobs import revalidate_saved_review
        base=self.app.local/'runs'/self.rid/self.tid/'reviews'
        for name,tokens in [('job-first',10),('job-feedback',7)]:
            folder=base/name;folder.mkdir(parents=True)
            (folder/'answer.json').write_text(json.dumps(self.value),encoding='utf-8')
            events=[{'type':'turn.completed','usage':{'input_tokens':tokens,'output_tokens':1}}]
            if name=='job-first':events.insert(0,{'type':'item.completed','item':{'id':'cmd1',
                'type':'command_execution','command':'python3 main.py','aggregated_output':'hello\n','exit_code':0}})
            (folder/'events.jsonl').write_text('\n'.join(map(json.dumps,events)),encoding='utf-8')
            (folder/'protocol.json').write_text(json.dumps({'captureId':self.capture['id'],
                'previousReviewJobId':'job-first' if name=='job-feedback' else None}),encoding='utf-8')
        (base/'job-feedback/validation-error.json').write_text(json.dumps({'captureId':self.capture['id']}),encoding='utf-8')
        run=self.app.db.get('run',self.rid);trial=run['trials'][0]
        trial['judgeExecution']={'status':'failed','environment':'local','jobId':'job-feedback',
            'captureId':self.capture['id'],'model':'fixture','reasoning':'low',
            'automaticRepair':{'status':'partial','attempts':[{'jobId':'job-first'},{'jobId':'job-feedback'}]}}
        trial['lastJobError']={'kind':'judge','message':'评分报告未通过校验：引用无效。'}
        self.app.db.save('run',run,run['revision'])
        with patch('chb.arena.local_review.execute_local',side_effect=AssertionError('must not call model')):
            result=revalidate_saved_review(self.app,self.rid,self.tid)
        report=result['trials'][0]['reviews'][-1]
        self.assertEqual(report['ratings']['intent']['score'],80)
        self.assertEqual(report['ratings']['intent']['evidence'][0]['commandId'],'prior:cmd1')
        self.assertEqual(report['judgeUsage']['inputTokens'],17)
        self.assertEqual(result['trials'][0]['judgeExecution']['status'],'partial')
        (base/'job-first/protocol.json').write_text(json.dumps({'captureId':'another-capture'}),encoding='utf-8')
        run=self.app.db.get('run',self.rid);run['trials'][0]['judgeExecution']['status']='failed'
        run['trials'][0]['lastJobError']={'kind':'judge','message':'评分报告未通过校验：引用无效。'}
        self.app.db.save('run',run,run['revision'])
        with self.assertRaisesRegex(ValueError,'冻结版本不一致'):revalidate_saved_review(self.app,self.rid,self.tid)

    def test_only_owned_raster_review_artifacts_can_be_previewed(self):
        from chb.arena.api import post
        from chb.arena.jobs import require_visual_artifacts

        self.report()
        folder=self.app.local/'runs'/self.rid/self.tid/'reviews/job-images'
        visual={'ratings':{'visual':{'score':85,'method':'runtime','evidence':[{'commandId':'cmd1'}]}},
                'scores':{'visual':85},'validationWarnings':[]}
        require_visual_artifacts(visual,folder)
        self.assertIsNone(visual['ratings']['visual']['score'])
        image=folder/'harbor/review/task/artifacts/logs/artifacts/page.png'
        image.parent.mkdir(parents=True)
        image.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
        visual={'ratings':{'visual':{'score':85,'method':'runtime','evidence':[{'commandId':'cmd1'}]}},
                'scores':{'visual':85},'validationWarnings':[]}
        require_visual_artifacts(visual,folder)
        self.assertEqual(visual['ratings']['visual']['score'],85)
        (image.parent/'unsafe.svg').write_text('<svg/>',encoding='utf-8')
        run=self.app.db.get('run',self.rid)
        run['trials'][0]['reviews'][-1]['jobPath']=str(folder)
        review_id=run['trials'][0]['reviews'][-1]['id']
        self.app.db.save('run',run,run['revision'])
        route=f'/api/arena/runs/{self.rid}/trials/{self.tid}/judge-screenshots'
        items=post(self.app,route,{'reviewId':review_id})['images']
        self.assertEqual(items,['harbor/review/task/artifacts/logs/artifacts/page.png'])
        self.assertTrue(post(self.app,route,{'reviewId':review_id,'path':items[0]})['image'].startswith('data:image/png;base64,'))
        with self.assertRaises(ValueError):post(self.app,route,{'reviewId':review_id,'path':'../other.png'})
        run=self.app.db.get('run',self.rid)
        run['trials'][0]['reviews']=[]
        run['trials'][0]['judgeExecution']={'status':'budget_exhausted','jobId':'job-images','captureId':self.capture['id']}
        self.app.db.save('run',run,run['revision'])
        self.assertEqual(post(self.app,route,{})['images'],items)

    def test_progress_tracks_commands_not_reasoning_and_redacts_credentials(self):
        from chb.arena.api import post
        folder=self.app.local/'runs'/self.rid/self.tid/'reviews/job-fixture'
        folder.mkdir(parents=True)
        events=[{'type':'item.started','item':{'id':'cmd1','type':'command_execution','command':'run tests'}},
                {'type':'item.completed','item':{'id':'cmd1','type':'command_execution','command':'run tests',
                    'aggregated_output':'passed api_key=secret Bearer abc123','exit_code':0}},
                {'type':'turn.completed','usage':{'input_tokens':120,'cached_input_tokens':80,
                    'output_tokens':30,'reasoning_output_tokens':12}},
                {'type':'item.completed','item':{'id':'thought','type':'reasoning','text':'private reasoning'}}]
        (folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n{"unfinished":')
        route=f'/api/arena/runs/{self.rid}/trials/{self.tid}/judge-progress'
        result=post(self.app,route,{})
        self.assertEqual(len(result['commands']),1)
        self.assertEqual(result['commands'][0]['status'],'completed')
        self.assertEqual(result['usage'],{'inputTokens':120,'cachedInputTokens':80,'outputTokens':30,'reasoningOutputTokens':12})
        serialized=json.dumps(result)
        for value in ['secret','abc123','private reasoning']:self.assertNotIn(value,serialized)
        self.assertIn('[redacted]',serialized)
        run=self.app.db.get('run',self.rid)
        run['trials'][0]['judgeExecution']={'status':'preparing'}
        self.app.db.save('run',run,run['revision'])
        self.assertEqual(post(self.app,route,{})['commands'],[])
        with self.assertRaises(ValueError):post(self.app,f'/api/arena/runs/{self.rid}/trials/not-owned/judge-progress',{})

    def test_cancelled_judge_usage_comes_from_saved_rollout(self):
        from chb.arena.judge_progress import read_judge_usage
        job=self.root/'cancelled-review'
        session=job/'harbor/review/agent/sessions/2026/09/27'
        session.mkdir(parents=True)
        record={'payload':{'type':'token_count','info':{'total_token_usage':{
            'input_tokens':278480,'cached_input_tokens':202624,'output_tokens':6685,'reasoning_output_tokens':2358}}}}
        (session/'rollout-fixture.jsonl').write_text(json.dumps(record)+'\n',encoding='utf-8')
        self.assertEqual(read_judge_usage(job),{'inputTokens':278480,'cachedInputTokens':202624,
                                                'outputTokens':6685,'reasoningOutputTokens':2358})

    def test_interrupted_judge_never_remains_running_after_restart(self):
        run=self.app.db.get('run',self.rid)
        run['trials'][0].update(state='judging',judgeExecution={'status':'running','jobId':'job-fixture'},
            assessmentExecution={'status':'running','phase':'AI取证','captureId':self.capture['id']})
        self.app.db.save('run',run,run['revision'])
        restarted=Arena(self.root)
        trial=restarted.db.get('run',self.rid)['trials'][0]
        self.assertEqual(trial['judgeExecution']['status'],'interrupted')
        self.assertEqual(trial['assessmentExecution']['status'],'interrupted')
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
        self.assertEqual(t['score']['taskScorecard']['version'],'project-policy-v1')
        self.assertEqual([item['key'] for item in t['score']['taskScorecard']['items']],['intent','handoff'])
        self.assertEqual(t['score']['machineCoverage'],100);self.assertEqual(t['score']['acceptance']['status'],'met')
        self.assertEqual(t['score']['assurance'],'ai-reference')

    def test_program_rerun_preserves_ai_report_correction_and_original_check_evidence(self):
        self.report();self.correct()
        run=self.app.db.get('run',self.rid)
        run['tasks'][0]['checks']=[{'id':'smoke','label':'Smoke','image':'fixture','argv':['true'],'weight':1}]
        self.app.db.save('run',run,run['revision'])
        started=threading.Event();release=threading.Event()
        result={'id':'smoke','label':'Smoke','status':'failed','output':'failed fixture','seconds':1,'exitCode':1,'imageId':'fixture'}
        def check(*args):
            started.set();release.wait(3);return [result]
        with patch('chb.arena.jobs.run_checks',side_effect=check),patch('chb.arena.jobs.run_judge') as judge:
            start_job(self.app,self.rid,self.tid,'check',{'captureId':self.capture['id']})
            control=self.app.jobs[(self.rid,self.tid)]
            try:
                self.assertTrue(started.wait(2))
                self.assertEqual(self.current()['score']['machineReviewId'],'ai-1')
                self.assertEqual(self.current()['score']['machineOverrides']['intent']['score'],90)
            finally:release.set();control['thread'].join(3)
            judge.assert_not_called()
        trial=self.current();score=trial['score']
        self.assertEqual(score['machine'],80)
        self.assertEqual(score['machineReviewId'],'ai-1')
        self.assertEqual(score['machineEvidenceKey'],self.packet['evidenceKey'])
        self.assertNotEqual(score['objectiveEvidenceKey'],score['machineEvidenceKey'])
        self.assertTrue(score['machineChecksChanged'])
        self.assertEqual(score['machineCheckEvidence'],[])
        self.assertEqual(score['objective'],0)
        self.assertEqual(score['effectiveScores']['intent'],90)
        self.correct(score=75)
        self.assertEqual(self.current()['score']['effectiveScores']['intent'],75)

    def test_legacy_check_history_recovers_valid_report_without_rewriting_it(self):
        self.report()
        run=self.app.db.get('run',self.rid);capture=run['trials'][0]['captures'][-1]
        saved=copy.deepcopy(run['trials'][0]['reviews'])
        capture['checkAttempts']=[{'at':'earlier','results':[]}]
        capture['checks']=[{'id':'smoke','status':'passed','output':'new observation'}]
        self.app.db.save('run',run,run['revision'])
        score=self.current()['score']
        self.assertEqual(score['machineReviewId'],'ai-1')
        self.assertTrue(score['machineChecksChanged'])
        self.assertEqual(self.app.db.get('run',self.rid)['trials'][0]['reviews'],saved)
        # The history must not make a report valid for modified files.
        run=self.app.db.get('run',self.rid);capture=run['trials'][0]['captures'][-1]
        capture['manifest']['sha256']='changed'
        self.app.db.save('run',run,run['revision'])
        self.assertIsNone(self.current()['score']['machineReviewId'])

    def test_report_with_unknown_check_history_stays_invalid(self):
        self.report()
        run=self.app.db.get('run',self.rid);capture=run['trials'][0]['captures'][-1]
        capture['checks']=[{'id':'smoke','status':'failed'}]
        capture['checkAttempts']=[{'at':'fixture','results':[{'id':'unrelated','status':'passed'}]}]
        self.app.db.save('run',run,run['revision'])
        self.assertIsNone(self.current()['score']['machineReviewId'])

    def test_generic_smoke_cannot_qualify_an_ai_score_for_configuration_comparison(self):
        check={'id':'browser','image':'chb-verifier:creative-web-v1',
               'argv':['node','/tests/verify.cjs','/app','interactive']}
        task={'id':'original-creative-mini-exhibit-3d-v1','sourceKind':'repository-original',
              'revision':1,'stages':[{'id':'stage-1'}],'checks':[check]}
        trial={'captures':[{'checks':[{'id':'browser','status':'passed'}]}]}
        self.assertEqual(score_assurance(task,trial),'ai-reference')
        task['id']='original-web-metrics-v1'
        check['image']='chb-verifier:web-metrics-v1'
        self.assertEqual(score_assurance(task,trial),'task-check-pass')
        task['revision']=2
        self.assertEqual(score_assurance(task,trial),'ai-reference')
        task['revision']=1
        task['stages'].append({'id':'stage-2'})
        self.assertEqual(score_assurance(task,trial),'ai-reference')
        task['stages'].pop()
        trial['captures'].append({'checks':[]})
        self.assertEqual(score_assurance(task,trial),'ai-reference')
        trial['captures'].pop()
        trial['captures'][0]['checks'][0]['status']='failed'
        self.assertEqual(score_assurance(task,trial),'task-check-fail')
        trial['captures'][0]['checks'][0]['status']='error'
        self.assertEqual(score_assurance(task,trial),'ai-reference')
        trial['captures'][0]['checks']=[]
        self.assertEqual(score_assurance(task,trial),'ai-reference')

    def test_visual_presets_do_not_apply_to_non_web_tasks(self):
        selected={**self.policy,'dimensions':{'intent':50,'visual':50},
                  'rubrics':{'intent':self.policy['rubrics']['intent'],'visual':{'label':'视觉构图','description':'查看页面'}}}
        self.assertEqual(dimensions(selected,self.task),{'intent':50})

    def test_zero_is_score_unknown_is_partial_and_full_score_can_be_provisional(self):
        value=copy.deepcopy(self.value);value['ratings']['intent']['score']=0
        value['ratings']['handoff']={'score':None,'method':'unverified','reason':'Missing evidence','evidence':[]}
        t=self.report(value=value);self.assertEqual(t['score']['machine'],0);self.assertEqual(t['score']['machineCoverage'],80)
        self.assertIsNone(t['score']['overall'])
        self.report('ai-2')
        run=self.app.db.get('run',self.rid);run['trials'][0]['state']='captured';self.app.db.save('run',run,run['revision'])
        self.assertEqual(self.current()['score']['overall'],80)
        self.assertTrue(self.current()['score']['provisional'])
        self.assertEqual(self.current()['score']['taskScorecard']['overall'],80)

    def test_public_reward_is_separate_from_unavailable_local_card(self):
        self.report()
        run=self.app.db.get('run',self.rid)
        run['tasks'][0]['publicSource']={'id':'fixture-benchmark','revision':'fixture'}
        trial=run['trials'][0]
        trial['state']='captured'
        self.app.db.save('run',run,run['revision'])
        self.assertIsNone(self.current()['score']['overall'])
        self.assertEqual(self.current()['score']['scoreSource'],'native-verifier')
        run=self.app.db.get('run',self.rid)
        capture=run['trials'][0]['captures'][-1]
        capture['nativeVerifications']=[{'id':'native-stale','captureHash':'wrong','reward':1},
                                        {'id':'native-pass','captureHash':capture['manifest']['sha256'],'reward':1}]
        self.app.db.save('run',run,run['revision'])
        score=self.current()['score']
        self.assertIsNone(score['overall'])
        self.assertEqual(score['nativeReward'],1)
        self.assertEqual(score['nativeVerificationId'],'native-pass')
        self.assertIsNone(score['partialScore'])
        run=self.app.db.get('run',self.rid)
        run['trials'][0]['captures'][-1]['nativeVerifications'].append(
            {'id':'native-fail','captureHash':capture['manifest']['sha256'],'reward':0})
        self.app.db.save('run',run,run['revision'])
        self.assertIsNone(self.current()['score']['overall'])
        self.assertEqual(self.current()['score']['nativeReward'],0)

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
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture','usageAcknowledged':True})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
            judge.assert_called_once();checks.assert_not_called()
        self.assertFalse(self.app.jobs);self.assertEqual(self.current()['score']['overall'],80)

    def test_failed_judge_does_not_invent_score(self):
        with patch('chb.arena.jobs.run_judge',side_effect=ValueError('机器环境未就绪')):
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture','usageAcknowledged':True})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
        t=self.current();self.assertIsNone(t['score']['overall']);self.assertEqual(t['state'],'completed')
        self.assertIn('未就绪',t['lastJobError']['message'])

    def test_one_assessment_runs_native_before_ai_and_keeps_separate_evidence(self):
        native={'id':'native-fixture','reward':0,'captureHash':self.capture['manifest']['sha256']}
        report=validate_machine(self.value,self.packet,self.commands)
        def judge(app,rid,tid,capture,task,data,control,*,deadline):
            self.assertEqual(self.current()['captures'][-1]['nativeVerifications'],[native])
            self.assertEqual(capture['nativeVerifications'],[native])
            self.assertGreater(deadline,time.monotonic())
            self.assertLessEqual(data['timeoutSeconds'],300)
            return report
        with patch('chb.arena.native_verifier.supported',return_value=True),patch('chb.arena.native_verifier.run',return_value=native) as check,patch('chb.arena.jobs.run_judge',side_effect=judge) as review:
            start_job(self.app,self.rid,self.tid,'assess',{'captureId':self.capture['id'],'model':'fixture','environment':'local','timeoutSeconds':300,'usageAcknowledged':True})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
        check.assert_called_once();review.assert_called_once()
        t=self.current();self.assertEqual(t['score']['overall'],80)
        self.assertEqual(t['assessmentExecution']['status'],'completed')
        self.assertEqual(t['reviews'][-1]['assessmentVersion'],'delivery-assessment-v1')

    def test_assessment_reuses_valid_failed_native_result_but_not_another_snapshot(self):
        native={'id':'native-prior','reward':0,'captureHash':self.capture['manifest']['sha256']}
        for stale in (False,True):
            with self.subTest(stale=stale):
                r=self.app.db.get('run',self.rid)
                r['trials'][0]['captures'][-1]['nativeVerifications']=[{**native,'captureHash':'stale' if stale else native['captureHash']}]
                self.app.db.save('run',r,r['revision'])
                with patch('chb.arena.native_verifier.supported',return_value=True),patch('chb.arena.native_verifier.run',return_value=native) as check,patch('chb.arena.jobs.run_judge',return_value=validate_machine(self.value,self.packet,self.commands)):
                    start_job(self.app,self.rid,self.tid,'assess',{'captureId':self.capture['id'],'model':'fixture','environment':'local','usageAcknowledged':True})
                    deadline=time.monotonic()+5
                    while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
                self.assertEqual(check.call_count,int(stale))
                self.assertEqual(len(self.current()['captures'][-1]['nativeVerifications']),2 if stale else 1)

    def test_native_environment_failure_does_not_abort_ai_assessment(self):
        with patch('chb.arena.native_verifier.supported',return_value=True),patch('chb.arena.native_verifier.run',side_effect=ValueError('原题环境未就绪')),patch('chb.arena.jobs.run_judge',return_value=validate_machine(self.value,self.packet,self.commands)) as review:
            start_job(self.app,self.rid,self.tid,'assess',{'captureId':self.capture['id'],'model':'fixture','environment':'local','usageAcknowledged':True})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
        review.assert_called_once();t=self.current()
        self.assertEqual(t['score']['overall'],80);self.assertEqual(t['assessmentExecution']['status'],'completed')
        self.assertEqual(t['nativeExecution']['status'],'failed')
        self.assertFalse(t['captures'][-1].get('nativeVerifications'))

    def test_ai_failure_after_native_preserves_the_program_result(self):
        native={'id':'native-fixture','reward':1,'captureHash':self.capture['manifest']['sha256']}
        with patch('chb.arena.native_verifier.supported',return_value=True),patch('chb.arena.native_verifier.run',return_value=native),patch('chb.arena.jobs.run_judge',side_effect=ValueError('模型额度不足')):
            start_job(self.app,self.rid,self.tid,'assess',{'captureId':self.capture['id'],'model':'fixture','environment':'local','usageAcknowledged':True})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
        t=self.current();self.assertIsNone(t['score']['overall'])
        self.assertEqual(t['captures'][-1]['nativeVerifications'],[native])
        self.assertEqual(t['nativeExecution']['status'],'completed')
        self.assertEqual(t['assessmentExecution']['status'],'failed')
        self.assertEqual(t['lastJobError']['kind'],'assess')

    def test_assessment_requires_one_usage_acknowledgement_before_any_job(self):
        with patch('chb.arena.native_verifier.run') as native,patch('chb.arena.jobs.run_judge') as review:
            with self.assertRaisesRegex(ValueError,'额度'):
                start_job(self.app,self.rid,self.tid,'assess',{'captureId':self.capture['id'],'model':'fixture'})
        native.assert_not_called();review.assert_not_called();self.assertFalse(self.app.jobs)
        self.assertNotIn('assessmentExecution',self.current())

    def test_assessment_budget_stops_program_stage_without_calling_model(self):
        def wait_for_stop(*args):
            control=args[5]
            self.assertTrue(control['stop'].wait(3))
            raise ValueError('已取消本机测试验收。')
        with patch('chb.arena.assessment.timeout_seconds',return_value=1),patch('chb.arena.native_verifier.supported',return_value=True),patch('chb.arena.native_verifier.run',side_effect=wait_for_stop),patch('chb.arena.jobs.run_judge') as review:
            start_job(self.app,self.rid,self.tid,'assess',{'captureId':self.capture['id'],'model':'fixture','environment':'local','usageAcknowledged':True})
            deadline=time.monotonic()+5
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
        review.assert_not_called();t=self.current()
        self.assertEqual(t['assessmentExecution']['status'],'budget_exhausted')
        self.assertIsNone(t['score']['overall']);self.assertEqual(t['state'],'completed')
        self.assertIn('预算',t['lastJobError']['message'])

    def test_feedback_does_not_misclassify_a_missing_counter_as_an_unavailable_environment(self):
        from chb.arena.judge_repair import repair_issues
        result={'ratings':{'robustness':{'score':None,'checks':{
            'coverage':{'score':None,'reason':'此环境的正例已运行，未提供反例引用。'},
            'quality':{'score':None,'reason':'浏览器环境不支持此操作。'},
        }}}}
        issues=repair_issues(result)
        self.assertEqual(len(issues),1);self.assertEqual(issues[0]['facet'],'coverage')

    def test_harbor_packet_and_real_event_parser_without_model_call(self):
        from chb.arena.jobs import run_judge, review_packet
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
            test.assertEqual(definition['agent']['timeout_sec'],3600)
            test.assertEqual((source/'environment/candidate/main.py').read_text(),'print("hello")\n')
            test.assertFalse((source/'environment/candidate/AGENTS.md').exists())
            test.assertFalse((source/'environment/candidate/.codex').exists())
            test.assertFalse((source/'environment/Dockerfile').exists())
            test.assertIn('ratings',(source/'instruction.md').read_text(encoding='utf-8'))
            test.assertLess((source/'instruction.md').stat().st_size,10000)
            packet=json.loads((source/'environment/judge-packet.json').read_text(encoding='utf-8'))
            test.assertEqual(packet['omittedFileCount'],500)
            test.assertNotIn('omittedFiles',packet)
            test.assertNotIn('files',packet)
            line_map=json.loads((source/'environment/source-lines.json').read_text(encoding='utf-8'))
            test.assertEqual(line_map['main.py'],[{'line':1,'text':'print("hello")'}])
            test.assertNotIn('AGENTS.md',line_map)
            test.assertNotIn('.codex/config.toml',line_map)
            test.assertIn('/app/source-lines.json',(source/'instruction.md').read_text(encoding='utf-8'))
            logs=Path(cfg.jobs_dir)/'fixture/agent';logs.mkdir(parents=True)
            # The simulated CLI obeys the new contract; this exercises packet
            # transport, event parsing, citation validation and computed scores.
            value=copy.deepcopy(test.value)
            ref={'command':'python3 main.py','quote':'hello'}
            value['ratings']={key:{'checks':{facet:{'level':3,'method':'runtime','reason':'Fixture observed hello.',
                'evidence':[ref]} for facet in ('coverage','quality','resilience')}} for key in packet['dimensions']}
            value['requirementChecks']={key:{'status':'met','notes':'Fixture matched.','evidence':[ref]}
                for key in packet['scoringContract']['requirements']}
            events=[{'type':'item.completed','item':{'id':'cmd1','type':'command_execution','command':'python3 main.py','aggregated_output':'hello\n','exit_code':0}},
                    {'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}]
            (logs/'codex.txt').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
            return JobFixture()
        def large_packet(*args):
            packet=review_packet(*args)
            packet['omittedFiles']=[f'output/playwright/phone-profile/cache/very-long-generated-file-{index:04d}' for index in range(500)]
            return packet
        with patch('chb.cli.pin_image',return_value='sha256:fixture'),patch('harbor.job.Job.create',side_effect=create),patch('chb.arena.jobs.review_packet',side_effect=large_packet):
            report=run_judge(self.app,self.rid,self.tid,self.capture,self.task,{'model':'fixture'},{'stop':threading.Event()})
        self.assertEqual(report['scoreSchema'],'arena-machine-v1');self.assertEqual(report['scores']['intent'],75)
        self.assertEqual(report['scoringProtocol'],'anchored-observations-v1')
        self.assertEqual(report['commands'][0]['output'],'hello\n')
        self.assertEqual(len(report['judgePromptSha256']),64)
        self.assertEqual(len(report['judgePacketSha256']),64)
        self.assertEqual(json.loads((Path(report['jobPath'])/'protocol.json').read_text(encoding='utf-8'))['instructionSha256'],report['judgePromptSha256'])

    def test_feedback_material_and_prior_commands_cross_both_transports(self):
        from chb.arena.jobs import run_judge
        for environment,target_attempts in [('local',2),('docker',2),('local',3),('docker',3)]:
            with self.subTest(environment=environment,attempts=target_attempts):
                calls=[]
                def emit(folder,source):
                    packet=json.loads((source/'environment/judge-packet.json').read_text(encoding='utf-8'))
                    value=copy.deepcopy(self.value);ref={'command':'python3 main.py','quote':'hello'}
                    value['ratings']={key:{'checks':{facet:{'level':3,'method':'runtime','reason':'Observed hello.',
                        'evidence':[ref]} for facet in ('coverage','quality','resilience')}} for key in packet['dimensions']}
                    value['requirementChecks']={key:copy.deepcopy(value['criteria']['hello']) for key in packet['scoringContract']['requirements']}
                    if len(calls)==1 and target_attempts==3:
                        value['ratings']['intent']['checks']['coverage']['level']=4
                    if not calls:
                        value['ratings']['intent']['checks']['coverage']['level']=4
                        artifacts=folder/'artifacts';artifacts.mkdir()
                        (artifacts/'fixture.png').write_bytes(b'\x89PNG\r\n\x1a\nfixture')
                    else:
                        feedback=json.loads((source/'environment/review-feedback.json').read_text(encoding='utf-8'))
                        self.assertEqual(feedback['issues'][0]['dimension'],'intent')
                        self.assertEqual(feedback['issues'][0]['facet'],'coverage')
                        self.assertTrue((source/'environment/prior-report.json').is_file())
                        prior=json.loads((source/'environment/prior-commands.json').read_text(encoding='utf-8'))
                        self.assertEqual(prior[0]['output'],'hello\n')
                        self.assertEqual(len(feedback['priorImages']),1)
                        self.assertEqual((folder/'artifacts/prior-01.png').read_bytes(),b'\x89PNG\r\n\x1a\nfixture')
                    events=[] if calls else [{'type':'item.completed','item':{'id':'cmd1','type':'command_execution',
                        'command':'python3 main.py','aggregated_output':'hello\n','exit_code':0}}]
                    events.extend([{'type':'turn.completed','usage':{'input_tokens':7 if calls else 10,'output_tokens':1}},
                        {'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}])
                    log=folder/'events.jsonl' if environment=='local' else folder/'harbor/fixture/agent/codex.txt'
                    log.parent.mkdir(parents=True,exist_ok=True);log.write_text('\n'.join(map(json.dumps,events)),encoding='utf-8')
                    (folder/'answer.json').write_text(json.dumps(value),encoding='utf-8')
                    calls.append(folder)
                    return log,json.dumps(value),'fixture-cli'
                def local(folder,source,*_,**kwargs):
                    self.assertIsNotNone(kwargs['absolute_deadline'])
                    return emit(folder,source)
                class JobFixture:
                    async def run(self):pass
                async def create(cfg):
                    source=Path(cfg.tasks[0].path);emit(source.parent,source)
                    return JobFixture()
                with patch('chb.cli.pin_image',return_value='sha256:fixture'),patch('harbor.job.Job.create',side_effect=create),patch('chb.arena.local_review.execute_local',side_effect=local),patch('chb.arena.judge_repair.connection_fingerprint',return_value='fixture'):
                    report=run_judge(self.app,self.rid,self.tid,self.capture,self.task,
                        {'model':'fixture','environment':environment,'timeoutSeconds':600},{'stop':threading.Event()})
                self.assertEqual(len(calls),target_attempts)
                self.assertEqual(report['ratings']['intent']['score'],75)
                self.assertEqual(report['commands'][0]['id'],'prior:'*(target_attempts-1)+'cmd1')
                self.assertEqual(report['judgeUsage']['inputTokens'],10+7*(target_attempts-1))
                self.assertNotEqual(report['judgePromptSha256'],report['judgeFinalInstructionSha256'])
                self.assertEqual(json.loads((calls[0]/'answer.json').read_text())['ratings']['intent']['checks']['coverage']['level'],4)

    def test_browser_profile_is_not_copied_to_blind_judge(self):
        from chb.arena.jobs import judge_visible_file
        self.assertFalse(judge_visible_file('output/playwright/phone-profile/Default/Preferences'))
        self.assertFalse(judge_visible_file('output/playwright/desktop-profile-2/Cache/data_0'))
        self.assertTrue(judge_visible_file('output/playwright/desktop.png'))
        self.assertTrue(judge_visible_file('src/main.ts'))

    def test_missing_optional_verifier_still_allows_machine_review(self):
        run=self.app.db.get('run',self.rid);run['tasks'][0]['checks']=[{'id':'c','label':'optional','image':'fixture','argv':['true'],'weight':1}]
        self.app.db.save('run',run,run['revision'])
        report=validate_machine(self.value,self.packet,self.commands)
        with patch('chb.arena.jobs.run_checks',side_effect=ValueError('无法读取检查镜像')),patch('chb.arena.jobs.run_judge',return_value=report) as judge:
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture','usageAcknowledged':True})
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

    def test_pretty_json_command_accepts_same_object_fragment_only(self):
        output=json.dumps({'desktop':{'phase':'航程暂停','timer':'01:14'},
                           'mobile':{'phase':'救援进行中','timer':'01:15',
                                     'ship':[420,355.37499999999966]}},ensure_ascii=False,indent=2)
        commands=[{'id':'browser','command':'node browser.cjs','output':output,'exitCode':0}]
        value=copy.deepcopy(self.value)
        value['ratings']['intent']['evidence']=[{'command':'node browser.cjs',
            'quote':'"phase": "救援进行中", "timer": "01:15", "ship": [420, 355.37499999999966]'}]
        result=validate_machine(value,self.packet,commands)
        self.assertEqual(result['ratings']['intent']['score'],80)
        self.assertEqual(result['ratings']['intent']['evidence'][0]['anchor'],'json-object-fragment')
        value['ratings']['intent']['evidence'][0]['quote']='"phase": "航程暂停", "timer": "01:15"'
        self.assertIsNone(validate_machine(value,self.packet,commands)['ratings']['intent']['score'])
        value['ratings']['intent']['evidence'][0]['quote']='"timer": "01:15", "phase": "救援进行中"'
        self.assertIsNone(validate_machine(value,self.packet,commands)['ratings']['intent']['score'])

    def test_json_report_repairs_only_one_extra_closing_brace(self):
        from chb.arena.jobs import parse_judge_answer
        self.assertEqual(parse_judge_answer('{"summary":"ok"}'),({'summary':'ok'},None))
        self.assertEqual(parse_judge_answer('{"summary":"ok"}}'),
                         ({'summary':'ok'},'single-extra-closing-brace-v1'))
        for answer in ('{"summary":"ok"}}}', '{"summary":"ok"} commentary', '{"summary":'):
            with self.subTest(answer=answer),self.assertRaises(json.JSONDecodeError):
                parse_judge_answer(answer)

    def test_shell_escaped_command_matches_exact_logged_output(self):
        commands=[{'id':'x','command':'pwsh.exe -Command \'python3  main.py\'','output':'hello\n','exitCode':0}]
        result=validate_machine(self.value,self.packet,commands)
        self.assertEqual(result['ratings']['intent']['score'],80)
        self.assertEqual(result['ratings']['intent']['evidence'][0]['reportedCommand'],'python3 main.py')
        commands[0]['output']='unrelated\n'
        self.assertIsNone(validate_machine(self.value,self.packet,commands)['ratings']['intent']['score'])

    def test_saved_success_with_badly_wrapped_citations_can_be_revalidated(self):
        from chb.arena.jobs import revalidate_saved_review
        job='job-wrapped'
        folder=self.app.local/'runs'/self.rid/self.tid/'reviews'/job
        folder.mkdir(parents=True)
        (folder/'answer.json').write_text(json.dumps(self.value),encoding='utf-8')
        (folder/'events.jsonl').write_text(json.dumps({'type':'item.completed','item':{'id':'cmd1',
            'type':'command_execution','command':"pwsh -Command 'python3  main.py'",'aggregated_output':'hello\n','exit_code':0}}),encoding='utf-8')
        previous=validate_machine(self.value,self.packet,[{'id':'cmd1','command':'unmatched','output':'hello\n','exitCode':0}])
        self.assertTrue(previous['validationWarnings'])
        run=self.app.db.get('run',self.rid)
        trial=run['trials'][0]
        trial['reviews'].append({'id':'ai-previous','kind':'ai','captureId':self.capture['id'],'at':'fixture',
                                  'jobPath':str(folder),**previous})
        trial['judgeExecution']={'status':'completed','environment':'local','jobId':job,
                                 'captureId':self.capture['id'],'model':'fixture','reasoning':'low'}
        self.app.db.save('run',run,run['revision'])
        updated=revalidate_saved_review(self.app,self.rid,self.tid)
        self.assertEqual(updated['trials'][0]['score']['machineCoverage'],100)
        self.assertEqual(updated['trials'][0]['score']['overall'],80)
        self.assertEqual(len(self.app.db.get('run',self.rid)['trials'][0]['reviews']),2)

    def test_local_judge_never_runs_docker_checks(self):
        run=self.app.db.get('run',self.rid);run['tasks'][0]['checks']=[{'id':'c','label':'check','image':'fixture','argv':['true'],'weight':1}]
        self.app.db.save('run',run,run['revision'])
        with patch('chb.arena.jobs.run_checks') as checks,patch('chb.arena.jobs.run_judge',return_value=validate_machine(self.value,self.packet,self.commands)):
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture','environment':'local','usageAcknowledged':True})
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
            start_job(self.app,self.rid,self.tid,'judge',{'captureId':self.capture['id'],'model':'fixture','environment':'local','usageAcknowledged':True})
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
