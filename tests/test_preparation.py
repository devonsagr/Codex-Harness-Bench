import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
from chb.cli import ROOT
from chb.arena.service import Arena
from chb.arena.preparation import start
from chb.arena.public_sources import task_bundle,preview,download_file
from chb.arena.files import hash_bytes
from chb.arena.scoring import MACHINE_POLICY


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        shutil.copytree(ROOT/'profiles',self.root/'profiles');(self.root/'catalog').mkdir()
        (self.root/'catalog/arena-tasks.json').write_text('[]')
        self.items=[{'id':name,'title':name,'category':kind,'language':'go','repositoryUrl':'https://github.com/u/r'+('.git' if name=='second' else ''),
                     'baseCommit':'a'*40,'taskUrl':'https://github.com/u/tasks'} for name,kind in [('first','feature_request'),('second','enhancement')]]
        (self.root/'catalog/public-task-sources.json').write_text(json.dumps({'revision':'b'*40,'license':'test','tasks':self.items}))
        self.files={}
        for name in ['first','second']:
            self.files.update({f'tasks/{name}/instruction.md':b'Implement the public requirement',
               f'tasks/{name}/task.toml':b'[metadata]\ndisplay_description="feature"\n[environment]\ndocker_image="fixture:1"',
               f'tasks/{name}/tests/hidden.txt':b'never in the candidate'})
        (self.root/'catalog/public-task-files.json').write_text(json.dumps({'revision':'b'*40,'tasks':{
            name:{p:hash_bytes(v) for p,v in self.files.items() if p.startswith('tasks/'+name+'/')} for name in ['first','second']}}))
        self.app=Arena(self.root);self.downloads=[]
    def tearDown(self):
        thread=getattr(self.app,'preparation_thread',None)
        if thread:thread.join(10)
        self.temp.cleanup()
    def data(self,key='request-one',task='first'):
        return {'requestId':key,'configIds':['minimal'],'taskIds':['deepswe-'+task],'policy':MACHINE_POLICY}
    def download(self,source,name,digest):
        self.downloads.append(name);return self.files[name]
    def repository(self,app,data):
        folder=self.root/'repo';folder.mkdir(exist_ok=True);(folder/'main.go').write_text('package main')
        baseline=app.import_files('baseline',{'path':str(folder),'name':'fixed source'})
        baseline.update(sourceUrl='https://github.com/u/r',sourceCommit='a'*40)
        return app.db.save('baseline',baseline,baseline['revision'])
    def finish(self,job):
        self.app.preparation_thread.join(10)
        current=self.app.db.get('preparation_job',job['id'])
        self.assertEqual(current['status'],'completed',current)
        return self.app.db.get('run',current['runId'])

    def test_selected_download_is_lazy_and_preview_never_fetches_source_or_tests(self):
        with patch('chb.arena.public_sources.download_file',side_effect=self.download):
            self.assertIn('requirement',preview(self.app,'first')['text'])
            self.assertEqual(self.downloads,['tasks/first/instruction.md'])
            first=task_bundle(self.app,'first');task_bundle(self.app,'first')
        self.assertEqual(set(self.downloads),{p for p in self.files if p.startswith('tasks/first/')})
        self.assertFalse((first/'tasks/second').exists())
        self.assertEqual(len(self.downloads),3)

    def test_cache_reuse_unique_workspaces_and_duplicate_request_idempotence(self):
        with patch('chb.arena.public_sources.download_file',side_effect=self.download),patch('chb.arena.public_sources.import_repository',side_effect=self.repository) as repo:
            first=self.finish(start(self.app,self.data()))
            again=start(self.app,self.data());self.assertEqual(again['runId'],first['id'])
            second=self.finish(start(self.app,self.data('request-two','second')))
            third=self.finish(start(self.app,self.data('request-three')))
            self.assertEqual(repo.call_count,1)
        paths=[Path(r['trials'][0]['workspacePath']) for r in [first,second,third]]
        self.assertEqual(len(set(paths)),3)
        (paths[0]/'main.go').write_text('candidate changed')
        self.assertEqual((paths[2]/'main.go').read_text(),'package main')
        self.assertFalse((paths[0]/'tests/hidden.txt').exists())
        self.assertEqual(first['tasks'][0]['baselineId'],second['tasks'][0]['baselineId'])

    def test_failure_retry_and_conflicting_payload(self):
        with patch('chb.arena.public_sources.download_file',side_effect=ValueError('下载中断')):
            job=start(self.app,self.data());self.app.preparation_thread.join(10)
        self.assertEqual(self.app.db.get('preparation_job',job['id'])['status'],'failed')
        self.assertEqual(self.app.db.list('run'),[])
        with self.assertRaisesRegex(ValueError,'内容已改变'):start(self.app,self.data(task='second'))
        with patch('chb.arena.public_sources.download_file',side_effect=self.download),patch('chb.arena.public_sources.import_repository',side_effect=self.repository):
            self.finish(start(self.app,self.data()))

    def test_download_runs_outside_main_lock_and_detects_config_edits(self):
        entered=threading.Event();release=threading.Event()
        def delayed(*args):
            entered.set();release.wait(5);return self.download(*args)
        with patch('chb.arena.public_sources.download_file',side_effect=delayed),patch('chb.arena.public_sources.import_repository',side_effect=self.repository):
            job=start(self.app,self.data());self.assertTrue(entered.wait(3))
            with self.app.lock:
                config=self.app.db.get('config','minimal');config['name']='Edited';self.app.db.save('config',config,config['revision'])
            release.set();self.app.preparation_thread.join(10)
        current=self.app.db.get('preparation_job',job['id'])
        self.assertEqual(current['status'],'failed');self.assertIn('配置已修改',current['error'])
        self.assertEqual(self.app.db.list('run'),[])

    def test_restart_marks_interrupted_and_does_not_discard_cache(self):
        job={'id':'pending','status':'running','fingerprint':'x','phase':'download'}
        self.app.db.save('preparation_job',job)
        restarted=Arena(self.root)
        self.assertEqual(restarted.db.get('preparation_job','pending')['status'],'interrupted')

    def test_network_timeout_has_actionable_error_and_bounded_retry(self):
        with patch('chb.arena.public_sources.urlopen',side_effect=TimeoutError()) as request:
            with self.assertRaisesRegex(ValueError,'已校验文件保留'):
                download_file({'revision':'b'*40},'tasks/first/instruction.md','unused')
            self.assertEqual(request.call_count,2)

if __name__=='__main__':unittest.main()
