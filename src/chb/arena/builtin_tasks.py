"""Bundled task installation; no network, execution, or overwrite of saved tasks."""
import tomllib

def import_originals(app):
    """Install missing bundled tasks, preserving edits and archived records."""
    names={'search-notes-v1':'笔记搜索修复','storage-migration-v1':'笔记存储演进：归档与 SQLite','csv-catalog-v1':'CSV 目录导入修复'}
    saved=[]
    for name,title in names.items():
        tid='original-'+name
        if any(t['id']==tid for t in app.db.list('task')+app.db.list('task',True)):continue
        folder=app.root/'tasks'/name
        if not (folder/'task.toml').is_file():continue
        definition=tomllib.loads((folder/'task.toml').read_text(encoding='utf-8'))
        baseline=app.import_files('baseline',{'path':str(folder/'environment/fixture'),'name':title+' 起点'})
        prompt=(folder/'instruction.md').read_text(encoding='utf-8').replace('/app','当前工作目录')
        stages=[];checks=[]
        for i,step in enumerate(definition.get('steps',[])):
            stages.append({'title':step['name'],'prompt':(folder/'steps'/step['name']/'instruction.md').read_text(encoding='utf-8').replace('/app','当前工作目录')})
            checks.append({'label':step['name']+' 独立验收','image':'chb-verifier:'+name,'argv':['env','CHB_STAGE='+step['name'],'python','-I','/tests/verify.py','/app'],'weight':1,'timeout':45,'stageIndex':i})
        if not stages:
            stages=[{'title':'完成修复','prompt':prompt}]
            checks=[{'label':'独立验收','image':'chb-verifier:'+name,'argv':['python','-I','/tests/verify.py','/app'],'weight':1,'timeout':45}]
        saved.append(app.save_task({'id':tid,'title':title,'inputPrompt':prompt,'stages':stages,'checks':checks,'baselineId':baseline['id'],
          'hasFrontendUI':False,'taskParadigm':'open-ended-project' if len(stages)>1 else 'deterministic-bugfix','channel':'deepswe-core','difficulty':'Medium',
          'sourceKind':'repository-original','referenceUrl':'https://github.com/devonsagr/1/tree/main/tasks/'+name,'license':'MIT',
          'environmentNote':'Python 3.12+ · 标准库，无第三方依赖。已有测试：python -m unittest discover -s tests -v。',
          'sourceNote':'项目原创完整题目。仅导入 environment/fixture；参考解和独立验收器不交给桌面。容器路径在题面改写为当前工作目录。桌面真实成绩仍需重新执行。'}))
    return {'imported':saved}
