import copy
import os
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
import zipfile
from unittest.mock import patch
from chb.arena.service import Arena, applicable_checks
from chb.arena.api import post, export
from chb.arena.files import snapshot, verify_snapshot, safe_path
from chb.arena.scoring import DEFAULT_POLICY
from chb.arena.telemetry import read_trace
from chb.arena.jobs import validate_judge, start_job
from chb.cli import ROOT

class ArenaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        shutil.copytree(ROOT/'profiles',self.root/'profiles');(self.root/'catalog').mkdir()
        (self.root/'catalog/arena-tasks.json').write_text('[]')
        self.app=Arena(self.root)
        self.task=self.app.save_task({'id':'qa-task','title':'QA two stages','inputPrompt':'Build a text utility','taskParadigm':'open-ended-project','channel':'deepswe-core','hasFrontendUI':False,'stages':[{'title':'Design','prompt':'Design first'},{'title':'Build','prompt':'Implement'}],'checks':[]})
    def tearDown(self):self.tmp.cleanup()
    def prepare(self,**patch):
        return post(self.app,'/api/arena/runs/prepare',{'deliveryMode':'staged','requestId':'qa-1','configIds':['minimal'],'taskIds':[self.task['id']],**patch})
    def mutate(self,r,action,**data):return self.app.mutate(r['id'],r['trials'][0]['id'],action,data)

    def test_default_delivery_contains_all_requirements_without_stage_gate(self):
        run=self.app.prepare({'requestId':'default-delivery','configIds':['minimal'],'taskIds':[self.task['id']]})
        task=run['tasks'][0];prompt=run['trials'][0]['currentStage']['executionPrompt']
        self.assertEqual(task['deliveryMode'],'single-delivery')
        self.assertEqual(len(task['stages']),1)
        self.assertEqual(len(task['authoredStages']),2)
        self.assertIn('Build a text utility',prompt)
        self.assertIn('Design first',prompt);self.assertIn('Implement',prompt)
        self.assertNotIn('当前阶段',prompt)
        self.assertEqual(len(self.app.db.get('task',self.task['id'])['stages']),2)
        run=self.mutate(run,'capture');run=self.mutate(run,'complete')
        self.assertEqual(run['trials'][0]['state'],'completed')
        run=self.mutate(run,'capture')
        self.assertEqual(len(run['trials'][0]['captures']),2)

    def test_single_delivery_keeps_final_checks_not_transient_stage_checks(self):
        from chb.arena.contracts import delivery_task
        task=copy.deepcopy(self.task)
        task['checks']=[{'id':'transient','stageIndex':0},
                        {'id':'regression','stageIndex':0,'runOnFinal':True},
                        {'id':'final','stageIndex':1}]
        result=delivery_task(task,'single-delivery')
        self.assertEqual([c['id'] for c in result['checks']],['regression','final'])
        self.assertTrue(all(c['stageIndex']==0 for c in result['checks']))
        self.assertEqual([c['id'] for c in result['authoredChecks']],[c['id'] for c in task['checks']])
    @unittest.skipUnless(os.name=="nt", "Windows protocol launcher")
    def test_desktop_draft_uses_frozen_prompt_and_does_not_start_execution(self):
        from urllib.parse import urlparse,parse_qs
        r=self.prepare();trial=r['trials'][0]
        with patch('chb.arena.service.os.startfile',create=True) as launch:
            result=self.mutate(r,'open',draft=True)
        url=launch.call_args.args[0];query=parse_qs(urlparse(url).query)
        self.assertTrue(url.startswith('codex://threads/new?'))
        self.assertEqual(query['path'],[str(Path(trial['workspacePath']).resolve())])
        self.assertEqual(query['prompt'],[trial['currentStage']['executionPrompt']])
        self.assertEqual(result['trials'][0]['state'],'prepared')
        self.assertNotIn('startedAt',result['trials'][0])
        with patch('chb.arena.service.os.startfile',side_effect=OSError('unavailable'),create=True):
            with self.assertRaisesRegex(ValueError,'复制本轮提示词'):self.mutate(r,'open',draft=True)

    def test_freeze_single_workspace_and_idempotency(self):
        r=self.prepare();self.assertEqual(r['executionMode'],'desktop');self.assertEqual(len(r['trials']),1)
        self.assertEqual(self.prepare()['id'],r['id'])
        with self.assertRaises(ValueError):self.prepare(notes='different')
        c=self.app.db.get('config','minimal');c['agentsPrompt']='new version';self.app.save_config(c)
        self.assertNotEqual(self.app.db.get('config','minimal')['agentsPrompt'],r['configs'][0]['agentsPrompt'])
        workspace=Path(r['trials'][0]['workspacePath']);self.assertTrue((workspace/'.git').exists());self.assertTrue((workspace/'AGENTS.override.md').exists())
        restored=self.app.restore_config(r['id'],'minimal');self.assertNotEqual(restored['id'],'minimal');self.assertEqual(restored['agentsPrompt'],r['configs'][0]['agentsPrompt'])
    def test_revision_conflict_and_archive(self):
        c=self.app.db.get('config','minimal');self.app.save_config(c)
        with self.assertRaises(ValueError):self.app.save_config(c)
        r=self.prepare();self.app.db.archive('run',r['id'],True,r['revision'])
        self.assertEqual(len(self.app.state()['archivedRuns']),1)
        with self.assertRaises(ValueError):self.mutate(r,'capture')
        self.app.db.archive('run',r['id'],False,r['revision']+1);self.assertEqual(len(self.app.state()['runs']),1)

    def test_history_visibility_preserves_owned_files_and_can_restore(self):
        run=self.prepare()
        work=Path(run['trials'][0]['workspacePath'])
        with self.assertRaisesRegex(ValueError,'确认'):
            post(self.app,f"/api/arena/runs/{run['id']}/history-visibility",{'revision':run['revision'],'hidden':True})
        hidden=post(self.app,f"/api/arena/runs/{run['id']}/history-visibility",{'revision':run['revision'],'hidden':True,'confirmation':'移出历史 '+run['id']})
        self.assertTrue(hidden['historyHidden'])
        self.assertTrue(work.is_dir())
        self.assertTrue(self.app.state()['runs'][0]['historyHidden'])
        restored=post(self.app,f"/api/arena/runs/{run['id']}/history-visibility",{'revision':self.app.db.get('run',run['id'])['revision'],'hidden':False})
        self.assertFalse(restored['historyHidden'])
        self.assertTrue(work.is_dir())
    def test_delete_archived_config_keeps_frozen_run(self):
        r=self.prepare()
        c=self.app.db.get('config','minimal')
        with self.assertRaisesRegex(ValueError,'先归档'):
            post(self.app,'/api/arena/configs/minimal/delete',{'revision':c['revision']})
        archived=post(self.app,'/api/arena/configs/minimal/archive',{'revision':c['revision'],'archived':True})
        with self.assertRaisesRegex(ValueError,'版本已变化'):
            post(self.app,'/api/arena/configs/minimal/delete',{'revision':c['revision']})
        post(self.app,'/api/arena/configs/minimal/delete',{'revision':archived['revision']})
        self.assertEqual(r['configs'][0]['id'],self.app.db.get('run',r['id'])['configs'][0]['id'])
        self.assertFalse(any(c['id']=='minimal' for c in self.app.state()['archivedConfigs']))
        with self.assertRaises(ValueError):self.app.db.get('config','minimal')
    def test_stage_gates_complete_and_capture_immutability(self):
        r=self.prepare();w=Path(r['trials'][0]['workspacePath'])
        with self.assertRaises(ValueError):self.mutate(r,'continue')
        with self.assertRaises(ValueError):self.mutate(r,'start')
        r=self.mutate(r,'start',settingsConfirmed=True)
        (w/'one.txt').write_text('first\n');r=self.mutate(r,'capture',response='draft')
        cap=r['trials'][0]['captures'][-1];self.assertIn('one.txt',cap['manifest']['files']);self.assertTrue(cap['harnessUnchanged'])
        r=self.mutate(r,'continue');self.assertEqual(r['trials'][0]['state'],'waiting_confirmation')
        (w/'one.txt').unlink();(w/'two.txt').write_text('second\n');r=self.mutate(r,'start',settingsConfirmed=True);r=self.mutate(r,'capture')
        r=self.mutate(r,'complete');self.assertEqual(r['trials'][0]['state'],'completed');self.assertIsNone(r['trials'][0]['score']['overall'])
        old=self.app.local/'runs'/r['id']/r['trials'][0]['id']/'captures'/cap['id']/'files'
        self.assertEqual((old/'one.txt').read_text(),'first\n');verify_snapshot(old,cap['manifest'])
        (old/'one.txt').write_text('tamper')
        with self.assertRaises(ValueError):verify_snapshot(old,cap['manifest'])
        with self.assertRaises(ValueError):export(self.app,r['id'])
    def test_human_policy_no_defaults_and_review_binding(self):
        invalid=copy.deepcopy(DEFAULT_POLICY);invalid['dimensions']={k:int(k=='ux')*100 for k in invalid['dimensions']}
        with self.assertRaises(ValueError):self.prepare(policy=invalid)
        pol=copy.deepcopy(DEFAULT_POLICY);pol.update(objectiveWeight=0,humanWeight=100)
        r=self.prepare(policy=pol);r=self.mutate(r,'capture');r=self.mutate(r,'continue');r=self.mutate(r,'capture');r=self.mutate(r,'complete')
        c=r['trials'][0]['captures'][-1]
        with self.assertRaises(ValueError):self.mutate(r,'review',captureId=c['id'])
        r=self.mutate(r,'review',captureId=c['id'],scores={'intent':80,'maintainability':80,'robustness':80},notes='Test evidence',readiness='minor_polish',constraints={})
        self.assertEqual(r['trials'][0]['score']['overall'],80)
        r=self.mutate(r,'capture');self.assertIsNone(r['trials'][0]['score']['human'])
        with self.assertRaises(ValueError):self.mutate(r,'review',captureId=c['id'])
    def test_skill_and_nested_instruction_changes_are_observed(self):
        source=self.root/'example-skill';source.mkdir();(source/'SKILL.md').write_text('Example skill')
        skill=self.app.import_files('skill',{'path':str(source)})
        config=self.app.db.get('config','minimal');config['skills']=[skill['id']];self.app.save_config(config)
        r=self.prepare();w=Path(r['trials'][0]['workspacePath']);r=self.mutate(r,'capture')
        self.assertTrue(r['trials'][0]['captures'][-1]['harnessUnchanged'])
        (w/'.agents/skills/example-skill/SKILL.md').write_text('Changed instructions')
        r=self.mutate(r,'capture');self.assertFalse(r['trials'][0]['captures'][-1]['harnessUnchanged'])
        (w/'.agents/skills/example-skill/SKILL.md').write_text('Example skill')
        (w/'nested').mkdir();(w/'nested/AGENTS.md').write_text('New nested override')
        r=self.mutate(r,'capture');self.assertFalse(r['trials'][0]['captures'][-1]['harnessUnchanged'])
    def test_import_exclusions_export_and_link_boundaries(self):
        source=self.root/'source';source.mkdir();(source/'index.txt').write_text('fixture');(source/'.env').write_text('secret')
        baseline=self.app.import_files('baseline',{'path':str(source)});self.assertEqual(baseline['manifest']['excluded'],['.env'])
        task=self.app.db.get('task',self.task['id']);task['baselineId']=baseline['id'];self.app.save_task(task)
        r=self.prepare();r=self.mutate(r,'capture');bundle=zipfile.ZipFile(io.BytesIO(export(self.app,r['id'])))
        self.assertTrue(any(n.endswith('index.txt') for n in bundle.namelist()));self.assertFalse(any('.env' in n for n in bundle.namelist()))
        for path in ['../x','/outside','a/../../x','C:/x','a\\b']:
            with self.assertRaises(ValueError):safe_path(source,path)
    def test_checks_stage_and_job_failure_preserve_unknown(self):
        task=self.app.db.get('task',self.task['id']);task['checks']=[{'label':'final','image':'missing:qa','argv':['true'],'weight':1}];task=self.app.save_task(task)
        self.assertFalse(applicable_checks(task,0));self.assertEqual(len(applicable_checks(task,1)),1)
        r=self.prepare();r=self.mutate(r,'capture')
        with self.assertRaises(ValueError):start_job(self.app,r['id'],r['trials'][0]['id'],'check',{'captureId':r['trials'][0]['captures'][-1]['id']})
        r=self.mutate(r,'continue');r=self.mutate(r,'capture');r=self.mutate(r,'complete')
        with patch('chb.arena.jobs.run_checks',side_effect=ValueError('镜像不存在')):
            start_job(self.app,r['id'],r['trials'][0]['id'],'check',{'captureId':r['trials'][0]['captures'][-1]['id']})
            import time
            deadline=time.monotonic()+3
            while self.app.jobs and time.monotonic()<deadline:time.sleep(.01)
        t=self.app.present_run(self.app.db.get('run',r['id']))['trials'][0]
        self.assertEqual(t['state'],'completed');self.assertIsNone(t['score']['objective']);self.assertIn('镜像不存在',t['lastJobError']['message'])
    def test_multiround_objective_requires_each_declared_stage(self):
        task=self.app.db.get('task',self.task['id'])
        task['checks']=[{'label':'one','image':'qa:one','argv':['true'],'weight':1,'stageIndex':0},{'label':'two','image':'qa:two','argv':['true'],'weight':3,'stageIndex':1}]
        self.app.save_task(task)
        r=self.prepare();r=self.mutate(r,'capture');r=self.mutate(r,'continue');r=self.mutate(r,'capture');r=self.mutate(r,'complete')
        from chb.arena.scoring import calculate
        t=r['trials'][0];t['captures'][1]['checks']=[{'id':'2','weight':3,'status':'passed'}]
        self.assertIsNone(calculate(r,t)['objective'])
        t['captures'][0]['checks']=[{'id':'1','weight':1,'status':'failed'}]
        self.assertEqual(calculate(r,t)['objective'],75)
        t['captures'].append({**t['captures'][-1],'checks':[]})
        self.assertIsNone(calculate(r,t)['objective'])

    def test_original_task_import_never_copies_solutions(self):
        from chb.arena.api import import_originals
        shutil.copytree(ROOT/'tasks',self.root/'tasks')
        result=import_originals(self.app)
        self.assertEqual(len(result['imported']),3)
        self.assertEqual(len(import_originals(self.app)['imported']),0)
        t=self.app.db.get('task','original-search-notes-v1')
        r=self.prepare(taskIds=[t['id']]);workspace=Path(r['trials'][0]['workspacePath'])
        self.assertTrue((workspace/'notes.py').exists())
        self.assertFalse((workspace/'solution').exists());self.assertFalse((workspace/'tests/verify.py').exists())
        self.assertTrue(t['checks']);self.assertEqual(t['license'],'MIT')

    def test_bundled_tasks_install_on_startup_preserving_archives_and_edits(self):
        shutil.copytree(ROOT/'tasks',self.root/'tasks')
        restarted=Arena(self.root)
        original=restarted.db.get('task','original-search-notes-v1')
        self.assertTrue(original['baselineId'])
        original=restarted.save_task({**original,'title':'User edited title'})
        restarted.db.archive('task',original['id'],True,original['revision'])
        again=Arena(self.root)
        saved=again.db.get('task',original['id'])
        self.assertTrue(saved['archived']);self.assertEqual(saved['title'],'User edited title')
        self.assertEqual(len(again.db.list('baseline')),3)

    def test_bundled_repair_workspace_contains_executable_project_and_constraints(self):
        import subprocess,sys
        shutil.copytree(ROOT/'tasks',self.root/'tasks')
        self.app=Arena(self.root)
        for name in ['search-notes-v1','csv-catalog-v1']:
            task=self.app.db.get('task','original-'+name)
            run=self.prepare(requestId=name,taskIds=[task['id']])
            workspace=Path(run['trials'][0]['workspacePath'])
            source=ROOT/'tasks'/name/'environment/fixture'
            for path in source.rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    self.assertEqual((workspace/path.relative_to(source)).read_bytes(),path.read_bytes())
            self.assertFalse((workspace/'solution').exists());self.assertFalse((workspace/'tests/verify.py').exists())
            self.assertIn('AGENTS.override.md',run['trials'][0]['baseline']['files'])
            result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=workspace,capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            # Existing regressions run; this does not mean the intentionally buggy starting project is fixed.
            if name=='search-notes-v1':
                proof=subprocess.run([sys.executable,'-c',"from notes import search_notes; assert search_notes([{'title':'APPLE'}], 'apple') == []"],cwd=workspace,capture_output=True,timeout=10)
                self.assertEqual(proof.returncode,0)

    def test_delete_config_keeps_run_snapshot_and_can_restore(self):
        run=self.prepare()
        original=self.app.db.get('config','minimal')
        archived=post(self.app,'/api/arena/configs/minimal/archive',{'revision':original['revision'],'archived':True})
        self.assertFalse(any(c['id']=='minimal' for c in self.app.state()['configs']))
        self.assertEqual(self.app.db.get('run',run['id'])['configs'][0]['agentsPrompt'],original['agentsPrompt'])
        with self.assertRaisesRegex(ValueError,'归档'):self.prepare(requestId='deleted')
        restored=post(self.app,'/api/arena/configs/minimal/archive',{'revision':archived['revision'],'archived':False})
        self.assertFalse(restored['archived'])
        self.assertTrue(any(c['id']=='minimal' for c in self.app.state()['configs']))

    def test_refactoring_task_requires_source_even_when_classified_as_project(self):
        from chb.arena.contracts import task_view
        for patch in [{'id':'perf-01-props-to-signals'}, {'id':'custom-refactor','requiresBaseline':True}]:
            task={**self.task,**patch,'taskParadigm':'open-ended-project'}
            task.pop('baselineId',None);task.pop('revision',None)
            if 'requiresBaseline' not in patch:task.pop('requiresBaseline',None)
            saved=self.app.db.save('task',task)
            self.assertTrue(task_view(saved)['requiresBaseline'])
            with self.assertRaisesRegex(ValueError,'项目源码'):
                self.prepare(requestId=patch['id'],taskIds=[saved['id']])

    def test_prior_stage_can_be_checked_without_changing_active_stage(self):
        task=self.app.db.get('task',self.task['id'])
        task['checks']=[{'label':'first','image':'qa:first','argv':['true'],'stageIndex':0}];self.app.save_task(task)
        r=self.prepare();r=self.mutate(r,'capture');old=r['trials'][0]['captures'][-1]['id']
        r=self.mutate(r,'continue');r=self.mutate(r,'capture');r=self.mutate(r,'complete');tid=r['trials'][0]['id']
        done=threading.Event()
        def check(app,rid,trial_id,capture,task,control):
            self.assertEqual(capture['id'],old);done.set()
            return [{'id':'1','weight':1,'status':'passed'}]
        with patch('chb.arena.jobs.run_checks',side_effect=check):
            start_job(self.app,r['id'],tid,'check',{'captureId':old})
            thread=self.app.jobs.get((r['id'],tid),{}).get('thread')
            if thread:thread.join(timeout=5)
        self.assertTrue(done.is_set())
        t=self.app.present_run(self.app.db.get('run',r['id']))['trials'][0]
        self.assertEqual(t['stageIndex'],1);self.assertEqual(t['state'],'completed')
        self.assertEqual(t['score']['objective'],100);self.assertEqual(t['captures'][-1]['checks'],[])

    def test_citation_validation_never_trusts_invented_files(self):
        packet={'files':{'a.py':'x = 1\n'},'omittedFiles':[]}
        result=validate_judge({'summary':'review','findings':[{'path':'missing','line':1,'quote':'x'},{'path':'a.py','line':1,'quote':'x = 1','comment':'actual'},None]},packet)
        self.assertEqual(len(result['findings']),1);self.assertEqual(result['rejectedFindings'],2)
    def test_native_usage_binding_cumulative_cache_and_regression(self):
        r=self.prepare();w=r['trials'][0]['workspacePath']
        rows=[{'type':'session_meta','payload':{'id':'session-qa','cwd':w}},{'type':'turn_context','payload':{'model':'gpt-6-astra','effort':'medium'}}]
        token=lambda a,b,c:{'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':a,'output_tokens':b,'cached_input_tokens':c}}}}
        raw='\n'.join(json.dumps(x) for x in rows+[token(100,10,60),token(200,20,120),token(200,20,120)])
        u=read_trace(raw,w);self.assertEqual(u['totalTokens'],220);self.assertEqual(u['cacheHitRate'],60);self.assertIsNone(u['activeSeconds'])
        with self.assertRaises(ValueError):read_trace(raw,self.root/'elsewhere')
        with self.assertRaises(ValueError):read_trace(raw,w,'another-session')
        with self.assertRaises(ValueError):read_trace(raw+'\n'+json.dumps(token(100,10,60)),w)
        r=self.mutate(r,'trace',raw=raw)
        earlier='\n'.join(json.dumps(x) for x in rows+[token(100,10,60)])
        with self.assertRaises(ValueError):self.mutate(r,'trace',raw=earlier)
        bundle=zipfile.ZipFile(io.BytesIO(export(self.app,r['id'])))
        self.assertFalse(any(n.endswith('.jsonl') for n in bundle.namelist()))

