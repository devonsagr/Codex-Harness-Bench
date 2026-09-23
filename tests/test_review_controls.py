import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from chb.arena.service import Arena
from chb.arena.review_options import timeout_seconds,ReviewBudgetExceeded
from chb.arena.review_connection import connection
from chb.arena.models import capabilities
from chb.arena.initial_config import ensure,restore
from chb.arena.delete_run import delete
from chb.arena.local_review import execute_local
from chb.arena.judge_progress import read_progress

class ReviewControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.home=self.root/'home';self.home.mkdir()
        (self.root/'catalog').mkdir();(self.root/'catalog/arena-tasks.json').write_text('[]')
        self.env=patch.dict(os.environ,{'CODEX_HOME':str(self.home)});self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def run_fixture(self):
        app=Arena(self.root)
        c=app.save_config({'name':'fixture','baseModel':'fixture','reasoning':'low','agentsPrompt':'','interactiveMode':'adaptive','skills':[]})
        t=app.save_task({'title':'fixture','inputPrompt':'hello','taskParadigm':'open-ended-project','channel':'deepswe-core','checks':[]})
        r=app.prepare({'requestId':'fixture','configIds':[c['id']],'taskIds':[t['id']]})
        return app,r,r['trials'][0]
    def test_budget_is_explicit_and_bounded(self):
        self.assertEqual(timeout_seconds({}),3600)
        self.assertEqual(timeout_seconds({'timeoutSeconds':28800}),28800)
        for value in [True,0,-1,28801,'3600']:
            with self.assertRaises(ValueError):timeout_seconds({'timeoutSeconds':value})
    def test_native_connection_and_custom_catalog_do_not_invent_efforts(self):
        (self.home/'config.toml').write_text('model="deepseek-test"\nmodel_provider="proxy"\n[model_providers.proxy]\nbase_url="http://127.0.0.1:9000/v1"\nenv_key="FIXTURE_PROXY_KEY"\n')
        public=connection()['public'];self.assertEqual(public['provider'],'proxy')
        self.assertNotIn('FIXTURE_PROXY_KEY',json.dumps(public))
        self.assertEqual(capabilities()[0]['id'],'deepseek-test');self.assertEqual(capabilities()[0]['reasoningLevels'],[])
        (self.home/'catalog.json').write_text(json.dumps({'models':[{'slug':'deepseek-test','supported_reasoning_levels':[{'effort':'high'}]}]}))
        text=(self.home/'config.toml').read_text();(self.home/'config.toml').write_text('model_catalog_json="catalog.json"\n'+text)
        self.assertEqual(capabilities()[0]['reasoningLevels'],['high'])
    def test_initial_snapshot_is_once_and_restoration_has_undo(self):
        from chb.arena.codex_apply import restore as undo
        (self.home/'config.toml').write_text('model="fixture"\nmodel_reasoning_effort="low"\n# original comment\n')
        (self.home/'AGENTS.md').write_text('original rules')
        (self.home/'auth.json').write_text('do not copy')
        app=Arena(self.root);first=ensure(app)
        (self.home/'config.toml').write_text('model="changed"\n')
        (self.home/'AGENTS.override.md').write_text('later override')
        self.assertEqual(ensure(app),first)
        folder=Path(first['path']);self.assertFalse((folder/'auth.json').exists())
        receipt=restore(app,{'confirmation':'恢复最初配置'})
        self.assertIn('# original comment',(self.home/'config.toml').read_text())
        self.assertFalse((self.home/'AGENTS.override.md').exists())
        undo(app,{'applicationId':receipt['id']})
        self.assertEqual((self.home/'AGENTS.override.md').read_text(),'later override')
        self.assertEqual((self.home/'auth.json').read_text(),'do not copy')
    def test_delete_run_removes_owned_evidence_and_database_revisions_only(self):
        app,r,t=self.run_fixture();rid=r['id'];tid=t['id']
        shared=app.local/'baselines/shared';shared.mkdir(parents=True);(shared/'keep').write_text('shared')
        job=app.local/'runs'/rid/tid/'reviews/job-fixture';job.mkdir(parents=True)
        runtime=app.local/'reviewer-runtime/chb-review-work-fixture';runtime.mkdir(parents=True)
        home=app.local/'reviewer-runtime/chb-review-home-fixture';home.mkdir();(home/'auth.json').write_text('temporary fixture')
        (job/'runtime.json').write_text(json.dumps({'workspace':str(runtime),'temporaryHome':str(home)}))
        app.db.save('preparation_job',{'id':'prep','runId':rid,'status':'completed'})
        data={'runId':rid,'revision':r['revision'],'desktopStopped':True,'confirmation':'永久删除评测 '+rid}
        with self.assertRaises(ValueError):delete(app,{**data,'confirmation':'wrong'})
        delete(app,data)
        self.assertFalse((app.local/'runs'/rid).exists());self.assertFalse(runtime.exists());self.assertFalse(home.exists())
        self.assertTrue((shared/'keep').exists())
        with app.db.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM revisions WHERE id IN (?,?)',(rid,'prep')).fetchone()[0],0)
        with self.assertRaises(ValueError):app.db.get('run',rid)
    def test_delete_rejects_live_job_and_foreign_runtime_path(self):
        app,r,t=self.run_fixture();rid=r['id'];tid=t['id']
        data={'runId':rid,'revision':r['revision'],'desktopStopped':True,'confirmation':'永久删除评测 '+rid}
        app.jobs[(rid,tid)]={}
        with self.assertRaises(ValueError):delete(app,data)
        app.jobs.clear();job=app.local/'runs'/rid/tid/'reviews/job-fixture';job.mkdir(parents=True)
        (job/'runtime.json').write_text(json.dumps({'workspace':str(self.home),'temporaryHome':str(self.home)}))
        with self.assertRaises(ValueError):delete(app,data)
        self.assertTrue(Path(t['workspacePath']).exists())
    def test_progress_shows_sent_prompt_and_public_messages_not_reasoning(self):
        app,r,t=self.run_fixture();job=app.local/'runs'/r['id']/t['id']/'reviews/job-fixture'
        (job/'task').mkdir(parents=True);(job/'task/instruction.md').write_text('rubric fixture')
        events=[{'type':'item.completed','item':{'id':'a','type':'agent_message','text':'checking tests'}},
                {'type':'item.completed','item':{'id':'b','type':'reasoning','text':'private reasoning'}}]
        (job/'events.jsonl').write_text('\n'.join(json.dumps(x) for x in events))
        result=read_progress(app,r['id'],t['id'])
        self.assertEqual(result['instruction'],'rubric fixture');self.assertEqual(result['messages'],['checking tests'])
    def test_local_budget_exhaustion_kills_owned_process_and_cleans_scratch(self):
        (self.home/'auth.json').write_text('{}');folder=self.root/'review';(folder/'task').mkdir(parents=True)
        (folder/'task/instruction.md').write_text('fixture')
        with patch('chb.arena.local_review.codex_executable',return_value='codex'),patch('chb.arena.local_review.subprocess.run',return_value=MagicMock(stdout='fixture')),patch('chb.arena.local_review.subprocess.Popen',return_value=MagicMock(poll=lambda:None)),patch('chb.arena.local_review.ProcessTree') as tree,patch('chb.arena.local_review.time.monotonic',side_effect=[0,61]):
            with self.assertRaises(ReviewBudgetExceeded):execute_local(folder,folder/'task','fixture','fixture',{}, {'stop':threading.Event()},60,runtime_root=self.root/'scratch')
            tree.return_value.close.assert_called_once()
        self.assertEqual(list((self.root/'scratch').iterdir()),[])

    def test_custom_provider_passes_only_its_key_and_does_not_force_effort(self):
        (self.home/'config.toml').write_text('model="fixture"\nmodel_provider="proxy"\n[model_providers.proxy]\nname="Fixture"\nbase_url="http://127.0.0.1:9000/v1"\nwire_api="responses"\nenv_key="FIXTURE_PROXY_KEY"\n')
        folder=self.root/'review';(folder/'task').mkdir(parents=True)
        (folder/'task/instruction.md').write_text('fixture')
        def launch(args,**kwargs):
            self.assertEqual(kwargs['env']['FIXTURE_PROXY_KEY'],'fixture-only')
            self.assertNotIn('OPENAI_API_KEY',kwargs['env'])
            self.assertFalse((Path(kwargs['env']['CODEX_HOME'])/'auth.json').exists())
            self.assertIn('model_provider="proxy"',args)
            self.assertFalse(any('model_reasoning_effort=' in arg for arg in args))
            Path(args[args.index('-o')+1]).write_text('{"summary":"fixture","findings":[]}')
            return MagicMock(returncode=0,poll=lambda:0)
        with patch.dict(os.environ,{'FIXTURE_PROXY_KEY':'fixture-only','OPENAI_API_KEY':'must-not-forward'}),patch('chb.arena.local_review.codex_executable',return_value='codex'),patch('chb.arena.local_review.subprocess.run',return_value=MagicMock(stdout='fixture')),patch('chb.arena.local_review.subprocess.Popen',side_effect=launch),patch('chb.arena.local_review.ProcessTree'):
            execute_local(folder,folder/'task','fixture','fixture',{}, {'stop':threading.Event()},60,reasoning='',runtime_root=self.root/'scratch')
        self.assertNotIn('fixture-only',(folder/'connection.json').read_text())

    def test_partial_delete_keeps_history_for_retry_then_removes_it(self):
        app,r,t=self.run_fixture();rid=r['id']
        data={'runId':rid,'revision':r['revision'],'desktopStopped':True,'confirmation':'永久删除评测 '+rid}
        with patch('chb.arena.delete_run.shutil.rmtree',side_effect=PermissionError('fixture locked')):
            with self.assertRaises(PermissionError):delete(app,data)
        current=app.db.get('run',rid);self.assertTrue(current['deletionPending'])
        with self.assertRaises(ValueError):app.mutate(rid,t['id'],'capture',{})
        delete(app,{**data,'revision':current['revision']})
        with self.assertRaises(ValueError):app.db.get('run',rid)

    def test_unknown_model_can_use_native_default_without_an_invented_tier(self):
        from chb.arena.models import validate_effort
        from chb.arena.codex_apply import project_settings
        self.assertIsNone(validate_effort('unknown','',require_known=True))
        with self.assertRaises(ValueError):validate_effort('unknown','ultra',require_known=True)
        raw=project_settings({'baseModel':'unknown','reasoning':''},b'model_reasoning_effort="ultra"\n')
        self.assertNotIn(b'model_reasoning_effort',raw)

if __name__=='__main__':unittest.main()
