import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from chb.cli import ROOT
from chb.arena.service import Arena
from chb.arena.files import verify_snapshot
from chb.arena.storage import workspace, status
from chb.arena.public_sources import install, start
from chb.arena.repository_source import unpack


class SourceStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        shutil.copytree(ROOT/'profiles',self.root/'profiles');(self.root/'catalog').mkdir()
        (self.root/'catalog/arena-tasks.json').write_text('[]')
        self.app=Arena(self.root)

    def tearDown(self):self.temp.cleanup()

    def run_record(self):
        task=self.app.save_task({'id':'test','title':'Test','inputPrompt':'Make a file','taskParadigm':'open-ended-project','channel':'deepswe-core','hasFrontendUI':False,'checks':[]})
        run=self.app.prepare({'requestId':'storage-test','configIds':['minimal'],'taskIds':[task['id']]})
        tid=run['trials'][0]['id'];path=Path(run['trials'][0]['workspacePath']);(path/'output.txt').write_text('evidence')
        self.app.mutate(run['id'],tid,'capture',{})
        return self.app.mutate(run['id'],tid,'complete',{})

    def clean(self,run,action,**extra):
        return workspace(self.app,{'runId':run['id'],'trialId':run['trials'][0]['id'],'revision':run['revision'],'action':action,**extra})

    def test_cleanup_restore_purge_preserve_evidence_and_record(self):
        run=self.run_record();trial=run['trials'][0];path=Path(trial['workspacePath']);(path/'node_modules').mkdir();(path/'node_modules/dep').write_text('large cache')
        result=self.clean(run,'trash',desktopStopped=True);self.assertFalse(path.exists())
        row=result['workspaces'][0];self.assertEqual(row['cleanup']['status'],'trashed')
        run=self.app.db.get('run',run['id']);self.clean(run,'restore');self.assertTrue((path/'node_modules/dep').exists())
        run=self.app.db.get('run',run['id']);self.clean(run,'trash',desktopStopped=True)
        run=self.app.db.get('run',run['id'])
        with self.assertRaises(ValueError):self.clean(run,'purge')
        self.clean(run,'purge',confirmation='永久删除工作区')
        current=self.app.db.get('run',run['id']);self.assertEqual(current['trials'][0]['captures'],trial['captures'])
        capture=trial['captures'][0];verify_snapshot(path.parent/'captures'/capture['id']/'files',capture['manifest'])
        self.assertEqual(current['trials'][0]['workspaceCleanup']['status'],'deleted')
        with self.assertRaisesRegex(ValueError,'清理'):self.app.mutate(run['id'],trial['id'],'open',{})

    def test_uncollected_changes_active_jobs_and_stale_version_block_cleanup(self):
        run=self.run_record();path=Path(run['trials'][0]['workspacePath'])
        (path/'output.txt').write_text('new work')
        with self.assertRaisesRegex(ValueError,'未回收'):self.clean(run,'trash',desktopStopped=True)
        self.assertTrue(path.exists());(path/'output.txt').write_text('evidence')
        self.app.jobs[(run['id'],run['trials'][0]['id'])]={}
        with self.assertRaisesRegex(ValueError,'后台'):self.clean(run,'trash',desktopStopped=True)
        self.app.jobs.clear()
        with self.assertRaisesRegex(ValueError,'确认'):self.clean(run,'trash')
        old={**run,'revision':run['revision']-1}
        with self.assertRaisesRegex(ValueError,'变化'):self.clean(old,'trash',desktopStopped=True)

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):workspace(self.app,{'runId':'../outside','trialId':'x','action':'purge'})

    def test_failed_metadata_save_rolls_back_workspace_move(self):
        run=self.run_record();path=Path(run['trials'][0]['workspacePath'])
        with patch.object(self.app.db,'save',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.clean(run,'trash',desktopStopped=True)
        self.assertTrue(path.is_dir())
        self.assertFalse(self.app.db.get('run',run['id'])['trials'][0].get('workspaceCleanup'))

    def test_reference_solutions_not_extracted(self):
        archive=self.root/'a.tar.gz';out=self.root/'out';out.mkdir()
        with tarfile.open(archive,'w:gz') as tar:
            for name in ['tasks/x/instruction.md','tasks/x/solution/solve.sh','tasks/x/tests/test.sh']:
                item=tarfile.TarInfo('repo/'+name);item.size=2;tar.addfile(item,io.BytesIO(b'ok'))
        unpack(archive,out,lambda name:'/solution/' not in name)
        self.assertFalse((out/'tasks/x/solution').exists());self.assertTrue((out/'tasks/x/tests/test.sh').exists())

    def test_install_uses_only_repository_baseline_and_preserves_local_edits(self):
        item={'id':'bug','title':'Fix bug','category':'bugfix','language':'go','repositoryUrl':'https://github.com/u/r','baseCommit':'a'*40,'taskUrl':'https://github.com/u/tasks'}
        (self.root/'catalog/public-task-sources.json').write_text(json.dumps({'revision':'b'*40,'license':'Apache-2.0','tasks':[item]}))
        bundle=self.root/'bundle';folder=bundle/'tasks/bug';(folder/'tests').mkdir(parents=True)
        (folder/'instruction.md').write_text('Fix the public requirement')
        (folder/'task.toml').write_text('[metadata]\ndisplay_description="bug"\n[environment]\ndocker_image="fixture:1"')
        (folder/'tests/hidden.txt').write_text('held out')
        repo=self.root/'repo';repo.mkdir();(repo/'code.go').write_text('package main')
        baseline=self.app.import_files('baseline',{'path':str(repo),'name':'repo'})
        with patch('chb.arena.public_sources.import_repository',return_value=baseline):task=install(self.app,'bug',bundle)
        self.assertEqual(task['inputPrompt'],'Fix the public requirement')
        self.assertEqual(list(baseline['manifest']['files']),['code.go'])
        self.assertEqual(task['publicSource']['environmentStatus'],'unverified')
        self.assertEqual(task['checks'],[])
        run=self.app.prepare({'requestId':'source-copy','configIds':['minimal'],'taskIds':[task['id']]})
        work=Path(run['trials'][0]['workspacePath'])
        self.assertEqual((work/'code.go').read_text(),'package main')
        self.assertFalse((work/'tests/hidden.txt').exists())
        self.assertEqual(subprocess.check_output(['git','-C',str(work),'branch','--show-current'],text=True).strip(),'main')
        self.assertEqual(subprocess.check_output(['git','-C',str(work),'rev-list','--count','HEAD'],text=True).strip(),'1')
        task['title']='User edit';self.app.save_task(task)
        with patch('chb.arena.public_sources.import_repository') as download:
            self.assertEqual(install(self.app,'bug',bundle)['title'],'User edit');download.assert_not_called()
        with self.assertRaises(ValueError):start(self.app,{'taskIds':['../../oops']})


if __name__=='__main__':unittest.main()
