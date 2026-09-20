import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from chb.arena.repository_source import unpack,import_repository


class RepositorySourceTests(unittest.TestCase):
    def archive(self,path,entries):
        with tarfile.open(path,'w:gz') as tar:
            for name,kind in entries:
                entry=tarfile.TarInfo(name)
                if kind=='link':entry.type=tarfile.SYMTYPE;entry.linkname='../../outside';tar.addfile(entry)
                else:entry.size=len(kind);tar.addfile(entry,io.BytesIO(kind))

    def test_safe_source_without_credentials_or_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);target=root/'out';target.mkdir();archive=root/'source.tar.gz'
            self.archive(archive,[('repo/main.py',b'print(1)'),('repo/.env',b'secret'),('repo/node_modules/dep.js',b'dep')])
            unpack(archive,target)
            self.assertEqual([p.name for p in target.iterdir()],['main.py'])

    def test_paths_links_and_submodules_rejected(self):
        for name,kind in [('repo/../../outside',b'x'),('repo/link','link'),('repo/.gitmodules',b'x'),('repo/C:/outside',b'x')]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);target=root/'out';target.mkdir();archive=root/'source.tar.gz';self.archive(archive,[(name,kind)])
                with self.assertRaises(ValueError):unpack(archive,target)

    def test_only_explicit_public_repository_and_fixed_revision(self):
        for url,commit in [('https://example.com/repo','a'*40),('https://github.com/u/r','main'),('https://github.com/u/../r','a'*40)]:
            with patch('chb.arena.repository_source.urlopen') as download:
                with self.assertRaises(ValueError):import_repository(MagicMock(),{'url':url,'commit':commit})
                download.assert_not_called()


if __name__=='__main__':unittest.main()
