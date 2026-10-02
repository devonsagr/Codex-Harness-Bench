type Application={status:string;configId:string;configRevision:number;settingsMatch?:boolean};
export function applicationStatus(active:Application|undefined,config:{id:string;revision:number},unsaved=false,targetMismatch=false){
  if(unsaved)return {label:'修改尚未保存',detail:'应用时会先保存新版本，再写入文件。',ready:false};
  if(!active)return {label:'尚未写入全局配置',detail:'每题的独立工作区仍会使用所选配置；需要更改全局默认值时点击应用。',ready:false};
  if(active.status==='restore_failed')return {label:'撤销未完成',detail:'当前文件已保留。请核对下方错误与文件回执，再决定保持现状或重新应用。',ready:false};
  if(active.status!=='applied')return {label:'写入待核对',detail:'尚未收到完整应用回执，请核对当前文件。',ready:false};
  if(active.configId!==config.id||active.configRevision!==config.revision)return {label:'全局仍是另一配置',detail:'所选配置尚未应用到全局默认值。',ready:false};
  if(active.settingsMatch!==true||targetMismatch)return {label:'写入的设置已变化或尚未核实',detail:'请核对当前文件；运行中的任务结束前不要切换全局配置。',ready:false};
  return {label:'所选设置已写入并读回核对',detail:'这是文件状态；已有对话与项目覆盖值仍需核对。',ready:true};
}
export function applicationErrorHelp(message:string){
  if(message.includes('已被其他操作修改')||message.includes('写入的设置也已改变'))return '未覆盖你后来修改的配置，也无法直接切换。先点“核对当前文件”，在回执中查看变动文件。可以保留现状；若要撤销，等当前任务结束后，先把变动项恢复为本次应用的设置或规则，再点“撤销上次应用”。';
  if(message.includes('仍有执行')||message.includes('后台检查')||message.includes('先结束当前执行'))return '先结束正在执行的任务或后台检查，再回来操作。当前配置未撤销。';
  return '请先核对当前文件和下方错误详情，再重试该操作。未核实前不要按切换成功记录成绩。';
}
