from .plugin_v050 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.51: visually group each BOM requirement with its notes and allocation plan."""

    VERSION = "0.2.51"

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)
        for panel in panels:
            target_id = (panel.get("context") or {}).get("build_id")
            if target_id:
                panel["source"] = self.plugin_static_file("smart_allocation_v051.js:renderPanel")
                panel["context"]["version"] = self.VERSION
        return panels
