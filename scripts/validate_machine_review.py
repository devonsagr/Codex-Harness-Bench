"""Explicit, bounded real machine-judge smoke test on a synthetic, isolated project."""
import argparse
import json
import os
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
    args=parser.parse_args()
    root=Path(tempfile.mkdtemp(prefix='machine-smoke-',dir=ROOT/'.local'))
    (root/'catalog').mkdir();(root/'catalog/arena-tasks.json').write_text('[]')
    (root/'home').mkdir();os.environ['CODEX_HOME']=str(root/'home')
    app=Arena(root)
    config=app.save_config({'name':'Synthetic judge smoke','agentsPrompt':'','baseModel':args.judge_model,
        'reasoning':'low','interactiveMode':'adaptive','skills':[]})
    task=app.save_task({'title':'Synthetic hello CLI','inputPrompt':'Provide a Python CLI that prints hello followed by the supplied name. Running without a name must print usage and exit nonzero.',
        'schemaVersion':2,'taskParadigm':'open-ended-project','channel':'deepswe-core','hasFrontendUI':False,
        'stages':[{'title':'Deliver','prompt':'Implement the CLI.'}],
        'criteria':[{'id':'greet','label':'python3 main.py Ada prints hello Ada','required':True,'dimension':'intent'},
                    {'id':'missing','label':'Missing name prints usage and exits nonzero','required':True,'dimension':'robustness'}],'checks':[]})
    policy={**MACHINE_POLICY,'dimensions':{'intent':70,'robustness':30},'rubrics':{k:MACHINE_POLICY['rubrics'][k] for k in ['intent','robustness']}}
    run=app.prepare({'requestId':'smoke','configIds':[config['id']],'taskIds':[task['id']],'policy':policy})
    trial=run['trials'][0];rid,tid=run['id'],trial['id']
    Path(trial['workspacePath'],'main.py').write_text('import sys\nif len(sys.argv) != 2:\n    print("usage: main.py NAME")\n    sys.exit(2)\nprint("hello " + sys.argv[1])\n')
    run=app.mutate(rid,tid,'capture',{});run=app.mutate(rid,tid,'complete',{})
    start_job(app,rid,tid,'judge',{'captureId':run['trials'][0]['captures'][-1]['id'],'model':args.judge_model})
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


if __name__=='__main__':main()
