"use strict";
const main = document.querySelector("#main");
const token = document.querySelector('meta[name="chb-token"]').content;
let state = {profiles: [], tasks: [], experiments: [], warnings: []};
let environment = null;
let profile = null;
let experiment = null;
let preview = null;
let viewSerial = 0;
const titles = {overview:"总览", profiles:"配置库", new:"新建对比", runs:"运行详情", results:"结果与历史"};
const taskTitles = {"search-notes-v1":"笔记搜索", "storage-migration-v1":"存储迁移", "csv-catalog-v1":"CSV 商品导入"};
const labels = {planned:"计划已保存", running:"运行中", interrupted:"异常中止", partial:"尚未完成", finished:"已结束", completed:"已完成", execution_error:"执行异常", infrastructure_error:"环境异常", verifier_error:"验收异常", protocol_error:"续接异常", timeout:"超时", not_run:"未运行"};
const e = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const num = value => value == null ? "—" : Number(value).toLocaleString("zh-CN", {maximumFractionDigits:3});
const badge = value => `<span class="badge ${["completed","finished"].includes(value)?"good":["interrupted","execution_error","timeout"].includes(value)?"warn":""}">${e(labels[value] || value)}</span>`;
const page = () => (location.hash.slice(1).split("/")[0] || "overview");
const pageId = () => location.hash.slice(1).split("/")[1] || "";
const title = (name, summary, action="") => `<div class="page-head"><div><p class="eyebrow">${e(titles[page()] || "本地工作台")}</p><h1>${name}</h1><p class="lead">${summary}</p></div>${action}</div>`;
function notice(message) { const n=document.querySelector("#notice"); n.textContent=message; n.hidden=!message; }
async function api(path, data) {
  const response = await fetch(path, {method:data===undefined?"GET":"POST", headers:{"X-CHB-Token":token,...(data===undefined?{}:{"Content-Type":"application/json"})}, body:data===undefined?undefined:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || "操作失败，请刷新后重试。");
  return result;
}
function historyTable(items) {
  if (!items.length) return '<div class="empty">还没有实验。先选择两套配置，保存第一份对比计划。</div>';
  return `<div class="table-wrap"><table class="table"><thead><tr><th>实验 / 题目</th><th>配置</th><th>状态</th><th>已结束 / 计划</th><th></th></tr></thead><tbody>${items.map(x=>`<tr><td><strong>${e(x.tasks.map(n=>taskTitles[n]||n).join(" · "))}</strong><span class="small muted">${e(x.id)}</span></td><td>${x.profiles.map(e).join("<br>")}</td><td>${badge(x.status)}</td><td class="num">${x.finished} / ${x.planned}</td><td><a href="#results/${e(x.id)}">查看</a></td></tr>`).join("")}</tbody></table></div>`;
}
function environmentHTML() {
  return `<dl class="environment"><div><dt>Docker 引擎</dt><dd>${environment ? environment.docker ? "可用 · "+e(environment.docker) : "未连接；保存计划前需要启动" : "正在检查…"}</dd></div><div><dt>实验 Codex 版本</dt><dd>${environment?e(environment.codex):"—"}</dd></div><div><dt>认证状态</dt><dd>${environment?environment.authentication_present?"发现本机认证文件":"未发现本机认证文件":"正在检查…"}</dd></div></dl><p class="small muted">认证文件存在不代表额度可用。本版的页面浏览、配置操作和计划预览均不调用模型。</p>`;
}
function overview() {
  const active=state.experiments.filter(x=>x.status==="running").length;
  const recentError=state.experiments.find(x=>x.status==="interrupted");
  main.innerHTML=title("把配置、对比和证据放在一起。","从已有规则创建配置副本，用相同题目比较交付结果。先看清变化与预算，再保存一份可追溯的实验计划。",'<a class="btn" href="#new">新建对比</a>')+
  `<div class="metrics"><div class="metric"><span class="number num">${state.profiles.length}</span><strong>可选择的配置</strong><p>示例与本机私有副本</p></div><div class="metric"><span class="number num">${state.tasks.length}</span><strong>可用题目</strong><p>单轮与连续两轮任务</p></div><div class="metric"><span class="number num">${active}</span><strong>记录显示运行中</strong><p>刷新读取当前文件状态</p></div></div>`+
  `<div class="split"><section class="section"><div class="section-head"><h2>最近实验</h2><a class="small" href="#results">全部历史</a></div>${historyTable(state.experiments.slice(0,5))}</section><aside><section class="section"><h2>本机环境</h2><div id="environment">${environmentHTML()}</div></section></aside></div>`+
  (recentError?`<div class="callout"><strong>有一份中止的实验等待查看</strong><p>${e(recentError.id)} · 已结束 ${recentError.finished} / ${recentError.planned} 项。<a href="#runs/${e(recentError.id)}">查看异常与未运行项</a></p></div>`:"")+
  `<p class="small muted">这些数字表示本机实验记录，不是产品开发完成度。完整多题模型验收仍待完成；当前前端支持管理配置、冻结计划与查看结果。</p>`;
}
async function profilesView(id, serial) {
  const selected=state.profiles.some(p=>p.name===id)?id:state.profiles[0]?.name;
  if (!selected) {main.innerHTML=title("配置库","没有找到有效配置。请检查项目中的示例配置文件。");return;}
  const loaded=await api('/api/profiles/'+encodeURIComponent(selected));
  if(serial!==viewSerial)return;
  const p=profile=loaded;
  main.innerHTML=title("保存一套配置，再比较一次变化。","所有编辑都另存为新的私有副本。原配置、历史实验与宿主 Codex 设置保持原样。")+
  `<div class="config-layout"><aside><div class="config-list">${state.profiles.map(x=>`<button type="button" class="config-item ${x.name===p.name?"selected":""}" data-select-profile="${e(x.name)}" aria-pressed="${x.name===p.name}"><strong>${e(x.name)}</strong><span>${x.private?"私有副本":"项目示例"} · ${x.skills.length} 个附加技能 · ${e(x.native.model_reasoning_effort)}</span></button>`).join("")}</div><details class="import-box"><summary>导入当前全局规则</summary><form id="import-form" class="stack"><label class="field">新配置名称<input name="name" required placeholder="my-agents"></label><label class="field">固定推理档位<select name="reasoning"><option>medium</option><option>low</option><option>high</option><option>xhigh</option></select></label><p class="small muted">只导入全局说明与支持的设置。认证、MCP、插件与完整技能库不导入。</p><button class="btn secondary" type="submit">导入为私有副本</button></form></details></aside>`+
  `<section class="section"><div class="section-head"><h2>${e(p.name)}</h2><span class="badge">${p.private?"私有副本":"项目示例"}</span></div><form id="profile-form"><div class="fields"><label class="field">另存为名称<input name="name" required value="${e(p.name.slice(0,30)+'-copy')}" autocomplete="off"><small>小写字母、数字和连字符；已有名称不会覆盖。</small></label><label class="field">推理档位<select name="reasoning">${["low","medium","high","xhigh"].map(n=>`<option ${n===p.native.model_reasoning_effort?"selected":""}>${n}</option>`).join("")}</select></label><label class="field full">配置说明<input name="description" maxlength="500" value="${e(p.description)}"></label><label class="field full">全局指令 · AGENTS.md<textarea class="agent-editor" name="agents" spellcheck="false" maxlength="300000">${e(p.agents)}</textarea></label></div><hr class="divider"><h3>保留哪些附加技能</h3><div class="skills">${p.skills.length?p.skills.map(s=>`<label class="check"><input type="checkbox" name="skills" value="${e(s)}" checked>${e(s)}</label>`).join(""):'<span class="small muted">这套配置没有附加用户技能。</span>'}</div>${Object.entries(p.skill_documents).map(([name,text])=>`<details><summary>查看 ${e(name)}</summary><pre>${e(text)}</pre></details>`).join("")}<p class="small muted">搜索固定为 disabled。新增其他来源技能当前需先用命令行显式导入；这里可以保留或移除源配置已有技能。</p><div class="form-actions"><button class="btn" type="submit">保存为新配置</button><p>写入本机私有配置目录，不触发模型调用。</p></div></form><details><summary>查看版本指纹</summary><code>${e(p.sha256)}</code></details></section></div>`;
}
function newView() {
  preview=null;
  const options=state.profiles.map(p=>`<option value="${e(p.name)}">${e(p.name)}</option>`).join("");
  main.innerHTML=title("把这次对比的条件先固定下来。","选择两套配置和相同的题目。预览会检查固定项、展示配置差异，并计算真实轮数与时间上限。")+
  `<form id="plan-form"><div class="plan-grid"><div><section class="section"><h2>01 / 两套配置</h2><div class="fields"><label class="field">配置 A<select name="left" required>${options}</select></label><label class="field">配置 B<select name="right" required>${options}</select></label><label class="field">模型请求名称<input name="model" required value="openai/gpt-6-astra" maxlength="100"><small>需对你的账号可用；不会自动切换模型。</small></label><label class="field">每题重复次数<select name="repeat">${[1,2,3,4,5].map(n=>`<option value="${n}">${n} 次</option>`).join("")}</select></label></div></section><section class="section"><h2>02 / 选择题目</h2>${state.tasks.map(t=>`<div class="task"><input id="task-${e(t.name)}" type="checkbox" name="tasks" value="${e(t.name)}" checked><div><label for="task-${e(t.name)}"><span class="task-title">${e(taskTitles[t.name]||t.name)}</span><span class="task-desc">${e(t.description)}</span></label><span class="meta">${t.turns} 轮 · ${e(t.group)} · ${e(t.license)}</span><details><summary>题面与来源</summary><p class="small"><a href="${e(t.source_repository)}" target="_blank" rel="noreferrer">源码仓库</a> · 原创任务；正式公开状态以仓库实际文件为准。</p><pre>${e(t.instruction)}</pre>${t.steps.length?`<p class="small muted">连续轮次：${t.steps.map(e).join(" → ")}。完整逐轮题面保存在本机题库。</p>`:""}</details></div></div>`).join("")}</section></div><aside class="budget"><h2>本次计划</h2><div><span class="number num" id="budget-trials">—</span> <span class="small muted">次整题运行</span></div><dl><dt>Agent 轮次</dt><dd id="budget-turns">—</dd><dt>每轮时间上限</dt><dd>300 秒</dd><dt>Agent 总上限</dt><dd id="budget-seconds">—</dd></dl><p class="small muted">环境准备与验收另计。不同轮次不算不同题，同题重复不增加独立样本。</p><button class="btn" type="submit" ${state.profiles.length<2?"disabled":""}>预览差异与预算</button><p class="small muted">预览与保存均不调用模型。</p></aside></div></form><div id="plan-preview"></div>`;
  const right=main.querySelector('[name="right"]');if(right.options.length>1)right.selectedIndex=1;
  updateBudget();
}
function selection() {
  const data=new FormData(document.querySelector('#plan-form'));
  return {profiles:[data.get('left'),data.get('right')],model:data.get('model'),repeat:Number(data.get('repeat')),tasks:data.getAll('tasks')};
}
function updateBudget() {
  const f=document.querySelector('#plan-form');if(!f)return;
  const data=selection();const turns=data.tasks.reduce((sum,n)=>sum+(state.tasks.find(t=>t.name===n)?.turns||0),0)*2*data.repeat;
  document.querySelector('#budget-trials').textContent=num(data.tasks.length*2*data.repeat);
  document.querySelector('#budget-turns').textContent=num(turns);
  document.querySelector('#budget-seconds').textContent=num(turns*300)+' 秒';
}
function showPreview(p) {
  document.querySelector('#plan-preview').innerHTML=`<section class="section"><h2>03 / 核对后保存计划</h2><div class="compare-pair"><div><small>配置 A</small><strong>${e(p.selection.profiles[0])}</strong></div><div><small>配置 B</small><strong>${e(p.selection.profiles[1])}</strong></div></div><p class="small">固定项：${e(p.selection.model)} · 推理 ${e(p.native.model_reasoning_effort)} · 搜索 ${e(p.native.web_search)}。${p.trials} 次运行，${p.turns} 轮，总 Agent 上限 ${num(p.budget_seconds)} 秒。</p><pre>${e(p.diff||"配置文件内容一致。")}</pre><div class="form-actions"><button class="btn" type="button" data-action="save-plan">保存冻结计划</button><p>需要已准备的 Docker 镜像。保存后进入计划详情，不启动模型。</p></div></section>`;
  document.querySelector('#plan-preview').scrollIntoView({behavior:'auto',block:'start'});
}
async function experimentsView(id, serial) {
  if(!id){
    const items=page()==='runs'?state.experiments.filter(x=>x.status!=='finished'):state.experiments;
    main.innerHTML=title(page()==='runs'?"查看每次运行停在哪里。":"每一份结果，都能回到原始条件。",page()==='runs'?"这里读取正在运行、尚未执行或中止的本机记录。本版提供状态查看，页面启动和停止将在运行控制阶段接入。":"记录来自本机已有实验。通过、未通过与执行异常分别保留；不同版本的实验不会拼成排名。",'<a class="btn" href="#new">新建对比</a>')+`<section class="section">${historyTable(items)}</section><p class="small muted">最多显示最近 ${state.history_limit} 份记录。刷新数据会重新读取本机文件。</p>`;return;
  }
  const loaded=await api('/api/experiments/'+encodeURIComponent(id));if(serial!==viewSerial)return;
  const x=experiment=loaded;
  main.innerHTML=title(x.status==='planned'?"计划已保存。条件已经固定。":"先看验收，再看差异。",`${e(x.id)} · ${e(x.model)} · Codex ${e(x.codex_version)}`,`<a class="btn secondary" href="#results">返回历史</a>`)+
  `<div class="row spread"><div class="row">${badge(x.status)}<span class="small">已结束 ${x.finished} / ${x.planned} 项 · 通过 ${x.accepted} 项 · 未运行 ${x.pending} 项</span></div><span class="small muted">Agent 预算上限 ${num(x.budget_seconds)} 秒</span></div><div class="state-track" aria-label="${x.finished} 项已结束，共 ${x.planned} 项">${x.trials.map(t=>`<span class="${t.status==='completed'?'complete':t.status==='not_run'?'':'error'}"></span>`).join("")}</div>`+
  (x.status==='planned'?'<div class="callout"><strong>本次没有调用模型。</strong><p>当前页面可以保存和查看计划，尚不提供启动与停止。运行需要后续运行控制接入或使用项目命令行。</p></div>':x.status==='interrupted'?`<div class="callout"><strong>实验没有完整结束</strong><p>${e(x.trials.find(t=>t.cause)?.cause||"存在异常，请查看逐项状态。")} 已有记录保留，未运行项不会计成失败或零消耗。</p></div>`:"")+
  `<section class="section"><h2>同批分组比较</h2><div class="group-grid">${x.groups.map(g=>`<div class="group"><h3>${g.tasks.map(t=>e(taskTitles[t]||t)).join(" · ")}</h3><p>双方通过配对 ${g.accepted_pairs} / ${g.planned_pairs}</p><dl>${Object.entries(g.profiles).map(([name,p])=>`<dt>${e(name)}</dt><dd>通过 ${p.accepted} · 未通过 ${p.failed} · 异常 ${p.error}<br><span class="small muted">配对耗时 ${num(p.paired_agent_seconds)} 秒 · 待完成 ${p.pending}</span></dd>`).join("")}</dl></div>`).join("")}</div><p class="small muted">只有双方通过的同题同重复结果计入配对耗时。— 代表不可计算；小规模题目不支持配置优劣或统计显著性结论。</p></section>`+
  `<section class="section"><h2>逐项结果与证据</h2><div class="table-wrap"><table class="table"><thead><tr><th>题目 / 配置</th><th>状态</th><th>验收</th><th>Agent 秒数</th><th>输入 / 其中缓存</th><th>输出</th><th></th></tr></thead><tbody>${x.trials.map((t,i)=>`<tr><td><strong>${e(taskTitles[t.task]||t.task)}</strong><span class="small">${e(t.profile)}</span><span class="small muted">${e(t.id)} · 第 ${(t.repeat||0)+1} 次</span></td><td>${badge(t.status)}</td><td>${t.accepted===true?'通过':t.accepted===false?'未通过':'—'}</td><td class="num">${num(t.agent_seconds)}</td><td class="num">${num(t.input_tokens)}<span class="small muted">${num(t.cached_input_tokens)}</span></td><td class="num">${num(t.output_tokens)}</td><td><button class="action" data-evidence="${i}">查看</button></td></tr>`).join("")}</tbody></table></div></section>`+
  `<div class="split"><section class="section"><h2>冻结的配置差异</h2><p class="small muted">推理 ${e(x.native.model_reasoning_effort||'未记录')} · 搜索 ${e(x.native.web_search||'未记录')}</p><details><summary>展开完整差异</summary><pre>${e(x.diff)}</pre></details><p class="small muted">完整原始产物保存在本机：</p><code>${e(x.local_evidence)}</code></section><section class="section"><h2>取出历史配置</h2><form id="restore-form" class="stack"><label class="field">源配置<select name="profile">${x.profiles.map(n=>`<option>${e(n)}</option>`).join("")}</select></label><label class="field">新副本名称<input name="name" required placeholder="restored-profile"></label><button class="btn secondary" type="submit">恢复为新配置</button><p class="small muted">先核对旧快照，再创建新副本；不会覆盖旧实验。</p></form></section></div>`;
}
function evidence(index) {
  const t=experiment.trials[index];if(!t)return;
  const dialog=document.createElement('dialog');
  dialog.innerHTML=`<div class="section-head"><h2>${e(t.id)} · 验收与装载证据</h2><button class="quiet" data-close>关闭</button></div><p>${badge(t.status)} ${e(t.cause)}</p><dl class="environment"><div><dt>配置装载校验</dt><dd>${t.effective_profile_evidence===true?'有装载证据':t.status==='not_run'?'未运行':'未取得'}</dd></div><div><dt>多轮会话连续</dt><dd>${t.session_continuity===true?'已观察到':t.session_continuity===false?'未通过':'不适用 / 未取得'}</dd></div><div><dt>多轮用量校验</dt><dd>${e(t.usage_status||'不适用 / 未取得')}</dd></div></dl>${t.steps.map(s=>`<hr class="divider"><h3>${e(s.name)} · ${e(labels[s.status]||s.status)}</h3><p class="small">验收：${s.accepted===true?'通过':s.accepted===false?'未通过':'—'} · ${num(s.agent_seconds)} 秒 · 第 ${num(s.profile_load_index)} 次配置装载</p>`).join("")}<p class="small muted">技能完整读取：${[...(t.skill_reads||[]),...t.steps.flatMap(s=>s.skill_reads||[])].some(r=>r.complete_read_output_observed)?'观察到完整输出':'未观察到 / 无附加技能'}。装载或读取不代表证明内部完全遵循。</p>`;
  document.body.append(dialog);dialog.showModal();dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.addEventListener('close',()=>dialog.remove());
}
async function render() {
  const serial=++viewSerial;
  const current=titles[page()]?page():'overview';
  document.querySelector('#breadcrumb').textContent=titles[current];
  document.querySelectorAll('[data-page]').forEach(a=>{if(a.dataset.page===current)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  try {if(current==='overview')overview();else if(current==='profiles')await profilesView(pageId(),serial);else if(current==='new')newView();else await experimentsView(pageId(),serial);}
  catch(error){if(serial===viewSerial){main.innerHTML=title("暂时无法打开记录。",e(error.message),'<a class="btn secondary" href="#overview">回到总览</a>');notice(error.message);}}
}
async function reload() {state=await api('/api/state');await render();if(state.warnings.length)notice(state.warnings.join(' '));}
document.querySelector('#refresh').addEventListener('click',async function(){this.disabled=true;try{await reload();environment=await api('/api/environment');const box=document.querySelector('#environment');if(box)box.innerHTML=environmentHTML();notice('已重新读取本机记录。');}catch(err){notice(err.message);}finally{this.disabled=false;}});
window.addEventListener('hashchange',()=>{notice('');render();});
main.addEventListener('change',event=>{if(event.target.closest('#plan-form')){preview=null;document.querySelector('#plan-preview').innerHTML='';updateBudget();}});
main.addEventListener('input',event=>{if(event.target.closest('#plan-form')){preview=null;document.querySelector('#plan-preview').innerHTML='';}});
main.addEventListener('click',async event=>{
  const el=event.target.closest('button');if(!el)return;
  if(el.dataset.selectProfile){location.hash='profiles/'+encodeURIComponent(el.dataset.selectProfile);return;}
  if(el.dataset.evidence!==undefined){evidence(Number(el.dataset.evidence));return;}
  if(el.dataset.action==='save-plan'){
    if(!preview)return;el.disabled=true;
    try{const result=await api('/api/plans/create',{preview_id:preview.preview_id});state=await api('/api/state');location.hash='results/'+result.id;notice('冻结计划已保存，没有调用模型。');}
    catch(error){notice(error.message);el.disabled=false;}
  }
});
main.addEventListener('submit',async event=>{
  event.preventDefault();const form=event.target;const button=event.submitter;const f=new FormData(form);if(button)button.disabled=true;
  try{
    if(form.id==='profile-form'){
      const result=await api('/api/profiles/save',{source:profile.name,source_sha256:profile.sha256,name:f.get('name'),description:f.get('description'),agents:f.get('agents'),reasoning:f.get('reasoning'),skills:f.getAll('skills')});
      state=await api('/api/state');location.hash='profiles/'+result.name;notice('已保存新配置，源配置未修改。');
    }else if(form.id==='import-form'){
      const result=await api('/api/profiles/import',{name:f.get('name'),reasoning:f.get('reasoning')});state=await api('/api/state');location.hash='profiles/'+result.name;notice('已部分导入全局规则，宿主设置未修改。');
    }else if(form.id==='plan-form'){
      const requested=selection();const currentView=viewSerial;
      const loaded=await api('/api/plans/preview',requested);
      if(currentView!==viewSerial || JSON.stringify(selection())!==JSON.stringify(requested))return;
      preview=loaded;showPreview(preview);notice('预览已生成，请核对差异与预算。');
    }else if(form.id==='restore-form'){
      const result=await api('/api/profiles/restore',{experiment:experiment.id,profile:f.get('profile'),name:f.get('name')});state=await api('/api/state');location.hash='profiles/'+result.name;notice('历史快照校验通过，已恢复为新的配置副本。');
    }
  }catch(error){notice(error.message);}finally{if(button)button.disabled=false;}
});
reload().then(async()=>{try{environment=await api('/api/environment');const box=document.querySelector('#environment');if(box)box.innerHTML=environmentHTML();}catch(error){notice(error.message);}}).catch(error=>{main.innerHTML=title('无法读取本机数据。',e(error.message));});
