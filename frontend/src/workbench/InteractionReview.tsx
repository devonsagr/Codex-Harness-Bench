import {Details} from './ui';

type Verdict='met'|'missed'|'unknown'|'not_applicable';
type Metric='request'|'correction'|'interruption';
type Ref={speaker:'user'|'assistant';quote:string};
export type DialogueEvidence={version:string;sha256:string;status:string;note:string;totalTurns:number;omittedTurns:number;turns:{id:string;user:string;assistant:string;incomplete:boolean}[]};
export type DialogueReview={version:string;evidenceSha256:string;status:string;note:string;totalTurns:number;omittedTurns:number;counts:Record<Metric,Record<Verdict,number>>;turns:{id:string;results:Record<Metric,{verdict:Verdict;reason:string;evidence:Ref[]}>}[]};
const keys:Metric[]=['request','correction','interruption'];
const labels:Record<Metric,string>={request:'回应请求',correction:'接受纠正',interruption:'追问必要性'};
const verdicts:Record<Verdict,string>={met:'符合',missed:'偏离',unknown:'未判定',not_applicable:'不适用'};

export function InteractionReview({evidence,report,scoringWeight=0}:{evidence?:DialogueEvidence;report?:DialogueReview;scoringWeight?:number}){
  const valid=report&&evidence&&report.evidenceSha256===evidence.sha256?report:undefined;
  const judged=valid?.turns.some(turn=>keys.some(key=>['met','missed'].includes(turn.results[key].verdict)));
  return <section className="dialogue-evidence" aria-label="对话证据">
    <p>判定由本次 AI 裁判完成：逐回合对照用户请求、纠正和助手回答，引用原话给出结论。程序只核对引用与统计次数，同一次产物评分会读取这些材料。</p>
    <p>{scoringWeight>0?`本题已设置“沟通体感”维度，权重 ${scoringWeight}%。AI 按该维度量表给分，以下对话用于支持判断；回合次数不另加分。`:'本题未设置沟通评分维度。以下对话保留为审查附件，不额外计入单题总分或雷达。'}</p>
    <Details title="判定依据"><dl className="score-rules"><div><dt>回应请求</dt><dd>回答是否直接回应本轮核心请求并说明结果；偏题或只承诺而无回应记为偏离。</dd></div><div><dt>接受纠正</dt><dd>用户明确纠正后，后续回答是否按纠正更新；没有纠正机会时不适用。代码修改效果由产物证据另行核实。</dd></div><div><dt>追问必要性</dt><dd>是否确实缺少必要信息或授权；重复追问已答信息、索取已有授权记为偏离。没有追问时不适用。</dd></div></dl></Details>
    {!evidence?<p>此快照没有封存对话。</p>:<>
      <p>已封存 {evidence.turns.length} / {evidence.totalTurns} 个文本回合{evidence.omittedTurns?`，另有 ${evidence.omittedTurns} 回合未纳入`:''}。{valid?(judged?'AI 对话判定与引用见下方。':'这份 AI 报告没有可用的对话判定，保留原始文本。'):'尚无匹配这份材料的 AI 对话判定。'}</p>
      {judged&&valid&&<Details title={`AI 逐回合判定 · ${valid.turns.length} 回合`}>
        <div className="dialogue-turns">{valid.turns.map(turn=><section className="dialogue-turn" key={turn.id}><h4>回合 {turn.id}</h4>{keys.map(key=>{const item=turn.results[key];return <section className="dialogue-judgment" key={key}><header><h5>{labels[key]}</h5><span className={`dialogue-verdict dialogue-verdict-${item.verdict}`}>{verdicts[item.verdict]}</span></header><p>{item.reason}</p><div className="dialogue-quotes">{item.evidence.map((ref,i)=><blockquote key={i}><cite>{ref.speaker==='user'?'用户原话':'助手原话'}</cite><p>{ref.quote}</p></blockquote>)}</div></section>;})}</section>)}</div>
      </Details>}
      {evidence.turns.length>0&&<Details title={`封存原文 · ${evidence.turns.length} 回合`}><div className="dialogue-turns">{evidence.turns.map(turn=><section className="dialogue-turn" key={turn.id}><h4>回合 {turn.id}{turn.incomplete?' · 材料不完整':''}</h4><div className="dialogue-transcript"><section><h5>用户</h5><pre className="source">{turn.user}</pre></section><section><h5>助手</h5><pre className="source">{turn.assistant||'尚无回复'}</pre></section></div></section>)}</div></Details>}
      <Details title="材料与报告记录"><dl className="dialogue-record"><div><dt>对话版本</dt><dd>{evidence.version}</dd></div><div><dt>材料范围</dt><dd>{evidence.note}</dd></div><div><dt>材料 SHA-256</dt><dd>{evidence.sha256}</dd></div>{report&&<><div><dt>报告版本</dt><dd>{report.version}</dd></div><div><dt>报告状态</dt><dd>{report.status}</dd></div><div><dt>报告对应材料</dt><dd>{report.evidenceSha256}</dd></div><div><dt>原始回合统计</dt><dd>{keys.map(key=><p key={key}>{labels[key]}：{Object.entries(report.counts[key]).map(([status,count])=>`${verdicts[status as Verdict]} ${count}`).join(' · ')}</p>)}</dd></div>{report.note&&<div><dt>报告备注</dt><dd>{report.note}</dd></div>}</>}</dl></Details>
    </>}
  </section>;
}
