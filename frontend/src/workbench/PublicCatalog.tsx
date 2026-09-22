import {useEffect,useState} from 'react';
import catalog from '../../../catalog/public-task-sources.json';
import type {State,Task} from './types';
import {request} from './api';

export const publicCategories:Record<string,string>={bugfix:'修复 Bug',feature_request:'增加功能',enhancement:'工程改进'};
export const nativeTaskIds=['tengo-callable-instance-isolation','tengo-destructuring-bindings','yaegi-go-embed-directives'];
export function availableTasks(state:State):Task[]{
  const existing=new Set([...state.tasks,...state.archivedTasks].map(t=>t.id));
  const publicTasks=catalog.tasks.filter(t=>!existing.has('deepswe-'+t.id)).map(t=>({
    id:'deepswe-'+t.id,title:t.title,revision:0,taskParadigm:t.category==='bugfix'?'deterministic-bugfix':'open-ended-project',
    requiresBaseline:true,sourceKind:'deepswe',channel:'deepswe-core',difficulty:'未标注',hasFrontendUI:false,
    inputPrompt:'',checks:[],stages:[],referenceUrl:t.instructionUrl,
    description:t.repositoryUrl,
    publicSource:{id:t.id,category:t.category,language:t.language,environmentStatus:'on-demand',verifierStatus:'pending'},
  }));
  return [...state.tasks,...publicTasks];
}
export function PublicPrompt({task}:{task:Task}){
  const [text,setText]=useState(task.inputPrompt);const [error,setError]=useState('');
  useEffect(()=>{let live=true;setText(task.inputPrompt);setError('');
    if(!task.inputPrompt&&task.publicSource)request<{text:string}>('/sources/preview',{taskId:task.publicSource.id}).then(r=>{if(live)setText(r.text);}).catch(e=>{if(live)setError(e.message);});
    return()=>{live=false;};
  },[task.id,task.inputPrompt]);
  return <>{error?<p className="alert-error">{error}</p>:<p className="reading-copy task-prompt">{text||'正在读取原始题面；不会下载目标项目…'}</p>}</>;
}
