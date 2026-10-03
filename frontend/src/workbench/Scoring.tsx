import type {Policy,State,Trial,Task} from './types';
import {verdicts} from './Contracts';
import {Field,ScoreSlider,Details} from './ui';
import {distribute,adjustWeight} from './weights';
import {ObjectivePlan,RatingGuide} from './ScorePlan';
import {rubricRadarDestinations} from './capabilityProfiles';
import {rubricGroups,scoringPresets,uiRubricKeys} from './rubricCatalog';
import {autoProfile,scoredDimensions} from './autoScorecard';

export function percentPolicy(p:Policy):Policy{
  return {...p,dimensionUnit:'percent',requireDimensionEvidence:true,dimensions:distribute(p.dimensions)};
}
export const validPercentPolicy=(p:Policy)=>Math.abs(Object.values(p.dimensions).reduce((a,b)=>a+b,0)-100)<.005;
export function ScoringSettings({state,tasks,policy,onChange}:{state:State;tasks:Task[];policy:Policy;onChange:(p:Policy)=>void}){
  if(policy.version==='arena-machine-v1')return policy.taskTypeAuto?<AutoMachineSettings state={state} tasks={tasks} policy={policy} onChange={onChange}/>:<MachineSettings state={state} tasks={tasks} policy={policy} onChange={onChange}/>;
  const share=(key:string)=>{
    const weight=policy.dimensions[key]||0;const nonUiTotal=Object.entries(policy.dimensions).filter(([k])=>k!=='ux').reduce((n,[,w])=>n+w,0);
    const fmt=(v:number)=>(Math.round((v+Number.EPSILON)*100)/100).toFixed(2);
    const ui='折合总分约 '+fmt(weight*policy.humanWeight/100)+'%';
    const nonUi=key==='ux'?'无界面题不计此项':'无界面题折合总分约 '+fmt(nonUiTotal?weight/nonUiTotal*policy.humanWeight:0)+'%';
    return tasks.length&&tasks.every(t=>!t.hasFrontendUI)?nonUi:tasks.some(t=>!t.hasFrontendUI)?ui+'；'+nonUi:ui;
  };
  const items=policy.rubrics||{};const total=Object.values(policy.dimensions).reduce((a,b)=>a+b,0);
  const add=(key:string,label:string,description:string)=>onChange(percentPolicy({...policy,version:'arena-review-v2',dimensions:{...policy.dimensions,[key]:10},rubrics:{...items,[key]:{label,description}}}));
  return <section className="space-y-6"><h3 className="font-semibold">评分方案与依据</h3>
    <div className="score-mix"><div className="flex justify-between gap-3 text-sm"><span>客观检查 <strong>{policy.objectiveWeight}%</strong></span><span>人工评分 <strong>{policy.humanWeight}%</strong></span></div><input aria-label="客观检查占总分（%）" type="range" min="0" max="100" step="1" value={policy.objectiveWeight} onChange={e=>onChange({...policy,objectiveWeight:Number(e.target.value),humanWeight:100-Number(e.target.value)})}/></div>
    <p className="muted">总分 = 客观检查分 × {policy.objectiveWeight}% + 人工评分分 × {policy.humanWeight}%。两部分各按0–100分计算；缺少所需证据时总分为空。</p>
    {tasks.some(t=>!t.checks.length)&&policy.objectiveWeight>0&&<div className="score-notice space-y-2"><p>所选题目中有题目未配置自动检查。当前方案无法得到完整总分。</p><button type="button" className="btn-secondary" onClick={()=>onChange({...policy,objectiveWeight:0,humanWeight:100})}>本次改用纯人工验收</button></div>}
    <ObjectivePlan tasks={tasks}/>
    <section className="score-section space-y-4"><h3 className="font-semibold">人工评分 · 查看真实交付后评分</h3><p className="muted">拖动一项，其余项按比例联动，合计始终为100%。这里调整权重，交付后再评分。</p>
      <div className="flex gap-3 flex-wrap items-center"><strong aria-live="polite">人工内部合计：{total.toFixed(2)}%</strong></div>
      {!validPercentPolicy(policy)&&<p role="alert" className="alert-error">内部占比必须合计100%，调整后才能创建评测。</p>}
      <div className="rubric-list">{Object.entries(items).map(([key,item])=><div className="rubric-row" key={key}><div><strong className="text-sm">{item.label}</strong><p className="muted">{item.description}</p><p className="text-sm">{share(key)}</p></div><ScoreSlider label={item.label+'：人工内部占比'} suffix="%" value={String(policy.dimensions[key]??0)} onChange={v=>onChange({...policy,dimensions:adjustWeight(policy.dimensions,key,Number(v))})} fixed/><button type="button" className="btn-ghost" aria-label={'移除评分项 '+item.label} disabled={Object.keys(items).length<=1} onClick={()=>{const dims={...policy.dimensions};const rubrics={...items};delete dims[key];delete rubrics[key];onChange(percentPolicy({...policy,dimensions:dims,rubrics}));}}>移除</button></div>)}</div>
      <div className="rubric-add-row"><Field label="添加人工评分项"><select disabled={Object.keys(items).length>=16} value="" onChange={e=>{const item=state.rubricCatalog[e.target.value];if(item)add(e.target.value,item.label,item.description);}}><option value="">选择适用维度</option>{Object.entries(state.rubricCatalog).filter(([k])=>!items[k]).map(([k,v])=><option value={k} key={k}>{v.label}</option>)}</select></Field><button type="button" className="btn-secondary" disabled={Object.keys(items).length>=16} onClick={()=>add('custom-'+crypto.randomUUID().slice(0,8),'自定义评分项','按本题的实际证据评分；请在创建前修改名称和依据。')}>添加自定义项</button></div>
      {Object.entries(items).filter(([k])=>k.startsWith('custom-')).map(([key,item])=><div className="grid sm:grid-cols-2 gap-3" key={key}><Field label="自定义评分名称"><input value={item.label} onChange={e=>onChange({...policy,rubrics:{...items,[key]:{...item,label:e.target.value}}})}/></Field><Field label="自定义评分依据"><input value={item.description} onChange={e=>onChange({...policy,rubrics:{...items,[key]:{...item,description:e.target.value}}})}/></Field></div>)}
      <Details title="评分依据与分档"><RatingGuide/></Details>
    </section>
    <Details title="AI 审查与人工裁定的区别"><p className="muted">回收后可单独启动一次 AI 审查：它读取冻结需求、产物、差异和检查回执，引用文件指出问题；不是再执行原任务，也不是客观检查。它会使用模型额度，不能代替实际运行和人工视觉验收。</p><p className="muted">对自动结果有异议时，可在结果页填写“人工裁定”，附理由与证据；保留自动原分并单列裁定后的分数，不把人工修正伪装成脚本通过。Token、耗时、介入与可靠性另列。</p></Details>
  </section>;
}
function AutoMachineSettings({state,tasks,policy,onChange}:{state:State;tasks:Task[];policy:Policy;onChange:(p:Policy)=>void}){
  return <section className="space-y-5"><div><h3 className="font-semibold">按题型自动评分</h3><p className="muted mt-2">创建时冻结每道题的适用评分卡，无需逐项选择。回收后先查原题脚本和实际交付，再由独立裁判逐项取证；人工可按证据修正。</p></div>
    <div className="score-notice"><strong>一题一个综合分。</strong>开放项目按“目标与范围 60 / 使用与可靠性 25 / 交付维护 15”组成；已接通连续评分卡的 DeepSWE 题使用原题语义组与回归检查 90 分、可维护性审查 10 分。原题通过/未通过另列，不能冒充连续分。没有证据的项保持未测。</div>
    <div className="auto-scorecards">{tasks.map(task=>{const profile=autoProfile(task);const weights=scoredDimensions(policy,task);const overridden=!!policy.taskOverrides?.[task.id];return <article key={task.id} className="auto-scorecard"><header><strong>{task.title}</strong><span>{overridden?'本题自定义':profile.label}</span></header>{profile.id==='public'?<p>本题有连续评分卡时，目标功能语义组 70 · 旧功能回归 20 · 可维护性 10；卡未接入时只显示原题结果与质量意见。合成总分由平台计算，AI 不再重判测试分。</p>:<><p>{overridden?'仅本题采用下列冻结权重；其他题保持自己的方案。':'目标与范围 60 · 使用与可靠性 25 · 交付维护 15'}</p><Details title={`本题评分项与自定义 · ${Object.keys(weights).length} 项`}><div className="auto-scorecard-groups">{overridden?<ul>{Object.entries(weights).map(([key,weight])=><li key={key}><span>{policy.taskOverrides?.[task.id]?.rubrics[key]?.label||key}</span><b>{weight}%</b></li>)}</ul>:profile.groups.map(group=><div key={group.label}><strong>{group.label}</strong><ul>{Object.entries(group.weights).map(([key,weight])=><li key={key}><span>{state.rubricCatalog[key]?.label||key}</span><b>{weight}%</b></li>)}</ul></div>)}</div><TaskScoreEditor task={task} state={state} policy={policy} onChange={onChange}/></Details></>}</article>;})}</div>
    <Details title="评分依据与分档"><RatingGuide machine/><p className="muted">“规则与范围遵守”计入目标组，不单独生成雷达轴；其他能力图只读取相应评分证据，不会因为题目标签就给分。规则违背按本题评分依据扣分一次。</p></Details>
  </section>;
}
function TaskScoreEditor({task,state,policy,onChange}:{task:Task;state:State;policy:Policy;onChange:(p:Policy)=>void}){
  const override=policy.taskOverrides?.[task.id];
  const save=(dimensions:Record<string,number>,rubrics:NonNullable<Policy['rubrics']>)=>onChange({...policy,taskOverrides:{...policy.taskOverrides,[task.id]:{dimensions:distribute(dimensions),rubrics}}});
  const start=()=>{const dimensions=scoredDimensions(policy,task);save(dimensions,Object.fromEntries(Object.keys(dimensions).map(key=>[key,state.rubricCatalog[key]||{label:key,description:'依据本题实际交付与证据评分。'}])));};
  const reset=()=>{const next={...policy.taskOverrides};delete next[task.id];onChange({...policy,taskOverrides:next});};
  if(!override)return <button type="button" className="btn-secondary" onClick={start}>只自定义本题</button>;
  const active=scoringPresets.find(preset=>Object.keys(preset.weights).length===Object.keys(override.dimensions).length&&Object.entries(preset.weights).every(([key,value])=>override.dimensions[key]===value));
  return <div className="task-score-editor"><div className="source-actions"><strong>本题权重合计 100%</strong><button type="button" className="btn-secondary" onClick={reset}>恢复本题自动方案</button></div><Field label="本题预制方案"><select value={active?.id||''} onChange={event=>{const preset=scoringPresets.find(item=>item.id===event.target.value);if(preset)save({...preset.weights},Object.fromEntries(Object.keys(preset.weights).map(key=>[key,state.rubricCatalog[key]])));}}><option value="">当前自定义</option>{scoringPresets.map(preset=><option key={preset.id} value={preset.id} disabled={!task.hasFrontendUI&&Object.keys(preset.weights).some(key=>uiRubricKeys.has(key))}>{preset.label}</option>)}</select></Field><div className="rubric-list">{Object.entries(override.dimensions).map(([key,weight])=><div className="rubric-row" key={key}><div><strong>{override.rubrics[key].label}</strong><p className="muted">{override.rubrics[key].description}</p><small>{rubricRadarDestinations(key,[task]).join('；')||'仅计入单题分'}</small></div><ScoreSlider label={override.rubrics[key].label+'权重'} suffix="%" fixed value={String(weight)} onChange={value=>save(adjustWeight(override.dimensions,key,Number(value)),override.rubrics)}/><button type="button" className="btn-ghost" disabled={Object.keys(override.dimensions).length<=1} onClick={()=>{const dims={...override.dimensions},rubrics={...override.rubrics};delete dims[key];delete rubrics[key];save(dims,rubrics);}}>移除</button></div>)}</div><Field label="只给本题添加评分项"><select value="" disabled={Object.keys(override.dimensions).length>=16} onChange={event=>{const key=event.target.value;if(key)save({...override.dimensions,[key]:10},{...override.rubrics,[key]:state.rubricCatalog[key]});}}><option value="">选择标准评分项</option>{rubricGroups.map(group=><optgroup key={group.label} label={group.label}>{group.keys.filter(key=>state.rubricCatalog[key]&&!override.dimensions[key]).map(key=><option key={key} value={key} disabled={uiRubricKeys.has(key)&&!task.hasFrontendUI}>{state.rubricCatalog[key].label}</option>)}</optgroup>)}</select></Field><button type="button" className="btn-secondary" disabled={Object.keys(override.dimensions).length>=16} onClick={()=>{const key='custom-'+crypto.randomUUID().slice(0,8);save({...override.dimensions,[key]:10},{...override.rubrics,[key]:{label:'自定义评分项',description:'依据本题交付证据评分。'}});}}>添加本题专属项</button>{Object.entries(override.rubrics).filter(([key])=>key.startsWith('custom-')).map(([key,item])=><div key={key} className="grid sm:grid-cols-2 gap-3"><Field label="本题评分项名称"><input value={item.label} onChange={event=>save(override.dimensions,{...override.rubrics,[key]:{...item,label:event.target.value}})}/></Field><Field label="本题评分依据"><input value={item.description} onChange={event=>save(override.dimensions,{...override.rubrics,[key]:{...item,description:event.target.value}})}/></Field></div>)}</div>;
}
function MachineSettings({state,tasks,policy,onChange}:{state:State;tasks:Task[];policy:Policy;onChange:(p:Policy)=>void}){
  const items=policy.rubrics||{};
  const hasPublicTask=tasks.some(task=>!!task.publicSource);
  const activePreset=scoringPresets.find(preset=>{
    const selected=Object.entries(policy.dimensions);
    return selected.length===Object.keys(preset.weights).length&&selected.every(([key,weight])=>
      key in preset.weights&&Math.abs(weight-preset.weights[key as keyof typeof preset.weights])<.005);
  });
  const applyPreset=(id:string)=>{
    const preset=scoringPresets.find(item=>item.id===id);
    if(!preset)return;
    const dimensions=Object.fromEntries(Object.entries(preset.weights));
    const rubrics=Object.fromEntries(Object.keys(dimensions).map(key=>[key,state.rubricCatalog[key]]));
    onChange(percentPolicy({...policy,dimensions,rubrics}));
  };
  const radarTarget=(key:string)=>{
    if(key==='instruction')return '规则与范围计入单题总分，不单列雷达轴。';
    const destinations=rubricRadarDestinations(key,tasks);
    return destinations.length?`对应雷达：${destinations.join('；')}`:'本次题目没有对应的雷达细轴；该项仍可单独评分。';
  };
  return <section className="space-y-5"><div><h3 className="font-semibold">自定义评分方案</h3><p className="muted mt-2">本批题共用这套评分项与权重；新建评测时冻结，不更改已有记录。</p><button type="button" className="btn-secondary mt-2" onClick={()=>onChange(percentPolicy(structuredClone(state.defaultPolicy)))}>恢复按题型自动评分</button></div>
    {hasPublicTask&&<div className="score-notice"><strong>DeepSWE 以原题验收为主。</strong>下方是本项目统一的 AI 质量参考量表，不是 DeepSWE 官方评分协议，也不会自动变成原题通过率。已接通 Windows 原生测试的题在回收后另列目标测试、回归测试与失败组；未接通的题留空。本地连续分固定含可维护性审查，混合批次也须保留该项。</div>}
    <div className="score-notice"><strong>评分项与雷达的关系：</strong>开放项目的新评测按此处冻结的适用项和权重计算单题分；雷达展示该项原始 0–100 分，不再乘权重。选项只定义要检查什么，回收后有有效证据才显示轴分。题型表现来自题目分类，原题验收来自程序测试，不在此处手选。</div>
    <Details title={`选择与调整评分项 · ${Object.keys(items).length} 项`}><Field label="标准方案"><select value={activePreset?.id||''} onChange={e=>applyPreset(e.target.value)}><option value="">当前自定义 · {Object.keys(items).length} 项</option>{scoringPresets.map(preset=><option key={preset.id} value={preset.id} disabled={(preset.id==='web'&&!tasks.some(task=>task.hasFrontendUI))||(hasPublicTask&&!('maintainability' in preset.weights))}>{preset.label}</option>)}</select></Field><p className="muted">选择标准方案会替换下面的项与权重。修改后只影响新评测。</p><div className="rubric-list">{Object.entries(items).map(([key,item])=><div className="rubric-row" key={key}><div><strong>{item.label}</strong><p className="muted">{item.description}</p><small className="score-radar-target">{radarTarget(key)}</small>{uiRubricKeys.has(key)&&tasks.some(t=>!t.hasFrontendUI)&&<small>无界面题自动排除此项，其余权重归一。</small>}</div><ScoreSlider label={item.label+'权重'} suffix="%" fixed value={String(policy.dimensions[key]||0)} onChange={value=>onChange({...policy,dimensions:adjustWeight(policy.dimensions,key,Number(value))})}/><button className="btn-ghost" disabled={Object.keys(items).length<=1||(hasPublicTask&&key==='maintainability')} onClick={()=>{const dimensions={...policy.dimensions};const rubrics={...items};delete dimensions[key];delete rubrics[key];onChange(percentPolicy({...policy,dimensions,rubrics}));}}>移除</button></div>)}</div>
    <Field label="添加标准评分项"><select value="" disabled={Object.keys(items).length>=16} onChange={e=>{const key=e.target.value;if(!key)return;onChange(percentPolicy({...policy,dimensions:{...policy.dimensions,[key]:10},rubrics:{...items,[key]:state.rubricCatalog[key]}}));}}><option value="">按雷达领域选择（最多 16 项）</option>{rubricGroups.map(group=><optgroup key={group.label} label={group.label}>{group.keys.filter(key=>state.rubricCatalog[key]&&!items[key]).map(key=><option key={key} value={key} disabled={uiRubricKeys.has(key)&&!tasks.some(task=>task.hasFrontendUI)}>{state.rubricCatalog[key].label}</option>)}</optgroup>)}</select></Field></Details>
    <Details title="本题评分依据与检查方式">{tasks.map(task=><div key={task.id}><strong>{task.title}</strong><p className="muted">{task.criteria?.length||0} 条结构化要求 · {task.checks.length} 项专用脚本 · 同时对照完整题面</p><p className="muted">{task.criteria?.map(c=>c.label).join('；')||task.inputPrompt}</p></div>)}<p className="muted">先运行已有检查，再由独立 AI 查文件、尝试构建和实际操作。文件行与执行输出需可核对；未知项显示未验证。默认权重是本项目的起点，可调整，不是行业统一标准。</p><RatingGuide machine/></Details>
    <Details title="自动评分环境与费用"><p className="muted">默认使用本机独立裁判，无需 Docker；也可选择容器裁判。评分使用所选模型额度，检查冻结产物副本。缺少依赖或无法取证的项目保持未验证。</p><p className="muted">选择容器裁判时，需先准备专用镜像；准备方式见项目说明。</p></Details>
  </section>;
}
export function EvaluationMetrics({trial:t}:{trial:Trial}){
  const latest=t.captures[t.captures.length-1];const review=t.reviews.filter(r=>r.kind==='human'&&r.captureId===latest?.id).slice(-1)[0];
  const rows=[['必要需求',`${t.score.acceptance.met}/${t.score.acceptance.required} 已满足（${verdicts[t.score.acceptance.status]||t.score.acceptance.status}）`],['本次快照检查',latest?`${latest.checks.filter(c=>c.status==='passed').length} 通过 / ${latest.checks.length} 已执行 / ${latest.checksConfigured} 已配置`:'尚无回收'],['规则与宿主条件',latest?(latest.harnessUnchanged&&latest.hostUnchanged?'已检查的文件指纹一致':'已检查的文件指纹发生变化'):'尚未核对'],['个人约束',review?`${Object.values(review.constraints||{}).filter(v=>v==='met').length} 已满足 / ${Object.keys(review.constraints||{}).length} 项`:'未复审'],['总 Token',t.usage?.totalTokens??'缺少有效原生日志'],['日志活动时长（秒）',t.usage?.activeSeconds??'未知'],['重复可靠性 / 每次成功成本','需要同条件独立重复与成本证据；当前不估算'],['人工介入次数','当前尚未完整采集，不用轮数代替']];
  return <section className="space-y-3"><h3 className="font-semibold">评测指标全貌</h3><div className="overflow-x-auto"><table className="w-full text-sm"><tbody>{rows.map(([label,value])=><tr className="border-b border-slate-200 dark:border-zinc-800" key={label}><th className="text-left p-3 font-medium">{label}</th><td className="p-3">{value}</td></tr>)}</tbody></table></div></section>;
}
