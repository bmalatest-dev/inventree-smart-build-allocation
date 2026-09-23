from types import SimpleNamespace
from inventree_smart_build_allocation.rules import rank_stock_items

def stock(pk,qty,loc,price=1.0,packaging="cut tape",part_pk=1):
    return SimpleNamespace(pk=pk,quantity=qty,purchase_price=price,packaging=packaging,part=SimpleNamespace(pk=part_pk),location=SimpleNamespace(name=loc))
def test_component_room_first():
    assert rank_stock_items([stock(1,100,"Storage Room"),stock(2,100,"Main Component Room")],SimpleNamespace(pk=1),50)[0].pk==2
def test_smallest_sufficient():
    assert rank_stock_items([stock(1,500,"Component Room"),stock(2,100,"Component Room"),stock(3,20,"Component Room")],SimpleNamespace(pk=1),50)[0].pk==2
def test_out_for_assembly_last():
    assert rank_stock_items([stock(1,50,"out-for-assembly - BO-1"),stock(2,500,"Storage Room")],SimpleNamespace(pk=1),40)[0].pk==2
def test_low_cost_reel_preferred():
    assert rank_stock_items([stock(1,100,"Component Room",0.10,"cut tape"),stock(2,500,"Component Room",0.10,"reel")],SimpleNamespace(pk=1),50)[0].pk==2
def test_exact_part_before_variant():
    assert rank_stock_items([stock(1,100,"Component Room",part_pk=2),stock(2,100,"Component Room",part_pk=1)],SimpleNamespace(pk=1),50)[0].pk==2
