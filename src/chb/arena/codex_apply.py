"""Explicit, reversible writes to the local Codex configuration. Never execute a task."""
import base64
import json
import os
from pathlib import Path
import uuid
import tomlkit
from .files import hash_bytes, inventory, now, safe_path, verify_snapshot
from .skills import codex_home, checked_directory, invocation
from .models import validate_effort

OPTIONS = {'web_search':['disabled','cached','live'],
           'model_verbosity':['low','medium','high'],
           'model_reasoning_summary':['auto','concise','detailed','none']}

def settings(value):
    if not isinstance(value,dict) or not set(value)<=set(OPTIONS):raise ValueError('不支持的 Codex 设置。')
    if any(v not in OPTIONS[k] for k,v in value.items()):raise ValueError('Codex 设置值无效。')
    return value

def connections(value):
    if not isinstance(value,dict) or not set(value)<={'mcp_servers','plugins'}:raise ValueError('工具配置无效。')
    for group,items in value.items():
        if not isinstance(items,dict) or len(items)>60:raise ValueError('工具配置过多。')
        if any(not isinstance(k,str) or not k or len(k)>200 or type(v)!=bool for k,v in items.items()):raise ValueError('工具启用状态无效。')
    return value

def native():
    home=checked_directory(str(codex_home()))
    path=safe_path(home,'config.toml')
    if path.exists() and path.stat().st_size>2_000_000:raise ValueError('本机配置文件过大。')
    raw=path.read_bytes() if path.exists() else b''
    try:doc=tomlkit.parse(raw.decode('utf-8-sig'))
    except Exception as exc:raise ValueError('本机 config.toml 无法解析；未修改文件。') from exc
    return home,doc,raw

