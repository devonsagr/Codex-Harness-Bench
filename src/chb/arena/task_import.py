"""Preview a versioned JSON task bundle; commit only validated new copies."""
import copy
import uuid

from .contracts import import_document
from .files import fingerprint, now
from .service import identifier


def preview(app, document):
    source=import_document(document)
    tasks, errors, warnings=[], [], []
    for index, original in enumerate(source):
        value=copy.deepcopy(original)
        origin={k:value[k] for k in ['id','revision'] if k in value}
        for key in ['id','revision','updatedAt','createdAt','archived','archiveEvents','importSource']:
            value.pop(key,None)
        try:
            normalized=app.validate_task(value)
            normalized['importSource']={'original':origin,'sha256':fingerprint(original)}
            tasks.append(normalized)
            if original.get('schemaVersion',1)!=2:
                warnings.append(f'第{index+1}题将转成版本2；旧细则转为验收观察项，必要项需在题库明确指定。')
            if not normalized['checks']:
                warnings.append(f'第{index+1}题没有可执行检查；题包导入不证明题目已验证。')
        except (ValueError,TypeError,KeyError) as exc:
            errors.append({'index':index+1,'message':str(exc)})
    return {'valid':not errors,'tasks':tasks,'errors':errors,'warnings':warnings,
            'fingerprint':fingerprint(tasks) if not errors else None}


def commit(app, data):
    result=preview(app,data.get('document'))
    if not result['valid']:
        raise ValueError('题包校验失败，没有写入任何题目：'+'；'.join(f"第{x['index']}题：{x['message']}" for x in result['errors']))
    if result['fingerprint']!=data.get('fingerprint'):
        raise ValueError('题包与预览内容不一致，请重新预览后导入。')
    tasks=[{**t,'id':'task-'+uuid.uuid4().hex[:12],'updatedAt':now()} for t in result['tasks']]
    receipt={'id':identifier(data.get('requestId')),'fingerprint':result['fingerprint'],
             'taskIds':[t['id'] for t in tasks],'createdAt':now()}
    receipt=app.db.import_tasks(receipt,tasks)
    return {'receipt':receipt,'imported':[app.db.get('task',tid) for tid in receipt['taskIds']]}
