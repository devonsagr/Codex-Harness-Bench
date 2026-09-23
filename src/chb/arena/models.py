"""Read model capabilities from the active Codex home; never invent tiers."""
import json
from .skills import codex_home

EFFORTS={'none','minimal','low','medium','high','xhigh','max','ultra'}


def capabilities():
    from .review_connection import native_config
    doc={};provider='openai';custom=None
    try:
        from pathlib import Path
        doc=native_config();provider=doc.get('model_provider','openai')
        custom=doc.get('model_catalog_json')
        path=(Path(custom).expanduser() if Path(custom).is_absolute() else codex_home()/custom) if custom else codex_home()/'models_cache.json'
        if path.stat().st_size>5_000_000:return []
        document=json.loads(path.read_text(encoding='utf-8'))
        rows=document.get('models',[])
    except (OSError,ValueError,AttributeError,TypeError):rows=[]
    result=[]
    for row in rows if isinstance(rows,list) else []:
        if not isinstance(row,dict):continue
        name=row.get('slug') or row.get('id')
        if not isinstance(name,str) or not name:continue
        if provider!='openai' and not custom and name!=doc.get('model'):continue
        levels=row.get('supported_reasoning_levels',[])
        efforts=list(dict.fromkeys(r.get('effort') for r in levels if isinstance(r,dict) and isinstance(r.get('effort'),str) and r['effort'] in EFFORTS)) if isinstance(levels,list) else []
        result.append({'id':name,'name':row.get('display_name',name),'source':'当前提供商模型目录' if custom else '本机 Codex 模型缓存',
                       'reasoningLevels':efforts,'defaultReasoning':row.get('default_reasoning_level'),
                       'capabilitiesKnown':bool(efforts)})
    current=doc.get('model')
    if isinstance(current,str) and current and not any(m['id']==current for m in result):
        result.append({'id':current,'name':current,'source':'当前 Codex 配置，档位能力未知','reasoningLevels':[],'capabilitiesKnown':False})
    return result


def validate_effort(model,effort,require_known=False):
    if effort=='':return None  # No model-specific override; use native/default behavior.
    if not isinstance(effort,str) or effort not in EFFORTS:raise ValueError('推理档位无效。')
    entry=next((m for m in capabilities() if m['id']==model and m['capabilitiesKnown']),None)
    if entry and effort not in entry['reasoningLevels']:
        raise ValueError(f'{model} 不支持 {effort}；可用档位：'+ '、'.join(entry['reasoningLevels'])+'。未写入配置。')
    if require_known and not entry:
        raise ValueError('本机尚无该模型的档位能力记录。请先在 Codex 刷新模型列表，再应用；未写入配置。')
    return entry
