"""Pure allocation-ranking rules for the Per Vices smart allocation plugin."""
PASSIVE_FOOTPRINT_SPILLAGE = {"0201":200,"0402":100,"0603":50,"0805":25,"1206":20,"1210":20}
LOW_COST_REEL_THRESHOLD = 0.15

def _txt(v): return str(v or "").strip()
def location_name(stock):
    loc=getattr(stock,"location",None)
    return "" if loc is None else _txt(getattr(loc,"name",None) or loc)
def is_component_room(stock): return "component room" in location_name(stock).lower()
def is_out_for_assembly(stock): return location_name(stock).lower().startswith("out-for-assembly")
def packaging(stock):
    for obj in (stock,getattr(stock,"supplier_part",None)):
        if obj is not None:
            for attr in ("packaging","packaging_type"):
                v=getattr(obj,attr,None)
                if v: return _txt(v)
    return ""
def is_reel(stock):
    p=packaging(stock).lower(); return "reel" in p or "spool" in p
def purchase_price(stock):
    v=getattr(stock,"purchase_price",None)
    try: return None if v is None else float(getattr(v,"amount",v))
    except (TypeError,ValueError): return None
def quantity(stock):
    try: return float(getattr(stock,"quantity",0) or 0)
    except (TypeError,ValueError): return 0.0
def relation_rank(stock,required_part):
    part=getattr(stock,"part",None)
    if part is None or required_part is None: return 2
    return 0 if getattr(part,"pk",None)==getattr(required_part,"pk",None) else 1

def rank_stock_items(stock_items,required_part=None,required_qty=0):
    req=max(float(required_qty or 0),0.0)
    def key(stock):
        q=quantity(stock); enough=q>=req if req>0 else True; price=purchase_price(stock)
        cheap_reel=price is not None and price<LOW_COST_REEL_THRESHOLD and is_reel(stock)
        return (1 if is_out_for_assembly(stock) else 0,0 if is_component_room(stock) else 1,
                relation_rank(stock,required_part),0 if cheap_reel else 1,0 if enough else 1,
                q if enough else -q,getattr(stock,"pk",0) or 0)
    return sorted(list(stock_items),key=key)

def normalize_footprint(value):
    s=_txt(value).upper().replace("-","").replace("_","").replace(" ","")
    return next((fp for fp in PASSIVE_FOOTPRINT_SPILLAGE if fp in s),"")

def planned_spillage(part,build_qty=1):
    for attr in ("footprint","package","case_package"):
        fp=normalize_footprint(getattr(part,attr,None))
        if fp: return PASSIVE_FOOTPRINT_SPILLAGE[fp],f"footprint:{fp}"
    price=None
    for attr in ("pricing_max","price","purchase_price"):
        v=getattr(part,attr,None)
        try:
            if v is not None: price=float(getattr(v,"amount",v)); break
        except (TypeError,ValueError): pass
    if price is None: return 5,"fallback:missing-price"
    if price>200: return 0,"fallback:price>200"
    if price>50: return 1,"fallback:50<price<=200"
    if price>10: return 2,"fallback:10<price<=50"
    return 5,"fallback:price<=10"
