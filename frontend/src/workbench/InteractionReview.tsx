import {Details} from './ui';
import {useState} from 'react';
import {dialogueResult} from './presentation';

type Verdict='met'|'missed'|'unknown'|'not_applicable';
type Metric='request'|'correction'|'interruption';
type Ref={speaker:'user'|'assistant';quote:string};
export type DialogueEvidence={version:string;sha256:string;status:string;note:string;totalTurns:number;omittedTurns:number;turns:{id:string;user:string;assistant:string;incomplete:boolean}[]};
export type DialogueReview={version:string;evidenceSha256:string;status:string;note:string;totalTurns:number;omittedTurns:number;counts:Record<Metric,Record<Verdict,number>>;turns:{id:string;results:Record<Metric,{verdict:Verdict;reason:string;evidence:Ref[]}>}[]};
const metricKeys:Metric[]=['request','correction','interruption'];
const metrics:Record<Metric,{label:string;criterion:string;boundary:string}>={
  request:{label:'切题率',criterion:'直接回应本轮核心请求，并说清结果。答非所问或只有承诺，记为偏离。',boundary:'需要运行产物才能确认时，保留未判定。'},
  correction:{label:'纠正响应率',criterion:'用户明确纠正方向后，后续回答按纠正更新；重复原偏差，记为偏离。',boundary:'没有纠正时不适用；代码修改效果另看产物。'},
  interruption:{label:'必要追问率',criterion:'缺少必要信息或授权时追问；重复问已回答的问题、索取已有授权，记为偏离。',boundary:'没有追问或停顿时不适用，不奖励盲目执行。'},
};
const verdicts:Record<Verdict,string>={met:'符合',missed:'偏离',unknown:'未判定',not_applicable:'不适用'};

