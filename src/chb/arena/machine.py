"""Evidence-backed machine scores and append-only, per-dimension human corrections."""
import json
import re
from .contracts import string
from .files import fingerprint
from .scoring import number, acceptance, UI_RUBRIC_KEYS, auto_dimensions


class EvidenceError(ValueError):
    """A well-shaped citation that does not resolve to frozen evidence."""


# These bundled verifiers have task-specific positive/negative fixtures. The
# shared creative-web verifier only checks basic page health and must not turn
# an AI quality opinion into a comparison-ready configuration score.
TASK_VERIFIERS = {
    'original-search-notes-v1': 'search-notes-v1',
    'original-storage-migration-v1': 'storage-migration-v1',
    'original-csv-catalog-v1': 'csv-catalog-v1',
    'original-invoice-reconcile-v1': 'invoice-reconcile-v1',
    'original-web-metrics-v1': 'web-metrics-v1',
}


def score_assurance(task, trial):
    """Classify program evidence without treating a citation as validation."""
    verifier = TASK_VERIFIERS.get(task.get('id'))
    configured = task.get('checks') or []
    # An edited task no longer has the contract exercised by these fixtures.
    # Built-in multi-stage checks are not rerun against the final snapshot.
    if (not verifier or task.get('sourceKind') != 'repository-original'
            or task.get('revision') != 1 or len(task.get('stages') or []) != 1
            or not configured):
        return 'ai-reference'
    if any(check.get('image') != 'chb-verifier:' + verifier
           or not any('/tests/verify.' in str(arg) for arg in check.get('argv', []))
           for check in configured):
        return 'ai-reference'
    captures = trial.get('captures') or []
    observed = {check['id']: check for check in (captures[-1].get('checks', []) if captures else [])
                if check.get('id')}
    statuses = [observed.get(check.get('id'), {}).get('status') for check in configured]
    if any(status not in {'passed', 'failed'} for status in statuses):
        return 'ai-reference'
    return 'task-check-pass' if all(status == 'passed' for status in statuses) else 'task-check-fail'


def dimensions(policy, task):
    if policy.get('taskTypeAuto'):
        override=policy.get('taskOverrides',{}).get(task['id'])
        if override:return override['dimensions']
        return auto_dimensions(task,policy.get('autoScorecardVersion','project-tasktype-v2'))
    return {k:w for k,w in policy['dimensions'].items() if w>0 and (k not in UI_RUBRIC_KEYS or task.get('hasFrontendUI'))}


def policy_for_task(policy,task):
    override=policy.get('taskOverrides',{}).get(task['id']) if policy.get('taskTypeAuto') else None
    return {**policy,'taskTypeAuto':False,'dimensions':override['dimensions'],'rubrics':override['rubrics']} if override else policy


def evidence_key(capture):
    return fingerprint({'id':capture['id'],'manifest':capture['manifest'],'checks':capture['checks']})


def json_fragment_matches(output,quote):
    """Accept a re-formatted JSON member only inside one actual JSON command result."""
    try:
        document=json.loads(output)
        fragment=json.loads('{'+quote+'}')
    except (ValueError,TypeError):return False
    if not isinstance(fragment,dict) or not fragment:return False
    expected=list(fragment.items())
    def visit(value):
        if isinstance(value,dict):
            items=list(value.items())
            if any(items[index:index+len(expected)]==expected for index in range(len(items)-len(expected)+1)):
                return True
            return any(visit(child) for child in value.values())
        return isinstance(value,list) and any(visit(child) for child in value)
    return visit(document)


