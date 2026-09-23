"""Read only the active native model connection, without exposing credentials."""
import os
import re
import tomllib
from urllib.parse import urlsplit
from .skills import codex_home

def native_config():
    path=codex_home()/'config.toml'
    if not path.exists():return {}
    if path.stat().st_size>2_000_000:raise ValueError('Codex 配置过大，未读取连接。')
    try:doc=tomllib.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError,UnicodeError) as exc:raise ValueError('Codex 配置无法解析，未选择模型连接。') from exc
    profile=doc.get('profile')
    if profile:
        if not isinstance(profile,str) or not re.fullmatch(r'[\w-]+',profile):raise ValueError('Codex 配置档名称无效。')
        file=codex_home()/(profile+'.config.toml')
        if file.exists():
            if file.stat().st_size>2_000_000:raise ValueError('Codex 配置档过大。')
            doc={**doc,**tomllib.loads(file.read_text(encoding='utf-8-sig'))}
        else:doc={**doc,**doc.get('profiles',{}).get(profile,{})}
    return doc

def connection():
    doc=native_config();provider=doc.get('model_provider','openai')
    if not isinstance(provider,str) or not re.fullmatch(r'[\w-]+',provider):raise ValueError('模型提供商标识无效。')
    source=doc.get('model_providers',{}).get(provider,{})
    if not isinstance(source,dict):raise ValueError('模型提供商配置格式无效。')
    if source.get('query_params') and (not isinstance(source['query_params'],dict) or set(source['query_params'])-{'api-version'}):raise ValueError('模型连接含未支持的查询参数；认证请使用 env_key，未启动审查。')
    options={k:v for k,v in source.items() if k in {'name','base_url','wire_api','env_key','requires_openai_auth','query_params','request_max_retries','stream_max_retries','stream_idle_timeout_ms','supports_websockets'}}
    custom=provider!='openai' or bool(options.get('base_url'))
    endpoint=options.get('base_url') or 'https://api.openai.com/v1'
    url=urlsplit(endpoint)
    if url.scheme not in {'http','https'} or not url.hostname or url.username or url.password or url.query:raise ValueError('模型连接地址无效或在地址中包含凭据，未启动审查。')
    if custom and source.get('requires_openai_auth'):raise ValueError('自定义地址使用 OpenAI OAuth 的连接尚未验证；请使用提供商 API Key 连接，避免误用官方账号。')
    if custom and any(k in source for k in ['http_headers','env_http_headers','experimental_bearer_token']):raise ValueError('该提供商使用未支持的认证头；裁判当前支持 env_key 或 Codex API Key 登录，不会丢弃认证后重试。')
    key=options.get('env_key')
    if key and (not isinstance(key,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',key)):raise ValueError('提供商凭据环境变量名称无效。')
    return {'providerId':provider,'options':options,'custom':custom,'envKey':key,
            'public':{'provider':provider,'endpoint':url.scheme+'://'+url.netloc,
                'billing':'提供商 / 反代 API 计费（账户池分配由该服务决定）' if custom else '本机 Codex CLI 当前登录：ChatGPT 额度或 API Key 账单',
                'credentialSource':'指定环境变量' if key else '启动本次审查时的 Codex 登录凭据'}}

def public_connection():
    try:return connection()['public']
    except (OSError,ValueError,TypeError,AttributeError):return {'provider':'未就绪','billing':'模型连接尚不能用于裁判，请核对 Codex 配置。'}