def status(app):
    home,doc,_=native()
    rows={g:[{'id':k,'enabled':v.get('enabled',True)} for k,v in doc.get(g,{}).items() if isinstance(v,dict)] for g in ['mcp_servers','plugins']}
    folder=app.local/'codex-applications'
    receipts=[]
    for p in sorted(folder.glob('*/receipt.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        r=json.loads(p.read_text(encoding='utf-8'))
        if r['home']==str(home):
            item=public(r)
            if r['status'] in {'applying','applied','restore_failed'}:
                checks=[]
                for name,entry in r['files'].items():
                    try:
                        target=safe_path(home,name)
                        matches=target.is_file() and hash_bytes(target.read_bytes())==entry['afterHash']
                    except (OSError,ValueError):matches=False
                    checks.append({'path':name,'matches':matches})
                item['fileChecks']=checks
                item['filesMatch']=all(c['matches'] for c in checks)
                if not item['filesMatch']:
                    try:
                        restore_plan(app,r,home,True)
                        item['canPreserveChanges']=True
                    except (ValueError,OSError):item['canPreserveChanges']=False
            receipts.append(item)
    override=safe_path(home,'AGENTS.override.md')
    has_override=override.is_file() and bool(override.read_text(encoding='utf-8-sig').strip())
    return {'home':str(home),'instructionsFile':'AGENTS.override.md' if has_override else 'AGENTS.md',
            'settings':{k:doc[k] for k in OPTIONS if k in doc},'model':doc.get('model'),'reasoning':doc.get('model_reasoning_effort'),'connections':rows,'applications':[r for i,r in enumerate(receipts) if i<20 or r['status'] in {'applying','applied','restore_failed'}]}

def public(r):
    return {k:r[k] for k in ['id','configId','configName','configRevision','at','status','home','message']}

def write_file(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.chb-'+uuid.uuid4().hex+'.tmp')
    try:
        tmp.write_bytes(data);os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

def project_settings(config,raw=b''):
    try:doc=tomlkit.parse(raw.decode('utf-8-sig'))
    except Exception as exc:raise ValueError('题目起点的 .codex/config.toml 格式无效。') from exc
    doc['model']=config['baseModel'];doc['model_reasoning_effort']=config['reasoning']
    for key,value in settings(config.get('nativeSettings',{})).items():doc[key]=value
    for group,items in connections(config.get('integrations',{})).items():
        if not items:continue
        if group not in doc:doc[group]=tomlkit.table()
        for key,enabled in items.items():
            if key not in doc[group]:doc[group][key]=tomlkit.table()
            doc[group][key]['enabled']=enabled
    return tomlkit.dumps(doc).encode()

def store(folder,r):write_file(folder/'receipt.json',json.dumps(r,ensure_ascii=False,indent=2).encode())

def switch(app,data,frozen=None):
    from .service import identifier
    config=frozen or app.db.get('config',identifier(data.get('configId')))
    validate_effort(config['baseModel'],config['reasoning'],require_known=True)
    if config['revision']!=data.get('revision') or config.get('archived'):raise ValueError('配置版本已变化或已归档。')
    if app.jobs or any(t['state']=='working' for run in app.db.list('run') for t in run['trials']):raise ValueError('请先结束当前执行，再切换配置。')
    active=next((r for r in status(app)['applications'] if r['status'] in {'applying','applied','restore_failed'}),None)
    if active:restore(app,{'applicationId':active['id']})
    try:return apply(app,data,frozen=config)
    except Exception as exc:
        if active:raise ValueError('切换未完成：已撤销旧应用，新配置未成功应用；请检查冲突后重试。') from exc
        raise

def apply(app,data,frozen=None):
    from .service import identifier
    config=frozen or app.db.get('config',identifier(data.get('configId')))
    validate_effort(config['baseModel'],config['reasoning'],require_known=True)
    if config['revision']!=data.get('revision'):raise ValueError('配置版本已变化，请重新选用后应用。')
    if config.get('archived'):raise ValueError('归档配置不能应用。')
    if app.jobs or any(t['state']=='working' for run in app.db.list('run') for t in run['trials']):
        raise ValueError('工作台仍有执行或后台检查，请结束后再切换全局配置。')
    home,doc,raw=native()
    # A recoverable single application at a time avoids orphaned skills across switches.
    if any(r['status'] in {'applying','applied','restore_failed'} for r in status(app)['applications']):
        raise ValueError('请先撤销上次应用，再切换另一套配置，避免残留混入。')
    for group,items in config.get('integrations',{}).items():
        for key,enabled in items.items():
            if key not in doc.get(group,{}) or not isinstance(doc[group][key],dict):
                raise ValueError('所需 MCP 或插件尚未在本机配置，请先在 Codex 安装/连接。')
            doc[group][key]['enabled']=enabled
    doc['model']=config['baseModel'];doc['model_reasoning_effort']=config['reasoning']
    for key,value in settings(config.get('nativeSettings',{})).items():doc[key]=value
    changes={'config.toml':tomlkit.dumps(doc).encode()}
    skills=[app.db.get('skill',sid) for sid in config['skills']]
    instructions=config['agentsPrompt']
    for c in config.get('customConstraints',[]):
        if c.get('isActive'):instructions+='\n'+c['title']+': '+c.get('ruleDesc','')
    if config['interactiveMode']=='step-by-step-confirm':instructions+='\n每个实施阶段结束后等待用户确认。'
    if config['interactiveMode']=='one-shot-direct':instructions+='\n按当前需求完成可交付结果，信息缺口明确提出。'
    skill_text=invocation(skills,config.get('skillMode','auto')).replace('.agents/skills/',str(home/'skills').replace('\\','/')+'/')
    if skill_text:instructions+='\n\n'+skill_text.replace('已复制到本工作区','已应用到本机 Codex 技能目录')
    changes['AGENTS.override.md']=(instructions.strip()+'\n').encode()
    for skill in skills:
        source=app.local/'skills'/skill['id']/'files';verify_snapshot(source,skill['manifest'])
        destination=safe_path(home,'skills/'+skill['name'])
        files=inventory(source)[0]
        if destination.exists():
            if inventory(destination)[0]!=files:raise ValueError('本机已有同名但不同内容的技能：'+skill['name']+'。请先调整名称或来源。')
            continue
        for name,body in files.items():changes['skills/'+skill['name']+'/'+name]=body
    before={name:safe_path(home,name).read_bytes() if safe_path(home,name).is_file() else None for name in changes}
    aid='apply-'+uuid.uuid4().hex
    folder=app.local/'codex-applications'/aid;folder.mkdir(parents=True)
    r={'id':aid,'configId':config['id'],'configName':config['name'],'configRevision':config['revision'],'at':now(),
       'status':'applying','home':str(home),'message':'正在应用；异常中断可从备份撤销。',
       'files':{n:{'before':base64.b64encode(b).decode() if b is not None else None,'afterHash':hash_bytes(changes[n]),'after':base64.b64encode(changes[n]).decode() if n=='config.toml' else None} for n,b in before.items()}}
    store(folder,r)
    try:
        for name,body in changes.items():
            p=safe_path(home,name)
            if (p.read_bytes() if p.is_file() else None)!=before[name]:raise ValueError('应用期间来源发生变化，已停止。')
            write_file(p,body)
        if any(safe_path(home,n).read_bytes()!=body for n,body in changes.items()):raise ValueError('配置写入后核对失败。')
        r.update(status='applied',message='已写入 Codex 本机配置并核对文件。请新建任务；已有任务或项目覆盖值不保证改变，必要时重启 Codex。')
        store(folder,r)
    except Exception:
        try:restore(app,{'applicationId':aid})
        except Exception:pass
        raise
    return public(r)

def applied_toml(app,r,item):
    if item.get('after'):
        raw=base64.b64decode(item['after'])
    else:
        # Legacy receipts can only be reconstructed if the exact hash is proven.
        with app.db.connect() as db:
            row=db.execute("SELECT body FROM revisions WHERE kind='config' AND id=? AND revision=?",(r['configId'],r['configRevision'])).fetchone()
        if not row:raise ValueError('旧回执缺少应用版本，不能自动合并撤销。')
        config=json.loads(row['body'])
        before=base64.b64decode(item['before']) if item['before'] is not None else b''
        doc=tomlkit.parse(before.decode('utf-8-sig'))
        for group,items in config.get('integrations',{}).items():
            for key,enabled in items.items():doc[group][key]['enabled']=enabled
        doc['model']=config['baseModel'];doc['model_reasoning_effort']=config['reasoning']
        for key,value in config.get('nativeSettings',{}).items():doc[key]=value
        raw=tomlkit.dumps(doc).encode()
    if hash_bytes(raw)!=item['afterHash']:raise ValueError('不能核实原应用内容，请手动核对冲突文件。')
    return raw

def merge_restore(before,applied,current):
    try:
        old=tomlkit.parse((before or b'').decode('utf-8-sig'))
        after=tomlkit.parse(applied.decode('utf-8-sig'))
        live=tomlkit.parse(current.decode('utf-8-sig'))
    except Exception as exc:raise ValueError('配置无法解析，不能合并撤销。') from exc
    missing=object()
    def merge(b,a,c,path=''):
        for key in set(b)|set(a):
            bv=b.get(key,missing);av=a.get(key,missing);cv=c.get(key,missing)
            if bv==av:continue
            name=path+key
            if isinstance(av,dict) and (bv is missing or isinstance(bv,dict)) and isinstance(cv,dict):
                merge({} if bv is missing else bv,av,cv,name+'.')
                if bv is missing and not cv:del c[key]
            elif cv==bv:continue
            elif cv!=av:raise ValueError('本工具写入的设置也已改变：'+name+'；请先核对，未覆盖当前值。')
            elif bv is missing:del c[key]
            else:c[key]=bv
    merge(old,after,live)
    return tomlkit.dumps(live).encode()

def restore_plan(app,r,home,preserve=False):
    plan={}
    for name,item in r['files'].items():
        p=safe_path(home,name);current=p.read_bytes() if p.is_file() else None
        before=base64.b64decode(item['before']) if item['before'] is not None else None
        target=before
        if current!=before and (current is None or hash_bytes(current)!=item['afterHash']):
            if preserve and name=='config.toml' and current is not None:
                target=merge_restore(before,applied_toml(app,r,item),current)
            else:raise ValueError('应用后的文件已被其他操作修改：'+name+'；为保留你的修改，未执行撤销。')
        plan[name]=(current,target)
    return plan

def restore(app,data):
    from .service import identifier
    if app.jobs or any(t['state']=='working' for run in app.db.list('run') for t in run['trials']):
        raise ValueError('工作台仍有执行或后台检查，请结束后再撤销全局配置。')
    aid=identifier(data.get('applicationId'))
    folder=app.local/'codex-applications'/aid
    r=json.loads((folder/'receipt.json').read_text(encoding='utf-8'))
    home=checked_directory(r['home'])
    if home!=codex_home().resolve():raise ValueError('Codex 目录已改变，不能撤销其他环境的记录。')
    if r['status']=='restored':return public(r)
    plan=restore_plan(app,r,home,data.get('preserveUnrelated') is True)
    # Persist a retryable plan and recovery copy before touching any live file.
    if data.get('preserveUnrelated') is True:
        for name,(current,target) in plan.items():
            if target is not None:
                entry=r['files'][name]
                entry.setdefault('originalBefore',entry['before'])
                entry['before']=base64.b64encode(target).decode()
                entry['recoveryCopy']=base64.b64encode(current).decode() if current is not None else None
                if current is not None:entry['afterHash']=hash_bytes(current)
        store(folder,r)
    try:
        for name,(current,target) in reversed(list(plan.items())):
            p=safe_path(home,name)
            if (p.read_bytes() if p.is_file() else None)!=current:raise ValueError('撤销期间文件再次变化，已停止；请核对后重试。')
            if target is None:
                if p.is_file():p.unlink()
                parent=p.parent
                while parent!=home and parent.is_relative_to(home):
                    try:parent.rmdir()
                    except OSError:break
                    parent=parent.parent
            else:write_file(p,target)
        r.update(status='restored',message='已恢复应用前的文件；新建任务后使用恢复的配置。')
    except Exception:
        r.update(status='restore_failed',message='撤销中断；备份保留，可重试。');store(folder,r);raise
    store(folder,r)
    return public(r)
