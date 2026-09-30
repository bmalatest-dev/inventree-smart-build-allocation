"""Allocation rules for Per Vices Smart Build Allocation v0.2.0."""
PASSIVE_FOOTPRINT_SPILLAGE = {"0201":200,"0402":100,"0603":50,"0805":25,"1206":20,"1210":20}
LOW_COST_REEL_THRESHOLD = 0.15

def _txt(v): return str(v or "").strip()
def _num(v, default=0.0):
    try: return float(getattr(v,"amount",v))
    except (TypeError,ValueError): return default

def location_name(stock):
    loc=getattr(stock,"location",None)
    return "" if loc is None else _txt(getattr(loc,"name",None) or loc)
def is_component_room(stock): return "component room" in location_name(stock).lower()
def is_rework_room(stock): return "rework" in location_name(stock).lower()
def is_storage_room(stock): return "storage" in location_name(stock).lower()
def is_out_for_assembly(stock): return location_name(stock).lower().startswith("out-for-assembly")

def packaging(stock):
    for obj in (stock,getattr(stock,"supplier_part",None)):
        if obj is not None:
            for attr in ("packaging","packaging_type"):
                v=getattr(obj,attr,None)
                if v: return _txt(v)
    return ""
def packaging_rank(stock):
    p=packaging(stock).lower().replace('_',' ').replace('-',' ')
    if 'reel' in p or 'spool' in p: return 0
    if 'tray' in p: return 1
    if 'tube' in p: return 2
    if 'cut' in p and 'tape' in p: return 3
    return 4
def is_reel(stock): return packaging_rank(stock)==0

def purchase_price(stock):
    v=getattr(stock,"purchase_price",None)
    if v is None:
        sp=getattr(stock,"supplier_part",None)
        v=getattr(sp,"price",None) if sp else None
    return None if v is None else _num(v,None)

def quantity(stock): return _num(getattr(stock,"quantity",0),0.0)
def available_quantity(stock):
    # Prefer InvenTree's own availability properties when exposed by the model.
    for attr in ("available_stock","available_quantity","available"):
        v=getattr(stock,attr,None)
        if v is not None and not callable(v):
            n=_num(v,None)
            if n is not None: return n
    return quantity(stock)

def relation_rank(stock,required_part):
    part=getattr(stock,"part",None)
    if part is None or required_part is None: return 2
    return 0 if getattr(part,"pk",None)==getattr(required_part,"pk",None) else 1

def _allocation_build_id(allocation):
    build=getattr(allocation,"build",None)
    if build is not None: return getattr(build,"pk",None)
    line=getattr(allocation,"build_line",None) or getattr(allocation,"line",None)
    build=getattr(line,"build",None) if line is not None else None
    if build is not None: return getattr(build,"pk",None)
    item=getattr(allocation,"build_item",None)
    build=getattr(item,"build",None) if item is not None else None
    return getattr(build,"pk",None) if build is not None else None

def allocation_build_ids(stock):
    ids=set()
    for attr in ("allocations","build_allocations","builditem_set","build_items"):
        rel=getattr(stock,attr,None)
        if rel is None: continue
        try: vals=rel.all() if hasattr(rel,'all') else list(rel)
        except Exception: continue
        for a in vals:
            bid=_allocation_build_id(a)
            if bid is not None: ids.add(int(bid))
    return ids

def stock_used_by_group(stock,group_build_ids):
    return bool(allocation_build_ids(stock) & set(group_build_ids or []))

def part_parameter(part,name):
    if part is None:return None
    target=name.strip().lower()
    rel=getattr(part,"parameters",None) or getattr(part,"parameter_set",None)
    if rel is None:return None
    try: vals=rel.all() if hasattr(rel,'all') else list(rel)
    except Exception:return None
    for param in vals:
        template=getattr(param,"template",None)
        pname=_txt(getattr(template,"name",None) or getattr(param,"name",None)).lower()
        if pname==target:
            for attr in ("data","value","value_text"):
                v=getattr(param,attr,None)
                if v not in (None,""):return _txt(v)
    return None

def is_hand_placement(part): return _txt(part_parameter(part,"Hand Placement")).lower() in {"yes","true","1","y"}

def rank_stock_items(stock_items,required_part=None,required_qty=0,group_build_ids=None):
    """Rank candidates using the v0.2 workflow.

    Group stock already committed to one of the selected sequential BOs is preferred.
    Out-for-assembly stock outside the selected group is excluded from automatic allocation;
    it belongs in the future LOCATION WARNING / review path instead.
    """
    req=max(_num(required_qty,0),0.0); group=set(int(x) for x in (group_build_ids or []))
    hand=is_hand_placement(required_part)
    candidates=[]
    for stock in list(stock_items):
        group_use=stock_used_by_group(stock,group)
        if is_out_for_assembly(stock) and not group_use:
            continue
        candidates.append(stock)
    def key(stock):
        q=available_quantity(stock); enough=q>=req if req>0 else True
        group_use=stock_used_by_group(stock,group)
        price=purchase_price(stock); cheap_reel=price is not None and price<LOW_COST_REEL_THRESHOLD and is_reel(stock)
        if hand:
            # Hand-placement parts may intentionally consume partial packages and use non-standard locations.
            loc_rank=0 if is_component_room(stock) else (1 if is_rework_room(stock) else (2 if is_storage_room(stock) else 3))
            package_choice=(0 if enough else 1, q if enough else -q)
        else:
            loc_rank=0 if is_component_room(stock) else 1
            package_choice=(0 if enough else 1, q if enough else -q)
        return (
            0 if group_use else 1,
            relation_rank(stock,required_part),
            loc_rank,
            0 if cheap_reel else 1,
            packaging_rank(stock) if not hand else 0,
            *package_choice,
            getattr(stock,"pk",0) or 0,
        )
    return sorted(candidates,key=key)

def normalize_footprint(value):
    s=_txt(value).upper().replace("-","").replace("_","").replace(" ","")
    return next((fp for fp in PASSIVE_FOOTPRINT_SPILLAGE if fp in s),"")
def planned_spillage(part,build_qty=1):
    for attr in ("footprint","package","case_package"):
        fp=normalize_footprint(getattr(part,attr,None))
        if fp:return PASSIVE_FOOTPRINT_SPILLAGE[fp],f"footprint:{fp}"
    price=None
    for attr in ("pricing_max","price","purchase_price"):
        v=getattr(part,attr,None)
        try:
            if v is not None:price=float(getattr(v,"amount",v));break
        except (TypeError,ValueError):pass
    if price is None:return 5,"fallback:missing-price"
    if price>200:return 0,"fallback:price>200"
    if price>50:return 1,"fallback:50<price<=200"
    if price>10:return 2,"fallback:10<price<=50"
    return 5,"fallback:price<=10"