class ArenaHTTPTests(unittest.TestCase):
    def test_authenticated_routes_and_snapshot_file_boundary(self):
        import http.client
        from chb.webapp import LocalServer
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shutil.copytree(ROOT/'profiles',root/'profiles');(root/'catalog').mkdir();(root/'catalog/arena-tasks.json').write_text('[]')
            server=LocalServer(root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def request(method,path,body=None,auth=True,origin=True):
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                headers={'Host':f'127.0.0.1:{server.server_port}'}
                if auth:headers['X-CHB-Token']=server.token
                if method=='POST':headers.update({'Content-Type':'application/json','Origin':server.origin if origin else 'https://untrusted.invalid'})
                conn.request(method,path,json.dumps(body) if body is not None else None,headers)
                response=conn.getresponse();code=response.status;data=response.read();conn.close();return code,data
            try:
                self.assertEqual(request('GET','/api/arena/state',auth=False)[0],403)
                self.assertEqual(request('GET','/api/arena/state')[0],200)
                data={'name':'HTTP fixture','agentsPrompt':'test','baseModel':'gpt-6-astra','reasoning':'medium','interactiveMode':'adaptive','skills':[],'customConstraints':[]}
                self.assertEqual(request('POST','/api/arena/configs/save',data,origin=False)[0],403)
                code,body=request('POST','/api/arena/configs/save',data);self.assertEqual(code,200)
                config=json.loads(body)
                task=server.arena.save_task({'title':'HTTP task','inputPrompt':'test','taskParadigm':'open-ended-project','channel':'deepswe-core','checks':[]})
                run=server.arena.prepare({'requestId':'http-qa','configIds':[config['id']],'taskIds':[task['id']]})
                trial=run['trials'][0];w=Path(trial['workspacePath']);(w/'a.txt').write_text('allowed');(w/'.env').write_text('excluded secret')
                run=server.arena.mutate(run['id'],trial['id'],'capture',{})
                cap=run['trials'][0]['captures'][-1]
                prefix=f"/api/arena/runs/{run['id']}/trials/{trial['id']}/files/{cap['id']}/"
                self.assertEqual(json.loads(request('GET',prefix+'a.txt')[1])['content'],'allowed')
                for path in ['.env','%2e%2e/private','missing']:
                    code,body=request('GET',prefix+path);self.assertEqual(code,400);self.assertNotIn(b'excluded secret',body)
                self.assertEqual(request('POST','/api/arena/configs/save',[])[0],400)
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
