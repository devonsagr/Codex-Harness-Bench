"""Fixed Tengo verifier adapter: upstream tests, Windows Go, Codex command sandbox.

No model call and no user-supplied command. This is explicitly an adapted run,
not the upstream Linux image or an official leaderboard submission.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import threading
import uuid
import zipfile
from urllib.request import urlopen

from .files import hash_bytes, inventory, now, safe_path, verify_snapshot
from .local_review import codex_executable, ProcessTree
from .public_sources import bundle, catalog

TASK_ID='tengo-callable-instance-isolation'
REVISION='0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea'
GO_VERSION='go1.26.8'
GO_SHA='b92c3b2adae85a11ba71fe7216daf0d84e82af4c8ab6c5625807f28622043a59'
ADAPTER='tengo-windows-go-v1'
RUNTIME_LOCK=threading.Lock()


def supported(task):
    source=task.get('publicSource') or {}
    return source.get('id')==TASK_ID and source.get('revision')==REVISION


def runtime(app):
    return app.local/'toolchains'/f'{GO_VERSION}-windows-amd64'


def prepare_environment(app,task,progress=lambda message:None):
    if not supported(task):raise ValueError('这道题尚无本机免 Docker 环境适配。')
    if task.get('archived'):raise ValueError('请先恢复已归档题目。')
    baseline=app.db.get('baseline',task['baselineId'])
    folder=app.local/'environment-checks'/uuid.uuid4().hex[:12]
    result=run(app,task,app.local/'baselines'/baseline['id']/'files',baseline['manifest'],folder,{'stop':threading.Event()},progress)
    if result['p2p']!=1 or result['f2p']!=0:raise ValueError('故障起点校验不符合预期，未标记环境就绪。')
    with app.lock:
        fresh=app.db.get('task',task['id'])
        if fresh['revision']!=task['revision']:raise ValueError('准备期间题目已修改；环境回执保留，请重新核对。')
        fresh['publicSource'].update(environmentStatus='ready-windows',verifierStatus=ADAPTER,environmentReceipt=str(folder/'result.json'))
        fresh['environmentNote']=f'Windows 本机适配 · {GO_VERSION} · 无第三方 Go 依赖。故障起点已验证：修复测试 0/23，回归 122/122。创建工作区后用 .chb/go.ps1 运行 Go，无需全局安装。验收使用 Codex 命令沙箱，不调用模型；与上游 Linux 环境不同。'
        return app.save_task(fresh)


def workspace_launcher(app,task,workspace):
    if not supported(task) or task['publicSource'].get('environmentStatus')!='ready-windows':return ''
    go=runtime(app)/'go/bin/go.exe'
    if not go.is_file():raise ValueError('本机 Go 工具链已移除，请在题库重新准备环境。')
    folder=workspace/'.chb';folder.mkdir(exist_ok=True)
    script="param([Parameter(ValueFromRemainingArguments=$true)][string[]]$GoArgs)\n"
    script+="$ErrorActionPreference='Stop'\n"
    script+="$env:GOENV='off'; $env:GOTOOLCHAIN='local'; $env:GOWORK='off'; $env:CGO_ENABLED='0'\n"
    script+="$env:GOCACHE=Join-Path $PSScriptRoot '../.chb-cache/go-build'\n$env:GOPATH=Join-Path $PSScriptRoot '../.chb-cache/go-path'\n"
    script+="& '"+str(go).replace("'","''")+"' @GoArgs\nexit $LASTEXITCODE\n"
    # Windows PowerShell 5 reads BOM-less UTF-8 as ANSI (breaks Chinese paths).
    (folder/'go.ps1').write_text(script,encoding='utf-8-sig')
    return '\n\n开发环境已准备：在工作区用 `powershell -NoProfile -ExecutionPolicy Bypass -File .chb/go.ps1 test ./...` 运行 Go 测试；此入口使用固定本地工具链，不修改系统 PATH。'


def ensure_runtime(app,stop=None):
    def cancelled():
        if stop and stop.is_set():raise ValueError('已取消本机测试验收。')
    while not RUNTIME_LOCK.acquire(timeout=.2):cancelled()
    try:
        cancelled()
        return _ensure_runtime(app,cancelled)
    finally:RUNTIME_LOCK.release()


def _ensure_runtime(app,cancelled):
    if os.name!='nt':raise ValueError('当前本机适配器仅支持 Windows x64，其他平台请使用上游 Linux 环境。')
    if not codex_executable():raise ValueError('本机验收需要 Codex CLI 命令沙箱，不需要模型登录或 Docker。')
    root=runtime(app);root.mkdir(parents=True,exist_ok=True);archive=root/'go.zip'
    if not archive.exists() or hash_bytes(archive.read_bytes())!=GO_SHA:
        partial=root/'download.partial'
        try:
            with urlopen(f'https://go.dev/dl/{GO_VERSION}.windows-amd64.zip',timeout=30) as response,partial.open('wb') as out:
                length=0;deadline=time.monotonic()+180
                while chunk:=response.read(1048576):
                    cancelled()
                    length+=len(chunk)
                    if length>100_000_000 or time.monotonic()>deadline:raise ValueError('Go 工具链下载超时或超限，可以重试。')
                    out.write(chunk)
            if hash_bytes(partial.read_bytes())!=GO_SHA:raise ValueError('Go 工具链校验失败，未安装。')
            partial.replace(archive)
        finally:partial.unlink(missing_ok=True)
    # Extract only the verified official archive; never use a candidate toolchain.
    with zipfile.ZipFile(archive) as z:
        total=0
        for entry in z.infolist():
            cancelled()
            if entry.is_dir():continue
            total+=entry.file_size
            if total>600_000_000:raise ValueError('Go 解包超限。')
            dest=safe_path(root,entry.filename);dest.parent.mkdir(parents=True,exist_ok=True)
            body=z.read(entry)
            if not dest.exists() or hash_bytes(dest.read_bytes())!=hash_bytes(body):dest.write_bytes(body)
    return root/'go/bin/go.exe'


def clean_environment(work,home,go):
    allowed={'path','systemroot','windir','comspec','pathext','userprofile','localappdata','appdata','programfiles','programfiles(x86)','programdata','number_of_processors','os'}
    env={k:v for k,v in os.environ.items() if k.lower() in allowed}
    for name in ['tmp','cache','mod','gopath']:(work/name).mkdir(exist_ok=True)
    env.update(CODEX_HOME=str(home),HOME=str(home),TEMP=str(work/'tmp'),TMP=str(work/'tmp'),TMPDIR=str(work/'tmp'),
               GOROOT=str(go.parent.parent),GOCACHE=str(work/'cache'),GOMODCACHE=str(work/'mod'),GOPATH=str(work/'gopath'),
               GOPROXY='off',GOTOOLCHAIN='local',GOSUMDB='off',GOENV='off',GOWORK='off',CGO_ENABLED='0',NO_COLOR='1')
    return env


def sandbox_command(work,home,command,env,log,stop,timeout=330):
    home.mkdir(parents=True,exist_ok=True)
    # Current Windows backend requires root read. It restricts writes to this
    # disposable directory and disables networking; it is not a read-isolated VM.
    (home/'config.toml').write_text('[windows]\nsandbox="unelevated"\n[permissions.bench.filesystem]\n":root"="read"\n[permissions.bench.filesystem.":workspace_roots"]\n"."="write"\n[permissions.bench.network]\nenabled=false\n',encoding='utf-8')
    args=[codex_executable(),'sandbox','-P','bench','-C',str(work),*map(str,command)]
    with log.open('wb') as output:
        process=subprocess.Popen(args,env=env,cwd=work,stdout=output,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        tree=ProcessTree(process)
        try:
            deadline=time.monotonic()+timeout
            while process.poll() is None:
                if stop.wait(.15):raise ValueError('已取消本机测试验收。')
                if time.monotonic()>deadline:raise ValueError('本机测试超时，结果保持未知。')
                if log.stat().st_size>60_000_000:raise ValueError('本机测试输出超限，结果保持未知。')
            return process.returncode
        finally:tree.close()


def grade(config,logs):
    if not logs:raise ValueError('测试输出缺失，未生成分数。')
    statuses={}
    for log in logs:
        observed=False
        with log.open(encoding='utf-8',errors='replace') as stream:
            for line in stream:
                try:event=json.loads(line)
                except (ValueError,TypeError):continue
                if not isinstance(event,dict):continue
                if event.get('Action') in {'start','run','pass','fail','build-fail'} and event.get('Package'):observed=True
                if not event.get('Test') or event.get('Action') not in {'pass','fail','skip'}:continue
                key=event['Package']+'.'+event['Test'];value=event['Action']
                rank={'pass':0,'skip':1,'fail':2}
                if rank[value]>=rank.get(statuses.get(key),-1):statuses[key]=value
        if not observed:raise ValueError('没有可解析的 Go 测试事件，环境或沙箱未成功启动；不记为零分。')
    counts={}
    missing=[]
    for name in ['f2p','p2p']:
        ids=config[name+'_node_ids'];counts[name+'_total']=len(ids)
        counts[name+'_passed']=sum(statuses.get(n)=='pass' for n in ids)
        counts[name]=counts[name+'_passed']/len(ids) if ids else (0.0 if name=='f2p' else 1.0)
        missing.extend(n for n in ids if statuses.get(n)!='pass')
    total=counts['f2p_total']+counts['p2p_total']
    counts['partial']=(counts['f2p_passed']+counts['p2p_passed'])/total if total else 0
    counts['reward']=int(counts['f2p_total']>0 and counts['f2p']==1 and counts['p2p']==1)
    return {**counts,'notPassed':missing}


def run(app,task,source,manifest,folder,control,progress=lambda message:None):
    if not supported(task):raise ValueError('此题尚无本机测试适配器，不能冒充原生验收。')
    verify_snapshot(source,manifest)
    original=next(t for t in catalog(app)['tasks'] if t['id']==TASK_ID)
    baseline=app.db.get('baseline',task['baselineId']);base=app.local/'baselines'/baseline['id']/'files'
    if baseline.get('sourceCommit')!=original['baseCommit'] or baseline.get('sourceUrl')!=original['repositoryUrl']:
        raise ValueError('源码起点已更换，不能使用此固定题目的验收器；请重新下载原题。')
    verify_snapshot(base,baseline['manifest'])
    progress('校验 Go 工具链与固定测试包')
    go=ensure_runtime(app,control['stop']);tests=bundle(app)/'tasks'/TASK_ID/'tests'
    config=json.loads((tests/'config.json').read_text(encoding='utf-8'))
    if config['base_commit']!=original['baseCommit']:raise ValueError('验收器起点不一致。')
    if (source/'go.mod').read_bytes()!=(base/'go.mod').read_bytes():raise ValueError('当前适配器不支持修改 Go 依赖清单；请用上游环境复验，不生成猜测分数。')
    folder.mkdir(parents=True,exist_ok=True)
    temp_root=app.local/'native-runtime';temp_root.mkdir(exist_ok=True)
    home_root=app.local/'native-homes';home_root.mkdir(exist_ok=True)
    started=time.monotonic();commands=[]
    # mkdtemp uses private ACLs unsuitable for restricted tokens. Use a normal
    # directory inheriting the project ACL, matching the native reviewer strategy.
    work=temp_root/uuid.uuid4().hex;work.mkdir()
    try:
        with tempfile.TemporaryDirectory(dir=home_root) as homedir:
            home=Path(homedir)
            for name,body in inventory(source)[0].items():
                if name.startswith(('.codex/','.agents/')) or name in {'AGENTS.md','AGENTS.override.md'}:continue
                dest=safe_path(work,name);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(body)
            # Upstream prepare resets test.patch targets before applying hidden tests.
            patch=(tests/'test.patch').read_text(encoding='utf-8')
            targets={line[6:].strip() for line in patch.splitlines() if line.startswith('+++ b/')}
            for name in targets:
                dest=safe_path(work,name)
                if name in baseline['manifest']['files']:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((base/name).read_bytes())
                elif dest.exists():dest.unlink()
            subprocess.run(['git','init','--quiet',str(work)],check=True,capture_output=True,timeout=15)
            applied=subprocess.run(['git','apply','--whitespace=nowarn',str(tests/'test.patch')],cwd=work,capture_output=True,timeout=30)
            if applied.returncode:raise ValueError('隐藏测试补丁无法应用，未生成分数。')
            env=clean_environment(work,home,go)
            selectors=[('./parser',None),('.', '^TestScript_'),('.', '^TestCompiler_'),('.', '^TestCompilerScopes'),('.', '^TestCompiled_'),('.', '^TestScriptSourceModule'),('.', '^TestCompiledFunctionCall')]
            logs=[]
            for i,(package,pattern) in enumerate(selectors):
                if control['stop'].is_set():raise ValueError('已取消本机测试验收。')
                progress(f'运行固定测试组 {i+1}/{len(selectors)} · '+(pattern or package))
                args=[go,'test','-json','-count=1','-timeout','300s']
                if i==6:args+=['-tags','compiledcall']
                args+=[package]
                if pattern:args+=['-run',pattern]
                log=folder/f'suite-{i+1}.jsonl'
                code=sandbox_command(work,home,args,env,log,control['stop'])
                if code not in (0,1):raise ValueError('命令沙箱或测试工具异常，详见执行记录；未生成分数。')
                logs.append(log);commands.append({'argv':[str(x) for x in args],'exitCode':code,'log':log.name})
                (folder/'commands.json').write_text(json.dumps(commands,indent=2),encoding='utf-8')
            result=grade(config,logs)
            verify_snapshot(source,manifest)
            result.update(id='native-'+uuid.uuid4().hex[:12],at=now(),adapter=ADAPTER,environment='windows-codex-sandbox',
                          officialEnvironment=False,goVersion=GO_VERSION,sourceRevision=REVISION,captureHash=manifest['sha256'],
                          seconds=round(time.monotonic()-started,2),commands=commands,logDirectory=str(folder),
                          scope='上游隐藏测试与白名单，Windows 适配；不等同于上游 Linux 排行榜。')
            (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            return result
    finally:
        if not work.resolve().is_relative_to(temp_root.resolve()):raise ValueError('验收清理目录越界。')
        shutil.rmtree(work)
