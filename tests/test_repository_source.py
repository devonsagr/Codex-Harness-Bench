import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from chb.arena.repository_source import unpack,import_repository,pinned_submodules


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

    def test_submodule_uses_gitlink_commit_and_is_included_in_baseline(self):
        parent='a'*40;child='b'*40
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);main=root/'main.tar.gz';nested=root/'nested.tar.gz'
            self.archive(main,[('repo/.gitmodules',b'[submodule "data"]\n\tpath = benchmarks/release_data\n\turl = https://github.com/reagento/adaptix-benchmarks-data\n\tbranch = main\n'),('repo/main.py',b'print(1)')])
            self.archive(nested,[('data/results.json',b'{}')])
            response=MagicMock()
            response.__enter__.return_value=response
            response.url='https://api.github.com/repos/reagento/adaptix/git/trees/'+parent
            response.read.return_value=json.dumps({'tree':[{'path':'benchmarks/release_data','mode':'160000','sha':child}]}).encode()
            saved={}
            def imported(kind,data):
                source=Path(data['path'])
                saved['child']=(source/'benchmarks/release_data/results.json').read_bytes()
                saved['main']=(source/'main.py').read_bytes()
                return {'id':'baseline-test','revision':1}
            app=SimpleNamespace(local=root,lock=nullcontext(),import_files=imported,
                                db=SimpleNamespace(save=lambda kind,value,revision:value))
            calls=[]
            def archive(owner,repo,commit,destination,budget,deadline):
                calls.append((owner,repo,commit))
                source=main if len(calls)==1 else nested
                shutil.copyfile(source,destination)
                return source.stat().st_size
            with patch('chb.arena.repository_source.github_archive',side_effect=archive),patch('chb.arena.repository_source.urlopen',return_value=response):
                baseline=import_repository(app,{'url':'https://github.com/reagento/adaptix','commit':parent})
            self.assertEqual(calls,[('reagento','adaptix',parent),('reagento','adaptix-benchmarks-data',child)])
            self.assertEqual(saved,{'child':b'{}','main':b'print(1)'})
            self.assertEqual(baseline['submodules'][0]['sourceCommit'],child)

    def test_submodule_requires_matching_public_pinned_gitlink(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)
            modules=source/'.gitmodules'
            modules.write_text('[submodule "data"]\n path = data\n url = https://example.com/private\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'公开 GitHub'):
                pinned_submodules(source,'owner','repo','a'*40)
            modules.write_text('[submodule "data"]\n path = data\n url = https://github.com/owner/data\n',encoding='utf-8')
            response=MagicMock();response.__enter__.return_value=response
            response.url='https://api.github.com/repos/owner/repo/git/trees/'+'a'*40
            response.read.return_value=b'{"tree":[]}'
            with patch('chb.arena.repository_source.urlopen',return_value=response):
                with self.assertRaisesRegex(ValueError,'不一致'):
                    pinned_submodules(source,'owner','repo','a'*40)


if __name__=='__main__':unittest.main()
