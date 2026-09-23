export function renderPanel(context) {
  const React=globalThis.React; const e=React?.createElement; if(!e) return null;
  const rules=[
    'Existing manual allocations are left untouched.',
    'Prefer locations containing "component room" (case-insensitive).',
    'Treat locations starting with "out-for-assembly" as last-resort candidates.',
    'Prefer exact parts; variants / substitutes remain review items.',
    'For low-cost parts (< $0.15/pc), prefer reel / spool packaging where available.',
    'When possible, prefer the smallest stock item which satisfies the outstanding requirement.',
    'Multiple stock items may be used when a single item cannot satisfy the requirement.'
  ];
  return e('div',{style:{padding:'12px'}},
    e('div',{style:{padding:'10px',border:'1px solid #aaa',borderRadius:'4px',marginBottom:'10px'}},
      e('strong',null,'V0.1.0 test mode'),e('div',null,'Use the normal InvenTree Auto Allocate action. This plugin reorders InvenTree candidate stock before allocations are created.')),
    e('ul',null,...rules.map((r,i)=>e('li',{key:i},r))),
    e('div',{style:{fontSize:'0.9em'}},'Spillage rules are included in the package, but v0.1.0 intentionally does not add quantity beyond the BO requirement. Preview / Review / Commit with spillage is the next stage after candidate-order testing.'));
}
