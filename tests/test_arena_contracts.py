"""Contract fidelity, transactional import, and evidence-based acceptance gates."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from chb.arena.api import post
from chb.arena.contracts import normalize_contract, stage_prompt, applicable_checks
from chb.arena.scoring import calculate, DEFAULT_POLICY
from chb.arena.service import Arena

ROOT=Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        shutil.copytree(ROOT/'profiles',self.root/'profiles')
        (self.root/'catalog').mkdir();(self.root/'catalog/arena-tasks.json').write_text('[]')
        self.app=Arena(self.root)
        self.definition={'title':'Contract fixture','inputPrompt':'Build a task board','taskParadigm':'open-ended-project',
                         'channel':'frontend-ui','difficulty':'Hard','hasFrontendUI':True,'checks':[],
                         'projectSpec':{'userStories':['新增任务'],'apiEndpoints':['POST /tasks'], 'dataModel':['Task: id, title'],
                                        'acceptanceCriteria':['刷新恢复'],'techStack':'SQLite persistence'},
                         'fullstackScope':'fullstack-sqlite','customChecklist':[{'label':'错误反馈','points':20}]}
    def tearDown(self):self.tmp.cleanup()
    def prepare(self,definition=None):
        task=self.app.save_task(definition or self.definition)
        pol={**DEFAULT_POLICY,'objectiveWeight':0,'humanWeight':100}
        return self.app.prepare({'requestId':'contract-qa','configIds':['minimal'],'taskIds':[task['id']],'policy':pol})
    def mutate(self,run,action,**data):return self.app.mutate(run['id'],run['trials'][0]['id'],action,data)
    def review_data(self,run,status='unverified'):
        return {'captureId':run['trials'][0]['captures'][-1]['id'],'scores':{k:99 for k in DEFAULT_POLICY['dimensions']},
                'notes':'Manual fixture evidence, not a model benchmark.','readiness':'minor_polish','constraints':{},
                'criteria':{c['id']:{'status':status,'notes':'Observed fixture behavior' if status!='unverified' else ''} for c in run['tasks'][0]['criteria']}}

    def test_original_catalog_preserved_and_ids_stable(self):
        originals=json.loads((ROOT/'catalog/arena-tasks.json').read_text(encoding='utf-8'))
        self.assertEqual(len(originals),31)
        for original in originals:
            normalized=normalize_contract(original)
            for key in ['projectSpec','customChecklist','rubrics','evaluationRubric','fullstackScope']:
                if key=='projectSpec' and key in original:
                    for field,value in original[key].items():self.assertEqual(value,normalized[key][field])
                elif key in original:self.assertEqual(original[key],normalized[key])
            self.assertEqual(normalized,normalize_contract(normalized))
            self.assertTrue(all(not c['required'] for c in normalized['criteria']))
        a=normalize_contract(self.definition);b=copy.deepcopy(self.definition)
        b['projectSpec']['userStories'].insert(0,'删除任务')
        b=normalize_contract(b)
        self.assertEqual(next(c['id'] for c in a['criteria'] if c['label']=='新增任务'),next(c['id'] for c in b['criteria'] if c['label']=='新增任务'))

    def test_full_prompt_frozen_for_every_stage_and_revision(self):
        definition={**self.definition,'stages':[{'title':'First','prompt':'Build basics'},{'title':'Second','prompt':'Add export'}]}
        run=self.prepare(definition)
        for snapshot in run['tasks'][0]['promptSnapshots']:
            for value in ['新增任务','POST /tasks','Task: id, title','刷新恢复','SQLite persistence','错误反馈']:
                self.assertNotIn(value,snapshot['text'])
            self.assertIn('Build a task board',snapshot['text'])
            self.assertEqual(hashlib.sha256(snapshot['text'].encode()).hexdigest(),snapshot['sha256'])
        old=copy.deepcopy(run['tasks'])
        task=self.app.db.get('task',old[0]['id']);task['projectSpec']['userStories']=['Changed requirement'];self.app.save_task(task)
        self.assertEqual(self.app.present_run(self.app.db.get('run',run['id']))['tasks'],old)
        self.assertEqual(Arena(self.root).present_run(self.app.db.get('run',run['id']))['tasks'],old)

    def test_old_task_display_does_not_migrate_storage_or_old_run(self):
        task=self.app.save_task(self.definition);task.pop('schemaVersion');task.pop('criteria')
        self.app.db.save('task',task,task['revision']);before=self.app.db.get('task',task['id'])
        self.assertTrue(self.app.state()['tasks'][0]['contractUpgradePending'])
        self.assertEqual(self.app.db.get('task',task['id']),before)
        legacy={**before,'stages':[{'title':'Old','prompt':'Original sent prompt'}]}
        self.assertEqual(stage_prompt(legacy,0)['text'],'总体需求：\nBuild a task board\n\n本轮任务：\nOriginal sent prompt')
        self.assertNotIn('SQLite persistence',stage_prompt(legacy,0)['text'])

    def test_import_preview_atomic_idempotent_new_copies(self):
        saved=self.app.save_task(self.definition)
        document={'schemaVersion':2,'tasks':[saved,self.definition]}
        preview=post(self.app,'/api/arena/tasks/import-preview',{'document':document})
        self.assertTrue(preview['valid']);self.assertEqual(len(self.app.db.list('task')),1)
        payload={'document':document,'fingerprint':preview['fingerprint'],'requestId':'import-1'}
        first=post(self.app,'/api/arena/tasks/import',payload)
        again=post(self.app,'/api/arena/tasks/import',payload)
        self.assertEqual(first,again);self.assertEqual(len(self.app.db.list('task')),3)
        self.assertNotIn(saved['id'],first['receipt']['taskIds'])
        altered=copy.deepcopy(document);altered['tasks'][0]['title']='Changed'
        changed=post(self.app,'/api/arena/tasks/import-preview',{'document':altered})
        with self.assertRaises(ValueError):post(self.app,'/api/arena/tasks/import',{**payload,'document':altered,'fingerprint':changed['fingerprint']})
        invalid=copy.deepcopy(document);invalid['tasks'][1]['checks']=[{'label':'bad'}]
        bad=post(self.app,'/api/arena/tasks/import-preview',{'document':invalid})
        self.assertFalse(bad['valid']);self.assertEqual(bad['errors'][0]['index'],2)
        with self.assertRaises(ValueError):post(self.app,'/api/arena/tasks/import',{**payload,'document':invalid})
        self.assertEqual(len(self.app.db.list('task')),3)
        with self.assertRaises(ValueError):post(self.app,'/api/arena/tasks/import-preview',{'document':{'schemaVersion':99,'tasks':[self.definition]}})

    def test_import_storage_failure_rolls_back_batch_and_receipt(self):
        existing=self.app.save_task(self.definition)
        receipt={'id':'collision','fingerprint':'x','taskIds':['new-copy',existing['id']]}
        with self.assertRaises(sqlite3.IntegrityError):self.app.db.import_tasks(receipt,[{**existing,'id':'new-copy'},existing])
        self.assertEqual(len(self.app.db.list('task')),1)
        self.assertEqual(self.app.db.list('task_import'),[])

    def test_invalid_contract_ids_and_dangling_check_refs(self):
        definition=normalize_contract(self.definition)
        definition['criteria'].append(copy.deepcopy(definition['criteria'][0]))
        with self.assertRaises(ValueError):self.app.save_task(definition)
        definition=copy.deepcopy(self.definition)
        definition['checks']=[{'label':'Check','image':'fixture:qa','argv':['true'],'criterionIds':['missing']}]
        with self.assertRaises(ValueError):self.app.save_task(definition)
        definition['checks'][0].pop('criterionIds');definition['stages']=[None]
        with self.assertRaises(ValueError):self.app.save_task(definition)
        for key,value in [('difficulty',{}),('description',[]),('sourceNote',{}),('hasFrontendUI','false'),('baselineId',{})]:
            with self.subTest(field=key):
                result=post(self.app,'/api/arena/tasks/import-preview',{'document':{**self.definition,key:value}})
                self.assertFalse(result['valid'])

    def test_item_evidence_zero_unknown_revision_and_new_capture(self):
        definition=normalize_contract(self.definition);definition['criteria'][0]['required']=True
        run=self.prepare(definition);workspace=Path(run['trials'][0]['workspacePath']);(workspace/'proof.txt').write_text('Actual evidence')
        run=self.mutate(run,'capture');run=self.mutate(run,'complete')
        data=self.review_data(run)
        data['scores']={k:0 for k in data['scores']}
        run=self.mutate(run,'review',**data)
        self.assertEqual(run['trials'][0]['score']['overall'],0)
        self.assertEqual(run['trials'][0]['score']['acceptance']['status'],'unverified')
        cid=definition['criteria'][0]['id'];data=self.review_data(run,'met');data['revisionReason']='Checked the actual artifact'
        data['criteria'][cid]['filePath']='../forged.txt'
        with self.assertRaises(ValueError):self.mutate(run,'review',**data)
        data['criteria'][cid]['filePath']='proof.txt';data['criteria'][cid]['checkId']='fake'
        with self.assertRaises(ValueError):self.mutate(run,'review',**data)
        data['criteria'][cid].pop('checkId');data['criteria'][cid]['status']='unmet'
        run=self.mutate(run,'review',**data)
        self.assertEqual(run['trials'][0]['score']['overall'],99)
        self.assertEqual(run['trials'][0]['score']['acceptance']['status'],'not_met')
        self.assertEqual(len(run['trials'][0]['reviews']),2)
        self.assertEqual(run['trials'][0]['reviews'][-1]['criteria'][cid]['fileSha256'],hashlib.sha256(b'Actual evidence').hexdigest())
        data['criteria'][cid]['status']='met';data.pop('revisionReason')
        with self.assertRaises(ValueError):self.mutate(run,'review',**data)
        run=self.mutate(run,'capture')
        self.assertIsNone(run['trials'][0]['score']['human'])
        self.assertEqual(run['trials'][0]['score']['acceptance']['status'],'unverified')

    def test_final_regression_must_run_on_final_artifact(self):
        definition=normalize_contract(self.definition);cid=definition['criteria'][0]['id'];definition['criteria'][0]['required']=True
        definition['stages']=[{'title':'First','prompt':'Implement'},{'title':'Second','prompt':'Extend'}]
        definition['checks']=[{'id':'persist','label':'Persistence','image':'fixture:qa','argv':['true'],'weight':1,'stageIndex':0,'runOnFinal':True,'criterionIds':[cid]}]
        run=self.prepare(definition);run=self.mutate(run,'capture');run=self.mutate(run,'continue');run=self.mutate(run,'capture');run=self.mutate(run,'complete')
        run=self.mutate(run,'review',**self.review_data(run,'met'))
        task=run['tasks'][0];trial=run['trials'][0]
        self.assertEqual(len(applicable_checks(task,1)),1)
        trial['captures'][0]['checks']=[{'id':'persist','status':'passed','weight':1}]
        score=calculate(run,trial);self.assertIsNone(score['objective']);self.assertEqual(score['acceptance']['status'],'unverified')
        trial['captures'][1]['checks']=[{'id':'persist','status':'failed','weight':1}]
        score=calculate(run,trial);self.assertEqual(score['objective'],50);self.assertEqual(score['acceptance']['status'],'not_met')
        trial['captures'][1]['checks'][0]['status']='passed'
        self.assertEqual(calculate(run,trial)['acceptance']['status'],'met')
        trial['captures'][1]['checks'][0]['status']='timeout'
        self.assertIsNone(calculate(run,trial)['objective'])

    def test_legacy_score_and_constraints_evidence(self):
        from chb.arena.scoring import validate_review
        task={**self.definition,'schemaVersion':1,'hasFrontendUI':True}
        review={'scores':{k:0 for k in DEFAULT_POLICY['dimensions']},'notes':'Old review','readiness':'rejected','constraints':{'rule':'met'}}
        self.assertEqual(validate_review(review,task,[{'id':'rule','isActive':True}])['constraints'],{'rule':'met'})
        task=normalize_contract(task);review['criteria']={c['id']:{'status':'unverified'} for c in task['criteria']}
        with self.assertRaises(ValueError):validate_review(review,task,[{'id':'rule','isActive':True}])
        review['constraintNotes']={'rule':'Observed compliance'}
        self.assertEqual(validate_review(review,task,[{'id':'rule','isActive':True}])['constraintNotes'],review['constraintNotes'])


if __name__=='__main__':unittest.main()
