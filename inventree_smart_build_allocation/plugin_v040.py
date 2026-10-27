from .plugin_v039 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.40: uniquely-versioned UI asset with legacy v0.2.28 heading removed."""

    VERSION = "0.2.40"

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)
        for panel in panels:
            target_id = (panel.get("context") or {}).get("build_id")
            if target_id:
                panel["source"] = self.plugin_static_file("smart_allocation_v040.js:renderPanel")
                panel["context"]["version"] = self.VERSION
        return panels