export function InteractionReview({evidence,report,onReview}:{evidence?:DialogueEvidence;report?:DialogueReview;onReview?:()=>void}){
  const valid=report&&evidence&&report.evidenceSha256===evidence.sha256?report:undefined;
  const hasReport=!!valid?.turns.length;
  const hasJudgments=metricKeys.some(key=>dialogueResult(valid?.counts[key]).judged>0);
  const hasIssues=!!valid?.turns.some(turn=>metricKeys.some(key=>turn.results[key].verdict==='missed'));
  const [onlyIssues,setOnlyIssues]=useState(true);
  const turns=valid?.turns.filter(turn=>!onlyIssues||!hasIssues||metricKeys.some(key=>turn.results[key].verdict==='missed'))||[];
  return <section className="interaction-review dialogue-review" aria-label="沟通与交互">
    <header className="dialogue-heading"><h3>沟通与交互</h3><span className="dialogue-scope">真实对话 · AI 判断</span></header>
    <p className="dialogue-intro">用来检查 Harness 是否减少偏题、重复纠正和无效追问。每项比例 = 符合次数 ÷ 可判定次数；未知和不适用不进分母。对比同模型、同题的记录更有意义；这些对话指标不自动计入单题总分或雷达。</p>
    <div className="dialogue-metrics" aria-label="沟通指标与评价标准">
      {metricKeys.map(key=>{const counts=valid?.counts[key],result=dialogueResult(counts);return <section key={key}>
        <h4>{metrics[key].label}</h4><p className="dialogue-rate">{result.rate==null?'未判定':`${result.rate}%`}</p>
        <p>{metrics[key].criterion}</p><p className="dialogue-boundary">{metrics[key].boundary}</p>
        {counts&&<dl><div><dt>符合 / 可判定</dt><dd>{counts.met} / {result.judged}</dd></div><div><dt>偏离</dt><dd>{counts.missed} 次</dd></div><div><dt>未知</dt><dd>{counts.unknown} 次</dd></div><div><dt>不适用</dt><dd>{counts.not_applicable} 次</dd></div></dl>}
      </section>;})}
    </div>
    {!evidence?<div className="dialogue-state"><strong>没有封存对话</strong><p>旧快照没有这项材料。再次回收时会读取本题绑定的会话，旧报告保持原样；当前状态不表示沟通失败。</p></div>:<>
      <div className="dialogue-state">
        <strong>{hasJudgments?'可查看逐回合判定与原话':hasReport?'对话已有报告，但没有可判定的沟通指标':evidence.turns.length?'对话已封存，指标尚未判定':'没有可审查的对话'}</strong>
        <p>已封存 {evidence.turns.length} / {evidence.totalTurns} 个可见文本回合{evidence.omittedTurns>0?`，另有 ${evidence.omittedTurns} 回合未纳入`:''}。</p>
        {evidence.note&&<p>{evidence.note}</p>}
        {!hasReport&&<p>{report&&!valid?'现有报告与这份对话材料不匹配，因此不显示旧判断。':evidence.turns.length?'运行独立 AI 审查时，会一并观察这些回合；原题程序验收不依赖这项意见。':'没有材料可判断，结果保持未知。'} 未判定或报告尚未生成，都不代表失败。</p>}
        {!hasJudgments&&evidence.turns.length>0&&onReview&&<button type="button" className="btn-secondary" onClick={onReview}>去 AI 评分审查对话</button>}
      </div>
      {hasReport&&valid&&<>
        <section className="dialogue-evidence"><header className="dialogue-heading"><h4>逐回合判定与原话 · {turns.length} / {valid.turns.length} 回合</h4><div className="run-actions"><button type="button" className="btn-secondary" disabled={!hasIssues} aria-pressed={onlyIssues&&hasIssues} onClick={()=>setOnlyIssues(true)}>只看偏离</button><button type="button" className="btn-secondary" aria-pressed={!onlyIssues||!hasIssues} onClick={()=>setOnlyIssues(false)}>全部回合</button></div></header>
          <div className="dialogue-turns">{turns.map(turn=><Details key={turn.id} title={`回合 ${turn.id} · ${metricKeys.filter(key=>turn.results[key].verdict==='missed').length} 项偏离`}>
            {metricKeys.map(key=>{const item=turn.results[key];return <section className="dialogue-judgment" key={key}>
              <header><h5>{metrics[key].label}</h5><span className={`dialogue-verdict dialogue-verdict-${item.verdict}`}>{verdicts[item.verdict]}</span></header>
              <p>{item.reason}</p>
              <div className="dialogue-quotes">{item.evidence.map((ref,i)=><blockquote key={i}><cite>{ref.speaker==='user'?'用户原话':'助手原话'}</cite><p>{ref.quote}</p></blockquote>)}</div>
            </section>;})}
          </Details>)}</div>
        </section>
      </>}
      {evidence.turns.length>0&&<Details title={`已封存的原始对话 · ${evidence.turns.length} 回合`}>
        <div className="dialogue-turns">{evidence.turns.map(turn=><section className="dialogue-turn" key={turn.id}>
          <header className="dialogue-turn-heading"><h4>回合 {turn.id}</h4>{turn.incomplete&&<span>材料不完整</span>}</header>
          <div className="dialogue-transcript"><section><h5>用户</h5><pre className="source">{turn.user}</pre></section><section><h5>助手</h5><pre className="source">{turn.assistant||'尚无可见回复'}</pre></section></div>
        </section>)}</div>
      </Details>}
      <Details title="材料范围与报告记录">
        <dl className="dialogue-record"><div><dt>对话版本</dt><dd>{evidence.version}</dd></div><div><dt>材料状态</dt><dd>{evidence.status}</dd></div><div><dt>材料 SHA-256</dt><dd>{evidence.sha256}</dd></div>
          {report&&<><div><dt>观察报告版本</dt><dd>{report.version}</dd></div><div><dt>报告状态</dt><dd>{report.status}</dd></div><div><dt>报告对应材料</dt><dd>{report.evidenceSha256}</dd></div><div><dt>报告回合范围</dt><dd>{report.totalTurns} 回合，未纳入 {report.omittedTurns} 回合</dd></div>{report.note&&<div><dt>报告备注</dt><dd>{report.note}</dd></div>}</>}
        </dl>
      </Details>
    </>}
  </section>;
}
