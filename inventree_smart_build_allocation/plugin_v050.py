from .plugin_v049 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.50: clearer allocation-plan UI without changing allocation behavior."""

    VERSION = "0.2.50"

    def _preview(self, build_id, overrides=None):
        result = super()._preview(build_id, overrides=overrides)

        # Older automatic multi-package rows did not carry the before / after
        # quantities which the UI needs for a useful allocation-plan table.
        # v0.2.47 already supplies native/manual stock_options on every row, so
        # use those values only to fill missing display fields. Do not alter the
        # selected StockItems or allocation quantities.
        for section_name in ("easy", "variant", "spillage", "location", "multi"):
            for row in result.get(section_name, []):
                options = {
                    int(option["stock_id"]): option
                    for option in (row.get("stock_options") or [])
                    if option.get("stock_id") is not None
                }
                for item in row.get("stock_items") or []:
                    stock_id = item.get("stock_id")
                    if stock_id is None:
                        continue
                    option = options.get(int(stock_id), {})
                    if item.get("projected_before") is None:
                        item["projected_before"] = option.get("quantity")
                    if item.get("projected_after") is None and item.get("projected_before") is not None:
                        item["projected_after"] = max(
                            float(item["projected_before"]) - float(item.get("qty") or 0),
                            0,
                        )
                    item.setdefault("packaging", option.get("packaging") or "—")

        return result

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)
        for panel in panels:
            target_id = (panel.get("context") or {}).get("build_id")
            if target_id:
                panel["source"] = self.plugin_static_file("smart_allocation_v050.js:renderPanel")
                panel["context"]["version"] = self.VERSION
        return panels
