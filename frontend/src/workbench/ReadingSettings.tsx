import {useEffect,useState} from 'react';
const fonts=[['yahei','微软雅黑'],['deng','等线'],['song','宋体'],['kai','楷体'],['system','系统字体']];
export function ReadingSettings(){
  const [font,setFont]=useState(()=>localStorage.getItem('chb_font')||'yahei');
  const [size,setSize]=useState(()=>localStorage.getItem('chb_font_size')||'18');
  useEffect(()=>{document.documentElement.dataset.readingFont=font;localStorage.setItem('chb_font',font);},[font]);
  useEffect(()=>{document.documentElement.style.fontSize=['16','18','20'].includes(size)?size+'px':'18px';localStorage.setItem('chb_font_size',size);},[size]);
  return <details className="reading-settings"><summary>字体与字号</summary><div className="panel p-4 space-y-3"><label>阅读字体<select aria-label="阅读字体" value={font} onChange={e=>setFont(e.target.value)}>{fonts.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label><label>字号<select aria-label="界面字号" value={size} onChange={e=>setSize(e.target.value)}><option value="16">标准</option><option value="18">舒适</option><option value="20">大字</option></select></label><p>中文阅读 Aa 0123</p><small>字体用于正文与规则编辑；导航保持清晰的无衬线字体，代码保持等宽。</small></div></details>;
}
