import os
from contextlib import closing
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch,MagicMock

from chb.arena.delete_run import delete
from chb.arena.service import Arena
from chb.arena.telemetry import linked_sessions


class CodexSessionCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.home=self.root/'codex-home';self.home.mkdir()
        self.env=patch.dict(os.environ,{'CODEX_HOME':str(self.home)});self.env.start()
        (self.root/'catalog').mkdir();(self.root/'catalog/arena-tasks.json').write_text('[]',encoding='utf-8')
        self.app=Arena(self.root)
        config=self.app.save_config({'name':'fixture','baseModel':'fixture','reasoning':'low','agentsPrompt':'','interactiveMode':'adaptive','skills':[]})
        task=self.app.save_task({'title':'fixture','inputPrompt':'hello','taskParadigm':'open-ended-project','channel':'deepswe-core','checks':[]})
        self.run=self.app.prepare({'requestId':'fixture','configIds':[config['id']],'taskIds':[task['id']]})
        self.trial=self.run['trials'][0]
        self.session=str(uuid.uuid4())
        rollout=self.home/'sessions'/'2026'/'fixture.jsonl';rollout.parent.mkdir(parents=True);rollout.write_text('',encoding='utf-8')
        with closing(sqlite3.connect(self.home/'state_1.sqlite')) as db:
            db.execute('CREATE TABLE threads(id TEXT,cwd TEXT,title TEXT,rollout_path TEXT,project_id TEXT)')
            db.execute('INSERT INTO threads VALUES(?,?,?,?,?)',(self.session,self.trial['workspacePath'],'exact trial',str(rollout),'project-one'))
            db.execute('INSERT INTO threads VALUES(?,?,?,?,?)',(str(uuid.uuid4()),str(self.root/'unrelated'),'other',str(rollout),'other-project'))
            db.commit()

    def tearDown(self):self.env.stop();self.temp.cleanup()

    def test_only_exact_workspace_sessions_are_listed(self):
        self.assertEqual(linked_sessions(self.home,self.trial['workspacePath']),[{'id':self.session,'title':'exact trial','projectId':'project-one'}])
        self.assertEqual(linked_sessions(self.home,self.root/'another'),[])

    def test_delete_requires_fresh_exact_list_before_fixed_cli_command(self):
        data={'runId':self.run['id'],'revision':self.run['revision'],'desktopStopped':True,
              'confirmation':'永久删除评测 '+self.run['id'],'deleteCodexSessions':True,'sessionIds':[]}
        with self.assertRaisesRegex(ValueError,'列表已变化'):delete(self.app,data)
        self.assertTrue(Path(self.trial['workspacePath']).exists())
        with patch('chb.arena.delete_run.shutil.which',return_value='codex'),patch('chb.arena.delete_run.subprocess.run',return_value=MagicMock(returncode=0)) as execute:
            delete(self.app,{**data,'sessionIds':[self.session]})
        self.assertEqual(execute.call_args.args[0],['codex','delete',self.session,'--force'])
        self.assertEqual(execute.call_args.kwargs['env']['CODEX_HOME'],str(self.home))
        self.assertFalse(Path(self.trial['workspacePath']).exists())


if __name__=='__main__':unittest.main()
