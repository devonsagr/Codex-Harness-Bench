"""Inventory and reversible cleanup of owned, finished development workspaces."""
import shutil
from .files import safe_path, inventory, hash_bytes, now, verify_snapshot
from .service import identifier


def size(path):
    if not path.exists():return 0
    if path.is_symlink() or path.is_junction():return 0
    if path.is_file():return path.stat().st_size
    return sum(size(p) for p in path.iterdir())


def status(app):
    with app.lock:
        runs=app.db.list('run')+app.db.list('run',True)
        jobs=set(app.jobs)
        source_jobs=app.db.list('source_job')
    rows=[]
    for run in runs:
        for trial in run['trials']:
            folder=safe_path(app.local,'runs/'+identifier(run['id'])+'/'+identifier(trial['id']))
            rows.append({'runId':run['id'],'trialId':trial['id'],'revision':run['revision'],
                'title':next(t['title'] for t in run['tasks'] if t['id']==trial['taskId']),
                'state':trial['state'],'workspaceBytes':size(folder/'workspace'),'reviewBytes':size(folder/'reviews')+size(folder/'native-checks'),
                'snapshotBytes':size(folder/'captures')+size(folder/'baseline'),'captures':len(trial['captures']),
                'reviews':len(trial['reviews']),'workspacePath':str(folder/'workspace'),
                'cleanup':trial.get('workspaceCleanup'),'canClean':trial['state']=='completed' and bool(trial['captures']) and (folder/'workspace').exists() and not trial.get('ownedContainers') and (run['id'],trial['id']) not in jobs})
    return {'root':str(app.local),'categories':[
        {'name':'配置、题目与历史记录','path':'arena.sqlite3','bytes':size(app.db.path),'purpose':'保存版本、评分、人工修正和索引；不会随工作区清理删除。'},
        {'name':'固定源码起点','path':'baselines/','bytes':size(app.local/'baselines'),'purpose':'创建工作区的来源。与已开始的评测副本分离。'},
        {'name':'公开题面与隐藏验收','path':'public-sources/','bytes':size(app.local/'public-sources'),'purpose':'可重新下载的固定题包；不把隐藏测试复制到开发目录。'},
        {'name':'固定工具链与环境检查','path':'toolchains/ + environment-checks/','bytes':size(app.local/'toolchains')+size(app.local/'environment-checks'),'purpose':'免 Docker 工具链和故障起点校验日志；与用户系统安装分开。'},
        {'name':'技能快照','path':'skills/','bytes':size(app.local/'skills'),'purpose':'已选配置引用的版本，不清理用户全局技能。'},
        {'name':'待删除工作区','path':'trash/workspaces/','bytes':size(app.local/'trash/workspaces'),'purpose':'清理先移入这里；可恢复，彻底删除后才释放磁盘。'},
    ],'workspaces':rows,'sourceJobs':source_jobs,
    'tools':{'git':bool(shutil.which('git')),'codex':bool(shutil.which('codex')),'dockerInstalled':bool(shutil.which('docker'))}}

def reject_links(path):
    if path.is_symlink() or path.is_junction():raise ValueError('目录含链接或目录联接，未清理；请先人工核对。')
    if path.is_dir():
        for child in path.iterdir():reject_links(child)


def workspace(app,data):
    rid=identifier(data.get('runId'));tid=identifier(data.get('trialId'));action=data.get('action')
    with app.lock:
        run=app.db.get('run',rid)
        if data.get('revision')!=run['revision']:raise ValueError('记录已变化，请刷新后重新核对清理范围。')
        trial=next((t for t in run['trials'] if t['id']==tid),None)
        if not trial or trial['state']!='completed' or not trial['captures']:raise ValueError('只能清理已标记交付结束且已回收的工作区。')
        if (rid,tid) in app.jobs or trial.get('ownedContainers'):raise ValueError('后台检查尚未结束，不能清理。')
        root=safe_path(app.local,'runs/'+rid+'/'+tid);work=safe_path(root,'workspace')
        trash=safe_path(app.local,'trash/workspaces/'+rid+'/'+tid)
        if action=='trash':
            if data.get('desktopStopped') is not True:raise ValueError('请先确认桌面对话已停止写入。')
            if not work.is_dir() or trash.exists():raise ValueError('目录状态已变化，请刷新。')
            capture=trial['captures'][-1]
            verify_snapshot(root/'captures'/capture['id']/'files',capture['manifest'])
            files,_=inventory(work)
            if {n:hash_bytes(b) for n,b in files.items()}!=capture['manifest']['files']:
                raise ValueError('工作区存在未回收改动，请先回收新版本，再标记交付结束。')
            reject_links(work);trash.parent.mkdir(parents=True,exist_ok=True);work.rename(trash)
            trial['workspaceCleanup']={'status':'trashed','at':now(),'captureId':capture['id']}
        elif action=='restore':
            if trial.get('workspaceCleanup',{}).get('status')!='trashed' or work.exists() or not trash.is_dir():raise ValueError('没有可恢复的工作区，或原位置已被占用。')
            reject_links(trash);trash.rename(work);trial['workspaceCleanup']={'status':'restored','at':now()}
        elif action=='purge':
            if data.get('confirmation')!='永久删除工作区':raise ValueError('请输入“永久删除工作区”确认；快照与评分保留。')
            if trial.get('workspaceCleanup',{}).get('status') not in {'trashed','deleting'}:raise ValueError('请先移入待删除区。')
            reject_links(trash)
            # Keep a durable intent before irreversible removal. A retry can finish
            # an interrupted purge without treating a missing directory as lost evidence.
            trial['workspaceCleanup']={'status':'deleting','at':now()}
            run=app.db.save('run',run,run['revision'])
            trial=next(t for t in run['trials'] if t['id']==tid)

            if trash.exists():shutil.rmtree(trash)
            trial['workspaceCleanup']={'status':'deleted','at':now()}
        else:raise ValueError('未知工作区清理操作。')
        app.event(run,{'trash':'工作区移入待删除区；快照、AI复查、评分与记录保留。','restore':'工作区已恢复到原位置。','purge':'待删除工作区已永久删除；快照、AI复查、评分与记录保留。'}[action],tid)
        try:
            app.db.save('run',run,run['revision'])
        except Exception:
            # Undo reversible file moves when their metadata cannot be committed.
            if action=='trash':trash.rename(work)
            elif action=='restore':work.rename(trash)
            raise
        return status(app)
