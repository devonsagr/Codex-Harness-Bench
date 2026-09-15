const base='/api/arena';
function headers(){return {'X-CHB-Token':document.querySelector<HTMLMetaElement>('meta[name="chb-token"]')?.content || ''};}
export async function request<T>(path:string,data?:unknown):Promise<T>{
  const response=await fetch(base+path,{method:data===undefined?'GET':'POST',headers:{...headers(),...(data===undefined?{}:{'Content-Type':'application/json'})},body:data===undefined?undefined:JSON.stringify(data)});
  if(!response.ok){const error=await response.json().catch(()=>({error:'服务未返回有效响应，请检查本地服务。'}));throw new Error(error.error);}
  return response.json();
}
export async function downloadRun(id:string){
  const r=await fetch(base+`/runs/${id}/export`,{headers:headers()});
  if(!r.ok){const data=await r.json();throw new Error(data.error);}
  const url=URL.createObjectURL(await r.blob()); const a=document.createElement('a');a.href=url;a.download=id+'.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
