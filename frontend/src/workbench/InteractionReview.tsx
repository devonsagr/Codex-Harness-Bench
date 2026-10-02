import {Details} from './ui';

type Verdict='met'|'missed'|'unknown'|'not_applicable';
type Metric='request'|'correction'|'interruption';
type Ref={speaker:'user'|'assistant';quote:string};
export type DialogueEvidence={version:string;sha256:string;status:string;note:string;totalTurns:number;omittedTurns:number;turns:{id:string;user:string;assistant:string;incomplete:boolean}[]};
export type DialogueReview={version:string;evidenceSha256:string;status:string;note:string;totalTurns:number;omittedTurns:number;counts:Record<Metric,Record<Verdict,number>>;turns:{id:string;results:Record<Metric,{verdict:Verdict;reason:string;evidence:Ref[]}>}[]};
const metricKeys:Metric[]=['request','correction','interruption'];
const metrics:Record<Metric,{label:string;criterion:string;boundary:string}>={
  request:{label:'回答是否切题',criterion:'直接回应本轮的核心请求，并说清结果。答非所问或只有承诺，记为偏离。',boundary:'需要实际运行才能确认的结果，保留未判定。'},
  correction:{label:'是否听进纠正',criterion:'用户明确纠正表达或方向后，后续回答按纠正更新；继续重复原偏差，记为偏离。',boundary:'没有纠正时不适用；代码是否改好另看产物验收。'},
  interruption:{label:'追问是否必要',criterion:'确实缺少信息或授权时追问；重复问已经回答的问题、反复索取已有授权，记为偏离。',boundary:'没有追问或停顿时不适用，不奖励盲目执行。'},
};
const verdicts:Record<Verdict,string>={met:'符合',missed:'偏离',unknown:'未判定',not_applicable:'不适用'};

export function InteractionReview({evidence,report}:{evidence?:DialogueEvidence;report?:DialogueReview}){
  const valid=report&&evidence&&report.evidenceSha256===evidence.sha256?report:undefined;
  const hasReport=!!valid?.turns.length;
  return <section className="interaction-review dialogue-review" aria-label="对话观察">
    <header className="dialogue-heading"><h3>对话观察</h3><span className="dialogue-scope">不计入总分</span></header>
    <p className="dialogue-intro">用本题的真实对话找出偏题、没有听进纠正和不必要追问，帮助你调整提示词与协作方式。代码是否做对，仍由产物验收判断。</p>
    <Details title="三项观察怎样判断">
      <div className="dialogue-criteria" role="list">
        {metricKeys.map(key=><section key={key} role="listitem"><h4>{metrics[key].label}</h4><p>{metrics[key].criterion}</p><p className="dialogue-boundary">{metrics[key].boundary}</p></section>)}
      </div>
      <p>逐回合结合此前文本判断，用用户和助手原话支持结论，不用长短、关键词或礼貌代替语义。材料缺失、截断或含未读取的图片时，保留未判定。</p>
    </Details>
    {!evidence?<div className="dialogue-state"><strong>没有封存对话</strong><p>旧快照没有这项材料。再次回收时会读取本题绑定的会话，旧报告保持原样；当前状态不表示沟通失败。</p></div>:<>
      <div className="dialogue-state">
        <strong>{hasReport?'已生成逐回合观察':evidence.turns.length?'对话已封存，观察尚未完成':'没有可审查的对话'}</strong>
        <p>已封存 {evidence.turns.length} / {evidence.totalTurns} 个可见文本回合{evidence.omittedTurns>0?`，另有 ${evidence.omittedTurns} 回合未纳入`:''}。</p>
        {evidence.note&&<p>{evidence.note}</p>}
        {!hasReport&&<p>{report&&!valid?'现有报告与这份对话材料不匹配，因此不显示旧判断。':evidence.turns.length?'运行独立 AI 审查时，会一并观察这些回合；原题程序验收不依赖这项意见。':'没有材料可判断，结果保持未知。'} 未判定或报告尚未生成，都不代表失败。</p>}
      </div>
      {hasReport&&valid&&<>
        <div className="dialogue-metrics" aria-label="三项对话观察汇总">
          {metricKeys.map(key=>{const counts=valid.counts[key];return <section key={key}>
            <h4>{metrics[key].label}</h4>
            <dl><div><dt>符合</dt><dd>{counts.met} 次</dd></div><div><dt>偏离</dt><dd>{counts.missed} 次</dd></div><div><dt>未判定</dt><dd>{counts.unknown} 次</dd></div><div><dt>不适用</dt><dd>{counts.not_applicable} 次</dd></div></dl>
          </section>;})}
        </div>
        <p className="dialogue-limit">这些次数是逐回合的 AI 意见，尚未校准，不能当成沟通能力分。原话引用已经核对，缺项不算通过。</p>
        <Details title={`逐回合判断与引用 · ${valid.turns.length} 回合`}>
          <div className="dialogue-turns">{valid.turns.map(turn=><section className="dialogue-turn" key={turn.id}>
            <h4>回合 {turn.id}</h4>
            {metricKeys.map(key=>{const item=turn.results[key];return <section className="dialogue-judgment" key={key}>
              <header><h5>{metrics[key].label}</h5><span className={`dialogue-verdict dialogue-verdict-${item.verdict}`}>{verdicts[item.verdict]}</span></header>
              <p>{item.reason}</p>
              <div className="dialogue-quotes">{item.evidence.map((ref,i)=><blockquote key={i}><cite>{ref.speaker==='user'?'用户原话':'助手原话'}</cite><p>{ref.quote}</p></blockquote>)}</div>
            </section>;})}
          </section>)}</div>
        </Details>
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
