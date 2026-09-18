import copy
import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from chb.arena.service import Arena
from chb.arena.api import post
from chb.arena import codex_apply
from chb.arena.scoring import DEFAULT_POLICY, DESKTOP_POLICY, policy, validate_review

class CodexApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'catalog').mkdir();(self.root/'catalog/arena-tasks.json').write_text('[]')
        self.home=self.root/'codex';self.home.mkdir()
        self.env=patch.dict(os.environ,{'CODEX_HOME':str(self.home)});self.env.start()
        self.original=b'# preserve comments\nmodel = "old"\napproval_policy = "on-request"\n[private]\nkey="secret-token"\n[mcp_servers.local]\ncommand="noop"\nenabled=false\n[plugins."superpowers@example"]\nenabled=false\n'
        (self.home/'config.toml').write_bytes(self.original);(self.home/'AGENTS.md').write_text('keep global')
        self.app=Arena(self.root)
        self.config=self.app.save_config({'name':'test','agentsPrompt':'new rules','baseModel':'test-model','reasoning':'high',
          'interactiveMode':'adaptive','skills':[],'nativeSettings':{'model_verbosity':'low'},
          'integrations':{'mcp_servers':{'local':True},'plugins':{'superpowers@example':True}}})
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def apply(self):return post(self.app,'/api/arena/codex/apply',{'configId':self.config['id'],'revision':self.config['revision']})
    def undo(self,r):return post(self.app,'/api/arena/codex/restore',{'applicationId':r['id']})

    def test_roundtrip_preserves_unrelated_bytes_and_private_values(self):
        r=self.apply();doc=tomllib.loads((self.home/'config.toml').read_text())
        self.assertEqual(doc['model'],'test-model');self.assertEqual(doc['private']['key'],'secret-token')
        self.assertTrue(doc['mcp_servers']['local']['enabled']);self.assertTrue(doc['plugins']['superpowers@example']['enabled'])
        self.assertEqual((self.home/'AGENTS.md').read_text(),'keep global')
        self.assertEqual((self.home/'AGENTS.override.md').read_text().strip(),'new rules')
        self.assertNotIn('secret-token',json.dumps(codex_apply.status(self.app)))
        self.undo(r);self.assertEqual((self.home/'config.toml').read_bytes(),self.original)
        self.assertFalse((self.home/'AGENTS.override.md').exists());self.assertEqual(self.undo(r)['status'],'restored')

    def test_stale_unknown_settings_and_external_edit_conflicts(self):
        with self.assertRaises(ValueError):post(self.app,'/api/arena/codex/apply',{'configId':self.config['id'],'revision':0})
        with self.assertRaises(ValueError):self.app.save_config({**self.config,'nativeSettings':{'sandbox_mode':'danger-full-access'}})
        r=self.apply()
        with self.assertRaisesRegex(ValueError,'撤销'):self.apply()
        (self.home/'config.toml').write_text('model="external-edit"')
        with self.assertRaisesRegex(ValueError,'其他操作'):self.undo(r)
        self.assertIn('external-edit',(self.home/'config.toml').read_text())

    def test_status_distinguishes_receipt_from_current_file_state(self):
        receipt=self.apply()
        status=codex_apply.status(self.app)
        self.assertEqual(status['instructionsFile'],'AGENTS.override.md')
        self.assertTrue(status['applications'][0]['filesMatch'])
        changed=(self.home/'config.toml').read_bytes()+b'\n# desktop changed an unrelated setting\n'
        (self.home/'config.toml').write_bytes(changed)
        status=codex_apply.status(self.app)
        row=status['applications'][0]
        self.assertEqual(row['status'],'applied')
        self.assertFalse(row['filesMatch'])
        self.assertEqual({f['path']:f['matches'] for f in row['fileChecks']},{'config.toml':False,'AGENTS.override.md':True})
        self.assertNotIn('secret-token',json.dumps(status))
        self.assertEqual((self.home/'config.toml').read_bytes(),changed)
        self.assertEqual(receipt['id'],row['id'])

    def test_status_after_restore_uses_base_instructions(self):
        self.undo(self.apply())
        status=codex_apply.status(self.app)
        self.assertEqual(status['instructionsFile'],'AGENTS.md')
        self.assertNotIn('filesMatch',status['applications'][0])

    def test_selective_restore_preserves_external_projects_and_comments(self):
        r=self.apply()
        path=self.home/'config.toml'
        path.write_bytes(path.read_bytes()+b'\n# desktop project\n[projects.example]\ntrust_level="trusted"\n')
        self.assertTrue(codex_apply.status(self.app)['applications'][0]['canPreserveChanges'])
        post(self.app,'/api/arena/codex/restore',{'applicationId':r['id'],'preserveUnrelated':True})
        value=path.read_text();doc=tomllib.loads(value)
        self.assertEqual(doc['model'],'old')
        self.assertFalse(doc['mcp_servers']['local']['enabled'])
        self.assertEqual(doc['projects']['example']['trust_level'],'trusted')
        self.assertIn('# desktop project',value)
        self.assertNotIn('model_reasoning_effort',doc)
        self.assertFalse((self.home/'AGENTS.override.md').exists())

    def test_selective_restore_rejects_changed_managed_value_before_any_write(self):
        r=self.apply();path=self.home/'config.toml'
        path.write_text(path.read_text().replace('test-model','external-model'))
        before=path.read_bytes();rules=(self.home/'AGENTS.override.md').read_bytes()
        self.assertFalse(codex_apply.status(self.app)['applications'][0]['canPreserveChanges'])
        with self.assertRaisesRegex(ValueError,'model'):
            post(self.app,'/api/arena/codex/restore',{'applicationId':r['id'],'preserveUnrelated':True})
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual((self.home/'AGENTS.override.md').read_bytes(),rules)

    def test_legacy_receipt_requires_exact_reconstructed_hash(self):
        r=self.apply();receipt=self.app.local/'codex-applications'/r['id']/'receipt.json'
        data=json.loads(receipt.read_text());data['files']['config.toml'].pop('after')
        receipt.write_text(json.dumps(data))
        path=self.home/'config.toml';path.write_bytes(path.read_bytes()+b'\n# later edit\n')
        self.assertTrue(codex_apply.status(self.app)['applications'][0]['canPreserveChanges'])
        post(self.app,'/api/arena/codex/restore',{'applicationId':r['id'],'preserveUnrelated':True})
        self.assertIn('# later edit',path.read_text())

    def test_changed_rules_remain_protected_during_selective_restore(self):
        r=self.apply();(self.home/'AGENTS.override.md').write_text('user changed rules')
        before=(self.home/'config.toml').read_bytes()
        with self.assertRaisesRegex(ValueError,'AGENTS.override.md'):
            post(self.app,'/api/arena/codex/restore',{'applicationId':r['id'],'preserveUnrelated':True})
        self.assertEqual((self.home/'config.toml').read_bytes(),before)

    def test_mid_write_failure_restores_prior_files(self):
        real=codex_apply.write_file;failed=False
        def fail(path,data):
            nonlocal failed
            if path.resolve()==(self.home/'AGENTS.override.md').resolve() and not failed:
                failed=True;raise OSError('injected failure')
            return real(path,data)
        with patch.object(codex_apply,'write_file',side_effect=fail):
            with self.assertRaises(OSError):self.apply()
        self.assertEqual((self.home/'config.toml').read_bytes(),self.original)
        self.assertEqual(codex_apply.status(self.app)['applications'][0]['status'],'restored')

    def test_skill_install_and_undo_no_residue(self):
        source=self.root/'skill';source.mkdir();(source/'SKILL.md').write_text('a skill')
        skill=self.app.import_files('skill',{'path':str(source),'name':'example'})
        self.config=self.app.save_config({**self.config,'skills':[skill['id']]})
        r=self.apply();self.assertEqual((self.home/'skills/example/SKILL.md').read_text(),'a skill')
        self.undo(r);self.assertFalse((self.home/'skills/example').exists())
        (self.home/'skills/example').mkdir(parents=True);(self.home/'skills/example/SKILL.md').write_text('different')
        with self.assertRaisesRegex(ValueError,'同名'):self.apply()
        self.assertEqual((self.home/'config.toml').read_bytes(),self.original)

    def test_trial_applies_frozen_config_and_tracks_expected_host(self):
        task=self.app.save_task({'title':'task','inputPrompt':'build','taskParadigm':'open-ended-project','channel':'deepswe-core','hasFrontendUI':False,'stages':[{'title':'one','prompt':'build'}],'checks':[]})
        run=self.app.prepare({'requestId':'once','configIds':[self.config['id']],'taskIds':[task['id']]});trial=run['trials'][0]
        self.app.save_config({**self.config,'baseModel':'later-model'})
        r=post(self.app,f"/api/arena/runs/{run['id']}/trials/{trial['id']}/apply-config",{})
        self.assertEqual(tomllib.loads((self.home/'config.toml').read_text())['model'],'test-model')
        captured=self.app.mutate(run['id'],trial['id'],'capture',{})
        self.assertTrue(captured['trials'][0]['captures'][0]['hostUnchanged'])
        self.assertNotEqual(captured['hostFingerprint'],captured['trials'][0]['appliedHostFingerprint'])
        self.undo(r)

    def test_unknown_connection_refuses_before_writing(self):
        self.config=self.app.save_config({**self.config,'integrations':{'plugins':{'not-installed':True}}})
        with self.assertRaisesRegex(ValueError,'安装'):self.apply()
        self.assertEqual((self.home/'config.toml').read_bytes(),self.original)

    def test_switch_removes_previous_skills_and_undo_restores_original(self):
        source=self.root/'skill';source.mkdir();(source/'SKILL.md').write_text('old skill')
        skill=self.app.import_files('skill',{'path':str(source),'name':'old-skill'})
        self.config=self.app.save_config({**self.config,'skills':[skill['id']]})
        first=self.apply()
        second=self.app.save_config({**self.config,'skills':[],'baseModel':'second-model'})
        switched=post(self.app,'/api/arena/codex/switch',{'configId':second['id'],'revision':second['revision']})
        self.assertFalse((self.home/'skills/old-skill').exists())
        self.assertEqual(tomllib.loads((self.home/'config.toml').read_text())['model'],'second-model')
        self.assertEqual(next(r for r in codex_apply.status(self.app)['applications'] if r['id']==first['id'])['status'],'restored')
        self.undo(switched);self.assertEqual((self.home/'config.toml').read_bytes(),self.original)

    def test_failed_switch_restores_original_and_active_jobs_block_undo(self):
        receipt=self.apply();self.app.jobs['test']={}
        with self.assertRaisesRegex(ValueError,'后台检查'):self.undo(receipt)
        self.app.jobs.clear()
        broken=self.app.save_config({**self.config,'integrations':{'plugins':{'missing':True}}})
        with self.assertRaisesRegex(ValueError,'已撤销旧应用'):
            post(self.app,'/api/arena/codex/switch',{'configId':broken['id'],'revision':broken['revision']})
        self.assertEqual((self.home/'config.toml').read_bytes(),self.original)
        self.assertTrue(all(r['status']=='restored' for r in codex_apply.status(self.app)['applications']))

    def test_project_settings_preserve_starting_configuration(self):
        result=tomllib.loads(codex_apply.project_settings(self.config,b'# template\n[tools]\nviewer=true\n').decode())
        self.assertEqual(result['model'],'test-model')
        self.assertTrue(result['tools']['viewer'])
        self.assertTrue(result['mcp_servers']['local']['enabled'])

    def test_custom_scoring_and_legacy_compatibility(self):
        old=policy(DEFAULT_POLICY);self.assertEqual(old,DEFAULT_POLICY)
        new=copy.deepcopy(DESKTOP_POLICY)
        new['dimensions']={'handoff':1,'custom-workflow':2,'ux':0}
        new['rubrics']={k:{'label':k,'description':'Verify concrete evidence'} for k in new['dimensions']}
        selected=policy(new)
        data={'scores':{'handoff':80,'custom-workflow':0},'notes':'evidence','readiness':'major_rework','constraints':{}}
        reviewed=validate_review(data,{'hasFrontendUI':False},[],scoring_policy=selected)
        self.assertEqual(reviewed['scores']['custom-workflow'],0)
        with self.assertRaises(ValueError):validate_review(data,{'hasFrontendUI':False},[])
        with self.assertRaises(ValueError):policy({**new,'dimensions':{'wrong':1}})
        with self.assertRaises(ValueError):policy({**new,'rubrics':None})
        empty=copy.deepcopy(new);empty['rubrics']['handoff']['label']=''
        with self.assertRaises(ValueError):policy(empty)

    def test_new_criterion_categories_preserve_independent_acceptance(self):
        from chb.arena.contracts import normalize_contract
        value={'schemaVersion':2,'criteria':[{'id':'verify','label':'Run regression','required':True,'dimension':'verification'}],
               'stages':[{'title':'build','prompt':'build'}],'checks':[]}
        result=normalize_contract(value)
        self.assertEqual(result['criteria'][0]['dimension'],'verification')
        self.assertTrue(result['criteria'][0]['required'])
