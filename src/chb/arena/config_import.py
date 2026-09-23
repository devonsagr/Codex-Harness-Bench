"""Import supported settings as a copy; never write to the source environment."""
from pathlib import Path
import tomllib
from .files import hash_bytes, now, safe_path
from .skills import codex_home, checked_directory
from .codex_apply import OPTIONS


def preview(app,data):
    scope=data.get('scope','global')
    if scope not in {'global','project'}:raise ValueError('配置来源范围无效。')
    root=checked_directory(str(codex_home()) if scope=='global' else data.get('path'))
    files=[];rules='';native={}
    for name in ('AGENTS.override.md','AGENTS.md'):
        p=safe_path(root,name)
        if p.is_file():
            if p.stat().st_size>200_000:raise ValueError('规则文件超过 200 KB。')
            raw=p.read_bytes();rules=raw.decode('utf-8-sig')
            files.append({'path':str(p),'sha256':hash_bytes(raw),'kind':'rules'});break
    settings=safe_path(root,'config.toml' if scope=='global' else '.codex/config.toml')
    if settings.is_file():
        if settings.stat().st_size>200_000:raise ValueError('设置文件超过 200 KB。')
        raw=settings.read_bytes()
        try:native=tomllib.loads(raw.decode('utf-8-sig'))
        except (tomllib.TOMLDecodeError,UnicodeError) as exc:raise ValueError('设置文件格式无效，请修正后导入。') from exc
        files.append({'path':str(settings),'sha256':hash_bytes(raw),'kind':'settings'})
    if not files:raise ValueError('该来源没有规则或可读取的设置文件。')
    warnings=[]
    if not native.get('model'):warnings.append('来源未指定模型，暂用默认值；请在配置页与桌面核对。')
    if not native.get('model_reasoning_effort'):warnings.append('来源未指定推理档位；保留宿主默认，不添加档位覆盖。')
    return {'name':('全局规则' if scope=='global' else root.name)+' · 导入副本',
            'agentsPrompt':rules,'baseModel':native.get('model','gpt-6-astra'),
            'reasoning':native.get('model_reasoning_effort',''),'interactiveMode':'adaptive',
            'skills':[],'skillMode':'auto','customConstraints':[],
            'nativeSettings':{k:v for k,v in native.items() if k in OPTIONS and v in OPTIONS[k]},
            'integrations':{g:{k:v.get('enabled',True) for k,v in native.get(g,{}).items() if isinstance(v,dict) and type(v.get('enabled',True))==bool} for g in ['mcp_servers','plugins']},
            'tagline':'只导入规则、模型和推理档位；Skills 在面板选择。',
            'importSource':{'scope':scope,'root':str(root),'files':files,'at':now(),'warnings':warnings,
                            'note':'只读本层规则/设置与已配置工具开关，不是完整有效配置；未迁移认证、工具命令或插件安装文件。'}}


def commit(app,data):
    value=preview(app,data)
    source=value.pop('importSource')
    if 'expectedFiles' in data and source['files']!=data['expectedFiles']:
        raise ValueError('来源配置在预览后有变化，请重新读取。')
    if data.get('name'):value['name']=data['name']
    return app.save_config(value,import_source=source)
