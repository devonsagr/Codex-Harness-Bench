from contextlib import contextmanager
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from chb.cli import ROOT, pin_image
from chb.profiles import digest, files_in, read_json, write_json
from chb.webapp import LocalServer, Workbench


class WebappTests(unittest.TestCase):
    def test_stale_image_name_recovers_only_exact_unique_content(self):
        candidate = 'sha256:' + 'a' * 64
        with patch('chb.cli.image_id', side_effect=[subprocess.CalledProcessError(1, 'inspect'), candidate]), \
                patch('chb.cli.command', return_value=SimpleNamespace(stdout='other:tag sha256:other\nwanted:tag '+candidate)) as command:
            self.assertEqual(pin_image('wanted:tag'), candidate)
            self.assertIn(['docker', 'image', 'tag', candidate, 'wanted:tag'], [call.args[0] for call in command.call_args_list])
        with patch('chb.cli.image_id', side_effect=subprocess.CalledProcessError(1, 'inspect')), \
                patch('chb.cli.command', return_value=SimpleNamespace(stdout='other:tag '+candidate)):
            with self.assertRaisesRegex(ValueError, 'missing or ambiguous'):
                pin_image('wanted:tag')

    @contextmanager
    def app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "profiles", root / "profiles")
            shutil.copytree(ROOT / "tasks", root / "tasks")
            (root / "src/chb").mkdir(parents=True)
            (root / "src/chb/fixture.py").write_text("# test runner")
            yield Workbench(root)

    def selection(self):
        return {"profiles": ["minimal", "focused"], "tasks": ["search-notes-v1", "storage-migration-v1", "csv-catalog-v1"],
                "model": "openai/test", "repeat": 1}

    def create(self, app):
        preview = app.post('/api/plans/preview', self.selection())
        with patch('chb.cli.pin_image', side_effect=lambda name: 'sha256:' + name):
            result = app.post('/api/plans/create', {'preview_id': preview['preview_id']})
        self.assertEqual(result['model_calls_started'], 0)
        return result['id']

    def test_preview_budget_save_and_stale_inputs(self):
        with self.app() as app:
            preview = app.post('/api/plans/preview', self.selection())
            self.assertEqual((preview['trials'], preview['turns'], preview['budget_seconds']), (6, 8, 2400))
            self.assertFalse((app.root / 'runs').exists())
            (app.root / 'profiles/minimal/AGENTS.md').write_text('Changed after preview')
            with patch('chb.webapp.make_plan') as make:
                with self.assertRaisesRegex(ValueError, '变化'):
                    app.post('/api/plans/create', {'preview_id': preview['preview_id']})
                make.assert_not_called()
            result = self.create(app)
            self.assertEqual(app.experiment(result)['status'], 'planned')
            self.assertFalse(any((app.root / 'runs' / result).glob('trial-*')))
            for value in [True, 0, 6, '2']:
                with self.assertRaises(ValueError):
                    app.post('/api/plans/preview', {**self.selection(), 'repeat': value})
            for profiles in [['minimal', 'minimal'], ['../private', 'focused'], ['minimal']]:
                with self.assertRaises(ValueError):
                    app.post('/api/plans/preview', {**self.selection(), 'profiles': profiles})

    def test_edit_copy_and_restore_do_not_change_source_or_history(self):
        with self.app() as app:
            skill = app.root / 'profiles/minimal/skills/workflow/SKILL.md'
            skill.parent.mkdir(parents=True)
            skill.write_text('workflow rules')
            before = files_in(app.root / 'profiles')
            profile = app.profile('minimal')
            payload = {'source': 'minimal', 'source_sha256': profile['sha256'], 'name': 'edited',
                       'agents': 'new instructions', 'description': 'my edited copy', 'reasoning': 'medium', 'skills': []}
            created = app.post('/api/profiles/save', payload)
            self.assertEqual(created['agents'], 'new instructions')
            self.assertEqual(created['skills'], [])
            self.assertTrue(created['private'])
            self.assertEqual(files_in(app.root / 'profiles'), before)
            with self.assertRaises(ValueError):
                app.post('/api/profiles/save', payload)
            experiment = self.create(app)
            original = files_in(app.root / 'runs' / experiment)
            restored = app.post('/api/profiles/restore', {'experiment': experiment, 'profile': 'minimal', 'name': 'restored'})
            self.assertEqual(restored['agents'], profile['agents'])
            self.assertEqual(restored['skills'], ['workflow'])
            self.assertEqual(files_in(app.root / 'runs' / experiment), original)
            self.assertEqual(files_in(app.root / 'profiles'), before)

    def test_incomplete_history_is_read_only_and_redacts_error_trace(self):
        with self.app() as app:
            exp = self.create(app)
            path = app.root / 'runs' / exp
            write_json(path / 'trial-001/result.json', {'status':'completed', 'accepted':True, 'input_tokens':10})
            write_json(path / 'trial-002/result.json', {'status':'execution_error', 'accepted':None,
                       'error':{'exception_message':'Your workspace is out of credits. private-secret-token', 'exception_traceback':'private trace'}})
            before = files_in(path)
            result = app.experiment(exp)
            self.assertEqual((result['status'], result['finished'], result['pending']), ('interrupted',2,4))
            self.assertEqual(result['groups'][0]['accepted_pairs'], 0)
            self.assertNotIn('private-secret-token', json.dumps(result))
            self.assertNotIn('private trace', json.dumps(result))
            self.assertIn('额度不足', result['trials'][1]['cause'])
            self.assertEqual(app.state()['experiments'][0]['id'], exp)
            self.assertEqual(files_in(path), before)
            with self.assertRaises(ValueError):
                app.experiment('../../auth.json')

    def test_loopback_host_csrf_encoded_routes_and_assets(self):
        with self.app() as app:
            server = LocalServer(app.root, 0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            def request(method, path, data=None, headers=None):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                connection.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers or {})
                response = connection.getresponse()
                body = response.read()
                info = (response.status, dict(response.getheaders()), body)
                connection.close()
                return info
            try:
                status, headers, body = request('GET', '/')
                self.assertEqual(status, 200)
                self.assertIn(server.token.encode(), body)
                self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
                self.assertNotIn('Access-Control-Allow-Origin', headers)
                self.assertEqual(request('GET', '/', headers={'Host':'evil.example'})[0], 403)
                self.assertEqual(request('GET', '/api/state')[0], 403)
                self.assertEqual(request('GET', '/%61pi/state')[0], 403)
                good = {'X-CHB-Token':server.token, 'Content-Type':'application/json', 'Origin':server.origin}
                self.assertEqual(request('POST', '/api/plans/preview', self.selection(), {**good, 'Origin':'https://evil.example'})[0],403)
                self.assertEqual(request('POST', '/api/plans/preview', self.selection(), good)[0],200)
                self.assertEqual(request('GET', '/api/state', headers=good)[0],200)
                self.assertEqual(request('GET', '/api/profiles/%2e%2e%2fauth.json', headers=good)[0],400)
                self.assertEqual(request('GET', '/.local/profiles/current/auth.json')[0],404)
                self.assertEqual(request('GET', '/app.js')[0],200)
                self.assertEqual(request('GET', '/app.css')[0],200)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_linked_profile_parent_is_rejected_before_read(self):
        with self.app() as app:
            external = app.root / 'external'
            external.mkdir()
            try:
                (app.root / '.local').symlink_to(external, target_is_directory=True)
            except OSError:
                self.skipTest('Cannot create test symlink')
            try:
                with self.assertRaisesRegex(ValueError, '链接|联接'):
                    app.profile('minimal')
            finally:
                # Remove only the test-created link before TemporaryDirectory cleanup.
                (app.root / '.local').unlink()


if __name__ == '__main__':
    unittest.main()
