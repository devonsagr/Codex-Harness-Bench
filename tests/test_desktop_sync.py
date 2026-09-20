import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from chb.arena.telemetry import discover_trace
from chb.arena.service import Arena


class DesktopSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.home=self.root/'home';(self.home/'sessions').mkdir(parents=True)
        self.env=patch.dict(os.environ,{'CODEX_HOME':str(self.home)});self.env.start()
        (self.root/'catalog').mkdir();(self.root/'catalog/arena-tasks.json').write_text('[]')
        self.app=Arena(self.root)
        cfg=self.app.save_config({'name':'Fixture','agentsPrompt':'','baseModel':'fixture','reasoning':'low','interactiveMode':'adaptive','skills':[]})
        task=self.app.save_task({'title':'Fixture','inputPrompt':'Write hello','taskParadigm':'open-ended-project','hasFrontendUI':False,'channel':'deepswe-core','checks':[],
                                'stages':[{'title':'First','prompt':'Write hello'},{'title':'Second','prompt':'Add export'}]})
        self.run=self.app.prepare({'configIds':[cfg['id']],'taskIds':[task['id']],'requestId':'sync'})
        self.trial=self.run['trials'][0];self.workspace=Path(self.trial['workspacePath'])
        self.db=sqlite3.connect(self.home/'state_5.sqlite');self.db.execute('CREATE TABLE threads (id TEXT, rollout_path TEXT, cwd TEXT)')

    def tearDown(self):
        self.db.close();self.env.stop();self.temp.cleanup()

    def trace(self,session='native',cwd=None,total=100,start='2026-09-20T01:00:00+00:00'):
        path=self.home/'sessions'/f'{session}.jsonl'
        rows=[{'type':'session_meta','payload':{'id':session,'cwd':str(cwd or self.workspace)}},
              {'type':'turn_context','payload':{'model':'fixture','effort':'low'}},
              {'type':'event_msg','timestamp':start,'payload':{'type':'task_started'}},
              {'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':total,'cached_input_tokens':80,'output_tokens':10}}}},
              {'type':'event_msg','timestamp':'2026-09-20T01:01:00+00:00','payload':{'type':'task_complete'}}]
        path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n',encoding='utf-8')
        self.db.execute('DELETE FROM threads WHERE id=?',(session,))
        self.db.execute('INSERT INTO threads VALUES (?,?,?)',(session,str(path),str(self.workspace)));self.db.commit()
        return path

    def test_auto_start_native_timing_and_no_double_count(self):
        self.trace();self.app.sync_desktop_traces()
        t=self.app.db.get('run',self.run['id'])['trials'][0]
        self.assertEqual(t['state'],'working');self.assertEqual(t['usage']['activeSeconds'],60)
        self.assertEqual(t['usage']['inputTokens'],100);self.assertEqual(t['usage']['activity'],'completed')
        self.app._last_trace_sync=0;self.app.sync_desktop_traces()
        self.assertEqual(self.app.db.get('run',self.run['id'])['trials'][0]['usage']['inputTokens'],100)

    def test_ambiguous_sessions_require_selection(self):
        self.trace();self.trace('second')
        usage,message=discover_trace(self.home,self.workspace)
        self.assertIsNone(usage);self.assertIn('多个会话',message)
        self.assertEqual(discover_trace(self.home,self.workspace,'native')[0]['sessionId'],'native')

    def test_cwd_metadata_and_log_directory_are_verified(self):
        self.trace(cwd=self.root/'other')
        with self.assertRaisesRegex(ValueError,'工作区'):discover_trace(self.home,self.workspace)
        self.db.execute('UPDATE threads SET rollout_path=?',(str(self.root/'outside.jsonl'),));self.db.commit()
        with self.assertRaisesRegex(ValueError,'日志目录'):discover_trace(self.home,self.workspace)

    def test_truncated_last_line_and_windows_prefix(self):
        path=self.trace()
        with path.open('a',encoding='utf-8') as f:f.write('{"type":')
        self.assertEqual(discover_trace(self.home,self.workspace)[0]['inputTokens'],100)
        if os.name=='nt':
            self.db.execute('UPDATE threads SET cwd=?',('\\\\?\\'+str(self.workspace),));self.db.commit()
            self.assertEqual(discover_trace(self.home,self.workspace)[0]['inputTokens'],100)

    def test_completed_prior_turn_does_not_start_next_stage(self):
        self.trace();self.app.sync_desktop_traces()
        self.app.mutate(self.run['id'],self.trial['id'],'capture',{})
        self.app.mutate(self.run['id'],self.trial['id'],'continue',{})
        self.app._last_trace_sync=0;self.app.sync_desktop_traces()
        self.assertEqual(self.app.db.get('run',self.run['id'])['trials'][0]['state'],'waiting_confirmation')

    def test_regressed_totals_keep_last_good_usage(self):
        self.trace(total=200);self.app.sync_desktop_traces()
        self.trace(total=100);self.app._last_trace_sync=0;self.app.sync_desktop_traces()
        t=self.app.db.get('run',self.run['id'])['trials'][0]
        self.assertEqual(t['usage']['inputTokens'],200);self.assertIn('回退',t['telemetryStatus'])

    def test_bugfix_reference_does_not_replace_source(self):
        task=self.app.save_task({'title':'Missing source','inputPrompt':'Fix it','taskParadigm':'deterministic-bugfix','referenceUrl':'https://github.com/example/project','channel':'deepswe-core','checks':[]})
        with self.assertRaisesRegex(ValueError,'源码'):
            self.app.prepare({'configIds':[self.run['configs'][0]['id']],'taskIds':[task['id']],'requestId':'missing'})


if __name__=='__main__':unittest.main()
