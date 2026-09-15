"""Verify the new workbench with real containers; model use is explicit and optional."""
import argparse
from datetime import datetime,timezone
import json
import re
from pathlib import Path
import shutil
import time
from chb.cli import ROOT
from chb.arena.api import import_originals,export
from chb.arena.service import Arena,shell
from chb.arena.jobs import start_job,stop_job


def wait(app,rid,tid,limit=240):
    deadline=time.monotonic()+limit
    while (rid,tid) in app.jobs:
        if time.monotonic()>deadline:
            stop_job(app,rid,tid)
            raise RuntimeError('Validation exceeded its time limit')
        time.sleep(.1)
    return app.present_run(app.db.get('run',rid))


def reference_files(script,workspace):
    """Copy only known repository oracle heredocs; never execute host shell code."""
    source=script.read_text(encoding='utf-8')
    for match in re.finditer(r"^cat (>>?) /app/([\w.]+) <<'([A-Z]+)'\n(.*?)\n\3$",source,re.M|re.S):
        mode,name,_,body=match.groups()
        with (workspace/name).open('a' if mode=='>>' else 'w',encoding='utf-8',newline='\n') as output:output.write(body+'\n')
    if script.parent.parent.name=='sqlite':(workspace/'legacy_store.py').unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--judge-model',help='Explicitly spend model quota on one isolated AI review')
    args=parser.parse_args()
    root=ROOT/'.local/arena-validation'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root.mkdir(parents=True)
    project=root/'project';project.mkdir()
    shutil.copytree(ROOT/'profiles',project/'profiles');shutil.copytree(ROOT/'tasks',project/'tasks')
    (project/'catalog').mkdir();(project/'catalog/arena-tasks.json').write_text('[]')
    app=Arena(project);import_originals(app)
    evidence={'createdAt':datetime.now(timezone.utc).isoformat(),'purpose':'software-validation-no-desktop-model-run','checks':[]}
    def save():
        (root/'receipt.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    def new(task_id,request_id):
        r=app.prepare({'requestId':request_id,'configIds':['minimal'],'taskIds':[task_id],'notes':'Software validation only. No desktop execution or model score.'})
        return r,r['trials'][0]['id']
    def capture(r,tid):
        app.mutate(r['id'],tid,'capture',{'response':'Software validation fixture; not a desktop model output.'})
        return app.mutate(r['id'],tid,'complete',{})
    def check(r,tid):
        cid=r['trials'][0]['captures'][-1]['id']
        start_job(app,r['id'],tid,'check',{'captureId':cid})
        return wait(app,r['id'],tid)
    try:
        run,tid=new('original-search-notes-v1','negative')
        run=check(capture(run,tid),tid)
        result=run['trials'][0]['captures'][-1]['checks']
        assert len(result)==1 and result[0]['status']=='failed',result
        assert run['trials'][0]['score']['objective']==0
        evidence['checks'].append({'name':'unmodified-fixture-rejected','result':result});save();print('PASS: unmodified fixture rejected',flush=True)
        workspace=Path(run['trials'][0]['workspacePath'])
        solution=(ROOT/'tasks/search-notes-v1/solution/solve.sh').read_text(encoding='utf-8')
        code=solution.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]+'\n'
        (workspace/'notes.py').write_text(code,encoding='utf-8')
        run=check(capture(run,tid),tid)
        result=run['trials'][0]['captures'][-1]['checks']
        assert len(result)==1 and result[0]['status']=='passed',result
        assert run['trials'][0]['score']['objective']==100
        assert run['trials'][0]['captures'][0]['checks'][0]['status']=='failed'
        assert not run['trials'][0].get('ownedContainers')
        (root/'export.zip').write_bytes(export(app,run['id']))
        evidence['checks'].append({'name':'reference-solution-accepted','result':result});save();print('PASS: reference solution accepted; old failure retained',flush=True)
        image=result[0]['imageId']
        task=app.save_task({'id':'cancel-timeout','title':'Container lifecycle QA','taskParadigm':'open-ended-project','channel':'deepswe-core','hasFrontendUI':False,'inputPrompt':'Fixture only',
           'checks':[{'label':'sleep','image':image,'argv':['python','-c','import time; time.sleep(30)'],'weight':1,'timeout':1}]})
        timed,ttid=new(task['id'],'timeout');timed=check(capture(timed,ttid),ttid)
        report=timed['trials'][0]['captures'][-1]['checks']
        assert report[0]['status']=='timeout',report
        assert timed['trials'][0]['score']['objective'] is None
        evidence['checks'].append({'name':'timeout-not-failure','result':report});save();print('PASS: timeout preserves unknown score',flush=True)
        task['checks'][0]['timeout']=60;app.save_task(task)
        stopped,stid=new(task['id'],'cancel');stopped=capture(stopped,stid)
        start_job(app,stopped['id'],stid,'check',{'captureId':stopped['trials'][0]['captures'][-1]['id']})
        deadline=time.monotonic()+20
        while not app.db.get('run',stopped['id'])['trials'][0].get('ownedContainers'):
            if time.monotonic()>deadline:raise RuntimeError('Container did not start')
            time.sleep(.05)
        stop_job(app,stopped['id'],stid);stopped=wait(app,stopped['id'],stid)
        assert not stopped['trials'][0].get('ownedContainers')
        assert stopped['trials'][0]['score']['objective'] is None
        evidence['checks'].append({'name':'explicit-stop-cleans-owned-container','runId':stopped['id']});save();print('PASS: stopped only the owned check; container removed',flush=True)
        csv,ctid=new('original-csv-catalog-v1','csv')
        csv=check(capture(csv,ctid),ctid)
        assert csv['trials'][0]['score']['objective']==0
        reference_files(ROOT/'tasks/csv-catalog-v1/solution/solve.sh',Path(csv['trials'][0]['workspacePath']))
        csv=check(capture(csv,ctid),ctid)
        assert csv['trials'][0]['score']['objective']==100
        evidence['checks'].append({'name':'csv-negative-and-reference','runId':csv['id']});save();print('PASS: CSV fixture rejected and reference accepted',flush=True)
        storage,stid=new('original-storage-migration-v1','storage')
        workspace=Path(storage['trials'][0]['workspacePath'])
        for index,stage in enumerate(('archive','sqlite')):
            if index:storage=app.mutate(storage['id'],stid,'continue',{})
            storage=app.mutate(storage['id'],stid,'capture',{'response':'Software fixture, no model.'})
            storage=check(storage,stid)
            assert storage['trials'][0]['captures'][-1]['checks'][0]['status']=='failed'
            reference_files(ROOT/f'tasks/storage-migration-v1/steps/{stage}/solution/solve.sh',workspace)
            storage=app.mutate(storage['id'],stid,'capture',{'response':'Repository oracle, not a model result.'})
            storage=check(storage,stid)
            assert storage['trials'][0]['captures'][-1]['checks'][0]['status']=='passed'
        storage=app.mutate(storage['id'],stid,'complete',{})
        assert storage['trials'][0]['score']['objective']==100
        evidence['checks'].append({'name':'storage-two-stage-negative-and-reference','runId':storage['id']});save();print('PASS: both storage stages reject incomplete work and accept references',flush=True)
        if args.judge_model:
            start_job(app,run['id'],tid,'judge',{'captureId':run['trials'][0]['captures'][-1]['id'],'model':args.judge_model})
            run=wait(app,run['id'],tid,300)
            reviews=[r for r in run['trials'][0]['reviews'] if r['kind']=='ai']
            evidence['aiReview']={'model':args.judge_model,'reviews':reviews,'error':run['trials'][0].get('lastJobError')}
            save()
            if not reviews:raise RuntimeError('AI reviewer returned no validated report; see receipt')
            print('PASS: isolated AI report returned and citations validated',flush=True)
        evidence['status']='passed';evidence['runId']=run['id'];save()
    except Exception as exc:
        evidence['status']='failed';evidence['error']=str(exc);save();raise
    finally:print('Validation receipt:',root/'receipt.json',flush=True)

if __name__=='__main__':main()
