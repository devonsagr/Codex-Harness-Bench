import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from chb.arena.api import post
from chb.arena.service import Arena
from chb.arena.files import inventory, fingerprint, hash_bytes


class SkillLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'app'
        (self.root/'catalog').mkdir(parents=True)
        (self.root/'catalog/arena-tasks.json').write_text('[]')
        self.app=Arena(self.root)
        self.library=self.root/'library';self.library.mkdir()

    def tearDown(self):self.tmp.cleanup()

    def skill(self,folder,name,description='Test skill'):
        p=folder/name;p.mkdir(parents=True)
        (p/'SKILL.md').write_text(f'---\nname: {name}\ndescription: {description}\n---\nRead references.\n',encoding='utf-8')
        (p/'references').mkdir();(p/'references/example.md').write_text('immutable')
        return p

    def scan(self,**kwargs):
        return post(self.app,'/api/arena/skills/scan',{'scope':'custom','path':str(self.library),**kwargs})

    def import_rows(self,scan,rows=None):
        return post(self.app,'/api/arena/skills/import-selected',{'scanId':scan['scanId'],'candidateIds':[r['id'] for r in rows or scan['candidates']]})['imported']

    def test_scope_metadata_and_bulk_idempotent_snapshot(self):
        a=self.skill(self.library,'alpha');self.skill(self.library,'beta','"A quoted description"')
        scan=self.scan();self.assertEqual(len(scan['candidates']),2)
        self.assertEqual(scan['candidates'][1]['description'],'A quoted description')
        selected=self.import_rows(scan);again=self.import_rows(scan)
        self.assertEqual([s['id'] for s in selected],[s['id'] for s in again])
        self.assertEqual(len(self.app.db.list('skill')),2)
        self.assertEqual(selected[0]['scope'],'custom')
        (a/'references/example.md').write_text('changed')
        saved=self.app.local/'skills'/selected[0]['id']/'files/references/example.md'
        self.assertEqual(saved.read_text(),'immutable')
        with self.assertRaisesRegex(ValueError,'变化'):self.import_rows(scan)

    def test_global_and_project_scan_use_declared_roots(self):
        home=self.root/'home';codex=home/'different-codex'
        self.skill(home/'.agents/skills','user-one');self.skill(codex/'skills','compat-one')
        with patch('pathlib.Path.home',return_value=home),patch.dict(os.environ,{'CODEX_HOME':str(codex)}):
            found=self.scan(scope='global')['candidates']
        self.assertEqual({r['name'] for r in found},{'user-one','compat-one'})
        project=self.root/'project';self.skill(project/'.agents/skills','project-one')
        self.skill(project/'unrelated','do-not-scan')
        self.assertEqual([r['name'] for r in self.scan(scope='project',path=str(project))['candidates']],['project-one'])

    def test_conflicts_credentials_invalid_metadata_and_tampering(self):
        self.skill(self.library/'one','same');self.skill(self.library/'two','Same')
        secret=self.skill(self.library,'secret');(secret/'auth.json').write_text('{}')
        bad=self.library/'bad';bad.mkdir();(bad/'SKILL.md').write_text('no metadata')
        scan=self.scan();valid=[r for r in scan['candidates'] if not r['error']]
        self.assertTrue(all(r['duplicateName'] for r in valid))
        with self.assertRaisesRegex(ValueError,'同名'):self.import_rows(scan,valid)
        with self.assertRaisesRegex(ValueError,'无效'):self.import_rows(scan)
        with self.assertRaises(ValueError):post(self.app,'/api/arena/skills/import-selected',{'scanId':scan['scanId'],'candidateIds':['forged']})
        self.assertEqual(self.app.db.list('skill'),[])

    def test_failed_batch_leaves_no_files_or_records(self):
        self.skill(self.library,'alpha');self.skill(self.library,'beta')
        scan=self.scan()
        real=self.app.db.connect
        calls=0
        def fail_commit():
            nonlocal calls
            calls+=1
            if calls==3:raise OSError('injected transaction failure')
            return real()
        with patch.object(self.app.db,'connect',side_effect=fail_commit):
            with self.assertRaises(OSError):self.import_rows(scan)
        self.assertEqual(self.app.db.list('skill'),[])
        self.assertEqual(list((self.app.local/'skills').iterdir()),[])

    def test_config_import_provenance_and_changed_preview(self):
        project=self.root/'project';project.mkdir()
        (project/'AGENTS.md').write_text('old');(project/'AGENTS.override.md').write_text('preferred')
        (project/'.codex').mkdir()
        (project/'.codex/config.toml').write_text('model="custom-model"\nmodel_reasoning_effort="high"\napi_key="not imported"')
        before=inventory(project)
        data={'scope':'project','path':str(project)}
        preview=post(self.app,'/api/arena/configs/import-preview',data)
        self.assertEqual(preview['agentsPrompt'],'preferred');self.assertEqual(preview['baseModel'],'custom-model')
        config=post(self.app,'/api/arena/configs/import-source',{**data,'expectedFiles':preview['importSource']['files']})
        self.assertNotIn('not imported',json.dumps(config))
        config['agentsPrompt']='edited';config['importSource']={'forged':True}
        saved=self.app.save_config(config)
        self.assertEqual(saved['importSource']['root'],str(project.resolve()))
        self.assertEqual(inventory(project),before)
        (project/'AGENTS.override.md').write_text('changed')
        with self.assertRaisesRegex(ValueError,'变化'):
            post(self.app,'/api/arena/configs/import-source',{**data,'expectedFiles':preview['importSource']['files']})

    def test_workspace_prompt_is_per_config_and_frozen(self):
        self.skill(self.library,'alpha');skill=self.import_rows(self.scan())[0]
        config={'name':'selected','agentsPrompt':'rules','baseModel':'model','reasoning':'high',
                'interactiveMode':'adaptive','skills':[skill['id']],'skillMode':'explicit','customConstraints':[]}
        c=self.app.save_config(config);b=self.app.save_config({**config,'name':'plain','skills':[]})
        task=self.app.save_task({'title':'task','inputPrompt':'build','taskParadigm':'open-ended-project','channel':'deepswe-core',
                                'hasFrontendUI':False,'stages':[{'title':'one','prompt':'design'},{'title':'two','prompt':'build'}],'checks':[]})
        run=self.app.prepare({'requestId':'once','configIds':[c['id'],b['id']],'taskIds':[task['id']]})
        first=run['trials'][0];second=run['trials'][1]
        self.assertIn('明确请求使用',first['currentStage']['executionPrompt'])
        self.assertNotIn('alpha',second['currentStage']['executionPrompt'])
        self.assertEqual(len(first['executionPrompts']),2)
        self.assertTrue((Path(first['workspacePath'])/'.agents/skills/alpha/SKILL.md').is_file())
        c['skillMode']='auto';self.app.save_config(c)
        old=self.app.present_run(self.app.db.get('run',run['id']))
        self.assertEqual(old['trials'][0]['executionPrompts'],first['executionPrompts'])
        self.assertEqual(hash_bytes(first['currentStage']['executionPrompt'].encode()),first['currentStage']['promptSha256'])
        legacy=copy.deepcopy(run)
        for t in legacy['trials']:t.pop('executionPrompts')
        self.assertNotIn('明确请求使用',self.app.present_run(legacy)['trials'][0]['currentStage']['executionPrompt'])

    def test_baseline_collision_rejected_before_creating_run(self):
        self.skill(self.library,'alpha');skill=self.import_rows(self.scan())[0]
        c=self.app.save_config({'name':'c','agentsPrompt':'','baseModel':'m','reasoning':'low','interactiveMode':'adaptive','skills':[skill['id']]})
        baseline=self.root/'baseline-source';self.skill(baseline/'.agents/skills','alpha')
        imported=self.app.import_files('baseline',{'path':str(baseline)})
        t=self.app.save_task({'title':'task','inputPrompt':'build','taskParadigm':'open-ended-project','channel':'deepswe-core',
                             'hasFrontendUI':False,'stages':[{'title':'one','prompt':'design'}],'checks':[],'baselineId':imported['id']})
        with self.assertRaisesRegex(ValueError,'同名'):
            self.app.prepare({'requestId':'collision','configIds':[c['id']],'taskIds':[t['id']]})
        self.assertFalse((self.app.local/'runs').exists())

    def test_symbolic_link_not_imported(self):
        original=self.skill(self.root/'outside','alpha')
        try:(self.library/'linked').symlink_to(original,target_is_directory=True)
        except OSError:self.skipTest('symlink permission unavailable')
        self.assertEqual(self.scan()['candidates'],[])

    def test_trial_skill_changes_do_not_rewrite_saved_configs(self):
        self.skill(self.library,'alpha');skill=self.import_rows(self.scan())[0]
        config={'name':'base','agentsPrompt':'keep rules','baseModel':'model','reasoning':'high','interactiveMode':'adaptive','skills':[]}
        a=self.app.save_config(config);b=self.app.save_config({**config,'name':'control'})
        task=self.app.save_task({'title':'task','inputPrompt':'build','taskParadigm':'open-ended-project','channel':'deepswe-core',
                                'hasFrontendUI':False,'stages':[{'title':'one','prompt':'build'}],'checks':[]})
        data={'requestId':'trial-change','configIds':[a['id'],b['id']],'taskIds':[task['id']],
              'configOverrides':[{'configId':a['id'],'revision':a['revision'],'skills':[skill['id']],'skillMode':'explicit'}]}
        run=self.app.prepare(data)
        self.assertEqual(self.app.db.get('config',a['id'])['skills'],[])
        self.assertEqual(self.app.db.get('config',a['id'])['revision'],1)
        self.assertEqual(run['configs'][0]['preparationOverride']['sourceSkills'],[])
        self.assertEqual(run['configs'][0]['skills'],[skill['id']])
        self.assertNotIn('preparationOverride',run['configs'][1])
        self.assertIn('alpha',run['trials'][0]['currentStage']['executionPrompt'])
        self.assertNotIn('alpha',run['trials'][1]['currentStage']['executionPrompt'])
        self.assertTrue((Path(run['trials'][0]['workspacePath'])/'.agents/skills/alpha/SKILL.md').is_file())
        a['agentsPrompt']='new version';self.app.save_config(a)
        self.assertEqual(self.app.prepare(data)['id'],run['id'])
        self.assertEqual(self.app.prepare(data)['configs'][0]['agentsPrompt'],'keep rules')
        with self.assertRaisesRegex(ValueError,'内容已改变'):
            self.app.prepare({**data,'configOverrides':[]})

    def test_invalid_trial_changes_rejected_before_creating_workspace(self):
        self.skill(self.library/'a','same');self.skill(self.library/'b','same')
        scan=self.scan();skills=[self.import_rows(scan,[row])[0] for row in scan['candidates']]
        config=self.app.save_config({'name':'base','agentsPrompt':'','baseModel':'model','reasoning':'high','interactiveMode':'adaptive','skills':[]})
        task=self.app.save_task({'title':'task','inputPrompt':'build','taskParadigm':'open-ended-project','channel':'deepswe-core',
                                'hasFrontendUI':False,'stages':[{'title':'one','prompt':'build'}],'checks':[]})
        data={'requestId':'invalid-change','configIds':[config['id']],'taskIds':[task['id']]}
        base={'configId':config['id'],'revision':1,'skills':[],'skillMode':'auto'}
        for patch_data in [{'revision':0},{'baseModel':'injected'},{'configId':'unknown'},{'skills':['missing']},
                           {'skills':[s['id'] for s in skills]},{'skillMode':'bad'}]:
            with self.subTest(patch=patch_data),self.assertRaises(ValueError):
                self.app.prepare({**data,'configOverrides':[{**base,**patch_data}]})
        self.assertFalse((self.app.local/'runs').exists())
