import {Details} from './ui';

type Verdict='met'|'missed'|'unknown'|'not_applicable';
type Metric='request'|'correction'|'interruption';
type Ref={speaker:'user'|'assistant';quote:string};
export type DialogueEvidence={version:string;sha256:string;status:string;note:string;totalTurns:number;omittedTurns:number;turns:{id:string;user:string;assistant:string;incomplete:boolean}[]};
export type DialogueReview={version:string;evidenceSha256:string;status:string;note:string;totalTurns:number;omittedTurns:number;counts:Record<Metric,Record<Verdict,number>>;turns:{id:string;results:Record<Metric,{verdict:Verdict;reason:string;evidence:Ref[]}>}[]};
const metrics:Record<Metric,string>={request:'回答切中请求',correction:'回答落实纠正',interruption:'避免不必要打断'};
const verdicts:Record<Verdict,string>={met:'符合',missed:'偏离',unknown:'未知',not_applicable:'不适用'};

export function InteractionReview({evidence,report}:{evidence?:DialogueEvidence;report?:DialogueReview}){
  const valid=report&&evidence&&report.evidenceSha256===evidence.sha256?report:undefined;
  return <section className="interaction-review" aria-label="人机对话观察"><h3>这次沟通哪里出了问题</h3>
    <p className="muted">按真实回合看回答是否切题、纠正是否进入回答、追问是否必要。代码是否改好仍看产物验收；这些观察不加进总分。</p>
    {!evidence?<p>旧快照没有封存对话。再次回收会读取本题绑定会话，旧报告保持原样。</p>:<>
      <p>已封存 {evidence.turns.length}/{evidence.totalTurns} 个可见文本回合{evidence.omittedTurns>0?`，另有 ${evidence.omittedTurns} 回合未纳入`:''}。{evidence.note}</p>
      {valid&&valid.turns.length>0?<><div className="interaction-counts">{(Object.keys(metrics) as Metric[]).map(key=>{
        const row=valid.counts[key];return <section key={key}><h4>{metrics[key]}</h4><p><strong>{row.missed} 次偏离</strong> · {row.met} 次符合</p><small>{row.unknown} 次未知 · {row.not_applicable} 次不适用</small></section>;
      })}</div><p className="muted">全部纳入回合均列出，缺项不算通过；引用已经核对，语义判断仍是未校准的 AI 意见。</p>
      <Details title="逐回合判断与原话">{valid.turns.map(turn=><section className="interaction-turn" key={turn.id}><h4>{turn.id}</h4>{(Object.keys(metrics) as Metric[]).map(key=>{const item=turn.results[key];return <div key={key}><strong>{metrics[key]} · {verdicts[item.verdict]}</strong><p>{item.reason}</p>{item.evidence.map((ref,i)=><blockquote key={i}><small>{ref.speaker==='user'?'用户':'助手'}</small><p>{ref.quote}</p></blockquote>)}</div>;})}</section>)}</Details></>:<p>{evidence.turns.length?'使用机器评分的独立 AI 审查时，会一并检查这些回合。原题程序验收不依赖这项意见。':'没有可审查的对话，沟通结果保持未知。'}</p>}
      {evidence.turns.length>0&&<Details title="查看将交给裁判的对话文本">{evidence.turns.map(turn=><section className="interaction-turn" key={turn.id}><h4>{turn.id}{turn.incomplete?' · 材料不完整':''}</h4><strong>用户</strong><pre className="source">{turn.user}</pre><strong>助手</strong><pre className="source">{turn.assistant||'尚无可见回复'}</pre></section>)}</Details>}
    </>}
  </section>;
}
