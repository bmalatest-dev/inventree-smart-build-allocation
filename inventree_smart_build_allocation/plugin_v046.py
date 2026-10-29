from .plugin_v045 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.46: show all usable intervention stock in Manual Allocation.

    Automatic allocation remains unchanged. When a row is already presented for
    manual review, also expose any additional StockItems which have genuinely
    unallocated quantity but are excluded from automatic allocation (for example,
    stock partially allocated to another BO or staged Out-for-Assembly elsewhere).
    """

    VERSION = "0.2.46"

    def _preview(self, build_id, overrides=None):
        result = super()._preview(build_id, overrides=overrides)
        group_ids = self._get_group(build_id)

        for row in result.get("manual", []):
            part_id = row.get("part_id")
            if not part_id:
                continue

            intervention_options = self._manual_intervention_stock_options(part_id, group_ids)
            if not intervention_options:
                continue

            # Manual Allocation should be the operator's complete view of usable
            # stock. Preserve the normal candidates and append only missing
            # intervention StockItems; automatic ranking / selection is untouched.
            existing_options = list(row.get("stock_options") or row.get("options") or [])
            known_ids = {option.get("stock_id") for option in existing_options}
            existing_options.extend(
                option for option in intervention_options
                if option.get("stock_id") not in known_ids
                and float(option.get("unallocated_quantity") or 0) > 0
            )

            row["options"] = existing_options
            row["stock_options"] = existing_options

        return result
