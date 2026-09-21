"""The desktop workflow: freeze, prepare, hand off, capture, verify, review, restore."""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
import uuid
from urllib.parse import urlencode, quote

from .database import Database
from .files import diff_facts, fingerprint, hash_bytes, inventory, now, safe_path, snapshot, verify_snapshot
from .scoring import calculate, policy, validate_review, DEFAULT_POLICY, DIMENSIONS, DESKTOP_POLICY, MACHINE_POLICY, RUBRICS
from .contracts import normalize_contract, task_view, freeze_prompts, stage_prompt, applicable_checks, delivery_task
from .models import capabilities, validate_effort
from .skills import invocation, codex_home
from .codex_apply import settings, connections, project_settings


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,89}',value):
        raise ValueError('记录编号无效。')
    return value


def text(value, limit=10000, required=True):
    if not isinstance(value,str) or len(value)>limit or required and not value.strip():
        raise ValueError('文本为空、类型错误或超过允许长度。')
    return value


def shell(args, cwd=None, timeout=20):
    return subprocess.run(args,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def harness_files(manifest):
    return {name:digest for name,digest in manifest['files'].items()
            if name.rsplit('/',1)[-1] in {'AGENTS.md','AGENTS.override.md'}
            or '.agents/skills/' in name or name.startswith('.codex/')}


class Arena:
    def __init__(self, root):
        self.root=Path(root).resolve()
        self.local=self.root/'.local/arena'
        self.local.mkdir(parents=True,exist_ok=True)
        self.db=Database(self.local/'arena.sqlite3')
        self.lock=threading.RLock()
        self.jobs={}
        self._last_trace_sync=0.0
        self._seed()
        for run in self.db.list('run'):
            if any(t['state'] in {'checking','judging'} or t.get('ownedContainers') for t in run['trials']):
                for trial in run['trials']:
                    if trial['state'] in {'checking','judging'} or trial.get('ownedContainers'):
                        if trial.get('ownedContainers'):
                            remaining=[]
                            for cid in trial['ownedContainers']:
                                try:
                                    if not re.fullmatch('[a-f0-9]{64}',cid):continue
                                    result=shell(['docker','rm','--force',cid],timeout=8)
                                    if result.returncode:remaining.append(cid)
                                except (OSError,subprocess.SubprocessError):remaining.append(cid)
                            trial['ownedContainers']=remaining
                        if trial['state'] in {'checking','judging'}:trial['state']='captured'
                        if trial.get('judgeExecution',{}).get('status') in {'preparing','running'}:
                            trial['judgeExecution'].update(status='interrupted',endedAt=now())
                        self.event(run,'后台服务中断；已保留快照和检查记录，可重新验收。',trial['id'])
                        if trial.get('ownedContainers'):trial['observations'].append('服务重启后仍有本工具检查容器未确认清理，需先恢复 Docker 后处理。')
                self.db.save('run',run,run['revision'])

    def _seed(self):
        if not self.db.list('config') and not self.db.list('config',True):
            for name in ['minimal','focused']:
                folder=self.root/'profiles'/name
                if not folder.exists(): continue
                self.save_config({'id':name,'name':name,'agentsPrompt':(folder/'AGENTS.md').read_text(encoding='utf-8'),
                                  'baseModel':'gpt-6-astra','reasoning':'medium','interactiveMode':'adaptive','skills':[],
                                  'tagline':'项目提供的可编辑示例；没有预设成绩。','author':'本地','customConstraints':[]})
        if not self.db.list('task') and not self.db.list('task',True):
            for task in json.loads((self.root/'catalog/arena-tasks.json').read_text(encoding='utf-8')):
                self.save_task(task)

    def save_config(self, value, import_source=None):
        value=copy.deepcopy(value)
        for key,limit in [('name',100),('agentsPrompt',200000),('baseModel',100)]:
            text(value.get(key),limit,required=key!='agentsPrompt')
        if not re.fullmatch(r'[a-zA-Z0-9._/-]+',value['baseModel']): raise ValueError('模型标识格式无效。')
        if value.get('reasoning') not in {'none','minimal','low','medium','high','xhigh','max','ultra'}: raise ValueError('推理档位无效。')
        validate_effort(value['baseModel'],value['reasoning'])
        if value.get('interactiveMode') not in {'one-shot-direct','step-by-step-confirm','adaptive'}: raise ValueError('交互模式无效。')
        skills=value.get('skills',[])
        if not isinstance(skills,list) or len(skills)>30 or len(set(skills))!=len(skills): raise ValueError('技能列表无效或重复。')
        for skill in skills:
            self.db.get('skill',identifier(skill))
        if len({self.db.get('skill',s)['name'].casefold() for s in skills})!=len(skills):raise ValueError('所选技能同名，请只保留其中一个来源。')
        mode=value.get('skillMode','auto')
        if mode not in {'auto','explicit'}:raise ValueError('技能调用方式无效。')
        constraints=value.get('customConstraints',[])
        if not isinstance(constraints,list) or len(constraints)>40: raise ValueError('个人约束列表无效。')
        for c in constraints:
            identifier(c.get('id'));text(c.get('title'),200);text(c.get('ruleDesc',''),3000,False)
            c['isActive']=bool(c.get('isActive'))
        if len({c['id'] for c in constraints})!=len(constraints): raise ValueError('个人约束编号重复。')
        allowed=['id','name','agentsPrompt','baseModel','reasoning','interactiveMode','skills','customConstraints','tagline','author','specialFeatures']
        body={k:value[k] for k in allowed if k in value}
        body['skillMode']=mode
        body['nativeSettings']=settings(value.get('nativeSettings',{}))
        body['integrations']=connections(value.get('integrations',{}))
        if import_source is not None:body['importSource']=import_source
        elif value.get('id') and value.get('revision'):
            previous=self.db.get('config',identifier(value['id']))
            if previous.get('importSource'):body['importSource']=previous['importSource']
        body['id']=identifier(value.get('id') or 'cfg-'+uuid.uuid4().hex[:12])
        body.update(tagline=value.get('tagline',''),author=value.get('author','本地'),skills=skills,customConstraints=constraints,updatedAt=now())
        return self.db.save('config',body,value.get('revision'))

    def save_task(self, value):
        body=self.validate_task(value)
        body.update(id=identifier(value.get('id') or 'task-'+uuid.uuid4().hex[:12]),updatedAt=now())
        return self.db.save('task',body,value.get('revision'))

    def validate_task(self, value):
        if not isinstance(value,dict):raise ValueError('题目必须是对象。')
        value=copy.deepcopy(value)
        for key in ['revision','archived','contractUpgradePending','promptSnapshots','archiveEvents']:
            value.pop(key,None)
        for key,label,limit in [('title','题目名称',300),('inputPrompt','总体需求',80000)]:
            try:text(value.get(key),limit)
            except ValueError as exc:raise ValueError(label+'：'+str(exc)) from exc
        value.setdefault('difficulty','未标注')
        text(value['difficulty'],100)
        for key in ['description','sourceNote','sourceKind','referenceUrl','license']:
            if key in value:
                try:text(value[key],10000,False)
                except ValueError as exc:raise ValueError(key+'必须是文本。') from exc
        if 'hasFrontendUI' in value and type(value['hasFrontendUI']) is not bool:
            raise ValueError('包含界面标记必须是布尔值。')
        if 'baselineId' in value:
            if value['baselineId'] in (None,''):value.pop('baselineId')
            else:identifier(value['baselineId'])
        if value.get('taskParadigm') not in {'open-ended-project','deterministic-bugfix'}: raise ValueError('请区分项目构建与 Bug 修复。')
        if value.get('channel') not in {'frontend-ui','deepswe-core','architecture-constraint','interactive-confirm'}: raise ValueError('任务方向无效。')
        checks=value.get('checks',[])
        if not isinstance(checks,list) or len(checks)>30: raise ValueError('最多声明 30 项检查。')
        for i,c in enumerate(checks):
            if not isinstance(c,dict):raise ValueError('检查必须是对象。')
            text(c.get('label'),200)
            argv=c.get('argv')
            if not isinstance(argv,list) or not argv or len(argv)>50 or any(not isinstance(x,str) or len(x)>1000 for x in argv): raise ValueError('检查命令必须是参数数组，不直接执行拼接的宿主 shell。')
            text(c.get('image'),200)
            if not re.fullmatch(r'[a-zA-Z0-9._/:@-]+',c['image']): raise ValueError('镜像名称无效。')
            if type(c.get('weight',1)) not in (int,float) or not 0<c.get('weight',1)<=100: raise ValueError('检查权重必须大于 0 且不超过 100。')
            c.update(id=identifier(c.get('id') or str(i+1)),weight=c.get('weight',1))
        if len({c['id'] for c in checks})!=len(checks):raise ValueError('检查编号重复。')
        stages=value.get('stages') or value.get('multiTurnStages') or [{'title':'完成需求','prompt':value['inputPrompt']}]
        if not isinstance(stages,list) or not 1<=len(stages)<=20: raise ValueError('需要 1–20 个明确阶段。')
        for stage in stages:
            if not isinstance(stage,dict):raise ValueError('阶段必须是对象。')
            text(stage.get('title'),300);text(stage.get('prompt'),80000)
        for c in checks:
            if type(c.get('timeout',120)) is not int or not 1<=c.get('timeout',120)<=600:raise ValueError('检查超时需为 1–600 秒整数。')
            if 'stageIndex' in c and (type(c['stageIndex']) is not int or not 0<=c['stageIndex']<len(stages)):raise ValueError('检查对应的阶段不存在。')
        if value.get('baselineId'):self.db.get('baseline',identifier(value['baselineId']))
        value.update(checks=checks,stages=stages,expectedTurns=len(stages),hasFrontendUI=bool(value.get('hasFrontendUI')))
        return normalize_contract(value)

    def models(self):
        models=capabilities()
        if not models:
            models=[{'id':c['baseModel'],'name':c['baseModel'],'source':'已有配置，能力未知','reasoningLevels':[],'capabilitiesKnown':False} for c in self.db.list('config')]
        return list({m['id']:m for m in models}.values())

    def state(self):
        self.sync_desktop_traces()
        runs=[self.present_run(r) for r in self.db.list('run')]
        return {'configs':self.db.list('config'),'tasks':[task_view(t) for t in self.db.list('task')],'skills':self.db.list('skill'),
                'archivedConfigs':self.db.list('config',True),'archivedTasks':[task_view(t) for t in self.db.list('task',True)],
                'runs':runs,'archivedRuns':[self.present_run(r) for r in self.db.list('run',True)],'baselines':self.db.list('baseline'),
                'models':self.models(),'defaultPolicy':MACHINE_POLICY,'dimensions':DIMENSIONS,'rubricCatalog':{k:{'label':v[0],'description':v[1]} for k,v in RUBRICS.items()},
                'mode':'desktop','source':'SQLite 与本机冻结文件','legacyExperiments':len(list((self.root/'runs').glob('*/plan.json')))}

    def sync_desktop_traces(self):
        from .telemetry import discover_trace
        with self.lock:
            if time.monotonic()-self._last_trace_sync<5:return
            self._last_trace_sync=time.monotonic()
            for run in self.db.list('run'):
                changed=False
                for trial in run['trials']:
                    if trial['state'] in {'checking','judging'}:continue
                    before=copy.deepcopy(trial)
                    try:
                        usage,message=discover_trace(codex_home(),trial['workspacePath'],trial.get('sessionId'))
                        if usage:
                            old=trial.get('usage') or {}
                            if any(old.get(k) is not None and (usage.get(k) is None or usage[k]<old[k]) for k in ['inputTokens','outputTokens','cacheReadTokens']):
                                raise ValueError('日志累计值回退，保留上次有效用量。')
                            trial['usage']=usage;trial['sessionId']=usage['sessionId']
                            new_turn=usage.get('lastStartedAt') and usage['lastStartedAt']>trial.get('continueRequestedAt','')
                            if trial['state'] in {'prepared','waiting_confirmation'} and new_turn:
                                trial['state']='working';trial['startedAt']=usage['lastStartedAt']
                            config=next(c for c in run['configs'] if c['id']==trial['configId'])
                            trial['observations']=[m for m in trial['observations'] if not m.startswith('日志：')]
                            if usage['models']!=[config['baseModel']] or usage['reasoningLevels']!=[config['reasoning']]:
                                trial['observations'].append('日志：实际模型或推理档位不同/未完整记录；不能视为条件一致。')
                        trial['telemetryStatus']=message
                    except (OSError,ValueError,KeyError,TypeError) as exc:
                        trial['telemetryStatus']=str(exc) if isinstance(exc,ValueError) and any('\u4e00'<=c<='\u9fff' for c in str(exc)) else '本题日志暂不可读，保留上次记录。'
                    except Exception:
                        trial['telemetryStatus']='本机会话索引暂不可读，可手动导入日志。'
                    changed=changed or before!=trial
                if changed:self.db.save('run',run,run['revision'])

    def event(self,run,message,trial=None):
        run.setdefault('events',[]).append({'at':now(),'message':message,'trialId':trial})

    def host_fingerprint(self):
        home=codex_home()
        return {name:hash_bytes((home/name).read_bytes()) if (home/name).is_file() else None
                for name in ['AGENTS.md','AGENTS.override.md','config.toml']}

    def prepare(self,data):
        delivery_mode=data.get('deliveryMode','single-delivery')
        if delivery_mode not in {'single-delivery','staged'}:raise ValueError('交付方式无效。')
        ids=data.get('configIds',[]); tasks=data.get('taskIds',[])
        if not isinstance(ids,list) or not 1<=len(ids)<=2 or len(set(ids))!=len(ids): raise ValueError('选择一套配置；需要对比时可选两套不同配置。')
        if not isinstance(tasks,list) or not 1<=len(tasks)<=10 or len(set(tasks))!=len(tasks): raise ValueError('选择 1–10 道题，批量选择不代表自动启动。')
        configs=[self.db.get('config',identifier(x)) for x in ids]
        for config in configs:validate_effort(config['baseModel'],config['reasoning'])
        selected=[self.db.get('task',identifier(x)) for x in tasks]
        if any(t['taskParadigm']=='deterministic-bugfix' and not t.get('baselineId') for t in selected):
            raise ValueError('Bug 修复题尚未准备项目源码。请在题库导入起始项目后再开始；参考链接不等于已下载环境。')
        if any(x.get('archived') for x in configs+selected): raise ValueError('归档配置或题目不可创建新评测。')
        request_id=identifier(data.get('requestId'))
        existing=[r for r in self.db.list('run')+self.db.list('run',True) if r.get('requestId')==request_id]
        if existing:
            if existing[0].get('requestFingerprint')!=fingerprint(data):raise ValueError('同一请求编号的内容已改变，请重新创建。')
            return self.present_run(existing[0])
        overrides=data.get('configOverrides',[])
        if not isinstance(overrides,list) or len(overrides)>len(configs):raise ValueError('本次配置调整无效。')
        seen=set()
        for override in overrides:
            if not isinstance(override,dict) or set(override)-{'configId','revision','skills','skillMode'}:
                raise ValueError('本次只允许调整技能与调用方式。')
            cid=identifier(override.get('configId'))
            if cid not in ids or cid in seen:raise ValueError('本次配置调整不属于所选配置或重复。')
            seen.add(cid)
            config=next(c for c in configs if c['id']==cid)
            if override.get('revision')!=config['revision']:raise ValueError('配置版本已变化，请刷新并重新核对本次选择。')
            skills=override.get('skills',config['skills']);mode=override.get('skillMode',config.get('skillMode','auto'))
            if not isinstance(skills,list) or len(skills)>30 or not all(isinstance(s,str) for s in skills) or len(set(skills))!=len(skills):
                raise ValueError('本次技能列表无效，最多选择30个。')
            names=[self.db.get('skill',identifier(s))['name'].casefold() for s in skills]
            if len(set(names))!=len(names):raise ValueError('本次技能同名，请只保留一个来源。')
            if mode not in {'auto','explicit'}:raise ValueError('技能调用方式无效。')
            if skills!=config['skills'] or mode!=config.get('skillMode','auto'):
                config['preparationOverride']={'sourceRevision':config['revision'],'sourceSkills':config['skills'],
                                               'sourceSkillMode':config.get('skillMode','auto')}
                config.update(skills=skills,skillMode=mode)
        scoring_policy=policy(data.get('policy'))
        selected=[{**freeze_prompts(delivery_task(t,delivery_mode)), 'sourceSchemaVersion':t.get('schemaVersion',1)} for t in selected]
        if scoring_policy.get('dimensionUnit')=='percent' and scoring_policy['objectiveWeight'] and any(not t['checks'] for t in selected):
            raise ValueError('所选题目没有自动检查，请选择纯人工方案，或先在题库配置检查。')
        if scoring_policy['humanWeight'] and any(not t.get('hasFrontendUI') for t in selected):
            if not sum(v for k,v in scoring_policy['dimensions'].items() if k!='ux'):
                raise ValueError('非界面题至少需要一个非视觉维度的权重大于零。')
        # Reject an ambiguous baseline/selected skill collision before creating any workspace.
        for task in selected:
            if not task.get('baselineId'):continue
            baseline=self.db.get('baseline',identifier(task['baselineId']))
            existing={name.split('/')[2].casefold() for name in baseline['manifest']['files']
                      if name.startswith('.agents/skills/') and len(name.split('/'))>3}
            for config in configs:
                if any(self.db.get('skill',sid)['name'].casefold() in existing for sid in config['skills']):
                    raise ValueError('题目起点已有同名技能，请取消重复选择或调整起点后重试。')
        rid='run-'+uuid.uuid4().hex[:16]
        directory=self.local/'runs'/rid
        directory.mkdir(parents=True)
        run={'id':rid,'requestId':request_id,'requestFingerprint':fingerprint(data),'createdAt':now(),'executionMode':'desktop','policy':scoring_policy,
             'configs':configs,'tasks':selected,'trials':[],'events':[], 'hostFingerprint':self.host_fingerprint(),
             'harnessApplication':'workspace-overlay','comparisonWarnings':[], 'notes':text(data.get('notes',''),10000,False)}
        if len(configs)==2 and (configs[0]['baseModel'],configs[0]['reasoning'])!=(configs[1]['baseModel'],configs[1]['reasoning']):
            run['comparisonWarnings'].append('模型或推理档位不同，不能把差异归因于 Harness。')
        for task in selected:
            for config in configs:
                tid='trial-'+uuid.uuid4().hex[:12]
                trialdir=directory/tid
                workspace=trialdir/'workspace'
                workspace.mkdir(parents=True)
                baseline_id=task.get('baselineId')
                if baseline_id:
                    baseline=self.db.get('baseline',identifier(baseline_id))
                    source=self.local/'baselines'/baseline_id/'files'
                    verify_snapshot(source,baseline['manifest'])
                    for name,body in inventory(source)[0].items():
                        dest=safe_path(workspace,name);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(body)
                original_file=workspace/('AGENTS.override.md' if (workspace/'AGENTS.override.md').exists() else 'AGENTS.md')
                original=original_file.read_text(encoding='utf-8') if original_file.exists() else ''
                instructions=original+'\n\n'+config['agentsPrompt']
                active=[c for c in config.get('customConstraints',[]) if c.get('isActive')]
                if active:instructions+='\n\n'+ '\n'.join(c['title']+': '+c.get('ruleDesc','') for c in active)
                if config['interactiveMode']=='step-by-step-confirm':instructions+='\n每个实施阶段结束后先给出结果并等待用户确认，不自动继续下一阶段。\n'
                if config['interactiveMode']=='one-shot-direct':instructions+='\n根据给定需求完成可交付结果；有必要信息缺口时明确提出，不擅自编造。\n'
                (workspace/'AGENTS.override.md').write_text(instructions,encoding='utf-8')
                native_path=safe_path(workspace,'.codex/config.toml')
                native_bytes=project_settings(config,native_path.read_bytes() if native_path.is_file() else b'')
                native_path.parent.mkdir(parents=True,exist_ok=True);native_path.write_bytes(native_bytes)
                skills=[]
                for sid in config.get('skills',[]):
                    skill=self.db.get('skill',sid);src=self.local/'skills'/sid/'files'
                    verify_snapshot(src,skill['manifest'])
                    snapshot(src,workspace/'.agents/skills'/skill['name']);skills.append(skill)
                skill_text=invocation(skills,config.get('skillMode','auto'))
                prompts=[]
                for index in range(len(task['stages'])):
                    base=stage_prompt(task,index)
                    content=base['text']+('\n\n'+skill_text if skill_text else '')
                    prompts.append({'text':content,'sha256':hash_bytes(content.encode()),
                                    'source':'frozen-trial-v3','stageId':task['stages'][index].get('id')})
                # A separate repository marks the instruction-discovery boundary.
                init=shell(['git','init','--quiet',str(workspace)])
                if init.returncode:raise ValueError('无法创建独立题目 Git 工作区。')
                manifest=snapshot(workspace,trialdir/'baseline')
                trial={'id':tid,'taskId':task['id'],'configId':config['id'],'state':'prepared','stageIndex':0,
                       'workspacePath':str(workspace),'baseline':manifest,'captures':[],'reviews':[], 'skills':skills,
                       'executionPrompts':prompts,'skillMode':config.get('skillMode','auto'),
                       'preparedAt':now(),'harnessHash':manifest['files']['AGENTS.override.md'],'sessionId':None,'usage':None,'observations':[]}
                run['trials'].append(trial)
        self.event(run,'独立工作区已创建。尚未启动 Codex 或产生模型用量。')
        return self.present_run(self.db.save('run',run))

    def present_run(self,run):
        run=copy.deepcopy(run)
        for t in run['trials']:
            t['score']=calculate(run,t)
            task=next(x for x in run['tasks'] if x['id']==t['taskId'])
            prompt=t['executionPrompts'][t['stageIndex']] if t.get('executionPrompts') else stage_prompt(task,t['stageIndex'])
            t['currentStage']={**task['stages'][t['stageIndex']], 'executionPrompt':prompt['text'],
                               'promptSha256':prompt['sha256'],'promptSource':prompt['source']}
        run['state']='completed' if all(t['state']=='completed' for t in run['trials']) else 'active'
        return run

    def trial(self,rid,tid):
        run=self.db.get('run',identifier(rid))
        if run.get('archived'):raise ValueError('归档评测只读，请先恢复记录。')
        trial=next((t for t in run['trials'] if t['id']==identifier(tid)),None)
        if not trial:raise ValueError('运行项不存在。')
        return run,trial

    def mutate(self,rid,tid,action,data):
        with self.lock:
            run,t=self.trial(rid,tid)
            task=next(x for x in run['tasks'] if x['id']==t['taskId'])
            config=next(x for x in run['configs'] if x['id']==t['configId'])
            folder=self.local/'runs'/rid/tid
            workspace=folder/'workspace'
            if action=='start':
                if t['state'] not in {'prepared','waiting_confirmation'}:raise ValueError('该轮已开始或需要先完成当前步骤。')
                if not data.get('settingsConfirmed'):raise ValueError('请先核对桌面中的模型、推理档位和工作区。')
                t.update(state='working',startedAt=now())
                self.event(run,'用户确认桌面设置，开始记录本轮。工作台不会自动发送提示词。',tid)
            elif action=='open':
                if data.get('draft'):
                    if t['stageIndex']!=0:raise ValueError('后续轮次请继续原对话，不新建任务。')
                    prompt=t['executionPrompts'][0] if t.get('executionPrompts') else stage_prompt(task,0)
                    url='codex://threads/new?'+urlencode({'path':str(workspace.resolve()),'prompt':prompt['text']},quote_via=quote)
                    if os.name!='nt':raise ValueError('当前只支持 Windows 打开对话草稿；请使用打开目录与复制提示词。')
                    try:os.startfile(url)
                    except OSError as exc:raise ValueError('无法打开 Codex 对话草稿；请打开目录并复制本轮提示词。') from exc
                    self.event(run,'已请求 Codex 新对话并预填本轮提示词；需在桌面确认工作区并发送，尚未开始计时。',tid)
                else:
                    if not shutil.which('codex'):raise ValueError('本机找不到 codex 命令。可复制工作区路径到桌面打开。')
                    result=shell(['codex','app',str(workspace)],timeout=15)
                    if result.returncode:raise ValueError('无法自动打开桌面；请复制工作区路径到 Codex 桌面打开。')
                    self.event(run,'已请求打开 Codex 桌面工作区；未据此推断任务已开始。',tid)
            elif action=='capture':
                if t['state'] not in {'working','prepared','waiting_confirmation','captured','completed','interrupted'}:raise ValueError('检查运行中，请等待或停止后台检查。')
                cid='capture-'+uuid.uuid4().hex[:12]
                verify_snapshot(folder/'baseline',t['baseline'])
                dest=folder/'captures'/cid/'files'
                manifest=snapshot(workspace,dest)
                changes=diff_facts(folder/'baseline',dest)
                capture={'id':cid,'stageIndex':t['stageIndex'],'at':now(),'manifest':manifest,'facts':changes,
                         'response':text(data.get('response',''),60000,False),'checks':[],
                         'checksConfigured':len(applicable_checks(task,t['stageIndex'])),
                         'harnessUnchanged':harness_files(manifest)==harness_files(t['baseline']),'hostUnchanged':self.host_fingerprint()==t.get('appliedHostFingerprint',run['hostFingerprint'])}
                t['captures'].append(capture);t['state']='captured'
                t.pop('finalCaptureId',None)
                self.event(run,'产物已封存，包括新增/删除文件；之后修改工作区不会改写这份证据。',tid)
            elif action=='trace':
                from .telemetry import read_trace
                raw=data.get('raw')
                usage=read_trace(raw,workspace,t.get('sessionId'))
                for k in ['inputTokens','outputTokens','cacheReadTokens']:
                    old=(t.get('usage') or {}).get(k)
                    if old is not None and (usage[k] is None or usage[k]<old):raise ValueError('导入日志比已保存的累计用量更早或不完整。')
                trace_id='trace-'+uuid.uuid4().hex[:12]
                trace_dir=folder/'traces';trace_dir.mkdir(exist_ok=True)
                (trace_dir/(trace_id+'.jsonl')).write_text(raw,encoding='utf-8')
                t['sessionId']=usage['sessionId'];t['usage']=usage
                t.setdefault('traceReceipts',[]).append({'id':trace_id,'sha256':hash_bytes(raw.encode()),'at':now(),'usage':usage})
                t['observations']=[m for m in t['observations'] if not m.startswith('日志：')]
                if usage['models']!=[config['baseModel']] or usage['reasoningLevels']!=[config['reasoning']]:
                    t['observations'].append('日志：实际模型或推理档位不同/未完整记录；不能视为条件一致。')
                self.event(run,'原生日志已绑定到此工作区和会话；原文只保存在本地。',tid)
            elif action=='continue':
                if t.get('finalCaptureId'):raise ValueError('已标记整题交付；后续修改可继续原对话并再次回收。')
                if t['state'] not in {'captured','completed'} or not t['captures'] or t['captures'][-1]['stageIndex']!=t['stageIndex']:raise ValueError('请先回收当前轮产物，再确认下一轮。')
                if t['stageIndex']+1>=len(task['stages']):raise ValueError('已经是最后一个预定阶段；追加需求请另建题目版本。')
                t['stageIndex']+=1;t['state']='waiting_confirmation';t['continueRequestedAt']=now()
                self.event(run,'用户确认进入下一轮。请在同一桌面任务发送本轮提示词。',tid)
            elif action=='complete':
                if t['state']!='captured' or not t['captures']:raise ValueError('请先回收需要评估的产物。')
                if t['stageIndex']+1<len(task['stages']) and run['policy']['version']!='arena-machine-v1':
                    raise ValueError('旧版脚本计分记录保留原阶段规则；请新建机器评分评测。')
                t['finalCaptureId']=t['captures'][-1]['id']
                t['state']='completed';t['completedAt']=now()
                self.event(run,'用户标记当前产物为整题交付；后续按完整需求评分，既有阶段检查保留在历史中。',tid)
            elif action=='interrupt':
                if t['state'] in {'checking','judging'}:
                    raise ValueError('请用停止检查按钮终止本工具拥有的后台进程。')
                t['state']='interrupted';t['interruption']={'reason':text(data.get('reason'),3000),'at':now()}
                self.event(run,'已记录外部执行中断；本按钮不会终止桌面 Codex，请在桌面停止任务。',tid)
            elif action=='objective-review':
                from .scoring import number
                if t['state'] not in {'captured','completed','interrupted'} or not t['captures']:raise ValueError('请在回收并结束后台检查后裁定。')
                capture=t['captures'][-1];score=calculate(run,t)
                if data.get('captureId')!=capture['id'] or data.get('evidenceKey')!=score['objectiveEvidenceKey']:raise ValueError('检查证据已变化，请刷新后重新裁定。')
                if score['objective'] is None:raise ValueError('自动检查尚无完整原分，不能用人工裁定补成已验证。')
                for c in t['captures']:
                    verify_snapshot(folder/'captures'/c['id']/'files',c['manifest'])
                entry={'id':'decision-'+uuid.uuid4().hex[:12],'at':now(),'captureId':capture['id'],'evidenceKey':score['objectiveEvidenceKey'],
                       'score':number(data['score']) if data.get('score') is not None else None,
                       'reason':text(data.get('reason'),3000),'evidence':text(data.get('evidence'),5000),
                       'originalScore':score['objective']}
                t.setdefault('objectiveReviews',[]).append(entry)
                self.event(run,'人工裁定另存；自动原分与必要项结论保持原始证据。',tid)
            elif action=='machine-correction':
                from .machine import validate_correction
                if run['policy']['version']!='arena-machine-v1' or t['state'] not in {'captured','completed','interrupted'}:
                    raise ValueError('请先结束机器评分，再修正本次结果。')
                score=calculate(run,t)
                changes=validate_correction(data,score)
                capture=t['captures'][-1]
                verify_snapshot(folder/'captures'/capture['id']/'files',capture['manifest'])
                t.setdefault('machineCorrections',[]).append({'id':'correction-'+uuid.uuid4().hex[:12],'at':now(),
                    'captureId':capture['id'],'reviewId':score['machineReviewId'],'evidenceKey':score['machineEvidenceKey'],'changes':changes})
                self.event(run,'人工修正已保存；机器原分和执行证据保留。',tid)
            elif action=='review':
                if not t['captures']:raise ValueError('先回收产物，再提交评分。')
                if data.get('captureId')!=t['captures'][-1]['id']:raise ValueError('评分对象已变化，请刷新后复审最新快照。')
                capture=t['captures'][-1]
                verify_snapshot(folder/'captures'/capture['id']/'files',capture['manifest'])
                review=validate_review(data,task,config.get('customConstraints',[]),capture,run['policy'])
                if task.get('schemaVersion')==2 and any(r['kind']=='human' and r['captureId']==capture['id'] for r in t['reviews']) and not review['revisionReason'].strip():
                    raise ValueError('修改已有复审时，请填写本次修订原因。')
                review.update(id='review-'+uuid.uuid4().hex[:12],kind='human',at=now(),captureId=data['captureId'])
                t['reviews'].append(review)
                self.event(run,'人工评分已作为独立版本保存；自动化结果没有被覆盖。',tid)
            else:raise ValueError('未知的运行操作。')
            return self.present_run(self.db.save('run',run,run['revision']))

    def import_files(self,kind,data):
        selected=Path(text(data.get('path'),1000)).expanduser().absolute()
        if any(p.is_symlink() or p.is_junction() for p in [selected,*selected.parents]):raise ValueError('来源路径不能经过符号链接或目录联接。')
        source=selected.resolve()
        if source==Path(source.anchor) or source in {Path.home(),self.root}:
            raise ValueError('请选择具体技能或题目起点目录，不能选择用户目录或项目根。')
        imported_id=('skill-' if kind=='skill' else 'baseline-')+uuid.uuid4().hex[:12]
        name=text(data.get('name') or source.name,80)
        if kind=='skill' and (not re.fullmatch(r'[a-zA-Z0-9_-]+',name) or not (source/'SKILL.md').is_file()):raise ValueError('技能名只用字母数字连字符，来源需含 SKILL.md。')
        destination=self.local/('skills' if kind=='skill' else 'baselines')/imported_id/'files'
        manifest=snapshot(source,destination)
        if kind=='skill' and manifest['excluded']:raise ValueError('技能包含凭据文件，未加入可选择列表。')
        return self.db.save(kind,{'id':imported_id,'name':name,'sourcePath':str(source),'manifest':manifest,'createdAt':now()})

    def restore_config(self,rid,cid):
        run=self.db.get('run',identifier(rid))
        old=next((c for c in run['configs'] if c['id']==cid),None)
        if not old:raise ValueError('历史配置不存在。')
        value=copy.deepcopy(old);value.pop('revision',None);value['id']='cfg-'+uuid.uuid4().hex[:12];value['name']=old['name']+' · 历史副本'
        return self.save_config(value)