def validate_machine(value, packet, commands):
    """Validate provenance, not the truth of a model's interpretation."""
    if packet.get('scoringContract'):
        from .judge_protocol import VERSION, validate
        if packet['scoringContract'].get('version') != VERSION:
            raise ValueError('未知统一评分协议，不能按其他版本解释。')
        return validate(value, packet, commands)
    rows=value.get('ratings')
    expected=dimensions(packet['policy'],packet['task'])
    if not isinstance(rows,dict) or set(rows)!=set(expected):raise ValueError('机器评分必须逐项覆盖冻结的评分维度。')
    def contains(output,quote):
        # Windows tool output uses CRLF; JSON judges commonly quote LF. Only
        # reformatting of a complete JSON result is also allowed, but its
        # quoted members must match one nested object in their original order.
        exact=quote.replace('\r\n','\n').replace('\r','\n') in output.replace('\r\n','\n').replace('\r','\n')
        return exact or json_fragment_matches(output,quote)
    def evidence(items):
        if not isinstance(items,list):raise ValueError('评分引用格式无效。')
        if len(items)>50:raise EvidenceError('此项引用超过50条，无法可靠复核。')
        def one(item):
            if not isinstance(item,dict):raise ValueError('评分引用格式无效。')
            quote=item.get('quote')
            if not isinstance(quote,str) or not quote.strip() or len(quote)>3000:raise ValueError('评分引用缺少原文。')
            if 'turnId' in item:
                from .interaction import verify
                dialogue=packet.get('interactionEvidence')
                if not dialogue:raise EvidenceError('缺少冻结对话，不能验证沟通引用。')
                verify(dialogue)
                turn=next((t for t in dialogue['turns'] if t['id']==item['turnId']),None)
                speaker=item.get('speaker')
                if not turn or turn['incomplete'] or speaker not in {'user','assistant'} or quote not in turn[speaker]:
                    raise EvidenceError('对话回合、角色或原文不匹配，或该回合不完整。')
                return {'turnId':turn['id'],'speaker':speaker,'quote':quote}
            elif 'path' in item:
                if not isinstance(item['path'],str):raise ValueError('文件引用路径无效。')
                lines=packet['files'].get(item['path'],'').splitlines();line=item.get('line')
                ref={'path':item['path'],'line':line,'quote':quote}
                if type(line) is not int or not 1<=line<=len(lines) or quote not in lines[line-1]:
                    matches=[i+1 for i,text in enumerate(lines) if quote in text]
                    if type(line) is not int or line<1 or len(matches)!=1:
                        raise EvidenceError(f'文件 {item["path"][:80]} 第 {line if type(line) is int else "无效"} 行与引用原文不符，且无法唯一定位。')
                    ref.update(line=matches[0],reportedLine=line,anchor='unique-exact-quote')
                return ref
            elif 'command' in item:
                command=item['command']
                if not isinstance(command,str) or not command.strip():raise ValueError('命令引用无效。')
                match=next((c for c in commands if command in c['command'] and contains(c['output'],quote)),None)
                if match is None:
                    # Codex CLI logs the PowerShell executable and shell-escaped
                    # arguments. The judge quotes the command it typed, so the
                    # literal substring can differ despite identical tokens.
                    normalized=lambda value:re.sub('[^a-z0-9]+','',value.lower())
                    reported=normalized(command)
                    if len(reported)>=12:
                        match=next((c for c in reversed(commands) if reported in normalized(c['command'])
                                    and contains(c['output'],quote)),None)
                if match is None:raise EvidenceError('机器评分引用的执行记录不存在。')
                ref={'commandId':match['id'],'command':match['command'],'exitCode':match['exitCode'],'quote':quote}
                if command not in match['command']:ref['reportedCommand']=command
                if json_fragment_matches(match['output'],quote) and quote not in match['output']:
                    ref['anchor']='json-object-fragment'
                return ref
            elif 'checkId' in item:
                match=next((c for c in packet['checks'] if c['id']==item['checkId'] and contains(c.get('output',''),quote)),None)
                if match is None:raise EvidenceError('机器评分引用的检查记录不存在。')
                return {'checkId':match['id'],'status':match['status'],'quote':quote}
            else:raise ValueError('评分必须引用文件、执行记录或检查。')
        verified=[];invalid=[]
        for item in items:
            try:verified.append(one(item))
            except (EvidenceError,ValueError) as exc:invalid.append(str(exc))
        return verified,invalid
    ratings={};warnings=[]
    for key,row in rows.items():
        if not isinstance(row,dict):raise ValueError('机器评分项格式无效。')
        if 'score' not in row:raise ValueError('评分项须明确返回分数或 null。')
        score=None if row['score'] is None else number(row['score'])
        reason=string(row.get('reason'),'评分理由',5000,True)
        method=row.get('method')
        if method not in {'static','runtime','unverified'}:raise ValueError('评分取证方式无效。')
        try:refs,invalid=evidence(row.get('evidence',[]))
        except EvidenceError as exc:
            warnings.append({'section':'ratings','key':key,'message':str(exc)})
            ratings[key]={'score':None,'reason':'引用未通过校验，此项未计分：'+str(exc),'method':'unverified','evidence':[]}
            continue
        warnings.extend({'section':'ratings','key':key,'message':message} for message in invalid)
        if score is not None and not refs and invalid:
            ratings[key]={'score':None,'reason':'引用未通过校验，此项未计分。','method':'unverified','evidence':[]}
            continue
        if score is not None and (not refs or method=='unverified'):raise ValueError('没有证据的维度不能生成分数。')
        if method=='runtime' and not any('commandId' in r or 'checkId' in r for r in refs):raise ValueError('运行结论必须引用实际执行记录。')
        if key in UI_RUBRIC_KEYS|{'performance'} and score is not None and method!='runtime':raise ValueError('界面或性能评分需要实际运行证据。')
        ratings[key]={'score':score,'reason':reason,'method':method,'evidence':refs}
    criteria=value.get('criteria',{})
    if not isinstance(criteria,dict) or set(criteria)!={c['id'] for c in packet['task'].get('criteria',[])}:raise ValueError('机器验收必须覆盖冻结的需求条目。')
    verified={}
    for key,row in criteria.items():
        if not isinstance(row,dict) or row.get('status') not in {'met','partial','unmet','unverified'}:raise ValueError('机器验收状态无效。')
        notes=string(row.get('notes'),'需求验收理由',5000,True)
        try:refs,invalid=evidence(row.get('evidence',[]))
        except EvidenceError as exc:
            warnings.append({'section':'criteria','key':key,'message':str(exc)})
            verified[key]={'status':'unverified','notes':'引用未通过校验：'+str(exc),'evidence':[]}
            continue
        warnings.extend({'section':'criteria','key':key,'message':message} for message in invalid)
        if row['status']!='unverified' and not refs and invalid:
            verified[key]={'status':'unverified','notes':'引用未通过校验，此项未验收。','evidence':[]}
            continue
        if row['status']!='unverified' and not refs:raise ValueError('需求验收缺少证据。')
        verified[key]={'status':row['status'],'notes':notes,'evidence':refs}
    return {'ratings':ratings,'criteria':verified,'scores':{k:r['score'] for k,r in ratings.items() if r['score'] is not None},
            'scoreSchema':'arena-machine-v1','evidenceKey':packet['evidenceKey'],
            'commands':commands,'scoresAreAdvisory':False,'validationWarnings':warnings,
            'note':'AI 判断计入机器分；引用校验只证明材料存在，不保证结论正确。运行证据与静态判断分别标注。'}


