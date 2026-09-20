const base='/api/arena';
function headers(){return {'X-CHB-Token':document.querySelector<HTMLMetaElement>('meta[name="chb-token"]')?.content || ''};}
function connectionError(write=false){return new Error('无法连接本地工作台。请确认 launch-ui.cmd 仍在运行，再点击“刷新记录”。'+(write?'本次操作结果尚未确认，请先核对记录，勿重复提交。':'已保存的记录不会因页面断连而删除。'));}
async function responseFor(path:string,data?:unknown){
  let response:Response;
  try{response=await fetch(base+path,{method:data===undefined?'GET':'POST',headers:{...headers(),...(data===undefined?{}:{'Content-Type':'application/json'})},body:data===undefined?undefined:JSON.stringify(data)});}
  catch{throw connectionError(data!==undefined);}
  if(!response.ok){
    const error=await response.json().catch(()=>null);
    if(response.status===403)throw new Error('访问校验未通过。若服务刚刚重启，请先保留未提交内容，再重新加载页面。');
    throw new Error(error?.error || '服务未返回有效响应，请检查本地服务。');
  }
  return response;
}
export async function request<T>(path:string,data?:unknown):Promise<T>{
  const response=await responseFor(path,data);
  try{return await response.json();}
  catch{throw new Error('未能完整读取服务响应。请刷新记录核对结果，勿重复提交。');}
}
// A successful write remains successful even if the following state read fails.
export async function submitAndRefresh<T>(path:string,data:unknown,refresh:()=>Promise<void>){
  const result=await request<T>(path,data);
  try{await refresh();return {result,refreshed:true};}
  catch{return {result,refreshed:false};}
}
export async function downloadRun(id:string){
  const r=await responseFor(`/runs/${id}/export`);
  let blob:Blob;
  try{blob=await r.blob();}catch{throw connectionError();}
  const url=URL.createObjectURL(blob); const a=document.createElement('a');a.href=url;a.download=id+'.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
