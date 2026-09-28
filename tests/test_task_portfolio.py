"""Keep the curated entry set diverse without treating an index as runnable tasks."""
import json
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from chb.arena.builtin_tasks import creative_verifier_needs_refresh, CREATIVE_WEB_VERIFIER_VERSION


ROOT=Path(__file__).resolve().parents[1]


class TaskPortfolioTests(unittest.TestCase):
    def test_creative_checker_refreshes_stale_image_only_for_trusted_task(self):
        app=SimpleNamespace(root=ROOT)
        task={'id':'original-creative-pelican-unicycle-v1'}
        image='chb-verifier:creative-web-v1'
        with patch('chb.arena.service.shell',return_value=SimpleNamespace(returncode=0,stdout='<no value>')):
            self.assertTrue(creative_verifier_needs_refresh(app,task,image))
            self.assertFalse(creative_verifier_needs_refresh(app,{'id':'custom'},image))
        with patch('chb.arena.service.shell',return_value=SimpleNamespace(returncode=0,stdout=CREATIVE_WEB_VERIFIER_VERSION+'\n')):
            self.assertFalse(creative_verifier_needs_refresh(app,task,image))

    def test_core_set_is_distinct_and_cross_type(self):
        core=json.loads((ROOT/'catalog/core-task-set.json').read_text(encoding='utf-8'))['taskIds']
        creative={entry['id']:entry for entry in json.loads((ROOT/'tasks/creative-web-v1/catalog.json').read_text(encoding='utf-8'))}
        open_work={entry['id']:entry for entry in json.loads((ROOT/'tasks/open-work-v1/catalog.json').read_text(encoding='utf-8'))}
        bundled={path.name for path in (ROOT/'tasks').iterdir() if (path/'task.toml').is_file()}
        self.assertEqual(len(core),len(set(core)))
        kinds=Counter()
        for task_id in core:
            if task_id.startswith('original-creative-'):
                self.assertIn(task_id.removeprefix('original-creative-'),creative)
                kinds['visual']+=1
            elif task_id.startswith('original-open-'):
                entry=open_work[task_id.removeprefix('original-open-')]
                self.assertTrue((ROOT/'tasks/open-work-v1/environment'/entry['id']).is_dir())
                kinds[entry['family']]+=1
            else:
                self.assertIn(task_id.removeprefix('original-'),bundled)
                kinds['bundled']+=1
        self.assertLessEqual(kinds['visual']*3,len(core))
        self.assertLessEqual(sum(creative[task_id.removeprefix('original-creative-')]['profile'] in {'svg','interactive-svg'} for task_id in core if task_id.startswith('original-creative-')),1)
        self.assertTrue(any(creative[task_id.removeprefix('original-creative-')]['category']=='三维与空间交互' and creative[task_id.removeprefix('original-creative-')]['difficulty']=='Short' for task_id in core if task_id.startswith('original-creative-')))
        for family in ('business-workflow','data-analysis','architecture-engineering',
                       'long-horizon','collaboration-planning'):
            self.assertGreater(kinds[family],0)


if __name__=='__main__':unittest.main()
