import json
import tempfile
import unittest
from pathlib import Path

from chb.arena.cache_location import move_public_cache
from chb.arena.public_sources import cache_root
from chb.arena.service import Arena


class CacheLocationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/'project'
        (self.root/'catalog').mkdir(parents=True)
        (self.root/'catalog/arena-tasks.json').write_text('[]',encoding='utf-8')
        self.app=Arena(self.root)
        source=self.app.public_sources_root/'selected/revision/task/files'
        source.mkdir(parents=True)
        (source/'instruction.md').write_text('fixed public definition',encoding='utf-8')

    def tearDown(self):self.temp.cleanup()

    def test_migration_is_verified_persistent_and_does_not_move_runs(self):
        existing=self.app.local/'runs/keep/workspace'
        existing.mkdir(parents=True)
        (existing/'result.txt').write_text('private result',encoding='utf-8')
        target=Path(self.temp.name)/'other-drive-style-location'/'public-sources'
        result=move_public_cache(self.app,{'destination':str(target),'confirmation':'迁移题包缓存'})
        self.assertEqual(result['migration']['files'],1)
        self.assertEqual(result['publicSourcesRoot'],str(target.resolve()))
        self.assertEqual((target/'selected/revision/task/files/instruction.md').read_text(encoding='utf-8'),'fixed public definition')
        self.assertTrue((existing/'result.txt').is_file())
        self.assertFalse((self.app.local/'public-sources').exists())
        self.assertEqual(Arena(self.root).public_sources_root,target.resolve())
        self.assertEqual(json.loads((self.app.local/'public-sources-location.json').read_text(encoding='utf-8'))['path'],str(target.resolve()))

    def test_rejects_existing_target_and_paths_overlapping_local_data(self):
        target=Path(self.temp.name)/'existing';target.mkdir()
        with self.assertRaisesRegex(ValueError,'已存在'):
            move_public_cache(self.app,{'destination':str(target),'confirmation':'迁移题包缓存'})
        with self.assertRaisesRegex(ValueError,'项目数据目录'):
            move_public_cache(self.app,{'destination':str(self.app.local/'another'),'confirmation':'迁移题包缓存'})
        self.assertTrue((self.app.public_sources_root/'selected/revision/task/files/instruction.md').is_file())

    def test_missing_external_cache_is_not_silently_recreated(self):
        target=Path(self.temp.name)/'external'/'public-sources'
        move_public_cache(self.app,{'destination':str(target),'confirmation':'迁移题包缓存'})
        target.rename(target.parent/'disconnected')
        restarted=Arena(self.root)
        with self.assertRaisesRegex(ValueError,'外置题包缓存位置不可用'):cache_root(restarted)
        self.assertFalse(target.exists())


if __name__=='__main__':unittest.main()
