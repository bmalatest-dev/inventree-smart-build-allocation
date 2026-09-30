export function renderPanel(props) {
  const React=globalThis.React; const e=React?.createElement; if(!e) return null;
  const cfg=props?.context || props || {};
  const buildId=cfg.build_id; const groupUrl=cfg.group_url;
  const [data,setData]=React.useState(null); const [selected,setSelected]=React.useState([]);
  const [msg,setMsg]=React.useState(''); const [busy,setBusy]=React.useState(false);
  const load=()=>{ if(!groupUrl)return; setBusy(true); fetch(groupUrl,{credentials:'same-origin'}).then(r=>r.json()).then(d=>{setData(d);setSelected(d.build_ids||[buildId]);setMsg('');}).catch(err=>setMsg(String(err))).finally(()=>setBusy(false)); };
  React.useEffect(load,[groupUrl]);
  const toggle=(id)=>{ if(id===buildId)return; setSelected(s=>s.includes(id)?s.filter(x=>x!==id):[...s,id]); };
  const save=()=>{setBusy(true);fetch(groupUrl,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':document.cookie.match(/csrftoken=([^;]+)/)?.[1]||''},body:JSON.stringify({build_ids:selected})}).then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.error||'Save failed');setSelected(d.build_ids||selected);setMsg('Shared Allocation Group saved. Auto Allocate will use this group.');}).catch(err=>setMsg(String(err))).finally(()=>setBusy(false));};
  const box={padding:'10px',border:'1px solid #bbb',borderRadius:'5px',marginBottom:'10px'};
  const warning={padding:'10px',border:'1px solid #d99',borderRadius:'5px',marginBottom:'10px'};
  return e('div',{style:{padding:'12px'}},
    e('div',{style:box},e('strong',null,'V0.2.0 — Shared Allocation Group'),
      e('p',null,'Select BOs which are being assembled at the same physical location sequentially (not concurrently). The plugin may intentionally prefer the same physical StockItem across these BOs to minimize packages sent.'),
      e('p',null,e('strong',null,'Do not group '),'BOs at different locations or BOs running concurrently.')),
    busy&&!data?e('div',null,'Loading Build Orders…'):null,
    data?e('div',{style:box},
      e('div',{style:{fontWeight:600,marginBottom:'8px'}},'Build Orders in this Shared Allocation Group'),
      e('div',{style:{maxHeight:'280px',overflow:'auto'}},...(data.builds||[]).map(b=>e('label',{key:b.pk,style:{display:'block',padding:'4px 0'}},
        e('input',{type:'checkbox',checked:selected.includes(b.pk),disabled:b.current,onChange:()=>toggle(b.pk)}),' ',b.label,b.current?' (current BO)':''))),
      e('button',{onClick:save,disabled:busy,style:{marginTop:'10px',padding:'6px 12px'}},busy?'Saving…':'Save Shared Allocation Group'),
      msg?e('div',{style:{marginTop:'8px'}},msg):null):null,
    e('div',{style:box},e('strong',null,'Implemented allocation behaviour'),e('ul',null,
      e('li',null,'Fully allocated BO lines remain handled by InvenTree; this plugin ranks candidates for outstanding requirements.'),
      e('li',null,'Stock already used by another BO in the selected group receives highest preference where it remains a valid InvenTree candidate.'),
      e('li',null,'Component Room remains preferred for standard parts.'),
      e('li',null,'Hand Placement = Yes enables Rework / Storage consideration and use-up-stock behaviour.'),
      e('li',null,'Low-cost genuine reels retain Send-a-Reel preference.'),
      e('li',null,'Standard machine-placement packaging ranks Reel → Tray → Tube → Cut Tape → Other.'),
      e('li',null,'Out-for-Assembly stock outside the selected group is removed from automatic allocation rather than silently consumed.')),
    e('div',{style:warning},e('strong',null,'V0.2 testing limitation'),
      e('p',null,'Use normal InvenTree Auto Allocate after saving the group. V0.2 implements group-aware candidate selection, but does not yet provide the final Preview / Sign-off / Commit screen. SPILLAGE, LOCATION and MULTI-STOCKITEM warnings are therefore not yet interactive. Do not use this test build for production allocation.'))
  );
}
