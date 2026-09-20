import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch,MagicMock

from chb.arena.local_review import execute_local, output_schema, ProcessTree, failure_reason, codex_executable


class LocalReviewTests(unittest.TestCase):
    def test_only_fixed_sandboxed_invocation_and_auth_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);home=root/'home';home.mkdir();(home/'auth.json').write_text('{"fixture":true}')
            folder=root/'review';source=folder/'task';source.mkdir(parents=True);(source/'instruction.md').write_text('fixture')
            copied_home=[]
            def launch(args,**kwargs):
                self.assertEqual(args[args.index('-s')+1],'workspace-write')
                self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',args)
                self.assertIn('--ignore-user-config',args);self.assertIn('--output-schema',args)
                self.assertIn('model_reasoning_effort="max"',args)
                self.assertNotIn('OPENAI_API_KEY',kwargs['env'])
                self.assertEqual(Path(kwargs['env']['NPM_CONFIG_USERCONFIG']).read_text(),'')
                self.assertNotEqual(kwargs['env']['NPM_CONFIG_USERCONFIG'],kwargs['env']['NPM_CONFIG_GLOBALCONFIG'])
                self.assertTrue(Path(kwargs['env']['TMP']).is_relative_to(kwargs['cwd']))
                copied_home.append(Path(kwargs['env']['CODEX_HOME']))
                self.assertTrue((copied_home[-1]/'auth.json').exists())
                self.assertFalse(copied_home[-1].is_relative_to(kwargs['cwd']))
                Path(args[args.index('-o')+1]).write_text('{"summary":"fixture","findings":[]}')
                return MagicMock(returncode=0,poll=lambda:0)
            with patch.dict(os.environ,{'CODEX_HOME':str(home),'OPENAI_API_KEY':'never-forward'}),patch('chb.arena.local_review.shutil.which',return_value='codex'),patch('chb.arena.local_review.subprocess.run',return_value=MagicMock(stdout='codex fixture')),patch('chb.arena.local_review.subprocess.Popen',side_effect=launch),patch('chb.arena.local_review.ProcessTree') as tree:
                _,answer,_=execute_local(folder,source,'fixture','fixture',{}, {'stop':threading.Event()},1)
                self.assertEqual(json.loads(answer)['summary'],'fixture');tree.return_value.close.assert_called_once()
            self.assertFalse(copied_home[0].exists());self.assertFalse((folder/'auth.json').exists())

    def test_nonstandard_cli_path_can_be_explicitly_configured(self):
        with tempfile.TemporaryDirectory() as temp:
            binary=Path(temp)/'codex-custom.exe';binary.write_bytes(b'fixture')
            with patch.dict(os.environ,{'CHB_CODEX_BIN':str(binary)},clear=False):
                self.assertEqual(codex_executable(),str(binary.resolve()))

    def test_stop_cleans_owned_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);home=root/'home';home.mkdir();(home/'auth.json').write_text('{}')
            folder=root/'review';source=folder/'task';source.mkdir(parents=True);(source/'instruction.md').write_text('fixture')
            stop=threading.Event();stop.set()
            with patch.dict(os.environ,{'CODEX_HOME':str(home)}),patch('chb.arena.local_review.shutil.which',return_value='codex'),patch('chb.arena.local_review.subprocess.run',return_value=MagicMock(stdout='fixture')),patch('chb.arena.local_review.subprocess.Popen',return_value=MagicMock(poll=lambda:None)),patch('chb.arena.local_review.ProcessTree') as tree:
                with self.assertRaisesRegex(ValueError,'取消'):execute_local(folder,source,'fixture','fixture',{}, {'stop':stop},1)
                tree.return_value.close.assert_called_once()

    def test_real_owned_process_stops_without_model(self):
        import subprocess,sys
        process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')
        tree=ProcessTree(process);tree.close();self.assertIsNotNone(process.poll())

    def test_schema_matches_applicable_dimensions(self):
        packet={'task':{'hasFrontendUI':False,'criteria':[{'id':'required'}]},'policy':{'dimensions':{'intent':90,'ux':10}}}
        schema=output_schema(packet)
        self.assertEqual(list(schema['properties']['ratings']['properties']),['intent'])
        self.assertEqual(list(schema['properties']['criteria']['properties']),['required'])

    def test_quota_failure_has_actionable_message_without_raw_output(self):
        with tempfile.TemporaryDirectory() as temp:
            log=Path(temp)/'events.jsonl'
            log.write_text('Your workspace is out of credits. private diagnostic')
            message=failure_reason(log)
            self.assertIn('额度不足',message)
            self.assertNotIn('private diagnostic',message)


if __name__=='__main__':unittest.main()
