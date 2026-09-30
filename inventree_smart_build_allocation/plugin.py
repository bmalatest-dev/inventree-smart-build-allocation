import json
from django.core.cache import cache
from django.http import JsonResponse
from django.urls import path
from plugin import InvenTreePlugin
from plugin.mixins import AllocateMixin, SettingsMixin, UserInterfaceMixin, UrlsMixin
from . import PLUGIN_VERSION
from .rules import rank_stock_items

GROUP_TTL = 60 * 60 * 24 * 7

def _group_key(build_id): return f"smartbuildallocation:shared-group:{int(build_id)}"

def _build_label(build):
    ref=getattr(build,"reference",None) or getattr(build,"name",None) or f"BO-{build.pk}"
    title=getattr(build,"title",None) or getattr(build,"description",None) or ""
    return f"{ref} — {title}" if title else str(ref)

class SmartBuildAllocationPlugin(SettingsMixin,UserInterfaceMixin,UrlsMixin,AllocateMixin,InvenTreePlugin):
    NAME="SmartBuildAllocation"; SLUG="smartbuildallocation"; TITLE="Smart Build Allocation"
    DESCRIPTION="Per Vices stock-selection workflow for Build Order allocation"
    VERSION=PLUGIN_VERSION; AUTHOR="Per Vices Corporation"; LICENSE="MIT"
    SETTINGS={
      "COMPONENT_ROOM_TEXT":{"name":"Component Room location text","description":"Preferred stock location text (case-insensitive)","default":"component room"},
      "LOW_COST_REEL_THRESHOLD":{"name":"Low-cost reel preference threshold","description":"Prefer reel packaging below this unit purchase price","default":0.15,"validator":float},
    }

    def setup_urls(self):
        return [
            path('group/<int:build_id>/', self.group_view, name='smart-allocation-group'),
        ]

    def group_view(self,request,build_id):
        try:
            from build.models import Build
            current=Build.objects.get(pk=build_id)
        except Exception as exc:
            return JsonResponse({'error':f'Build Order {build_id} was not found: {exc}'},status=404)
        if request.method=='POST':
            try:data=json.loads(request.body.decode('utf-8') or '{}')
            except Exception:return JsonResponse({'error':'Invalid JSON'},status=400)
            selected=[]
            for value in data.get('build_ids',[]):
                try:
                    value=int(value)
                    if value!=build_id:selected.append(value)
                except (TypeError,ValueError):pass
            valid=set(Build.objects.filter(pk__in=selected).values_list('pk',flat=True))
            group=sorted({int(build_id),*valid})
            for bid in group: cache.set(_group_key(bid),group,GROUP_TTL)
            return JsonResponse({'ok':True,'build_ids':group})
        group=cache.get(_group_key(build_id)) or [int(build_id)]
        # Keep the selector intentionally broad for local testing. Closed/complete BOs are labelled by InvenTree but not hidden here.
        builds=[]
        for b in Build.objects.all().order_by('-pk')[:250]:
            builds.append({'pk':b.pk,'label':_build_label(b),'selected':b.pk in group,'current':b.pk==build_id})
        return JsonResponse({'build_id':build_id,'build_ids':group,'builds':builds,'term':'Shared Allocation Group'})

    def filter_build_allocation(self,build_line,stock_items,**kwargs):
        if not stock_items:return stock_items
        required=max(float(getattr(build_line,"quantity",0) or 0)-float(getattr(build_line,"allocated",0) or 0),0)
        build=getattr(build_line,'build',None)
        build_id=getattr(build,'pk',None)
        group=(cache.get(_group_key(build_id)) if build_id else None) or ([build_id] if build_id else [])
        return rank_stock_items(stock_items,getattr(build_line,"part",None),required,group_build_ids=group)

    def get_ui_panels(self,request,context,**kwargs):
        context=context or {}
        target_model=str(context.get('target_model') or context.get('model') or context.get('model_type') or '').lower()
        target_id=context.get('target_id') or context.get('pk') or context.get('id')
        if target_model and 'build' not in target_model:return []
        if not target_id:return []
        return [{
            "key":"smart-build-allocation","title":"Smart Allocation","description":"Configure a Shared Allocation Group before Auto Allocate",
            "icon":"ti:arrows-sort","source":self.plugin_static_file("smart_allocation_v020.js:renderPanel"),
            "context":{"version":self.VERSION,"build_id":int(target_id),"group_url":f"/plugin/{self.SLUG}/group/{int(target_id)}/"}
        }]
