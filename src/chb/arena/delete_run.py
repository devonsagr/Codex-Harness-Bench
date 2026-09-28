"""Two explicit deletion stages for one evaluation's owned data."""
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

from .files import now, safe_path
from .service import identifier
from .skills import codex_home
from .storage import status
from .telemetry import linked_sessions


def _stopped(app, run):
    rid = run['id']
    if any((rid, trial['id']) in app.jobs or trial['state'] in {'checking', 'judging'} or trial.get('ownedContainers')
           for trial in run['trials']):
        raise ValueError('后台检查或裁判仍在运行；停止后才能删除这次评测。')


def _remove_tree(path, stage):
    if not path.exists():
        return
    # The owned root must be a real directory. Nested package-manager links and
    # junctions are removed by rmtree without traversing their targets (Python
    # 3.8+ on Windows); rejecting them would make normal pnpm workspaces
    # impossible to delete.
    if path.is_symlink() or path.is_junction():
        raise ValueError(f'{stage}未完成：评测目录本身是链接，未删除。')

    def writable(function, name, error):
        if not isinstance(error, PermissionError):
            raise error
        if Path(name).is_symlink() or Path(name).is_junction():
            raise error
        os.chmod(name, os.stat(name, follow_symlinks=False).st_mode | stat.S_IWUSR)
        function(name)

    try:
        shutil.rmtree(path, onexc=writable)
    except OSError as exc:
        raise ValueError(f'{stage}未完成：文件仍被占用或无法写入。请关闭关联 Codex 对话后重试；已完成的部分无需重做。') from exc


def _workspace_paths(app, run):
    rid = run['id']
    return [safe_path(app.local, f'runs/{rid}/{identifier(trial["id"])}/workspace') for trial in run['trials']] + [
        safe_path(app.local, f'trash/workspaces/{rid}/{identifier(trial["id"])}') for trial in run['trials']]


def _sessions(run):
    return {session['id'] for trial in run['trials']
            for session in linked_sessions(codex_home(), trial['workspacePath'])}


