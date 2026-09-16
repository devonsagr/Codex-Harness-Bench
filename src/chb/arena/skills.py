"""Read declared skill roots, then atomically freeze the selected versions."""
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid

import yaml

from .files import fingerprint, hash_bytes, inventory, now, safe_path, verify_snapshot


def codex_home():
    return Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex').expanduser().absolute()


def checked_directory(value):
    if not isinstance(value, str) or not value.strip() or len(value)>1000:
        raise ValueError('请选择具体来源目录。')
    path=Path(value).expanduser().absolute()
    if any(p.is_symlink() or p.is_junction() for p in [path,*path.parents]):
        raise ValueError('来源路径不能经过链接或目录联接。')
    if not path.is_dir() or path==Path(path.anchor) or path==Path.home():
        raise ValueError('请选择具体项目或技能库，不能选择整盘或用户主目录。')
    return path.resolve()


def metadata(files):
    body=files.get('SKILL.md',b'')
    if len(body)>200_000:
        raise ValueError('技能说明超过 200 KB。')
    raw=body.decode('utf-8-sig')
    match=re.match(r'^---\s*\r?\n(.*?)\r?\n---(?:\s|$)',raw,re.S)
    if not match:
        raise ValueError('SKILL.md 缺少 name 和 description 元数据。')
    try: data=yaml.safe_load(match[1])
    except yaml.YAMLError as exc: raise ValueError('技能元数据格式无效。') from exc
    if not isinstance(data,dict) or not isinstance(data.get('name'),str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}',data['name']):
        raise ValueError('技能 name 需为字母数字及连字符/下划线，最多 80 字符。')
    description=data.get('description')
    if not isinstance(description,str) or not description.strip() or len(description)>8000:
        raise ValueError('技能 description 为空或过长。')
    return {'name':data['name'],'description':description}


def roots(scope,path):
    if scope=='global':
        return [(Path.home()/'.agents/skills','用户级'),(codex_home()/'skills','Codex 本机兼容目录')]
    base=checked_directory(path)
    if scope=='project':
        return [(base/'.agents/skills','项目级'),(base/'.codex/skills','项目兼容目录')]
    if scope=='custom':return [(base,'指定技能库（含插件来源时仍需原插件依赖）')]
    raise ValueError('技能来源范围无效。')


def scan(app,data):
    scope=data.get('scope','global')
    sources=roots(scope,data.get('path'))
    candidates=[]; source_rows=[]; seen=set(); visited=0
    for root,label in sources:
        source_rows.append({'path':str(root),'label':label,'exists':root.is_dir()})
        if not root.exists():continue
        stack=[(checked_directory(str(root)),0)]
        while stack:
            directory,depth=stack.pop();visited+=1
            if visited>500:raise ValueError('技能库目录过多，请选择更具体的来源。')
            if directory.is_symlink() or directory.is_junction():continue
            if (directory/'SKILL.md').exists():
                key=str(directory.resolve()).casefold()
                if key in seen:continue
                seen.add(key)
                row={'id':fingerprint(key)[:24],'sourcePath':str(directory),'scope':scope,'sourceLabel':label,
                     'name':directory.name,'description':'','error':None,'warnings':[]}
                try:
                    checked_directory(str(directory))
                    files,excluded=inventory(directory)
                    if excluded:raise ValueError('目录含凭据文件，不能作为技能导入。')
                    row.update(metadata(files))
                    row.update(sha256=fingerprint({n:hash_bytes(b) for n,b in files.items()}),fileCount=len(files))
                    if 'agents/openai.yaml' in files:
                        row['warnings'].append('包含工具/调用设置；复制技能文件不会安装其外部工具或插件。')
                except (ValueError,OSError,UnicodeError):
                    row['error']='无法读取完整技能：请核对元数据、大小、凭据或链接。'
                candidates.append(row)
                if len(candidates)>200:raise ValueError('一次最多显示 200 个技能，请缩小来源范围。')
                continue
            if depth<4:
                stack.extend((p,depth+1) for p in sorted(directory.iterdir(),reverse=True)
                             if p.is_dir() and p.name not in {'.git','node_modules','.venv','__pycache__'})
    counts={r['name'].casefold():sum(x['name'].casefold()==r['name'].casefold() for x in candidates) for r in candidates}
    for r in candidates:r['duplicateName']=counts[r['name'].casefold()]>1
    token=uuid.uuid4().hex
    cache=getattr(app,'skill_scans',{})
    cache={k:v for k,v in cache.items() if v['expires']>time.monotonic()}
    if len(cache)>=8:cache.pop(next(iter(cache)))
    cache[token]={'expires':time.monotonic()+900,'rows':candidates}
    app.skill_scans=cache
    return {'scanId':token,'sources':source_rows,'candidates':candidates}