def calculate_machine(run,trial):
    captures=trial.get('captures',[]);latest=captures[-1] if captures else None
    task=next(t for t in run['tasks'] if t['id']==trial['taskId']);weights=dimensions(run['policy'],task)
    key=evidence_key(latest) if latest else None
    # Rechecking the same frozen files adds observations; it does not erase an
    # already validated AI opinion. Reconstruct legacy keys from the checks
    # saved before each rerun, always using this capture's current manifest.
    # A new capture or changed manifest must still require its own report.
    observations={key:latest['checks']} if latest else {}
    for attempt in latest.get('checkAttempts',[]) if latest else []:
        results=attempt.get('results')
        if isinstance(results,list):
            observations[evidence_key({**latest,'checks':results})]=results
    reviews=[r for r in trial.get('reviews',[]) if latest and r['captureId']==latest['id'] and r.get('scoreSchema')=='arena-machine-v1' and r.get('evidenceKey') in observations]
    if latest and trial.get('finalCaptureId')==latest['id'] and latest['stageIndex']+1<len(task['stages']):
        reviews=[r for r in reviews if r.get('evaluationScope',{}).get('kind')=='final']
    report=reviews[-1] if reviews else None
    report_key=report['evidenceKey'] if report else key
    rows=(report or {}).get('ratings',{})
    raw={k:rows.get(k,{}).get('score') for k in weights}
    corrections=[r for r in trial.get('machineCorrections',[]) if report and r['reviewId']==report['id'] and r['evidenceKey']==report_key]
    overrides={}
    for correction in corrections:
        for dim,row in correction['changes'].items():
            if row['score'] is None:overrides.pop(dim,None)
            else:overrides[dim]=row
    effective={k:overrides[k]['score'] if k in overrides else raw[k] for k in weights}
    def average(scores):
        known={k:v for k,v in scores.items() if v is not None};total=sum(weights[k] for k in known)
        return round(sum(weights[k]*v for k,v in known.items())/total,2) if total else None
    coverage=round(sum(weights[k] for k in raw if raw[k] is not None)/sum(weights.values())*100,2)
    complete=all(v is not None for v in effective.values())
    original=average(raw);adjusted=average(effective)
    checks=latest['checks'] if latest else []
    objective=None
    if task['checks'] and latest:
        from .scoring import calculate
        # Keep existing multi-stage deterministic score semantics, without changing the run.
        objective=calculate({**run,'policy':{**run['policy'],'version':'arena-review-v2'}},trial)['objective']
    score={'machine':original,'machineReviewId':report['id'] if report else None,'machineEvidenceKey':report_key,
            'machineChecksChanged':bool(report and report_key!=key),
            'machineCheckEvidence':observations[report_key] if report else [],
            'machineCoverage':coverage,'machineRatings':rows,'machineOverrides':overrides,'effectiveScores':effective,
            'objective':objective,'human':None,'overall':adjusted if complete and trial['state']=='completed' else None,
            'provisional':not complete or trial['state']!='completed','partialScore':adjusted,
            'adjudicatedOverall':adjusted if overrides and complete and trial['state']=='completed' else None,
            'adjudicatedObjective':None,'objectiveReviewId':None,'objectiveEvidenceKey':key,'humanReviewId':None,'varianceMargin':None,
            'acceptance':acceptance(task,trial,report,{c['stageIndex']:c for c in captures}),
            'coverage':{'configuredChecks':len(task['checks']),'executedChecks':len(checks)}}
    if task.get('publicSource'):
        # Preserve the upstream pass/fail separately. Only a versioned local
        # card may produce the user's per-task continuous score.
        native=next((item for item in reversed(latest.get('nativeVerifications',[]))
                     if item.get('captureHash')==latest['manifest']['sha256']
                     and type(item.get('reward')) is int and item['reward'] in (0,1)),None) if latest else None
        from .task_scorecards import score_public
        from .task_scorecards import VERSION
        card=score_public(task,native,effective.get('maintainability') if report else None,report['id'] if report else None,
                          retrospective=run.get('localScorecardVersion')!=VERSION)
        local_total=card['overall'] if card else None
        score.update(scoreSource='task-scorecard' if card else 'native-verifier',overall=local_total,
                     taskScorecard=card,nativeReward=native['reward'] if native else None,
                     assurance='native' if local_total is not None else 'ai-reference',
                     provisional=local_total is None,partialScore=None,adjudicatedOverall=local_total if overrides and local_total is not None else None,
                     nativeVerificationId=native['id'] if native else None)
    else:
        from .task_scorecards import PROJECT_POLICY_VERSION, AUTO_PROJECT_VERSION, score_project, score_project_policy, score_project_auto
        required={'intent','instruction','verification','robustness','maintainability','handoff'}|({'ux'} if task.get('hasFrontendUI') else set())
        task_policy=policy_for_task(run['policy'],task)
        if run.get('projectScorecardVersion') in {'project-tasktype-v2',AUTO_PROJECT_VERSION} and task_policy.get('taskTypeAuto'):
            card=score_project_auto(task,trial,effective,report['id'] if report else None,run['projectScorecardVersion'])
        elif run.get('projectScorecardVersion') in {PROJECT_POLICY_VERSION,'project-tasktype-v2',AUTO_PROJECT_VERSION} and not task_policy.get('taskTypeAuto'):
            card=score_project_policy(task,trial,effective,report['id'] if report else None,task_policy)
        elif run.get('localScorecardVersion') and required<=set(weights):
            card=score_project(task,trial,effective,report['id'] if report else None)
        else:
            card=None
        if card:
            if latest and trial.get('finalCaptureId')!=latest['id'] and latest['stageIndex']+1<len(task['stages']):
                # A scored intermediate snapshot is not the final deliverable.
                card['overall']=None
            score.update(scoreSource='task-scorecard',taskScorecard=card,overall=card['overall'],
                         assurance=score_assurance(task,trial),
                         provisional=card['overall'] is None or trial['state']!='completed',
                         adjudicatedOverall=card['overall'] if overrides and card['overall'] is not None else None)
        else:score['scoreSource']='project-rubric'
    from .task_scorecards import score_progress
    score['scoreProgress']=score_progress(score.get('taskScorecard'))
    from .judge_reliability import summarize
    score['judgeReliability']=summarize(trial,score)
    return score


def validate_correction(data,score):
    if not score['machineReviewId'] or data.get('reviewId')!=score['machineReviewId'] or data.get('evidenceKey')!=score['machineEvidenceKey']:
        raise ValueError('机器评分或证据已变化，请刷新后重新调整。')
    changes=data.get('changes')
    if not isinstance(changes,dict) or not changes or not set(changes)<=set(score['effectiveScores']):raise ValueError('请选择需要修正的评分项。')
    result={}
    for key,row in changes.items():
        if not isinstance(row,dict):raise ValueError('修正格式无效。')
        result[key]={'score':None if row.get('score') is None else number(row['score']),
                     'reason':string(row.get('reason'),'修正理由与证据',5000,True)}
    return result
