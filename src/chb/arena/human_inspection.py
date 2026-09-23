"""Snapshot-bound human inspection; no arbitrary commands or host-file endpoint."""
import base64
import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from .files import safe_path,verify_snapshot,snapshot,hash_bytes,now
from .machine import dimensions
from .service import identifier


def context(app,rid,tid,data):
    run,trial=app.trial(rid,tid)
    cap=next((c for c in trial['captures'] if c['id']==data.get('captureId')),None)
    if not cap:raise ValueError('请选择已回收的产物版本。')
    root=safe_path(app.local,f'runs/{rid}/{tid}')
    source=safe_path(root,'captures/'+identifier(cap['id'])+'/files')
    task=next(t for t in run['tasks'] if t['id']==trial['taskId'])
    return run,trial,cap,root,source,task


def preview_url(value):
    if not value:return ''
    if not isinstance(value,str) or len(value)>2000:raise ValueError('预览地址无效。')
    url=urlsplit(value)
    try:port=url.port
    except ValueError:raise ValueError('预览端口无效。')
    if url.scheme!='http' or url.hostname not in {'127.0.0.1','localhost','::1'} or not port or port in {8765,8877} or url.username or url.password or url.query or url.fragment:
        raise ValueError('请填写独立项目的本机 HTTP 地址与端口，不含凭据或查询参数；不能使用工作台端口。')
    return value


def operate(app,rid,tid,action,data):
    with app.lock:
        run,trial,cap,root,source,task=context(app,rid,tid,data)
        if action=='inspection-status':
            files=sorted(cap['manifest']['files'])
            docs=[p for p in files if Path(p).name.lower().startswith(('readme','交付','运行'))]
            scripts={}
            if 'package.json' in files:
                path=safe_path(source,'package.json')
                if path.stat().st_size<200000:
                    raw=path.read_bytes()
                    if hash_bytes(raw)!=cap['manifest']['files']['package.json']:raise ValueError('快照文件已变化，不能据此审查。')
                    try:
                        value=json.loads(raw);scripts=value.get('scripts',{}) if isinstance(value,dict) else {}
                        if not isinstance(scripts,dict):scripts={}
                    except ValueError:pass
            return {'files':files,'documents':docs,'scripts':scripts,'captureHash':cap['manifest']['sha256'],
                    'inspections':[r for r in trial.get('humanInspections',[]) if r['captureId']==cap['id']],
                    'assessments':[r for r in trial.get('humanAssessments',[]) if r['captureId']==cap['id']]}
        if action=='inspection-file':
            name=data.get('path')
            if not isinstance(name,str) or name not in cap['manifest']['files']:raise ValueError('文件不在所选快照内。')
            path=safe_path(source,name)
            if path.stat().st_size>8_000_000:raise ValueError('文件过大，请导出查看。')
            raw=path.read_bytes()
            if hash_bytes(raw)!=cap['manifest']['files'][name]:raise ValueError('快照文件已变化，停止读取。')
            # Only inert raster formats are displayed as images; never serve HTML/SVG.
            mime='image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if raw.startswith(b'\xff\xd8\xff') else 'image/webp' if raw[:4]==b'RIFF' and raw[8:12]==b'WEBP' else None
            if mime:return {'path':name,'image':'data:'+mime+';base64,'+base64.b64encode(raw).decode()}
            return {'path':name,'text':raw[:200000].decode('utf-8',errors='replace'),'truncated':len(raw)>200000}
        if run.get('archived') or run.get('deletionPending'):raise ValueError('归档或正在删除的评测不能新增人工审查。')
        if action=='inspection-prepare':
            verify_snapshot(source,cap['manifest'])
            key='inspection-'+uuid.uuid4().hex[:12]
            destination=safe_path(root,'human-inspections/'+key+'/workspace')
            manifest=snapshot(source,destination)
            if manifest['sha256']!=cap['manifest']['sha256']:raise ValueError('人工审查副本与快照不一致。')
            row={'id':key,'captureId':cap['id'],'captureHash':manifest['sha256'],'path':str(destination),'at':now()}
            trial.setdefault('humanInspections',[]).append(row)
            (destination.parent/'receipt.json').write_text(json.dumps(row,ensure_ascii=False),encoding='utf-8')
            app.event(run,'已从回收快照创建人工审查副本；尚未执行项目代码。',tid)
        elif action=='inspection-open':
            entry=next((r for r in trial.get('humanInspections',[]) if r['id']==data.get('inspectionId') and r['captureId']==cap['id']),None)
            if not entry:raise ValueError('请先创建所选版本的审查副本。')
            destination=safe_path(root,'human-inspections/'+identifier(entry['id'])+'/workspace')
            if not destination.is_dir():raise ValueError('人工审查副本已不存在，请重新创建。')
            if os.name!='nt':raise ValueError('本系统请复制页面中的审查路径打开。')
            os.startfile(str(destination))
            return {'opened':True}
        elif action=='inspection-save':
            if data.get('reviewed') is not True:raise ValueError('请先查看产物并确认实际复核的版本。')
            verify_snapshot(source,cap['manifest'])
            weights=dimensions(run['policy'],task);ratings=data.get('ratings',{})
            if not isinstance(ratings,dict) or set(ratings)-set(weights):raise ValueError('人工评分维度无效。')
            values={}
            for key,row in ratings.items():
                if not isinstance(row,dict):raise ValueError('人工评分格式无效。')
                score=row.get('score');reason=row.get('reason','')
                if score is None:continue
                if type(score) not in {int,float} or not 0<=score<=100:raise ValueError('人工评分需为 0–100。')
                if not isinstance(reason,str) or not reason.strip() or len(reason)>8000:raise ValueError('每项人工分数须说明实际观察依据。')
                values[key]={'score':score,'reason':reason.strip()}
            if not values:raise ValueError('至少填写一项已复核的分数。')
            method=data.get('method')
            if method not in {'source','runtime','visual'}:raise ValueError('请选择实际复核方式。')
            if 'ux' in values and method!='visual':raise ValueError('交互与视觉评分须实际体验界面，请选择界面复核方式；仅阅读源码的项目请留空。')
            coverage=sum(weights[k] for k in values)/sum(weights.values())*100
            row={'id':'human-'+uuid.uuid4().hex[:12],'at':now(),'captureId':cap['id'],'captureHash':cap['manifest']['sha256'],
                 'method':method,'previewUrl':preview_url(data.get('previewUrl','')),'ratings':values,
                 'coverage':round(coverage,2),'score':round(sum(weights[k]*v['score'] for k,v in values.items())/sum(weights[k] for k in values),2)}
            trial.setdefault('humanAssessments',[]).append(row)
            app.event(run,'已保存独立人工参考评分；机器原分与程序验收未改写。',tid)
        else:raise ValueError('未知人工审查操作。')
        app.db.save('run',run,run['revision'])
        return row
