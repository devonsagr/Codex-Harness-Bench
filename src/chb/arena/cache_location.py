"""Explicit, verified relocation of the downloaded public task definitions."""
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path


LOCATION_FILE='public-sources-location.json'


def current_root(local):
    receipt=local/LOCATION_FILE
    if not receipt.exists():return local/'public-sources'
    value=json.loads(receipt.read_text(encoding='utf-8'))
    path=Path(value['path'])
    if not path.is_absolute() or str(path)!=str(path.resolve()):
        raise ValueError('题包缓存位置记录无效，请核对本机数据目录。')
    return path


def _reject_link_parents(path):
    for item in (path,*path.parents):
        if item.is_symlink() or item.is_junction():
            raise ValueError('目标路径包含链接或目录联接，请选择普通本机目录。')


def _contents(root):
    """Hash files without following links, including while copying between drives."""
    from .storage import reject_links
    if not root.exists():return {}
    reject_links(root)
    result={}
    for folder,dirs,files in os.walk(root,followlinks=False):
        dirs.sort();files.sort()
        for name in files:
            path=Path(folder)/name
            digest=hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
            result[path.relative_to(root).as_posix()]=(path.stat().st_size,digest.hexdigest())
    return result


def move_public_cache(app,data):
    from .public_sources import DOWNLOAD_LOCK
    from .storage import status
    value=data.get('destination')
    if not isinstance(value,str) or not value.strip() or len(value)>1000:
        raise ValueError('请输入题包缓存的完整目标路径。')
    destination=Path(value.strip())
    if not destination.is_absolute():raise ValueError('请输入绝对路径。')
    _reject_link_parents(destination)
    destination=destination.resolve()
    source=app.public_sources_root.resolve()
    local=app.local.resolve()
    if destination==source or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('目标不能与当前题包缓存重叠。')
    if destination.is_relative_to(local) or local.is_relative_to(destination):
        raise ValueError('请选择项目数据目录以外的独立目标文件夹。')
    if destination.exists():raise ValueError('目标文件夹已存在；请选择尚不存在的新文件夹，避免覆盖已有文件。')
    if data.get('confirmation')!='迁移题包缓存':raise ValueError('请确认迁移题包缓存。')
    with DOWNLOAD_LOCK,app.lock:
        if any(getattr(app,name,None) and getattr(app,name).is_alive() for name in ('preparation_thread','source_thread')):
            raise ValueError('题目准备或下载仍在运行，请完成后再迁移。')
        if destination.exists():raise ValueError('目标文件夹已出现，请重新选择。')
        if (app.local/LOCATION_FILE).exists() and not source.is_dir():
            raise ValueError('当前外置题包缓存不可用，请先恢复原磁盘位置后迁移。')
        original=_contents(source)
        destination.parent.mkdir(parents=True,exist_ok=True)
        try:
            if source.exists():shutil.copytree(source,destination,symlinks=False)
            else:destination.mkdir()
            if _contents(destination)!=original:raise ValueError('迁移校验失败，位置保持不变。')
            receipt=app.local/LOCATION_FILE
            temporary=app.local/(LOCATION_FILE+'.'+uuid.uuid4().hex+'.tmp')
            try:
                temporary.write_text(json.dumps({'path':str(destination)},ensure_ascii=False),encoding='utf-8')
                os.replace(temporary,receipt)
            finally:
                temporary.unlink(missing_ok=True)
            app.public_sources_root=destination
        except Exception:
            if destination.exists():shutil.rmtree(destination)
            raise
        leftover=None
        if source.exists():
            try:shutil.rmtree(source)
            except OSError:leftover=str(source)
        return {**status(app),'migration':{'files':len(original),'leftoverPath':leftover}}
