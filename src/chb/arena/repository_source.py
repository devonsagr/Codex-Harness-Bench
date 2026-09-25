"""Explicit public GitHub revision import; no git hooks, credentials or install scripts."""
import configparser
import json
import re
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import urlsplit

from .files import safe_path, IGNORED, SECRET


def unpack(archive,target, include=None, allow_gitmodules=False):
    size=0;count=0;seen=set()
    with tarfile.open(archive,mode='r|gz') as tar:
        for entry in tar:
            count+=1
            if count>10000:raise ValueError('仓库条目过多，请导入较小的题目起点。')
            parts=entry.name.split('/')[1:]
            if not parts or not any(parts):continue
            relative='/'.join(parts).rstrip('/')
            if include is not None and not include(relative):continue
            dest=safe_path(target,relative)
            if entry.issym() or entry.islnk() or not (entry.isdir() or entry.isfile()):raise ValueError('仓库包含链接或特殊文件，不能作为题目起点。')
            if any(part in IGNORED for part in parts) or SECRET.search(relative):continue
            if relative=='.gitmodules' and not allow_gitmodules:raise ValueError('嵌套子模块尚未支持，未创建不完整的源码起点。')
            if entry.isdir():continue
            size+=entry.size
            if entry.size>8_000_000 or size>50_000_000 or len(seen)>=5000:raise ValueError('仓库超过起点快照上限（50 MB / 5000 文件）。')
            key=relative.casefold()
            if key in seen:raise ValueError('仓库文件名重复或大小写冲突。')
            seen.add(key);dest.parent.mkdir(parents=True,exist_ok=True)
            with tar.extractfile(entry) as file:dest.write_bytes(file.read())
    if not seen:raise ValueError('仓库没有可导入的源码。')


def github_archive(owner,repo,commit,archive,budget,deadline):
    request=Request(f'https://codeload.github.com/{owner}/{repo}/tar.gz/{commit}',headers={'User-Agent':'Codex-Harness-Bench'})
    size=0
    with urlopen(request,timeout=15) as response,archive.open('wb') as file:
        location=urlsplit(response.url)
        if location.scheme!='https' or location.hostname!='codeload.github.com':raise ValueError('下载被重定向到不支持的来源。')
        while chunk:=response.read(65536):
            size+=len(chunk)
            if size>budget or time.monotonic()>deadline:raise ValueError('源码下载超限或超时，请缩小题目批次后重试。')
            file.write(chunk)
    return size


def pinned_submodules(source,owner,repo,commit):
    modules=source/'.gitmodules'
    if not modules.is_file():return []
    if modules.stat().st_size>16_384:raise ValueError('子模块清单过大，未创建源码起点。')
    parser=configparser.ConfigParser(interpolation=None)
    try:parser.read_string(modules.read_text(encoding='utf-8'))
    except (UnicodeError,configparser.Error) as exc:raise ValueError('子模块清单无法校验，未创建源码起点。') from exc
    declared={}
    for section in parser.sections():
        if not section.startswith('submodule '):raise ValueError('子模块清单格式无效。')
        path=parser.get(section,'path',fallback='')
        safe_path(source,path)
        match=re.fullmatch(r'https://github\.com/([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?',parser.get(section,'url',fallback=''))
        if not match or match[2] in {'.','..'}:raise ValueError('子模块不是公开 GitHub 仓库，不能自动准备完整源码。')
        if path in declared or path.casefold() in {name.casefold() for name in declared}:raise ValueError('子模块路径重复。')
        declared[path]=match.groups()
    if not declared or len(declared)>4:raise ValueError('子模块清单为空或超过数量上限。')
    request=Request(f'https://api.github.com/repos/{owner}/{repo}/git/trees/{commit}?recursive=1',headers={'User-Agent':'Codex-Harness-Bench','Accept':'application/vnd.github+json'})
    try:
        with urlopen(request,timeout=15) as response:
            location=urlsplit(response.url)
            if location.scheme!='https' or location.hostname!='api.github.com':raise ValueError('子模块版本查询被重定向。')
            payload=response.read(2_000_001)
        if len(payload)>2_000_000:raise ValueError('仓库文件树过大，无法核对子模块版本。')
        tree=json.loads(payload)
    except (URLError,OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise ValueError('无法读取固定子模块版本；请检查 GitHub 连接后重试。') from exc
    if tree.get('truncated'):raise ValueError('仓库文件树不完整，不能核对子模块版本。')
    pinned={item['path']:item['sha'] for item in tree.get('tree',[]) if item.get('mode')=='160000'}
    if pinned.keys()!=declared.keys() or any(not re.fullmatch(r'[0-9a-fA-F]{40}',sha) for sha in pinned.values()):
        raise ValueError('子模块清单与固定提交不一致，未创建不完整的源码起点。')
    return [{'path':path,'owner':pair[0],'repo':pair[1],'commit':pinned[path].lower()} for path,pair in declared.items()]


def import_repository(app,data):
    match=re.fullmatch(r'https://github\.com/([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?',str(data.get('url','')))
    commit=str(data.get('commit',''))
    if not match or match[2] in {'.','..'}:raise ValueError('请输入公开 GitHub 仓库地址，格式为 https://github.com/作者/仓库。')
    if not re.fullmatch(r'[0-9a-fA-F]{40}',commit):raise ValueError('请选择题目起始版本的完整 40 位 commit SHA，不能使用变化中的分支。')
    owner,repo=match.groups();commit=commit.lower();url=f'https://github.com/{owner}/{repo}'
    temp_root=app.local/'downloads';temp_root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='source-',dir=temp_root) as temp:
        folder=Path(temp);archive=folder/'source.tar.gz';source=folder/'source';source.mkdir()
        try:
            deadline=time.monotonic()+90
            used=github_archive(owner,repo,commit,archive,50_000_000,deadline)
            unpack(archive,source,allow_gitmodules=True)
            submodules=pinned_submodules(source,owner,repo,commit)
            for index,module in enumerate(submodules):
                target=safe_path(source,module['path'])
                if target.exists() and (not target.is_dir() or any(target.iterdir())):raise ValueError('子模块路径已有内容，未覆盖源码。')
                target.mkdir(parents=True,exist_ok=True)
                subarchive=folder/f'submodule-{index}.tar.gz'
                used+=github_archive(module['owner'],module['repo'],module['commit'],subarchive,50_000_000-used,deadline)
                unpack(subarchive,target)
        except (URLError,OSError,tarfile.TarError) as exc:
            raise ValueError('源码下载或解包失败；请核对公开仓库、起始提交和网络。没有创建可执行题目。') from exc
        with app.lock:
            result=app.import_files('baseline',{'path':str(source),'name':f'{repo[:50]} · {commit[:8]}'})
            result.update(sourcePath=url,sourceUrl=url,sourceCommit=commit,dependenciesReady=False,
                          submodules=[{'path':m['path'],'sourceUrl':f"https://github.com/{m['owner']}/{m['repo']}",'sourceCommit':m['commit']} for m in submodules])
            return app.db.save('baseline',result,result['revision'])
