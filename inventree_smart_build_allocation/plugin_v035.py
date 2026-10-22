from .plugin_v032 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.35: reserved physical stock is a manual decision, not a false shortage."""

    def _reserved_stock_options(self, part_id, group_ids):
        """Return live physical packages reserved to BOs outside this group."""
        from build.models import BuildItem
        from stock.models import StockItem
        from .rules import is_consumed, is_unreceived, packaging

        options = []
        for stock in StockItem.objects.filter(
            part_id=part_id,
            consumed_by__isnull=True,
        ).select_related("location", "part"):
            if is_consumed(stock) or is_unreceived(stock):
                continue
            physical = float(getattr(stock, "quantity", 0) or 0)
            if physical <= 0:
                continue
            outside = self._outside_group_allocated_quantity(stock, group_ids)
            if outside <= 0:
                continue
            owners = sorted({
                str(item.build_line.build.reference)
                for item in BuildItem.objects.filter(stock_item=stock).select_related("build_line__build")
                if item.build_line and item.build_line.build_id not in group_ids
            })
            options.append({
                "stock_id": stock.pk,
                "batch_id": getattr(stock, "batch", None),
                "quantity": 0,
                "physical_quantity": physical,
                "outside_allocated": outside,
                "unallocated_quantity": max(physical - outside, 0),
                "location": self._location_label(getattr(stock, "location", None)) or "Unknown",
                "packaging": packaging(stock) or "—",
                "recommended": False,
                "selectable": False,
                "warnings": ["Allocated to another Build Order"],
                "reason": (
                    f"ALLOCATED TO ANOTHER BUILD ({', '.join(owners) or 'unknown BO'}): "
                    f"{outside:g} allocated; this physical package requires manual intervention "
                    "before it can be used by this Shared Allocation Group."
                ),
            })
        return options

    def _preview(self, build_id, overrides=None):
        result = super()._preview(build_id, overrides=overrides)
        group_ids = self._get_group(build_id)
        remaining_insufficient = []

        for row in result.get("insufficient", []):
            part_id = row.get("part_id")
            required = float(row.get("required") or row.get("allocate_qty") or 0)
            if not part_id or required <= 0:
                remaining_insufficient.append(row)
                continue

            reserved_options = self._reserved_stock_options(part_id, group_ids)
            reserved_physical = sum(float(x.get("physical_quantity") or 0) for x in reserved_options)
            automatic_available = float(row.get("available") or 0)

            # If enough physical stock exists once packages reserved to unrelated
            # BOs are acknowledged, this is an operator decision, not a shortage.
            if reserved_options and automatic_available + reserved_physical + 1e-9 >= required:
                decision = dict(row)
                existing_options = list(row.get("stock_options") or [])
                known_ids = {x.get("stock_id") for x in existing_options}
                existing_options.extend(x for x in reserved_options if x.get("stock_id") not in known_ids)
                decision["options"] = existing_options
                decision["stock_options"] = existing_options
                decision["available_automatic"] = automatic_available
                decision["available_reserved_physical"] = reserved_physical
                decision["message"] = (
                    "Manual intervention required. Enough physical stock exists, but one or more "
                    "packages are currently allocated to Build Orders outside this Shared Allocation Group. "
                    "Review/release the unrelated allocation or choose other valid stock before proceeding."
                )
                result["manual"].append(decision)
            else:
                remaining_insufficient.append(row)

        result["insufficient"] = remaining_insufficient
        return result
