/* Browser facts, not grades: small metadata and intentional ellipsis need context. */
function collectReadability() {
  const textRows=[], concerns=[];
  const round=n=>Math.round(n*100)/100;
  const box=r=>({x:round(r.x),y:round(r.y),width:round(r.width),height:round(r.height)});
  const visible=el=>el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true});
  const locator=el=>el.id?'#'+el.id:[el.tagName.toLowerCase(),...Array.from(el.classList).slice(0,2)].join('.');
  const category=el=>el.closest('svg,canvas')?'graphic':el.closest('small,footer')?'metadata':
    el.closest('button,label,input,select,textarea,[role="button"]')?'control':'body';
  const add=row=>{if(concerns.length<32)concerns.push(row);};
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  let node,visited=0;
  while((node=walker.nextNode())&&visited++<3000&&textRows.length<180){
    const el=node.parentElement,text=node.textContent.replace(/\s+/g,' ').trim();
    if(!el||!text||el.closest('script,style,noscript,template,[hidden],[aria-hidden="true"]')||!visible(el))continue;
    const range=document.createRange();range.selectNodeContents(node);
    let rects=Array.from(range.getClientRects()).filter(r=>r.width>0&&r.height>0).slice(0,8);
    if(!rects.length)continue;
    const style=getComputedStyle(el),fontSize=parseFloat(style.fontSize),role=category(el);
    const row={text:text.slice(0,120),selector:locator(el),role,fontSize:round(fontSize),lineHeight:style.lineHeight,bounds:box(range.getBoundingClientRect())};
    if(fontSize<12&&role!=='metadata'&&role!=='graphic')add({kind:'small-text',...row});
    let clipped=false;
    for(let parent=el;parent&&parent!==document.body;parent=parent.parentElement){
      const css=getComputedStyle(parent),r=parent.getBoundingClientRect();
      const clipX=['hidden','clip'].includes(css.overflowX),clipY=['hidden','clip'].includes(css.overflowY);
      const bounds=range.getBoundingClientRect();
      if((clipX&&(bounds.left<r.left-1||bounds.right>r.right+1))||(clipY&&(bounds.top<r.top-1||bounds.bottom>r.bottom+1))){
        if(!clipped)add({kind:'clipped-text',...row,container:locator(parent)});
        clipped=true;
      }
      // Hidden portions of a clipped line do not overlap other visible text.
      if(clipX||clipY)rects=rects.map(s=>{
        const left=clipX?Math.max(s.left,r.left):s.left,right=clipX?Math.min(s.right,r.right):s.right;
        const top=clipY?Math.max(s.top,r.top):s.top,bottom=clipY?Math.min(s.bottom,r.bottom):s.bottom;
        return {left,right,top,bottom,width:right-left,height:bottom-top};
      }).filter(s=>s.width>0&&s.height>0);
    }
    textRows.push({row,el,rects});
  }
  for(let i=0;i<textRows.length;i++)for(let j=i+1;j<textRows.length;j++){
    const a=textRows[i],b=textRows[j];
    if(a.el===b.el||a.el.contains(b.el)||b.el.contains(a.el)||a.row.role==='graphic'||b.row.role==='graphic')continue;
    const overlap=a.rects.some(r=>b.rects.some(s=>{
      const w=Math.min(r.right,s.right)-Math.max(r.left,s.left),h=Math.min(r.bottom,s.bottom)-Math.max(r.top,s.top);
      return w>2&&h>2&&w*h>Math.min(r.width*r.height,s.width*s.height)*.2;
    }));
    if(overlap)add({kind:'overlapping-text',...a.row,otherText:b.row.text,otherSelector:b.row.selector});
  }
  const controls=Array.from(document.querySelectorAll('button,input,select,textarea,[role="button"]')).filter(visible).slice(0,100);
  for(const el of controls){
    let r=el.getBoundingClientRect();
    const fontSize=parseFloat(getComputedStyle(el).fontSize);
    if(['INPUT','SELECT','TEXTAREA'].includes(el.tagName)&&fontSize<12){
      const text=(el.getAttribute('placeholder')||el.getAttribute('aria-label')||el.labels?.[0]?.innerText||el.tagName.toLowerCase()).slice(0,120);
      add({kind:'small-text',selector:locator(el),role:'control',text,fontSize:round(fontSize),bounds:box(r)});
    }
    if(el.labels?.length&&visible(el.labels[0])){
      const label=el.labels[0].getBoundingClientRect();
      r={x:Math.min(r.x,label.x),y:Math.min(r.y,label.y),width:Math.max(r.right,label.right)-Math.min(r.left,label.left),height:Math.max(r.bottom,label.bottom)-Math.min(r.top,label.top)};
    }
    if(r.width>0&&r.height>0&&(r.width<24||r.height<24))add({kind:'small-control',selector:locator(el),text:(el.innerText||el.getAttribute('aria-label')||el.type||'').slice(0,120),bounds:box(r)});
  }
  const body=textRows.filter(r=>r.row.role==='body');
  return {version:'browser-readability-v1',viewport:{width:innerWidth,height:innerHeight},
    sampledText:textRows.length,sampledControls:controls.length,
    smallestBodyFont:body.length?Math.min(...body.map(r=>r.row.fontSize)):null,
    concerns,limited:visited>=3000||textRows.length>=180||controls.length>=100||concerns.length>=32,
    note:'字号12px与点击区域24px是定位风险的触发值，不是自动扣分或通用合规判定。元数据、图注、间距、缩略和实际任务要结合页面核实。'};
}
module.exports={collectReadability};