def import_selected(app,data):
    cached=getattr(app,'skill_scans',{}).get(data.get('scanId'))
    if not cached or cached['expires']<time.monotonic():raise ValueError('技能列表已过期，请重新扫描。')
    ids=data.get('candidateIds')
    if not isinstance(ids,list) or not 1<=len(ids)<=30 or not all(isinstance(x,str) for x in ids) or len(set(ids))!=len(ids):
        raise ValueError('请选择 1–30 个不同技能。')
    rows=[next((r for r in cached['rows'] if r['id']==key),None) for key in ids]
    if any(r is None or r['error'] for r in rows):raise ValueError('所选技能无效，请重新扫描。')
    if len({r['name'].casefold() for r in rows})!=len(rows):raise ValueError('同名技能请选择一个来源，不能同时装载。')
    pending=[]; result=[]; size=0
    for row in rows:
        source=checked_directory(row['sourcePath'])
        files,excluded=inventory(source)
        hashes={n:hash_bytes(b) for n,b in files.items()}
        if excluded or fingerprint(hashes)!=row['sha256']:raise ValueError('技能在扫描后有变化，请重新扫描再导入。')
        size+=sum(map(len,files.values()))
        if size>50_000_000:raise ValueError('本批技能超过 50 MB，请减少选择。')
        sid='skill-'+fingerprint([str(source),row['sha256']])[:24]
        body={k:row[k] for k in ['name','description','sourcePath','scope','sourceLabel','warnings']}
        body.update(id=sid,createdAt=now(),manifest={'files':hashes,'sha256':row['sha256'],'excluded':[],'createdAt':now()})
        existing=next((s for s in app.db.list('skill') if s['id']==sid),None)
        if existing:
            verify_snapshot(app.local/'skills'/sid/'files',existing['manifest']);result.append(existing)
        else:
            pending.append((body,files));result.append(body)
    created=[]
    try:
        for body,files in pending:
            parent=app.local/'skills'/body['id']
            parent.mkdir(parents=True,exist_ok=False);created.append(parent)
            dest=parent/'files';dest.mkdir()
            for name,value in files.items():
                p=safe_path(dest,name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value)
        with app.db.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for body,_ in pending:
                encoded=json.dumps(body,ensure_ascii=False)
                db.execute('INSERT INTO records(kind,id,revision,body) VALUES(?,?,1,?)',('skill',body['id'],encoded))
                db.execute('INSERT INTO revisions VALUES(?,?,1,?,?)',('skill',body['id'],encoded,now()))
    except Exception:
        for parent in created:
            if parent.resolve().parent==(app.local/'skills').resolve() and not parent.is_symlink() and not parent.is_junction():
                shutil.rmtree(parent)
        raise
    return {'imported':[app.db.get('skill',r['id']) for r in result]}


def invocation(skills,mode):
    if not skills:return ''
    lines=['本次选定技能（已复制到本工作区）：']
    for skill in skills:
        lines.append(f"- {skill['name']}：.agents/skills/{skill['name']}/SKILL.md")
    lines.append('本轮明确请求使用上述技能，请读取对应 SKILL.md 并按其适用范围执行。' if mode=='explicit'
                 else '按当前任务与技能描述判断是否使用；需要时读取对应 SKILL.md，不为使用技能而增加无关工作。')
    return '\n'.join(lines)
