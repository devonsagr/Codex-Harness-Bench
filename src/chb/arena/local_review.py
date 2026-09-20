"""Fixed local Codex reviewer: separate copy, native sandbox, owned process lifetime."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager

from .skills import codex_home


@contextmanager
def review_workspace():
    # Python's private 0700 temp directories deny Windows restricted tokens even
    # after Codex grants its capability. A normal new project directory inherits
    # its parent's ACL; credentials remain in a separate private temp directory.
    parent=Path(tempfile.gettempdir()).resolve()
    root=parent/('chb-review-work-'+uuid.uuid4().hex)
    root.mkdir()
    try:yield root
    finally:
        if root.resolve().parent!=parent or root.is_symlink() or root.is_junction():
            raise ValueError('裁判临时目录路径已变化，未自动清理。')
        shutil.rmtree(root)


def output_schema(packet):
    def obj(properties):
        return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
    text={'type':'string'}
    refs={'type':'array','items':{'anyOf':[
        obj({'path':text,'line':{'type':'integer'},'quote':text}),
        obj({'command':text,'quote':text}),obj({'checkId':text,'quote':text})]}}
    result=obj({'summary':text,'findings':{'type':'array','items':obj({'path':text,'line':{'type':'integer'},'quote':text,'comment':text,'severity':text})}})
    if 'policy' in packet:
        from .machine import dimensions
        result['properties']['ratings']=obj({key:obj({'score':{'type':['number','null']},'method':{'type':'string','enum':['static','runtime','unverified']},'reason':text,'evidence':refs}) for key in dimensions(packet['policy'],packet['task'])})
        result['properties']['criteria']=obj({c['id']:obj({'status':{'type':'string','enum':['met','partial','unmet','unverified']},'notes':text,'evidence':refs}) for c in packet['task'].get('criteria',[])})
        result['required']=list(result['properties'])
    return result


def failure_reason(log):
    """Classify known errors without exposing arbitrary process output to UI."""
    raw=log.read_text(encoding='utf-8',errors='replace').lower()
    if any(word in raw for word in ['out of credits','usage_limit','insufficient_quota','quota_exhausted']):
        return '裁判模型额度不足，未生成新评分；已有产物和评分保留。'
    if any(word in raw for word in ['unauthorized','authentication','"status":401']):
        return '裁判模型认证失败，请检查本机 Codex CLI 登录。'
    return '本机裁判执行失败；请核对模型、网络或沙箱支持。诊断保留在本次 reviews 目录。'


class ProcessTree:
    """Kill only this review's descendants, including browser/server children."""
    def __init__(self,process):
        self.process=process;self.handle=None
        if os.name!='nt':return
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_=[('perProcess',ctypes.c_int64),('perJob',ctypes.c_int64),('flags',w.DWORD),('minWorking',ctypes.c_size_t),('maxWorking',ctypes.c_size_t),('active',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(ctypes.Structure):
            _fields_=[(name,ctypes.c_uint64) for name in ['readOps','writeOps','otherOps','readBytes','writeBytes','otherBytes']]
        class Extended(ctypes.Structure):
            _fields_=[('basic',Basic),('io',IO),('processMemory',ctypes.c_size_t),('jobMemory',ctypes.c_size_t),('peakProcess',ctypes.c_size_t),('peakJob',ctypes.c_size_t)]
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];self.kernel.CreateJobObjectW.restype=w.HANDLE
        self.kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
        self.kernel.CloseHandle.argtypes=[w.HANDLE]
        self.handle=self.kernel.CreateJobObjectW(None,None)
        info=Extended();info.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)) or not self.kernel.AssignProcessToJobObject(self.handle,int(process._handle)):
            if self.handle:self.kernel.CloseHandle(self.handle)
            self.handle=None;process.kill();process.wait(timeout=5)
            raise ValueError('无法建立本机裁判进程边界，已停止；没有关闭沙箱重试。')

    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None
        elif os.name!='nt':
            try:os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        if self.process.poll() is None:self.process.kill()
        self.process.wait(timeout=10)


