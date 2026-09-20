"""Explicit public GitHub revision import; no git hooks, credentials or install scripts."""
import re
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

from .files import safe_path, IGNORED, SECRET


def unpack(archive,target):
    size=0;count=0;seen=set()
    with tarfile.open(archive,mode='r|gz') as tar:
        for entry in tar:
            count+=1
            if count>10000:raise ValueError('仓库条目过多，请导入较小的题目起点。')
            parts=entry.name.split('/')[1:]
            if not parts or not any(parts):continue
            relative='/'.join(parts).rstrip('/')
            dest=safe_path(target,relative)
            if entry.issym() or entry.islnk() or not (entry.isdir() or entry.isfile()):raise ValueError('仓库包含链接或特殊文件，不能作为题目起点。')
            if any(part in IGNORED for part in parts) or SECRET.search(relative):continue
            if relative=='.gitmodules':raise ValueError('此仓库使用子模块，请先在本机准备完整源码，再导入文件夹。')
            if entry.isdir():continue
            size+=entry.size
            if entry.size>8_000_000 or size>50_000_000 or len(seen)>=5000:raise ValueError('仓库超过起点快照上限（50 MB / 5000 文件）。')
            key=relative.casefold()
            if key in seen:raise ValueError('仓库文件名重复或大小写冲突。')
            seen.add(key);dest.parent.mkdir(parents=True,exist_ok=True)
            with tar.extractfile(entry) as file:dest.write_bytes(file.read())
    if not seen:raise ValueError('仓库没有可导入的源码。')


def import_repository(app,data):
    match=re.fullmatch(r'https://github\.com/([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?',str(data.get('url','')))
    commit=str(data.get('commit',''))
    if not match or match[2] in {'.','..'}:raise ValueError('请输入公开 GitHub 仓库地址，格式为 https://github.com/作者/仓库。')
    if not re.fullmatch(r'[0-9a-fA-F]{40}',commit):raise ValueError('请选择题目起始版本的完整 40 位 commit SHA，不能使用变化中的分支。')
    owner,repo=match.groups();commit=commit.lower();url=f'https://github.com/{owner}/{repo}'
    with tempfile.TemporaryDirectory(prefix='chb-source-') as temp:
        folder=Path(temp);archive=folder/'source.tar.gz';source=folder/'source';source.mkdir()
        request=Request(f'https://codeload.github.com/{owner}/{repo}/tar.gz/{commit}',headers={'User-Agent':'Codex-Harness-Bench'})
        try:
            deadline=time.monotonic()+90;size=0
            with urlopen(request,timeout=15) as response,archive.open('wb') as file:
                if not response.url.startswith('https://codeload.github.com/'):raise ValueError('下载被重定向到不支持的来源。')
                while chunk:=response.read(65536):
                    size+=len(chunk)
                    if size>50_000_000 or time.monotonic()>deadline:raise ValueError('源码下载超限或超时，请在本机准备后导入文件夹。')
                    file.write(chunk)
            unpack(archive,source)
        except (URLError,OSError,tarfile.TarError) as exc:
            raise ValueError('源码下载或解包失败；请核对公开仓库、起始提交和网络。没有创建可执行题目。') from exc
        with app.lock:
            result=app.import_files('baseline',{'path':str(source),'name':f'{repo[:50]} · {commit[:8]}'})
            result.update(sourcePath=url,sourceUrl=url,sourceCommit=commit,dependenciesReady=False)
            return app.db.save('baseline',result,result['revision'])
