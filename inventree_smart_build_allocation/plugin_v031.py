from .plugin_v029 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.31: same-group Out-for-Assembly reuse is an easy allocation."""

    def _preview(self, build_id, overrides=None):
        """Reclassify only Out-for-Assembly stock already used by this shared group."""
        from stock.models import StockItem
        from .rules import is_out_for_assembly, stock_used_by_group

        result = super()._preview(build_id, overrides=overrides)
        group_ids = self._get_group(build_id)
        remaining_location = []

        for row in result.get("location", []):
            stock_id = row.get("stock_id")
            stock = None
            if stock_id is not None:
                try:
                    stock = StockItem.objects.get(pk=stock_id)
                except StockItem.DoesNotExist:
                    stock = None

            # A package which is Out-for-Assembly but already belongs to a BO in
            # this Shared Allocation Group is intentionally carried forward to
            # later BOs in sequence. It is not a location exception.
            if stock is not None and is_out_for_assembly(stock) and stock_used_by_group(stock, group_ids):
                row["message"] = "Out-for-Assembly stock is being reused sequentially within this Shared Allocation Group."
                result["easy"].append(row)
            else:
                remaining_location.append(row)

        result["location"] = remaining_location
        return result
