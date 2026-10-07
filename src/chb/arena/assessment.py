"""One assessment of a frozen delivery, using only the existing fixed verifiers."""
import threading
import time
import uuid
import math
from .files import now, verify_snapshot
from .review_options import timeout_seconds, ReviewBudgetExceeded

VERSION = 'delivery-assessment-v1'


def run_assessment(app, rid, tid, capture, task, data, control):
    from .jobs import run_checks, run_judge
    from .service import applicable_checks
    from .native_verifier import supported as local_supported, run as local_run
    from .upstream_verifier import supported as upstream_supported, run as upstream_run
    deadline = time.monotonic() + timeout_seconds(data)
    source = app.local / 'runs' / rid / tid / 'captures' / capture['id'] / 'files'

    def ensure_running():
        if time.monotonic() >= deadline:
            raise ReviewBudgetExceeded('本次评测已用完时间预算；已完成的结果保留，未执行项不判失败。')
        if control['stop'].is_set():
            raise ValueError('已取消本次评测；已完成的结果保留。')
        verify_snapshot(source, capture['manifest'])

    def update(phase, step=None):
        with app.lock:
            current, trial = app.trial(rid, tid)
            execution = trial['assessmentExecution']
            execution['phase'] = phase
            if step:
                execution['steps'].append(step)
            app.db.save('run', current, current['revision'])

    def recover(error, label):
        ensure_running()
        with app.lock:
            _, trial = app.trial(rid, tid)
            if trial.get('ownedContainers'):
                raise error
        # Exception text may contain private command/config details.
        reason = str(error)
        if len(reason) > 250 or not any('\u4e00' <= c <= '\u9fff' for c in reason):
            reason = '此验收环境未能完成检查；AI 继续按原题主动取证。'
        update(label, {'kind': 'program', 'status': 'unavailable', 'reason': reason})

    # A single deadline also covers preparation and program checks. Their own
    # cancellation paths stop owned processes; never touch the desktop task.
    def expire():
        from .jobs import stop_job
        try:stop_job(app, rid, tid)
        except ValueError:pass  # Operation may have finished while the timer fired.
    timer = threading.Timer(timeout_seconds(data), expire)
    timer.daemon = True
    timer.start()
    try:
        ensure_running()
        native = next((row for row in reversed(capture.get('nativeVerifications', []))
                       if row.get('captureHash') == capture['manifest']['sha256']
                       and type(row.get('reward')) is int and row['reward'] in (0, 1)), None)
        if local_supported(task) or upstream_supported(task):
            if native:
                update('原题结果已就绪', {'kind': 'native', 'status': 'reused', 'resultId': native['id']})
            else:
                job_id = uuid.uuid4().hex[:12]
                with app.lock:
                    current, trial = app.trial(rid, tid)
                    trial['nativeExecution'] = {'status': 'running', 'phase': '自动准备原题验收',
                        'startedAt': now(), 'captureId': capture['id'], 'jobId': job_id}
                    app.db.save('run', current, current['revision'])
                update('执行原题验收')
                folder = app.local / 'runs' / rid / tid / 'native-checks' / job_id
                def progress(message):
                    ensure_running()
                    with app.lock:
                        current, trial = app.trial(rid, tid)
                        trial['nativeExecution']['phase'] = message
                        app.db.save('run', current, current['revision'])
                try:
                    native = (local_run(app, task, source, capture['manifest'], folder, control, progress)
                              if local_supported(task) else
                              upstream_run(app, rid, tid, task, source, capture['manifest'], folder, control, progress))
                    ensure_running()
                    with app.lock:
                        current, trial = app.trial(rid, tid)
                        stored = next(c for c in trial['captures'] if c['id'] == capture['id'])
                        stored.setdefault('nativeVerifications', []).append(native)
                        capture['nativeVerifications'] = stored['nativeVerifications']
                        trial['nativeExecution'].update(status='completed', phase='原题验收完成', endedAt=now())
                        app.db.save('run', current, current['revision'])
                    update('原题验收完成', {'kind': 'native', 'status': 'completed', 'resultId': native['id']})
                except ValueError as exc:
                    recover(exc, '原题环境受限，继续 AI 取证')
                    with app.lock:
                        current, trial = app.trial(rid, tid)
                        trial['nativeExecution'].update(status='failed', phase='验收环境未完成', endedAt=now())
                        app.db.save('run', current, current['revision'])
        checks = applicable_checks(task, capture['stageIndex'])
        complete_checks = (checks and {row['id'] for row in capture['checks']} == {row['id'] for row in checks}
                           and all(row.get('status') in {'passed', 'failed'} for row in capture['checks']))
        if complete_checks:
            update('程序检查已就绪', {'kind': 'checks', 'status': 'reused'})
        elif checks and data.get('environment', 'docker') == 'docker':
            update('执行本题程序检查')
            with app.lock:
                current, trial = app.trial(rid, tid)
                stored = next(c for c in trial['captures'] if c['id'] == capture['id'])
                stored.setdefault('checkAttempts', []).append({'at': now(), 'results': stored['checks']})
                stored['checks'] = []; capture['checks'] = []
                app.db.save('run', current, current['revision'])
            try:
                capture['checks'] = run_checks(app, rid, tid, capture, task, control)
                ensure_running()
                update('程序检查完成', {'kind': 'checks', 'status': 'completed'})
            except ValueError as exc:
                with app.lock:
                    _, trial = app.trial(rid, tid)
                    capture['checks'] = next(c for c in trial['captures'] if c['id'] == capture['id'])['checks']
                recover(exc, '专用检查受限，继续 AI 取证')
        elif checks:
            update('本机由 AI 检查需求', {'kind': 'checks', 'status': 'unavailable',
                'reason': '本机裁判不执行 Docker 专用脚本；按原题收集可运行的测试证据。'})
        else:
            update('按原题需求取证', {'kind': 'checks', 'status': 'not_applicable'})
        from .behavior import check_definition
        supplemental = check_definition(task, app.root)
        if (supplemental and data.get('environment', 'docker') == 'docker'
                and not any(row.get('id') == supplemental['id'] and row.get('status') in {'passed', 'failed'}
                            for row in capture.get('behaviorChecks', []))):
            update('执行已接入的功能补充检查')
            try:
                run_checks(app, rid, tid, capture, task, control, behavior=True)
                ensure_running()
                update('功能补充检查完成', {'kind': 'behavior', 'status': 'completed'})
            except ValueError as exc:
                recover(exc, '功能补充检查受限，继续 AI 取证')
        from .frontend_readability import check_definition as readability_check, extract
        if readability_check(task,capture) and data.get('environment','docker')=='docker' and not extract(task,capture['checks'],capture):
            update('检查页面文字与操作区域')
            try:
                run_checks(app,rid,tid,capture,task,control,readability=True)
                ensure_running()
                measured=extract(task,capture['checks'],capture)
                update('浏览器实测已记录' if measured else '浏览器实测受限，继续 AI 取证',
                       {'kind':'readability','status':'completed' if measured else 'unavailable'})
            except ValueError as exc:
                recover(exc,'浏览器实测受限，继续 AI 取证')
        ensure_running()
        timer.cancel()  # Reviewer execution observes the same absolute deadline.
        update('AI 正在逐项取证与评分')
        remaining = min(timeout_seconds(data), math.ceil(deadline - time.monotonic()))
        if remaining < 60:
            raise ReviewBudgetExceeded('程序验收后剩余预算不足以启动 AI；已有程序结果已保留。')
        # A dedicated script that could not run is an environment limitation,
        # not evidence against the AI's independently observed verification.
        # Actual failed checks still apply their original score constraint.
        fallback = bool(checks and (not capture['checks'] or
            any(row.get('status') not in {'passed', 'failed'} for row in capture['checks'])))
        report = run_judge(app, rid, tid, capture, task, {**data, 'timeoutSeconds': remaining,
            'programChecksFallback': fallback}, control, deadline=deadline)
        report['assessmentVersion'] = VERSION
        report['programChecksFallback'] = fallback
        return report
    finally:
        timer.cancel()
