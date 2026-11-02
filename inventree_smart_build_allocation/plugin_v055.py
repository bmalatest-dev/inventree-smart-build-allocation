from .plugin_v054 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


SEQUENTIAL_REUSE_MESSAGE = (
    "Stock is already allocated to a Build Order in this Shared Allocation Group "
    "and is eligible for sequential reuse."
)


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.55: keep Manual Allocation stable on sequential-reuse rows.

    The current table renderer conditionally inserts the Manual Allocation editor
    immediately before an existing message row. In InvenTree's remote component
    renderer that specific transition can fail with a DOM ``insertBefore`` error.

    Keep all allocation and ranking behavior unchanged. For the one informational
    sequential-reuse message, avoid the extra sibling message row and carry the
    same notice into the recommended StockItem's Manual Allocation warnings.
    """

    VERSION = "0.2.55"

    def _preview(self, build_id, overrides=None):
        result = super()._preview(build_id, overrides=overrides)

        for section_name in ("easy", "variant", "spillage", "location", "multi"):
            for row in result.get(section_name, []):
                if row.get("message") != SEQUENTIAL_REUSE_MESSAGE:
                    continue

                # Preserve the information without rendering the separate table
                # message row which conflicts with dynamic Manual Allocation.
                row.pop("message", None)
                row["sequential_reuse"] = True

                recommended_ids = {row.get("stock_id")}
                recommended_ids.update(
                    item.get("stock_id")
                    for item in (row.get("stock_items") or [])
                    if item.get("stock_id") is not None
                )

                for option in row.get("stock_options") or []:
                    if option.get("stock_id") not in recommended_ids:
                        continue
                    warnings = list(option.get("warnings") or [])
                    if "Shared Allocation Group sequential reuse" not in warnings:
                        warnings.append("Shared Allocation Group sequential reuse")
                    option["warnings"] = warnings

        return result
