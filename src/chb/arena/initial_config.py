"""One-time, local-only recovery snapshot; never include authentication files."""
import json
from .skills import codex_home
from .files import hash_bytes, now, safe_path

FILES=('config.toml','AGENTS.md','AGENTS.override.md')

def ensure(app):
    from .codex_apply import write_file
    home=codex_home().resolve();key=hash_bytes(str(home).encode())[:16]
    folder=app.local/'initial-config'/key;receipt=folder/'receipt.json'
    if receipt.exists():return json.loads(receipt.read_text(encoding='utf-8'))
    present={}
    for name in FILES:
        path=safe_path(home,name)
        if path.is_file():
            if path.stat().st_size>2_000_000:raise ValueError('初始配置文件超过备份上限，未覆盖任何设置。')
            present[name]=path.read_bytes()
    if not present:return {'status':'missing','note':'尚未发现本机配置；首次发现后自动保护。'}
    # A committed receipt is the boundary: an interrupted partial snapshot is never used.
    folder.mkdir(parents=True,exist_ok=True)
    for name,body in present.items():write_file(folder/name,body)
    value={'status':'saved','path':str(folder),'home':str(home),'at':now(),
           'files':{n:hash_bytes(present[n]) if n in present else None for n in FILES},
           'note':'启用初始配置保护时的原文件；老安装无法追溯此前已被外部改写的内容。认证、技能安装和其他配置档不在此备份范围。'}
    try:
        from .config_import import preview
        config=preview(app,{'scope':'global'});source=config.pop('importSource')
        config.update(id='initial-'+key,name='最初配置 · 自动保存')
        saved=app.save_config(config,import_source=source);value['configId']=saved['id']
    except (ValueError,OSError):
        value['note']+=' 配置库副本无法完整转换；原文件备份仍保留。'
    write_file(receipt,json.dumps(value,ensure_ascii=False,indent=2).encode())
    return value

def status(app):
    try:return ensure(app)
    except (OSError,ValueError):return {'status':'error','note':'初始配置保护失败；应用设置前必须先解决备份问题。'}

def restore(app,data):
    """Explicit exact restoration of the three protected files, with undo receipt."""
    import base64
    import uuid
    from .codex_apply import write_file,store,public,status as application_status
    if data.get('confirmation')!='恢复最初配置':raise ValueError('请输入“恢复最初配置”；将替换这三份当前文件，替换前另存备份。')
    saved=ensure(app)
    if saved['status']!='saved':raise ValueError('没有完整初始备份。')
    if app.jobs or any(t['state']=='working' for r in app.db.list('run') for t in r['trials']):raise ValueError('先停止并结束工作台执行，再恢复配置。')
    if any(r['status'] in {'applying','applied','restore_failed'} for r in application_status(app)['applications']):raise ValueError('请先撤销当前工作台配置应用，再恢复最初配置。')
    home=codex_home().resolve();folder=app.local/'initial-config'/hash_bytes(str(home).encode())[:16]
    if saved.get('home')!=str(home) or set(saved.get('files',{}))!=set(FILES):raise ValueError('初始配置备份范围不一致，未写入。')
    before={};targets={}
    for name,digest in saved['files'].items():
        target=safe_path(folder,name).read_bytes() if digest else None
        if target is not None and hash_bytes(target)!=digest:raise ValueError('初始备份校验失败，未写入。')
        path=safe_path(home,name);before[name]=path.read_bytes() if path.is_file() else None;targets[name]=target
    aid='apply-'+uuid.uuid4().hex
    receipt={'id':aid,'configId':saved.get('configId','initial'),'configName':'恢复最初配置','configRevision':1,'at':now(),
             'status':'applying','home':str(home),'message':'正在恢复原文件；替换前内容可撤销恢复。',
             'files':{n:{'before':base64.b64encode(before[n]).decode() if before[n] is not None else None,
                         'afterHash':hash_bytes(b) if b is not None else None,
                         'after':base64.b64encode(b).decode() if b is not None else None} for n,b in targets.items()}}
    destination=app.local/'codex-applications'/aid;store(destination,receipt)
    for name,body in targets.items():
        path=safe_path(home,name)
        if (path.read_bytes() if path.is_file() else None)!=before[name]:raise ValueError('恢复期间配置被修改，已停止；恢复前备份保留。')
        if body is None:path.unlink(missing_ok=True)
        else:write_file(path,body)
    receipt.update(status='applied',message='已恢复最初配置的三份原文件；需要撤回可使用“撤销上次应用”。新任务才读取新设置。')
    store(destination,receipt)
    return public(receipt)
