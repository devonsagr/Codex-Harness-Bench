"""Run trusted browser probe sensitivity fixtures in Docker, without any AI call.

These deliberately small test doubles are not task solutions and never enter a
development workspace. A positive fixture passing only validates its probes.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><style>body{margin:8px}canvas,svg{max-width:100%;height:auto}button{padding:8px}</style><main><h1>浏览器验收测试替身</h1>'


def fixtures():
    bridge = '''<button onclick="set('blue')">晨雾</button><button onclick="set('black')">夜景</button><svg width="320" height="240"><rect id="scene" width="320" height="240" fill="blue"/></svg><script>function set(c){if(MUTATION!=='scene')scene.setAttribute('fill',c)}</script>'''
    exhibit = '''<button onclick="turn(-30)">向左旋转</button><button onclick="turn(30)">向右旋转</button><div style="perspective:600px;width:300px;height:260px"><div id="box" style="width:120px;height:180px;background:linear-gradient(90deg,blue,red);transform:rotateY(20deg)"></div></div><script>let angle=20;function turn(d){if(MUTATION!=='rotation')box.style.transform=`rotateY(${angle+=d}deg)`}</script>'''
    energy = '''<p>本周 TOTAL kWh</p><p>比上周下降 COMPARISON%</p><svg width="320" height="240">MARKS</svg>'''
    energy = energy.replace('MARKS', ''.join(f'<rect x="{i*40}" width="25" height="{v*10}" aria-label="周{day} {v} kWh"/>' for i,(day,v) in enumerate(zip('一二三四五六日',[9,8,11,10,7,12,6]))))
    pixel = '''<canvas id="art" width="240" height="240" aria-label="画布"></canvas><button onclick="undo()">撤销</button><button onclick="clearArt()">清空</button><button onclick="save()">导出 PNG</button><script>
const c=art.getContext('2d');c.fillStyle='white';c.fillRect(0,0,240,240);let history=[];const empty=art.toDataURL();
art.onpointerdown=e=>{history.push(c.getImageData(0,0,240,240));if(MUTATION==='draw')return;c.fillStyle='navy';c.fillRect(Math.floor(e.offsetX/20)*20,Math.floor(e.offsetY/20)*20,20,20)};
function undo(){if(history.length&&MUTATION!=='undo')c.putImageData(history.pop(),0,0)}
function clearArt(){if(MUTATION==='clear')return;c.fillStyle='white';c.fillRect(0,0,240,240)}
function save(){const a=document.createElement('a');a.download='art.png';a.href=MUTATION==='export'?empty:art.toDataURL();a.click()}
</script>'''
    game = '''<canvas id="game" width="300" height="240"></canvas><button onclick="start()">开始游戏</button><button id="pause" onclick="paused=!paused;this.textContent=paused?'继续':'暂停'">暂停</button><button onclick="restart()">重新开始</button><p id="score">得分 0</p><script>
const c=game.getContext('2d');let active=false,paused=false,tick=0;function start(){active=true;score.textContent='得分 1'}
function restart(){if(MUTATION!=='restart')score.textContent='得分 0'}
function frame(){if(active&&MUTATION!=='start'&&(!paused||MUTATION==='pause')){c.clearRect(0,0,300,240);c.fillRect((tick++%250),60,30,30)}requestAnimationFrame(frame)}frame();</script>'''
    cases=[]
    def add(task,html,mutations):
        for mutation,expected in [('',{}),*mutations]:
            body=html.replace('MUTATION',json.dumps(mutation))
            if task=='energy-dashboard-v1':
                body=body.replace('TOTAL','64' if mutation=='total' else '63').replace('COMPARISON','20' if mutation=='comparison' else '10')
                if mutation=='daily':body=body.replace('周三 11 kWh','周三 99 kWh')
            cases.append({'task':task,'name':task+'-'+(mutation or 'positive'),'html':PREFIX+body+'</main>','expected':expected})
    add('golden-gate-fog-v1',bridge,[('scene',{'scene-switch':'failed','scene-keyboard':'failed'})])
    add('mini-exhibit-3d-v1',exhibit,[('rotation',{'rotate-left':'failed','rotate-right':'failed','rotate-keyboard':'failed'})])
    add('energy-dashboard-v1',energy,[('total',{'weekly-total':'failed'}),('comparison',{'weekly-comparison':'failed'}),('daily',{'daily-values':'failed'})])
    add('pixel-postcard-v1',pixel,[(key,{key:'unverified' if key=='draw' else 'failed'}) for key in ['draw','undo','clear','export']])
    add('meteor-rescue-v1',game,[(key,{key:'failed'}) for key in ['start','pause','restart']])
    # Missing/ambiguous controls and ambient animations must never become passes.
    cases.append({'task':'golden-gate-fog-v1','name':'ambiguous-controls','html':PREFIX+bridge.replace('MUTATION',"''").replace('<svg','<button>夜景</button><svg'), 'expected':{'scene-switch':'unverified'}})
    cases.append({'task':'golden-gate-fog-v1','name':'autonomous-animation','html':PREFIX+bridge.replace('MUTATION',"'scene'")+"<script>setInterval(()=>scene.setAttribute('x',String(Math.random()*20)),60)</script>", 'expected':{'scene-switch':'unverified','scene-keyboard':'unverified'}})
    scaled=pixel.replace('a.href=MUTATION',"const out=document.createElement('canvas');out.width=480;out.height=480;const ctx=out.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.drawImage(art,0,0,480,480);a.href=MUTATION").replace("?empty:art.toDataURL()","?empty:out.toDataURL()")
    cases.append({'task':'pixel-postcard-v1','name':'integer-scaled-export','html':PREFIX+scaled.replace('MUTATION',"''"),'expected':{'export':'passed'}})
    energy_title=energy.replace('<svg width="320" height="240">','<svg width="320" height="240"><title>周一至周日的逐日用电量</title>').replace('TOTAL','63').replace('COMPARISON','10')
    cases.append({'task':'energy-dashboard-v1','name':'chart-title-is-not-day-value','html':PREFIX+energy_title,'expected':{'daily-values':'passed'}})
    return cases


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true');args=parser.parse_args()
    image='chb-verifier:creative-behavior-v3'
    if args.build:subprocess.run(['docker','build','-t',image,'-f',str(ROOT/'tasks/creative-web-v1/tests/Dockerfile.behavior'),str(ROOT/'tasks/creative-web-v1/tests')],check=True)
    qa=ROOT/'.local/qa';qa.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='behavior-',dir=qa) as tmp:
        folder=Path(tmp);cases=fixtures()
        for case in cases:
            p=folder/case['name'];p.mkdir();(p/'index.html').write_text(case.pop('html'),encoding='utf-8')
        (folder/'cases.json').write_text(json.dumps(cases),encoding='utf-8')
        runner="""const {run}=require('/tests/behavior.cjs');const cases=require('/fixtures/cases.json');(async()=>{let failed=0;for(const c of cases){const r=await run('/fixtures/'+c.name,c.task);const statuses=Object.fromEntries(r.rows.map(x=>[x.id,x.status]));const expected=Object.keys(c.expected).length?c.expected:Object.fromEntries(r.rows.map(x=>[x.id,'passed']));const errors=Object.entries(expected).filter(([id,s])=>statuses[id]!==s);console.log(JSON.stringify({name:c.name,ok:!errors.length,errors,rows:r.rows}));if(errors.length)failed++}process.exitCode=failed?1:0})().catch(e=>{console.error(e);process.exitCode=2})"""
        result=subprocess.run(['docker','run','--rm','--network','none','--memory','1g','--cpus','2','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={folder.resolve()},target=/fixtures,readonly',image,'node','-e',runner],capture_output=True,text=True,encoding='utf-8',timeout=300)
        (qa/'behavior-validation.jsonl').write_text(result.stdout,encoding='utf-8')
        for line in result.stdout.splitlines():
            r=json.loads(line);print(('PASS ' if r['ok'] else 'FAIL ')+r['name'],r['errors'])
        if result.stderr:print(result.stderr[-3000:])
        print(f'{len(cases)} fixtures; detailed evidence: .local/qa/behavior-validation.jsonl')
        raise SystemExit(result.returncode)


if __name__=='__main__':main()
