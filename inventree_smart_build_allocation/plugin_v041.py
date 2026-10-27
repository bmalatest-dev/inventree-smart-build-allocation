from .plugin_v038 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.41: cache-busted UI release preserving the current Easy Location and allocation behavior."""

    VERSION = "0.2.41"

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)
        for panel in panels:
            target_id = (panel.get("context") or {}).get("build_id")
            if target_id:
                # Preserve all context populated by the inherited v0.2.38 chain,
                # including easy_location_url. Only replace the UI asset with a
                # uniquely named version so InvenTree/browser caches cannot reuse
                # an earlier panel implementation.
                panel["source"] = self.plugin_static_file("smart_allocation_v041.js:renderPanel")
                panel["context"]["version"] = self.VERSION
        return panels
