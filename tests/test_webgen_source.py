import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from chb.arena.webgen_source import definitions, short_candidate, task_definition, install, COMMIT
from chb.arena.service import Arena


class WebGenSourceTests(unittest.TestCase):
    def rows(self):
        return [{'id': f'{index:06}', 'instruction': 'Create a local timer. Allow pausing.',
            'application_type': 'Productivity Applications', 'ui_instruct': [{'task': 'Pause timer', 'expected_result': 'The time stops.'}]} for index in range(101)]

    def test_checksum_rejects_changed_upstream(self):
        with self.assertRaisesRegex(ValueError, '校验'):
            definitions(b'changed')

    def test_task_preserves_prompt_and_expected_results(self):
        row = self.rows()[0]
        task = task_definition(row, 'blank')
        self.assertEqual(task['inputPrompt'], row['instruction'])
        self.assertEqual(task['criteria'][0]['description'], row['ui_instruct'][0]['expected_result'])
        self.assertNotIn('publicSource', task)
        self.assertEqual(task['checks'], [])
        self.assertIn('不是原版', task['evaluationRubric'][1])

    def test_default_draw_excludes_external_service_scope(self):
        row = self.rows()[0]
        self.assertTrue(short_candidate(row))
        for prompt in ('Create a payment service.', 'Use an API for live stock data.', 'Implement authentication.'):
            self.assertFalse(short_candidate({**row, 'instruction': prompt}))

    def test_install_is_idempotent_and_does_not_restore_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'catalog').mkdir();(root/'catalog/arena-tasks.json').write_text('[]')
            fixture = root/'tasks/creative-web-v1/environment/fixture';fixture.mkdir(parents=True)
            (fixture/'index.html').write_text('<html></html>')
            home = root/'home';home.mkdir()
            raw = '\n'.join(json.dumps(row) for row in self.rows()).encode()
            with patch.dict(os.environ, {'CODEX_HOME': str(home)}), patch('chb.arena.webgen_source.SHA256', hashlib.sha256(raw).hexdigest()):
                app = Arena(root)
                cache = app.local/'public-sources/webgen-bench'/COMMIT;cache.mkdir(parents=True)
                (cache/'test.jsonl').write_bytes(raw)
                self.assertEqual(install(app)['added'], 101)
                before = app.db.list('task')
                self.assertEqual(install(app)['added'], 0)
                self.assertEqual(app.db.list('task'), before)
                task = app.db.get('task', 'webgen-000000')
                app.db.archive('task', task['id'], True, task['revision'])
                self.assertEqual(install(app)['added'], 0)
                self.assertTrue(app.db.get('task', task['id'])['archived'])
