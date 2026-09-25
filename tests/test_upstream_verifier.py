import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from chb.arena.upstream_verifier import make_patch,_image,failed_tests


class UpstreamVerifierTests(unittest.TestCase):
    def test_failed_upstream_tests_explain_zero_without_hiding_environment_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'ctrf.json').write_text(json.dumps({'results':{'tests':[
                {'name':'[f2p] new behavior','status':'failed','message':'expected 2, got 1'},
                {'name':'[p2p] existing behavior','status':'passed'},
            ]}}),encoding='utf-8')
            self.assertEqual(failed_tests(root,{'reward':0}),['[f2p] new behavior：expected 2, got 1'])
            self.assertEqual(failed_tests(root,{'reward':0,'apply_failed':1}),
                             ['提交补丁未能应用到固定源码起点；查看测试输出中的 apply 错误。'])
            self.assertEqual(failed_tests(root,{'reward':1}),[])

    def test_unresponsive_docker_is_unknown_with_actionable_error(self):
        with tempfile.TemporaryDirectory() as temp,patch('chb.arena.upstream_verifier.shell',side_effect=subprocess.TimeoutExpired('docker',15)):
            with self.assertRaisesRegex(ValueError,'15秒内响应'):
                _image(None,'fixed:image',threading.Event(),Path(temp),lambda _:None)

    def test_patch_uses_only_frozen_project_changes_and_applies_cleanly(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);base=root/'base';candidate=root/'candidate';stage=root/'stage';replica=root/'replica'
            for folder in (base,candidate,stage,replica):folder.mkdir()
            (base/'change.py').write_text('value = 1\n',encoding='utf-8')
            (base/'delete.py').write_text('obsolete = True\n',encoding='utf-8')
            (candidate/'change.py').write_text('value = 2\n',encoding='utf-8')
            (candidate/'add.py').write_text('new = True\n',encoding='utf-8')
            (candidate/'AGENTS.md').write_text('private harness rule',encoding='utf-8')
            (candidate/'.codex').mkdir();(candidate/'.codex/config.toml').write_text('model="fixture"',encoding='utf-8')
            patch=make_patch(base,candidate,stage)
            self.assertNotIn(b'AGENTS.md',patch)
            self.assertNotIn(b'.codex',patch)
            (replica/'change.py').write_text('value = 1\n',encoding='utf-8')
            (replica/'delete.py').write_text('obsolete = True\n',encoding='utf-8')
            result=subprocess.run(['git','apply','--whitespace=nowarn','-'],cwd=replica,input=patch,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((replica/'change.py').read_text(encoding='utf-8'),'value = 2\n')
            self.assertFalse((replica/'delete.py').exists())
            self.assertEqual((replica/'add.py').read_text(encoding='utf-8'),'new = True\n')


if __name__=='__main__':unittest.main()
