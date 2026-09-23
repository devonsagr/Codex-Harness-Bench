import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from chb.arena.service import Arena
from chb.arena.human_inspection import operate,preview_url

class HumanInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        home=self.root/'home';home.mkdir();self.env=patch.dict(os.environ,{'CODEX_HOME':str(home)});self.env.start()
        (self.root/'catalog').mkdir();(self.root/'catalog/arena-tasks.json').write_text('[]')
        self.app=Arena(self.root)
        c=self.app.save_config({'name':'fixture','baseModel':'fixture','reasoning':'','agentsPrompt':'','interactiveMode':'adaptive','skills':[]})
        task=self.app.save_task({'title':'fixture','inputPrompt':'build UI','hasFrontendUI':True,'taskParadigm':'open-ended-project','channel':'deepswe-core','checks':[]})
        r=self.app.prepare({'requestId':'fixture','configIds':[c['id']],'taskIds':[task['id']]})
        self.rid=r['id'];self.tid=r['trials'][0]['id'];self.workspace=Path(r['trials'][0]['workspacePath'])
        (self.workspace/'README.md').write_text('run locally')
        (self.workspace/'package.json').write_text(json.dumps({'scripts':{'dev':'vite'}}))
        (self.workspace/'index.html').write_text('<script>alert(1)</script>')
        self.app.mutate(self.rid,self.tid,'capture',{})
        self.cap=self.app.trial(self.rid,self.tid)[1]['captures'][-1]
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def call(self,action,**data):return operate(self.app,self.rid,self.tid,'inspection-'+action,{'captureId':self.cap['id'],**data})
    def test_files_are_snapshot_bound_and_html_is_inert_text(self):
        status=self.call('status');self.assertEqual(status['scripts'],{'dev':'vite'})
        self.assertIn('README.md',status['documents'])
        value=self.call('file',path='index.html');self.assertEqual(value['text'],'<script>alert(1)</script>');self.assertNotIn('image',value)
        for path in ['../../home/config.toml','absent','C:/Windows/win.ini']:
            with self.assertRaises(ValueError):self.call('file',path=path)
        source=self.app.local/'runs'/self.rid/self.tid/'captures'/self.cap['id']/'files/README.md'
        source.write_text('tampered')
        with self.assertRaises(ValueError):self.call('file',path='README.md')
    def test_inspection_copies_do_not_change_snapshot_or_workspace(self):
        one=self.call('prepare');two=self.call('prepare');self.assertNotEqual(one['path'],two['path'])
        (Path(one['path'])/'README.md').write_text('manual edits')
        self.assertEqual(self.call('file',path='README.md')['text'],'run locally')
        self.assertEqual((self.workspace/'README.md').read_text(),'run locally')
        self.assertEqual(one['captureHash'],self.cap['manifest']['sha256'])
    def test_human_score_without_ai_is_versioned_and_does_not_rewrite_machine(self):
        run=self.app.db.get('run',self.rid);key=next(k for k,w in run['policy']['dimensions'].items() if w>0 and k!='ux')
        row=self.call('save',reviewed=True,method='runtime',ratings={key:{'score':80,'reason':'Observed fixture behavior'}})
        self.assertEqual(row['score'],80);self.assertLess(row['coverage'],100)
        trial=self.app.trial(self.rid,self.tid)[1];self.assertEqual(trial['reviews'],[]);self.assertEqual(trial['humanAssessments'][0]['captureId'],self.cap['id'])
        self.app.mutate(self.rid,self.tid,'capture',{});self.cap=self.app.trial(self.rid,self.tid)[1]['captures'][-1]
        self.assertEqual(self.call('status')['assessments'],[])
    def test_missing_evidence_and_source_only_ux_are_rejected(self):
        for data in [dict(reviewed=False,method='runtime',ratings={}),dict(reviewed=True,method='source',ratings={'ux':{'score':90,'reason':'looks good in code'}}),dict(reviewed=True,method='visual',ratings={'ux':{'score':90,'reason':''}})]:
            with self.assertRaises(ValueError):self.call('save',**data)
    def test_preview_urls_cannot_be_remote_or_workbench_or_script(self):
        self.assertEqual(preview_url('http://127.0.0.1:3000/demo'),'http://127.0.0.1:3000/demo')
        for value in ['javascript:alert(1)','https://evil.example','http://127.0.0.1:8765/','http://user:pass@localhost:3000/','http://localhost:3000/?key=secret']:
            with self.assertRaises(ValueError):preview_url(value)

if __name__=='__main__':unittest.main()
