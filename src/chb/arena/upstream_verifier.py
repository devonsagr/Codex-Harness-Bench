"""Run six selected DeepSWE verifiers in their pinned upstream Linux images."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
import uuid
from pathlib import Path

from .files import inventory, now, safe_path, verify_snapshot
from .public_sources import catalog, task_bundle
from .service import shell


TASKS=frozenset({
    'actionlint-action-pinning-lint','abs-stepped-slices','koota-pair-relation-tracking',
    'adaptix-name-mapping-aliases','aiomonitor-task-snapshots-diff','anko-default-function-arguments',
})
ADAPTER='deepswe-upstream-docker-v1'


def supported(task):
    source=task.get('publicSource') or {}
    return source.get('id') in TASKS and source.get('revision')==catalog_revision()


def catalog_revision():
    # This adapter was checked against the published v1.1 task package.
    return '0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea'


def _source_files(root):
    return {name:body for name,body in inventory(root)[0].items()
            if not name.startswith(('.codex/','.agents/','.chb/')) and name not in {'AGENTS.md','AGENTS.override.md'}}


def make_patch(base,candidate,stage):
    """Convert the frozen candidate into the upstream verifier's model.patch."""
    work=stage/'patch-repo';work.mkdir()
    original=_source_files(base);changed=_source_files(candidate)
    for name,body in original.items():
        path=safe_path(work,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    commands=[['git','-c','core.autocrlf=false','init','--quiet'],
              ['git','add','-A'],
              ['git','-c','user.name=Codex Harness','-c','user.email=local@codex.invalid','commit','--quiet','-m','frozen baseline']]
    for argv in commands:
        result=subprocess.run(argv,cwd=work,capture_output=True,timeout=60)
        if result.returncode:raise ValueError('无法构造固定源码与产物差异；未启动原题验收。')
    for name in original.keys()-changed.keys():safe_path(work,name).unlink()
    for name,body in changed.items():
        path=safe_path(work,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    staged=subprocess.run(['git','add','-A'],cwd=work,capture_output=True,timeout=60)
    if staged.returncode:raise ValueError('无法封存产物差异；未启动原题验收。')
    result=subprocess.run(['git','-c','core.quotepath=false','diff','--binary','--no-ext-diff','HEAD'],cwd=work,capture_output=True,timeout=60)
    if result.returncode or len(result.stdout)>50_000_000:raise ValueError('产物补丁生成失败或超过50 MB；未启动原题验收。')
    return result.stdout


def _wait(process,stop,deadline,log):
    while process.poll() is None:
        if stop.is_set():raise ValueError('已取消原题验收。')
        if time.monotonic()>deadline:raise ValueError('原题验收超过时限，结果保持未知。')
        if log.stat().st_size>100_000_000:raise ValueError('原题验收日志超限，结果保持未知。')
        stop.wait(.2)
    return process.returncode


def _image(app,image,stop,folder,progress):
    try:ready=shell(['docker','info','--format','{{.ServerVersion}}'],timeout=15)
    except (OSError,subprocess.SubprocessError) as exc:
        raise ValueError('Docker Desktop Linux 引擎没有在15秒内响应；启动并确认状态为运行中后重试，当前不记零分。') from exc
    if ready.returncode:raise ValueError('Docker Desktop Linux 引擎未运行；启动后重试原题验收，当前不记零分。')
    try:inspect=shell(['docker','image','inspect',image,'--format','{{.Id}}'],timeout=20)
    except (OSError,subprocess.SubprocessError) as exc:
        raise ValueError('无法检查固定镜像；请确认 Docker 引擎可用后重试。') from exc
    if inspect.returncode:
        progress('下载固定的上游 Linux 验收镜像；首次可能需要较长时间')
        log=folder/'image-pull.log'
        with log.open('wb') as output:
            process=subprocess.Popen(['docker','pull',image],stdout=output,stderr=subprocess.STDOUT,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                if _wait(process,stop,time.monotonic()+1800,log):raise ValueError('上游镜像下载失败；请查看本次验收目录的 image-pull.log。')
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=10)
    from chb.cli import pin_image
    try:return pin_image(image)
    except (OSError,ValueError,subprocess.SubprocessError) as exc:raise ValueError('上游镜像无法固定到内容摘要；未启动验收。') from exc


def failed_tests(verifier,reward):
    if reward.get('apply_failed'):
        return ['提交补丁未能应用到固定源码起点；查看测试输出中的 apply 错误。']
    if reward['reward']==1:return []
    failures=[]
    ctrf=verifier/'ctrf.json'
    if ctrf.is_file() and ctrf.stat().st_size<=10_000_000:
        try:
            result_tree=json.loads(ctrf.read_text(encoding='utf-8'))
            tests=result_tree.get('results',{}).get('tests',[])
        except (OSError,ValueError,AttributeError):tests=[]
        if isinstance(tests,list):
            for test in tests:
                if isinstance(test,dict) and test.get('status')!='passed':
                    failures.append((str(test.get('name','未命名测试'))+'：'+str(test.get('message','查看原始测试日志')))[:400])
                    if len(failures)>=30:break
    return failures or ['未通过测试的逐项报告缺失；查看原始测试输出。']


def run(app,rid,tid,task,source,manifest,folder,control,progress=lambda message:None):
    if not supported(task):raise ValueError('这道题尚未接入上游 Linux 原题验收。')
    source_info=task['publicSource'];task_id=source_info['id']
    item=next(t for t in catalog(app)['tasks'] if t['id']==task_id)
    baseline=app.db.get('baseline',task['baselineId'])
    if baseline.get('sourceCommit')!=item['baseCommit'] or baseline.get('sourceUrl')!=item['repositoryUrl']:
        raise ValueError('题目固定源码起点已变化，不能使用原题验收。')
    base=app.local/'baselines'/baseline['id']/'files'
    verify_snapshot(base,baseline['manifest']);verify_snapshot(source,manifest)
    tests=task_bundle(app,task_id)/'tasks'/task_id
    definition=tomllib.loads((tests/'task.toml').read_text(encoding='utf-8'))
    if definition['metadata']['base_commit_hash']!=item['baseCommit']:
        raise ValueError('上游验收起点与固定题目索引不一致。')
    image=definition['environment']['docker_image']
    ext=definition['metadata']['ext_id']
    if not re.fullmatch(r'kh[a-z0-9]{30}',ext) or image!=f'public.ecr.aws/d3j8x8q7/swe-bench-202605:{ext}-v1.1':
        raise ValueError('上游验收镜像不符合固定来源约束。')
    folder.mkdir(parents=True,exist_ok=True)
    artifacts=folder/'artifacts';artifacts.mkdir(exist_ok=True)
    verifier=folder/'verifier';verifier.mkdir(exist_ok=True)
    runtime=app.local/'native-runtime';runtime.mkdir(exist_ok=True)
    progress('从固定源码与回收快照构造补丁')
    with tempfile.TemporaryDirectory(prefix='deepswe-patch-',dir=runtime) as temp:
        stage=Path(temp)
        (artifacts/'model.patch').write_bytes(make_patch(base,source,stage))
    progress('核对上游 Linux 镜像与源码版本')
    pinned=_image(app,image,control['stop'],folder,progress)
    check=shell(['docker','run','--rm','--network','none',pinned,'git','-c','safe.directory=/app','-C','/app','rev-parse','HEAD'],timeout=45)
    if check.returncode or check.stdout.strip()!=item['baseCommit']:
        raise ValueError('验收镜像中的源码提交与题目固定起点不一致。')
    name='chb-upstream-'+uuid.uuid4().hex[:12]
    args=['docker','create','--name',name,'--network','none','--memory','8g','--cpus','2','--pids-limit','512',
          '--cap-drop','ALL','--security-opt','no-new-privileges',
          '--mount',f'type=bind,source={tests/"tests"},target=/tests,readonly',
          '--mount',f'type=bind,source={artifacts},target=/logs/artifacts,readonly',
          '--mount',f'type=bind,source={verifier},target=/logs/verifier',
          '--workdir','/app',pinned,'bash','/tests/test.sh']
    try:created=shell(args,timeout=60)
    except (OSError,subprocess.SubprocessError) as exc:
        raise ValueError('上游验收容器创建超时或 Docker 失去响应，当前不记分。') from exc
    if created.returncode:raise ValueError('上游验收容器创建失败；请核对 Docker 内存、磁盘和文件共享。')
    cid=created.stdout.strip()
    if not re.fullmatch(r'[a-f0-9]{64}',cid):
        shell(['docker','rm','--force',name],timeout=10)
        raise ValueError('Docker 容器编号无效，未启动验收。')
    with app.lock:
        control['containers'].add(name)
        fresh,trial=app.trial(rid,tid)
        trial.setdefault('ownedContainers',[]).append(cid)
        app.db.save('run',fresh,fresh['revision'])
    started=time.monotonic();log=folder/'suite-1.jsonl';process=None
    try:
        progress('运行上游隐藏测试（最多30分钟）')
        with log.open('wb') as output:
            process=subprocess.Popen(['docker','start','--attach',name],stdout=output,stderr=subprocess.STDOUT,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            _wait(process,control['stop'],time.monotonic()+1800,log)
        exited=shell(['docker','inspect',cid,'--format','{{.State.ExitCode}}'],timeout=15)
        if exited.returncode or exited.stdout.strip()!='0':
            raise ValueError('上游验收脚本未正常完成；请查看执行日志，当前不记分。')
        reward_file=verifier/'reward.json'
        if not reward_file.is_file() or reward_file.stat().st_size>100_000:
            raise ValueError('上游验收未产生有效 reward.json；请查看执行日志，当前不记分。')
        reward=json.loads(reward_file.read_text(encoding='utf-8'))
        for key in ('reward','f2p_total','f2p_passed','p2p_total','p2p_passed'):
            if type(reward.get(key)) is not int or reward[key]<0:raise ValueError('上游验收报告字段无效。')
        if reward['reward'] not in (0,1):raise ValueError('上游验收未完成，当前不记分。')
        if (reward['f2p_passed']>reward['f2p_total'] or reward['p2p_passed']>reward['p2p_total'] or
            reward['reward']!=int(reward['f2p_total']>0 and reward['f2p_passed']==reward['f2p_total'] and reward['p2p_passed']==reward['p2p_total'])):
            raise ValueError('上游验收报告计数与结论不一致，当前不记分。')
        verify_snapshot(source,manifest)
        not_passed=failed_tests(verifier,reward)
        report={key:reward.get(key) for key in ('reward','f2p','p2p','partial','f2p_total','f2p_passed','p2p_total','p2p_passed')}
        report.update(id='native-'+uuid.uuid4().hex[:12],at=now(),adapter=ADAPTER,environment='upstream-linux-docker',
                      upstreamVerifier=True,officialEnvironment=False,officialLeaderboardRun=False,sourceRevision=source_info['revision'],
                      captureHash=manifest['sha256'],seconds=round(time.monotonic()-started,2),imageId=pinned,
                      commands=[{'argv':['bash','/tests/test.sh'],'log':log.name}],logDirectory=str(folder),notPassed=not_passed,
                      scope='固定上游镜像与原题隐藏测试；桌面手动执行条件不同，不是官方排行榜提交。')
        (folder/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return report
    finally:
        if process and process.poll() is None:process.kill();process.wait(timeout=10)
        removed=shell(['docker','rm','--force',cid],timeout=15)
        with app.lock:
            control['containers'].discard(name)
            if removed.returncode==0:
                fresh,trial=app.trial(rid,tid)
                if cid in trial.get('ownedContainers',[]):
                    trial['ownedContainers'].remove(cid);app.db.save('run',fresh,fresh['revision'])
        if removed.returncode:raise ValueError('上游验收容器未确认清理；恢复 Docker 后重启工作台。')
