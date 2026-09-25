import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chb.arena.api import post
from chb.arena.service import Arena


class BatchOpenTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'catalog').mkdir();(self.root/'catalog/arena-tasks.json').write_text('[]',encoding='utf-8')
        self.app=Arena(self.root)
        config=self.app.save_config({'name':'fixture','baseModel':'fixture','reasoning':'low','agentsPrompt':'','interactiveMode':'adaptive','skills':[]})
        tasks=[self.app.save_task({'title':f'task {i}','inputPrompt':f'implement {i}','taskParadigm':'open-ended-project','channel':'deepswe-core','checks':[]}) for i in range(2)]
        self.run=self.app.prepare({'requestId':'batch-fixture','configIds':[config['id']],'taskIds':[t['id'] for t in tasks]})

    def tearDown(self):self.temp.cleanup()

    def test_batch_opens_only_unopened_trial_drafts_and_retries_partial(self):
        route=f'/api/arena/runs/{self.run["id"]}/open-batch'
        with patch('chb.arena.service.os.startfile',side_effect=[None,OSError('fixture')]) as open_draft:
            first=post(self.app,route,{})
        self.assertEqual(len(first['openedTrialIds']),1)
        self.assertEqual(first['failedTrialId'],self.run['trials'][1]['id'])
        self.assertIn('无法打开',first['error'])
        self.assertEqual(open_draft.call_count,2)
        with patch('chb.arena.service.os.startfile') as open_draft:
            second=post(self.app,route,{})
            third=post(self.app,route,{})
        self.assertEqual(second['openedTrialIds'],[self.run['trials'][1]['id']])
        self.assertEqual(third['openedTrialIds'],[])
        self.assertEqual(open_draft.call_count,1)
        self.assertTrue(all(t.get('draftOpenedAt') for t in self.app.db.get('run',self.run['id'])['trials']))


if __name__=='__main__':unittest.main()
