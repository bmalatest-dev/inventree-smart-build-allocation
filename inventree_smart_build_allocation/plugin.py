from plugin import InvenTreePlugin
from plugin.mixins import AllocateMixin, SettingsMixin, UserInterfaceMixin
from . import PLUGIN_VERSION
from .rules import rank_stock_items

class SmartBuildAllocationPlugin(SettingsMixin,UserInterfaceMixin,AllocateMixin,InvenTreePlugin):
    NAME="SmartBuildAllocation"; SLUG="smartbuildallocation"; TITLE="Smart Build Allocation"
    DESCRIPTION="Per Vices stock-selection rules for Build Order allocation"
    VERSION=PLUGIN_VERSION; AUTHOR="Per Vices Corporation"; LICENSE="MIT"
    SETTINGS={
      "COMPONENT_ROOM_TEXT":{"name":"Component Room location text","description":"Preferred stock location text (case-insensitive)","default":"component room"},
      "LOW_COST_REEL_THRESHOLD":{"name":"Low-cost reel preference threshold","description":"Prefer reel packaging below this unit purchase price","default":0.15,"validator":float},
    }
    def filter_build_allocation(self,build_line,stock_items,**kwargs):
        if not stock_items: return stock_items
        required=max(float(getattr(build_line,"quantity",0) or 0)-float(getattr(build_line,"allocated",0) or 0),0)
        return rank_stock_items(stock_items,getattr(build_line,"part",None),required)
    def get_ui_panels(self,request,context,**kwargs):
        model=str(context.get("model") or context.get("model_type") or "").lower()
        if model and "build" not in model: return []
        return [{"key":"smart-build-allocation","title":"Smart Allocation","description":"Per Vices stock-selection rules for this Build Order","icon":"ti:arrows-sort","source":self.plugin_static_file("smart_allocation.js:renderPanel"),"context":{"version":self.VERSION}}]