def execute_local(folder,source,instruction,model,packet,control,timeout):
    executable=shutil.which('codex')
    if not executable:raise ValueError('本机未安装 Codex CLI。请安装并登录后使用本机裁判，或选择 Docker 裁判。')
    auth=codex_home()/'auth.json'
    if not auth.is_file():raise ValueError('本机裁判需要 Codex CLI 登录凭据，请先运行 codex login。')
    version=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).stdout.strip()
    log=folder/'events.jsonl'
    # A short scratch path also avoids native Windows shell path-length/cwd issues.
    with review_workspace() as work, tempfile.TemporaryDirectory(prefix='chb-review-home-') as temp_home:
        work=str(Path(work).resolve());temp_home=str(Path(temp_home).resolve())
        source=Path(work)/'task'
        shutil.copytree(folder/'task',source)
        schema=Path(work)/'output-schema.json';schema.write_text(json.dumps(output_schema(packet),ensure_ascii=False),encoding='utf-8')
        answer=Path(work)/'answer.json'
        shutil.copyfile(auth,Path(temp_home)/'auth.json')
        allowed={'path','systemroot','windir','comspec','pathext','temp','tmp','userprofile','home','localappdata','appdata','programfiles','programfiles(x86)','programdata','number_of_processors','os'}
        env={k:v for k,v in os.environ.items() if k.lower() in allowed}
        runtime_temp=source/'tmp';runtime_temp.mkdir()
        env.update(CODEX_HOME=temp_home,NO_COLOR='1',TEMP=str(runtime_temp),TMP=str(runtime_temp),TMPDIR=str(runtime_temp))
        # Do not inherit personal npm proxy, auth tokens or install hooks/config.
        npmrc=source/'.review-npmrc';npmrc.write_text('',encoding='utf-8')
        env.update(NPM_CONFIG_USERCONFIG=str(npmrc),NPM_CONFIG_GLOBALCONFIG=str(npmrc),NPM_CONFIG_CACHE=str(source/'npm-cache'))
        args=[executable,'exec','--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check','--json',
              '-C',str(source),'-s','workspace-write','-m',model,'-c','approval_policy="never"',
              '-c','project_doc_max_bytes=0','-c','model_reasoning_effort="low"','-c','web_search="disabled"',
              '-c','sandbox_workspace_write.exclude_tmpdir_env_var=true','-c','sandbox_workspace_write.exclude_slash_tmp=true',
              '-c','sandbox_workspace_write.network_access=true','--output-schema',str(schema),'-o',str(answer),'-']
        if os.name=='nt':args[2:2]=['-c','windows.sandbox="unelevated"']
        with (source/'instruction.md').open('rb') as stdin,log.open('wb') as stdout,(folder/'stderr.log').open('wb') as stderr:
            process=subprocess.Popen(args,stdin=stdin,stdout=stdout,stderr=stderr,env=env,cwd=source,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')
            tree=ProcessTree(process)
            try:
                deadline=time.monotonic()+timeout
                while process.poll() is None:
                    if control['stop'].wait(.2):raise ValueError('已取消本机机器评分。')
                    if time.monotonic()>deadline:raise ValueError('本机裁判超过时限；已停止本次进程，未生成评分。')
                if process.returncode:raise ValueError(failure_reason(log))
            finally:
                tree.close()
                if answer.is_file():shutil.copyfile(answer,folder/'answer.json')
                from .files import snapshot
                if (source/'artifacts').is_dir():snapshot(source/'artifacts',folder/'artifacts')
    answer=folder/'answer.json'
    if not answer.is_file():raise ValueError('本机裁判没有返回评分报告，执行日志已保留。')
    return log,answer.read_text(encoding='utf-8'),version
