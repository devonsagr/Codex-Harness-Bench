"""Explicit, bounded real machine-judge smoke test on a synthetic, isolated project."""
import argparse
import json
import os
import shutil
from pathlib import Path
import tempfile
import time

from chb.cli import ROOT
from chb.arena.service import Arena
from chb.arena.jobs import start_job, stop_job
from chb.arena.scoring import MACHINE_POLICY


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--judge-model',required=True,help='Explicitly authorize one model call using this reviewer model.')
    parser.add_argument('--environment',choices=['docker','local'],default='docker')
    parser.add_argument('--frontend',action='store_true',help='Exercise a small browser interaction fixture.')
    args=parser.parse_args()
    from chb.arena.skills import codex_home
    original_home=os.environ.get('CODEX_HOME')
    original_auth=codex_home()/'auth.json'
    root=Path(tempfile.mkdtemp(prefix='machine-smoke-',dir=ROOT/'.local'))
    (root/'catalog').mkdir();(root/'catalog/arena-tasks.json').write_text('[]')
    (root/'home').mkdir();os.environ['CODEX_HOME']=str(root/'home')
    if args.environment=='local' and original_auth.is_file():shutil.copyfile(original_auth,root/'home/auth.json')
    try:
        app=Arena(root)
        config=app.save_config({'name':'Synthetic judge smoke','agentsPrompt':'','baseModel':args.judge_model,
            'reasoning':'low','interactiveMode':'adaptive','skills':[]})
        task=app.save_task({'title':'Synthetic hello CLI','inputPrompt':'Provide a Python CLI that prints hello followed by the supplied name. Running without a name must print usage and exit nonzero.',
            'schemaVersion':2,'taskParadigm':'open-ended-project','channel':'deepswe-core','hasFrontendUI':False,
            'stages':[{'title':'Deliver','prompt':'Implement the CLI.'}],
            'criteria':[{'id':'greet','label':'python3 main.py Ada prints hello Ada','required':True,'dimension':'intent'},
                        {'id':'missing','label':'Missing name prints usage and exits nonzero','required':True,'dimension':'robustness'}],'checks':[]})
        policy={**MACHINE_POLICY,'dimensions':{'intent':70,'robustness':30},'rubrics':{k:MACHINE_POLICY['rubrics'][k] for k in ['intent','robustness']}}
        if args.frontend:
            task=app.save_task({'title':'Synthetic theme interaction','inputPrompt':'Create an accessible light/dark toggle page. The button must change the page theme and aria-pressed, support Enter, persist after reload, and fit a 375px viewport without horizontal scrolling.',
                'taskParadigm':'open-ended-project','channel':'frontend-ui','hasFrontendUI':True,'checks':[],
                'criteria':[{'id':'toggle','label':'Theme toggle changes page and aria-pressed','required':True,'dimension':'intent'},
                            {'id':'persist','label':'Theme persists after reload','required':True,'dimension':'intent'}]})
            policy={**MACHINE_POLICY,'dimensions':{'intent':70,'ux':30},'rubrics':{k:MACHINE_POLICY['rubrics'][k] for k in ['intent','ux']}}
        run=app.prepare({'requestId':'smoke','configIds':[config['id']],'taskIds':[task['id']],'policy':policy})
        trial=run['trials'][0];rid,tid=run['id'],trial['id']
        Path(trial['workspacePath'],'main.py').write_text('import sys\nif len(sys.argv) != 2:\n    print("usage: main.py NAME")\n    sys.exit(2)\nprint("hello " + sys.argv[1])\n')
        if args.frontend:
            Path(trial['workspacePath'],'index.html').write_text("""<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Theme fixture</title><style>body{font:18px system-ui;margin:0;padding:24px;background:#f7f8fb;color:#15213a}body.dark{background:#15213a;color:#f7f8fb}main{max-width:600px;margin:auto}button{padding:12px 20px;font:inherit;border-radius:8px}button:focus-visible{outline:3px solid #3778ff;outline-offset:4px}</style><main><h1>Theme preview</h1><p>Switch between light and dark.</p><button type="button" aria-pressed="false">Toggle theme</button></main><script>const b=document.querySelector('button');function update(d){document.body.classList.toggle('dark',d);b.setAttribute('aria-pressed',String(d));localStorage.setItem('dark',String(d));}update(localStorage.getItem('dark')==='true');b.onclick=()=>update(!document.body.classList.contains('dark'));</script></html>""",encoding='utf-8')
        run=app.mutate(rid,tid,'capture',{});run=app.mutate(rid,tid,'complete',{})
        start_job(app,rid,tid,'judge',{'captureId':run['trials'][0]['captures'][-1]['id'],'model':args.judge_model,'environment':args.environment})
        deadline=time.monotonic()+660
        while app.jobs and time.monotonic()<deadline:time.sleep(.5)
        if app.jobs:
            stop_job(app,rid,tid)
            raise RuntimeError('Smoke deadline exceeded; cancellation requested.')
        result=app.present_run(app.db.get('run',rid));trial=result['trials'][0]
        (root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'evidenceRoot':str(root),'score':trial['score'],'error':trial.get('lastJobError')},ensure_ascii=False,indent=2))
        if trial.get('lastJobError') or trial['score']['machineReviewId'] is None:raise SystemExit(1)
        report=next(r for r in trial['reviews'] if r['id']==trial['score']['machineReviewId'])
        if not report.get('commands') or trial['score']['machineCoverage']!=100:raise SystemExit(2)
    finally:
        (root/'home/auth.json').unlink(missing_ok=True)
        if original_home is None:os.environ.pop('CODEX_HOME',None)
        else:os.environ['CODEX_HOME']=original_home



if __name__=='__main__':main()