def delete_workspaces(app, data):
    """Delete only development workspaces and their exact Codex sessions."""
    rid = identifier(data.get('runId'))
    if data.get('confirmation') != '删除工作区 ' + rid:
        raise ValueError('请按提示输入“删除工作区 记录编号”。')
    if data.get('desktopStopped') is not True:
        raise ValueError('请先确认这次评测的 Codex 对话已经停止写入。')
    with app.lock:
        run = app.db.get('run', rid)
        _stopped(app, run)
        stage = run.get('workspaceDeletion') or {}
        if stage.get('status') == 'deleted':
            return status(app)
        actual = _sessions(run)
        if stage.get('status') == 'deleting':
            intended = set(stage['sessionIds'])
            if not actual <= intended:
                raise ValueError('发现新的关联 Codex 对话；请先停止新对话，再核对删除范围。')
        else:
            if data.get('revision') != run['revision']:
                raise ValueError('评测已更新，请刷新并重新核对删除范围。')
            selected = data.get('sessionIds')
            if not isinstance(selected, list) or len(selected) != len(set(selected)) or set(selected) != actual:
                raise ValueError('Codex 关联对话列表已变化，请刷新后重新核对。')
            intended = actual
        executable = shutil.which('codex')
        if actual and not executable:
            raise ValueError('未找到 Codex CLI，无法同步删除关联对话；工作区尚未删除。')
        paths = _workspace_paths(app, run)
        for path in paths:
            if path.is_symlink() or path.is_junction():
                raise ValueError('评测工作区本身是链接，未删除。')
        if stage.get('status') != 'deleting':
            run['deletionPending'] = True
            run['workspaceDeletion'] = {'status': 'deleting', 'sessionIds': sorted(intended), 'at': now()}
            run = app.db.save('run', run, run['revision'])
        for session_id in sorted(actual):
            try:
                options = {'capture_output': True, 'text': True, 'encoding': 'utf-8', 'errors': 'replace',
                           'timeout': 30, 'env': {**os.environ, 'CODEX_HOME': str(codex_home())},
                           'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
                result = subprocess.run([executable, 'delete', session_id, '--force'], **options)
                if result.returncode:
                    # Codex refuses to delete a loaded idle chat. Archiving closes
                    # that chat; retry the same exact ID before touching its workspace.
                    archived = subprocess.run([executable, 'archive', session_id], **options)
                    if archived.returncode:
                        raise ValueError(f'Codex 对话 {session_id} 无法关闭并删除；请先停止该对话后重试。')
                    result = subprocess.run([executable, 'delete', session_id, '--force'], **options)
            except (OSError, subprocess.SubprocessError) as exc:
                raise ValueError(f'Codex 对话 {session_id} 删除未完成；请停止该对话后重试。') from exc
            if result.returncode:
                raise ValueError(f'Codex 对话 {session_id} 删除失败；请在 Codex 核对后重试。')
        if _sessions(run):
            raise ValueError('Codex 侧栏仍有这次评测的关联对话；请刷新后继续删除。')
        for path in paths:
            _remove_tree(path, '工作区删除')
        run['workspaceDeletion'] = {'status': 'deleted', 'sessionIds': sorted(intended), 'at': now()}
        # Workspace removal is complete. The retained capture/score record may
        # still be inspected and verified until the user separately deletes it.
        run['deletionPending'] = False
        for trial in run['trials']:
            trial['workspaceCleanup'] = {'status': 'deleted', 'at': now()}
        app.db.save('run', run, run['revision'])
        return status(app)


def delete(app, data):
    """After stage one, permanently remove the remaining record and evidence."""
    rid = identifier(data.get('runId'))
    if data.get('confirmation') != '永久删除评测 ' + rid:
        raise ValueError('请按提示输入“永久删除评测 记录编号”。')
    with app.lock:
        run = app.db.get('run', rid)
        _stopped(app, run)
        if (run.get('workspaceDeletion') or {}).get('status') != 'deleted':
            raise ValueError('请先完成第一步：删除工作区和关联 Codex 对话。')
        if _sessions(run) or any(path.exists() for path in _workspace_paths(app, run)):
            run['workspaceDeletion'] = {'status': 'recheck', 'at': now()}
            app.db.save('run', run, run['revision'])
            raise ValueError('第一步后又出现工作区或关联对话；请停止写入并重新核对第一步。')
        if not run.get('recordDeletionPending') and data.get('revision') != run['revision']:
            raise ValueError('评测已更新，请刷新并重新核对删除范围。')
        owned = [safe_path(app.local, 'runs/' + rid), safe_path(app.local, 'trash/workspaces/' + rid)]
        runtime = (app.local / 'reviewer-runtime').resolve()
        for receipt in owned[0].glob('*/reviews/job-*/runtime.json'):
            checked = safe_path(owned[0], receipt.relative_to(owned[0]).as_posix())
            if checked.stat().st_size > 10000:
                raise ValueError('裁判运行回执异常，未开始删除。')
            value = json.loads(checked.read_text(encoding='utf-8'))
            for key, prefix in [('workspace', 'chb-review-work-'), ('temporaryHome', 'chb-review-home-')]:
                path = Path(value[key])
                if path.resolve().parent != runtime or not path.name.startswith(prefix):
                    raise ValueError('裁判运行目录越界，未开始删除。')
                owned.append(safe_path(runtime, path.name))
        for path in owned:
            if path.is_symlink() or path.is_junction():
                raise ValueError('评测记录目录本身是链接，未删除。')
        if not run.get('recordDeletionPending'):
            run['deletionPending'] = True
            run['recordDeletionPending'] = True
            app.db.save('run', run, run['revision'])
        for path in owned[2:] + owned[:2]:
            _remove_tree(path, '评测记录删除')
        with app.db.connect() as db:
            db.execute('PRAGMA secure_delete=ON')
            db.execute('BEGIN IMMEDIATE')
            preparations = [row['id'] for row in db.execute("SELECT id,body FROM records WHERE kind='preparation_job'")
                            if json.loads(row['body']).get('runId') == rid]
            for kind, key in [('run', rid)] + [('preparation_job', key) for key in preparations]:
                db.execute('DELETE FROM revisions WHERE kind=? AND id=?', (kind, key))
                db.execute('DELETE FROM records WHERE kind=? AND id=?', (kind, key))
        with app.db.connect() as db:
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    return status(app)
