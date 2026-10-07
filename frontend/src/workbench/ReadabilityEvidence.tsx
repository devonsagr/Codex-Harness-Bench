import {Details} from './ui';
import type {ReadabilityConcern,ReadabilityReport} from './types';

const labels:Record<string,string>={'small-text':'文字偏小','clipped-text':'文字可能被裁切','overlapping-text':'文字区域重叠','small-control':'点击区域偏小'};
export function ReadabilityEvidence({data}:{data?:ReadabilityReport|null}){
  if(!data?.views.length)return null;
  const samples=new Map<string,{row:ReadabilityConcern;widths:Set<number>}>();
  for(const view of data.views)for(const row of view.concerns){
    const key=JSON.stringify([row.kind,row.selector,row.text,row.otherText]);
    if(!samples.has(key))samples.set(key,{row,widths:new Set()});
    samples.get(key)!.widths.add(view.viewport.width);
  }
  const fonts=data.views.map(view=>view.smallestBodyFont).filter((value):value is number=>value!=null);
  const viewWidths=[...new Set(data.views.map(view=>view.viewport.width))];
  const rows=[...samples.values()];
  return <Details title={`浏览器可读性记录 · ${viewWidths.length} 个窗口宽度`}>
    <p>检查宽度：{viewWidths.map(width=>`${width}px`).join('、')}。采样正文最小字号：{fonts.length?`${Math.min(...fonts)}px`:'没有正文样本'}。</p>
    {rows.length?<div className="score-table-scroll" tabIndex={0} role="region" aria-label="可读性样本，可横向滚动"><table className="score-summary-contributions"><thead><tr><th>观察</th><th>文字样本</th><th>出现的宽度</th><th>首次实测</th></tr></thead><tbody>{rows.slice(0,12).map(({row,widths},i)=><tr key={i}><td>{labels[row.kind]}</td><td>{row.text}{row.otherText&&<> / {row.otherText}</>}</td><td>{[...widths].join(' / ')}px</td><td>{row.fontSize!=null&&`${row.fontSize}px · `}{row.bounds.width} × {row.bounds.height}px</td></tr>)}</tbody></table>{rows.length>12&&<p>这里显示前 12 处，完整记录随报告保存。</p>}</div>:<p>采样范围内未触发文字或操作区域风险；业务流程、文案和审美仍需实际检查。</p>}
    <p>每个宽度最多采样 180 段文字、100 个控件。{data.views.some(view=>view.limited)?'本次达到采样上限，记录未覆盖全部内容。':'同一处风险已合并显示。'}正文/标签小于 12px、操作区域小于 24px 只提示风险；合理的缩略、元数据和操作间距需结合用途判断，不自动扣分。</p>
  </Details>;
}
