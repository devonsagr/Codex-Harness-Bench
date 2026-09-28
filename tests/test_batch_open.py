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

    def test_batch_launches_only_the_explicit_draft_and_retries_failures(self):
        route=f'/api/arena/runs/{self.run["id"]}/open-batch'
        confirm=f'/api/arena/runs/{self.run["id"]}/confirm-batch-draft'
        first_id,second_id=[trial['id'] for trial in self.run['trials']]
        with patch('chb.arena.service.os.startfile') as open_draft:
            with self.assertRaises(ValueError):post(self.app,route,{})
            first=post(self.app,route,{'trialId':first_id})
        self.assertEqual(len(first['openedTrialIds']),1)
        self.assertEqual(first['openedTrialIds'],[first_id])
        self.assertEqual(open_draft.call_count,1)
        self.assertIsNone(self.app.db.get('run',self.run['id'])['trials'][1].get('draftOpenedAt'))
        with self.assertRaisesRegex(ValueError,'仍待确认'):
            post(self.app,route,{'trialId':second_id})
        with self.assertRaises(ValueError):post(self.app,confirm,{'trialId':first_id})
        cancelled=post(self.app,confirm,{'trialId':first_id,'confirmed':False})
        self.assertEqual(cancelled['status'],'cancelled')
        with patch('chb.arena.service.os.startfile',side_effect=[OSError('fixture'),None]) as open_draft:
            failed=post(self.app,route,{'trialId':first_id})
            self.assertEqual(failed['failedTrialId'],first_id)
            self.assertIn('无法打开',failed['error'])
            self.assertEqual(open_draft.call_count,1)
            retried=post(self.app,route,{'trialId':first_id})
            self.assertEqual(retried['openedTrialIds'],[first_id])
            self.assertEqual(open_draft.call_count,2)
        self.assertEqual(post(self.app,confirm,{'trialId':first_id,'confirmed':True})['status'],'confirmed')
        with patch('chb.arena.service.os.startfile') as open_draft:
            second=post(self.app,route,{'trialId':second_id})
        self.assertEqual(second['openedTrialIds'],[second_id])
        self.assertEqual(open_draft.call_count,1)
        self.assertTrue(all(t.get('draftOpenedAt') for t in self.app.db.get('run',self.run['id'])['trials']))
        with patch('chb.arena.service.os.startfile') as reopen_draft:
            post(self.app,f'/api/arena/runs/{self.run["id"]}/trials/{first_id}/open',{'draft':True})
        self.assertEqual(reopen_draft.call_count,1)


if __name__=='__main__':unittest.main()
