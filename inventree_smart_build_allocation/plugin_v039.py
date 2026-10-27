from .plugin_v038 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.39: cache-busting UI asset release; allocation behavior is unchanged from v0.2.38."""

    VERSION = "0.2.39"

    def get_ui_panels(self, request, context, **kwargs):
        """Serve a uniquely-versioned UI asset so deployments cannot reuse an older cached panel."""
        panels = super().get_ui_panels(request, context, **kwargs)
        for panel in panels:
            target_id = (panel.get("context") or {}).get("build_id")
            if target_id:
                panel["source"] = self.plugin_static_file("smart_allocation_v039.js:renderPanel")
                panel["context"]["version"] = self.VERSION
        return panels
