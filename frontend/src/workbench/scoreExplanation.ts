import {capabilityProfiles} from './capabilityProfiles';
import type {CapabilityAxis} from './capabilityProfiles';
import type {Run,Task,Trial} from './types';

/** Presentation only: all grades and radar facets come from saved scores/helpers. */
export function currentNativeResult(trial:Trial){
  const latest=trial.captures[trial.captures.length-1];
  return latest?.nativeVerifications?.find(row=>row.id===trial.score.nativeVerificationId&&row.captureHash===latest.manifest.sha256);
}

export function currentTrialAxes(run:Run,trial:Trial,task:Task):CapabilityAxis[]{
  const entry={run,trial,task,archived:false,eligible:false};
  const rows=task.publicSource&&!currentNativeResult(trial)?[]:[{task,mean:trial.score.overall??0,entries:[entry],protocolKey:'current-trial'}];
  return capabilityProfiles(rows)[0].axes;
}

export function batchScoreSummary(run:Run){
  const scored=run.trials.filter(row=>row.score.overall!=null);
  const native=run.trials.flatMap(row=>run.tasks.find(task=>task.id===row.taskId)?.publicSource?currentNativeResult(row)||[]:[]);
  const nativeTotal=run.trials.filter(row=>run.tasks.find(task=>task.id===row.taskId)?.publicSource).length;
  return {
    total:run.trials.length,scored:scored.length,
    mean:scored.length>0&&scored.length===run.trials.length?scored.reduce((sum,row)=>sum+row.score.overall!,0)/scored.length:null,
    nativeTotal,nativeVerified:native.length,nativePassed:native.filter(row=>row.reward===1).length,
    nativeRate:native.length?native.filter(row=>row.reward===1).length/native.length*100:null,
  };
}

export function totalScoreExplanation(run:Run,trial:Trial,task:Task){
  const {score}=trial,card=score.taskScorecard;
  const legacy=run.policy.version!=='arena-machine-v1';
  const missing=legacy?[...(run.policy.objectiveWeight>0&&score.objective==null?['脚本检查分']:[]),...(run.policy.humanWeight>0&&score.human==null?['人工分']:[])]:card?card.items.filter(row=>row.points==null).map(row=>row.label):Object.entries(score.effectiveScores||{}).filter(([,value])=>value==null).map(([key])=>run.policy.taskOverrides?.[task.id]?.rubrics[key]?.label||run.policy.rubrics?.[key]?.label||key);
  const version=card?.version;
  let formula:string;
  if(legacy){
    formula=`历史综合分 = 脚本检查分 × ${run.policy.objectiveWeight}% + 人工分 × ${run.policy.humanWeight}%；需要策略要求的证据齐全且交付结束。`;
  }else if(task.publicSource){
    formula=card?'本地单题分 = 目标功能语义组贡献（合计70分） + 旧功能回归贡献（20分） + 可维护性评分 × 10%。每个功能组及回归组必须整组通过，才得到该组全部分。':currentNativeResult(trial)?'原题验收只有通过或未通过；已取得当前快照的原题结果，但本题没有对应的本地连续评分卡。':'原题尚未验收，本地连续评分卡尚未形成。先取得当前快照的原题结果，再查看是否有对应评分卡；未验收不表示本题不支持连续评分。';
  }else if(version==='project-tasktype-v2'||version==='project-tasktype-v3'||version==='deepswe-local-v1'){
    formula='本地单题分 = 目标与范围贡献（60分） + 使用与可靠性贡献（25分） + 交付与维护贡献（15分）。组内贡献 = 各适用项分数 × 冻结权重之和。';
  }else if(version==='project-policy-v1'){
    formula='本地单题分 = Σ（适用项分数 × 冻结权重）÷ 适用项权重之和。分项先按权重换算贡献，再相加；未验证项不填0。';
  }else if(run.policy.version==='arena-machine-v1'){
    formula='本地单题分 = Σ（有效分项分数 × 冻结权重）÷ 适用项权重之和；此历史方案需要全项有分且交付结束。AI原始均值只平均已评分项，人工修正另存。';
  }else{
    formula=`历史综合分 = 脚本检查分 × ${run.policy.objectiveWeight}% + 人工分 × ${run.policy.humanWeight}%；需要策略要求的证据齐全且交付结束。`;
  }
  let status:string;
  if(score.overall!=null)status=legacy?'本次历史综合分已按冻结的脚本检查与人工权重计算，交付已结束。':task.publicSource?'当前快照的原题验收与本地连续评分卡已有结果。':trial.state==='completed'?'本题各适用项已计分，交付已结束。':'当前是暂定单题分，后续回收或修正会重新计算。';
  else if(!trial.captures.length)status='尚未回收作品，暂无可评分的快照。';
  else if(legacy)status=missing.length?'历史策略待补证据：'+missing.join('、')+'。':'历史策略所需分项已有结果，整题交付结束后才形成综合分。';
  else if(task.publicSource&&!card)status=currentNativeResult(trial)?'原题结果已保存；本题没有本地连续评分卡，暂不生成100分总分。':'先运行原题程序验收；环境失败或未执行保持待验证。';
  else if(missing.length)status='待补证据：'+missing.join('、')+'。';
  else if(score.machineReviewId&&trial.captures[trial.captures.length-1].stageIndex+1<task.stages.length&&trial.finalCaptureId!==trial.captures[trial.captures.length-1].id)status='当前是中间阶段快照，整题总分等待最终交付版本。';
  else if(!score.machineReviewId&&run.policy.version==='arena-machine-v1')status='尚无当前快照的有效AI报告；可先查看程序验收结果。';
  else status='该记录的完整评分或交付条件尚未满足，原有分项仍可查看。';
  return {formula,status,missing,version:version||run.policy.version};
}

export function programScoreExplanation(trial:Trial,task:Task){
  const native=currentNativeResult(trial),fixed=trial.score.programAcceptance;
  if(task.publicSource)return {label:'原题程序结果',value:native?native.reward===1?'通过':'未通过':'待验证',detail:native?`目标测试 ${native.f2p_passed}/${native.f2p_total}，回归测试 ${native.p2p_passed}/${native.p2p_total}。原题reward为${native.reward}，独立于本地质量分。`:'运行原题验收后，才有通过或未通过；未运行、超时和环境异常不记失败。'};
  if(fixed)return {label:fixed.scope,value:fixed.score==null?'待验证':`${fixed.score}%`,detail:`${fixed.passed}/${fixed.total} 通过，${fixed.failed} 失败，${fixed.unverified} 未验证。`+(fixed.version==='evalplus-originfmt-v1'?'整套扩展输入全部满足才判这题通过；这是程序结果，AI质量分另列。':fixed.version==='community-engine-v1'?'此比例只覆盖功能核心，不代表页面连接、视觉或完整流程。':'此比例只覆盖列出的固定测试。')};
  return {label:'脚本检查分',value:trial.score.objective==null?'待验证':`${trial.score.objective} / 100`,detail:'按配置检查的通过权重计算；只证明已检查的要求，不等同整题需求或视觉全部正确。'};
}
