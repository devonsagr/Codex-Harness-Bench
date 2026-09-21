"""Bounded snapshots of explicitly selected directories; never traverse user homes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

IGNORED = {'.git', 'node_modules', '.venv', '__pycache__', '.pytest_cache', '.next', '.chb-cache'}
SECRET = re.compile(r'(^|/)(\.env(?:\..*)?|auth\.json|credentials(?:\.json)?|id_rsa|id_ed25519)$|\.(pem|key)$', re.I)


def now():
    return datetime.now(timezone.utc).isoformat()


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def fingerprint(data):
    return hash_bytes(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


def safe_path(base, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('路径必须为工作区中的相对路径。')
    path = base
    for part in relative.split('/'):
        if part in {'', '.', '..'}:
            raise ValueError('不允许越界路径。')
        path = path / part
        if path.is_symlink() or path.is_junction():
            raise ValueError('不支持链接或目录联接。')
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError('路径超出工作区。')
    return path


def inventory(source, max_bytes=50_000_000):
    """Do not follow links, include untracked/new files, explicitly omit credentials."""
    source = Path(source)
    if not source.is_dir() or source.is_symlink() or source.is_junction():
        raise ValueError('请选择真实存在的文件夹，不支持目录链接。')
    files, excluded, size = {}, [], 0
    stack = [source]
    while stack:
        directory = stack.pop()
        for p in sorted(directory.iterdir()):
            relative = p.relative_to(source).as_posix()
            if p.name in IGNORED:
                continue
            if p.is_symlink() or p.is_junction():
                raise ValueError('工作区存在链接，回收前请移除链接或改为真实副本。')
            if SECRET.search(relative):
                excluded.append(relative)
                continue
            if p.is_dir():
                stack.append(p)
            elif p.is_file():
                length = p.stat().st_size
                if length > 8_000_000 or size + length > max_bytes or len(files) >= 5000:
                    raise ValueError('文件或产物过大；单文件上限 8 MB，快照总上限 50 MB/5000 文件。')
                data = p.read_bytes()
                size += len(data)
                files[relative] = data
    return files, excluded


def snapshot(source, target):
    if target.exists():
        raise ValueError('快照已存在，不能覆盖。')
    files, excluded = inventory(source)
    target.mkdir(parents=True)
    hashes = {}
    for name, data in files.items():
        dest = safe_path(target, name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        hashes[name] = hash_bytes(data)
    after,_=inventory(source)
    if {name:hash_bytes(body) for name,body in after.items()}!=hashes:
        raise ValueError('回收时工作区仍在变化；请等待桌面停止写入，再重新回收。')
    return {'files': hashes, 'sha256': fingerprint(hashes), 'excluded': excluded, 'createdAt': now()}


def verify_snapshot(path, manifest):
    files, _ = inventory(path)
    if {n: hash_bytes(b) for n, b in files.items()} != manifest['files']:
        raise ValueError('已冻结的产物被改动，停止验收。请回到工作区另存新一轮快照。')


def diff_facts(before, after):
    import difflib
    left, _ = inventory(before)
    right, _ = inventory(after)
    changes, patches = [], []
    for name in sorted(left.keys() | right.keys()):
        if left.get(name) == right.get(name):
            continue
        row = {'path': name, 'status': 'added' if name not in left else 'deleted' if name not in right else 'modified'}
        try:
            a = left.get(name, b'').decode('utf-8').splitlines(keepends=True)
            b = right.get(name, b'').decode('utf-8').splitlines(keepends=True)
            diff = list(difflib.unified_diff(a, b, fromfile='before/'+name, tofile='after/'+name))
            row['linesAdded'] = sum(x.startswith('+') and not x.startswith('+++') for x in diff)
            row['linesRemoved'] = sum(x.startswith('-') and not x.startswith('---') for x in diff)
            patches.extend(diff)
        except UnicodeError:
            row.update(binary=True, linesAdded=None, linesRemoved=None)
        changes.append(row)
    patch = ''.join(patches)
    return {'changes': changes, 'diffPatch': patch[:200_000], 'diffTruncated': len(patch)>200_000,
            'note': '变更文件和行数仅为事实，不直接转换为质量或冗余扣分。'}
