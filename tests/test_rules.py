from inventree_smart_build_allocation.rules import rank_stock_items
class O:
    def __init__(self,**kw):self.__dict__.update(kw)
def stock(pk,qty,loc,pack='',price=1):
    return O(pk=pk,quantity=qty,location=O(name=loc),part=O(pk=1),purchase_price=price,supplier_part=O(packaging=pack))
def test_component_room_smallest_suitable():
    xs=[stock(1,500,'Component Room'),stock(2,75,'Component Room'),stock(3,65,'Storage Room')]
    assert rank_stock_items(xs,O(pk=1),60)[0].pk==2
def test_out_for_assembly_excluded_without_group_use():
    xs=[stock(1,60,'out-for-assembly-x'),stock(2,75,'Component Room')]
    out=rank_stock_items(xs,O(pk=1),60,group_build_ids=[10])
    assert [x.pk for x in out]==[2]
