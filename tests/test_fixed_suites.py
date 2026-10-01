import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from chb.arena.evalplus_source import COMMIT, definitions, install, task_definition
from chb.arena.fixed_suites import summary
from chb.arena.community_tasks import catalog
from chb.arena.experiments import delivery
from chb.arena.service import Arena
from chb.cli import ROOT


class FixedSuiteTests(unittest.TestCase):
    def fixture(self):
        task = task_definition({'task_id':'HumanEval/0','entry_point':'f','prompt':'def f(x):\n','test':'def check(f): assert f(1)==1'}, 'baseline')
        task['revision'] = 1
        contract = task['fixedSuite']
        output = {'version':contract['version'],'task':contract['task'],'testSha256':contract['testSha256'],
                  'rows':[{'id':'suite','status':'passed','detail':'OK'}]}
        check = {**task['checks'][0], 'status':'passed', 'imageId':'sha256:fixed', 'output':json.dumps(output)}
        return task, {'state':'prepared','captures':[{'id':'capture','manifest':{'sha256':'snapshot'},'checks':[check]}]}

    def test_program_result_needs_neither_ai_nor_delivery_end(self):
        task, trial = self.fixture()
        self.assertEqual(summary(task,trial)['score'], 100)
        self.assertEqual(delivery(task,trial)['status'], 'passed')
        self.assertFalse(summary(task,trial)['qualityCertified'])

    def test_explicit_failure_cannot_be_averaged_away_by_ai(self):
        task, trial = self.fixture()
        check = trial['captures'][0]['checks'][0]
        payload = json.loads(check['output']);payload['rows'][0]['status']='failed'
        check.update(status='failed',output=json.dumps(payload))
        trial['reviews']=[{'scores':{'intent':100}}]
        self.assertEqual(summary(task,trial)['score'], 0)
        self.assertEqual(delivery(task,trial)['status'], 'failed')

    def test_timeout_or_incomplete_suite_is_unknown(self):
        task, trial = self.fixture()
        check=trial['captures'][0]['checks'][0]
        payload=json.loads(check['output']);payload['rows'][0]['status']='unverified'
        check.update(status='failed',output=json.dumps(payload))
        self.assertIsNone(summary(task,trial)['score'])
        self.assertEqual(delivery(task,trial)['status'],'unknown')

    def test_checker_exit_two_is_environment_unknown_not_wrong_answer(self):
        from chb.arena.database import Database
        from chb.arena.jobs import run_checks
        for kind in ('evalplus-local','community-adapted'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                task,trial=self.fixture();task['sourceKind']=kind
                capture=trial['captures'][0];capture.update(stageIndex=0,checkImages={'suite':'sha256:fixed'})
                db=Database(Path(tmp)/'db.sqlite3')
                db.save('run',{'id':'r','trials':[{'id':'t','captures':[capture]}]})
                def get_trial(rid,tid):
                    run=db.get('run',rid);return run,run['trials'][0]
                app=SimpleNamespace(root=ROOT,local=Path(tmp),lock=threading.RLock(),db=db,trial=get_trial,event=lambda *args:None)
                def shell(args,**kwargs):
                    return SimpleNamespace(returncode=0,stdout='container-id' if args[1]=='create' else '2')
                def popen(args,**kwargs):
                    kwargs['stdout'].write(b'{"rows":[]}')
                    return SimpleNamespace(wait=lambda **kwargs:0,poll=lambda:0)
                with patch('chb.arena.jobs.verify_snapshot'),patch('chb.arena.jobs.shell',side_effect=shell),patch('chb.cli.pin_image',return_value='sha256:fixed'),patch('chb.arena.jobs.subprocess.Popen',side_effect=popen):
                    reports=run_checks(app,'r','t',capture,task,{'stop':threading.Event(),'containers':set()})
                self.assertEqual(reports[0]['status'],'error')
                self.assertEqual(reports[0]['exitCode'],2)
                capture['checks']=reports
                if kind=='evalplus-local':
                    self.assertEqual(delivery(task,trial)['status'],'unknown')
                self.assertEqual(db.get('run','r')['trials'][0]['ownedContainers'],[])

    def test_changed_protocol_truncated_missing_or_contradictory_receipts_fail_closed(self):
        for change in ('hash','version','task','duplicate','missing','bad-status','contradiction','truncated','image','argv'):
            with self.subTest(change=change):
                task,trial=self.fixture();check=trial['captures'][0]['checks'][0];p=json.loads(check['output'])
                if change in ('hash','version','task'):p[{'hash':'testSha256','version':'version','task':'task'}[change]]='wrong'
                elif change=='duplicate':p['rows']*=2
                elif change=='missing':p['rows']=[]
                elif change=='bad-status':p['rows'][0]['status']='partial'
                elif change=='contradiction':check['status']='failed'
                elif change=='truncated':check['outputTruncated']=True
                elif change=='image':check['imageId']='mutable:tag'
                elif change=='argv':check['argv']=['wrong']
                check['output']=json.dumps(p)
                self.assertEqual(summary(task,trial)['unverified'],1)

    def test_latest_snapshot_does_not_inherit_old_pass(self):
        task,trial=self.fixture()
        trial['captures'].append({'id':'new','manifest':{'sha256':'changed'},'checks':[]})
        self.assertIsNone(summary(task,trial)['score'])
        task['revision']=2
        self.assertIsNone(summary(task,trial))

    def test_malformed_user_metadata_does_not_crash(self):
        task,trial=self.fixture()
        for value in ([], 'bad', 3):
            task['fixedSuite']=value
            self.assertIsNone(summary(task,trial))

    def test_community_requires_all_fixed_cases_and_is_not_whole_project_pass(self):
        task,trial=self.fixture();task.update(sourceKind='community-adapted',fixedSuite={
            'version':'community-engine-v1','task':'fixture','testSha256':'hash','caseIds':['a','b']})
        check=trial['captures'][0]['checks'][0]
        check.update(status='failed',output=json.dumps({'version':'community-engine-v1','task':'fixture','testSha256':'hash',
            'rows':[{'id':'a','status':'passed','detail':'a'},{'id':'b','status':'failed','detail':'b'}]}))
        self.assertEqual(summary(task,trial)['score'],50)
        # Core results never certify the entire visual project.
        self.assertFalse(summary(task,trial)['qualityCertified'])

    def test_catalog_has_77_distinct_cases_and_checksum(self):
        rows=catalog(ROOT);cases=json.loads((ROOT/'tasks/community-web-v1/tests/cases.json').read_text(encoding='utf-8'))
        sha=hashlib.sha256((ROOT/'tasks/community-web-v1/tests/cases.json').read_bytes()).hexdigest()
        self.assertEqual(len(rows),8);self.assertEqual(sum(len(v) for v in cases.values()),77)
        for row in rows:
            self.assertEqual(row['caseIds'],[r['id'] for r in cases[row['id']]])
            self.assertEqual(row['testSha256'],sha)

    def test_dataset_checksum_and_id_membership(self):
        with self.assertRaisesRegex(ValueError,'校验'):definitions(b'bad')
        raw=gzip.compress(b'{"task_id":"HumanEval/0"}')
        with patch('chb.arena.evalplus_source.SHA256',hashlib.sha256(raw).hexdigest()):
            with self.assertRaisesRegex(ValueError,'数量'):definitions(raw)

    def test_broken_export_is_not_a_runnable_task(self):
        with self.assertRaisesRegex(ValueError,'资格检查'):
            task_definition({'task_id':'HumanEval/32'},'baseline')

    def test_import_and_archive_do_not_overwrite_or_leak_oracles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'catalog').mkdir();(root/'catalog/arena-tasks.json').write_text('[]')
            shutil.copytree(ROOT/'profiles',root/'profiles')
            rows=[{'task_id':f'HumanEval/{i}','entry_point':'f','prompt':'def f(x):\n','test':'def check(f): assert f(1)==1','canonical_solution':'    return x # SECRET_ORACLE'} for i in range(164)]
            app=Arena(root)
            with patch('chb.arena.evalplus_source.dataset',return_value=rows):
                self.assertEqual(install(app)['added'],163)
                self.assertNotIn('evalplus-32',{t['id'] for t in app.db.list('task')})
                task=app.db.get('task','evalplus-0');app.db.archive('task',task['id'],True,task['revision'])
                before=copy.deepcopy(app.db.list('task'))
                self.assertEqual(install(app)['added'],0);self.assertEqual(before,app.db.list('task'))
            for file in (app.local/'public-sources/evalplus-starters').rglob('*'):
                if file.is_file():
                    self.assertNotIn('SECRET_ORACLE',file.read_text());self.assertNotIn('def check',file.read_text())


if __name__=='__main__':unittest.main()
