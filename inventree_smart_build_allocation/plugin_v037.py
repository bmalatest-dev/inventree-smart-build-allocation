from django.db.models import Q

from .plugin_v036 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.37: apply manual-intervention classification to exact and accepted variant stock."""

    def _manual_intervention_stock_options(self, part_id, group_ids):
        """Return intervention stock for the BOM part and its accepted variants."""
        from build.models import BuildItem
        from part.models import Part
        from stock.models import StockItem
        from .rules import (
            has_blocked_stock_status, is_consumed, is_out_for_assembly,
            is_unreceived, packaging,
        )

        try:
            required_part = Part.objects.get(pk=part_id)
        except Part.DoesNotExist:
            return []

        # Match the same variant universe used by the normal allocation engine:
        # exact BOM part plus Parts whose variant_of points to that BOM part.
        stock_items = StockItem.objects.filter(
            Q(part=required_part) | Q(part__variant_of=required_part),
            consumed_by__isnull=True,
        ).select_related("location", "part")

        options = []
        for stock in stock_items:
            if is_consumed(stock) or is_unreceived(stock) or has_blocked_stock_status(stock):
                continue

            physical = float(getattr(stock, "quantity", 0) or 0)
            if physical <= 0:
                continue

            outside = self._outside_group_allocated_quantity(stock, group_ids)
            unallocated = max(physical - outside, 0)
            group_use = self._currently_allocated_to_group(stock, group_ids)
            unrelated_out_for_assembly = is_out_for_assembly(stock) and not group_use

            if outside <= 0 and not unrelated_out_for_assembly:
                continue
            if unallocated <= 0 and outside <= 0:
                continue

            owners = sorted({
                str(item.build_line.build.reference)
                for item in BuildItem.objects.filter(stock_item=stock).select_related("build_line__build")
                if item.build_line and item.build_line.build_id not in group_ids
            })

            is_variant = getattr(stock.part, "pk", None) != required_part.pk
            variant_note = f" Variant: {stock.part}." if is_variant else ""

            if unrelated_out_for_assembly and unallocated > 0:
                reason = (
                    f"OUT-FOR-ASSEMBLY FOR ANOTHER PROJECT: {unallocated:g} units are physically "
                    "unallocated but staged outside this Shared Allocation Group. Manual review is "
                    f"required before this stock can be reassigned.{variant_note}"
                )
                warning = "Out-for-Assembly for another project"
            else:
                reason = (
                    f"ALLOCATED TO ANOTHER BUILD ({', '.join(owners) or 'unknown BO'}): "
                    f"{outside:g} allocated; this physical package requires manual intervention "
                    f"before it can be used by this Shared Allocation Group.{variant_note}"
                )
                warning = "Allocated to another Build Order"

            options.append({
                "stock_id": stock.pk,
                "batch_id": getattr(stock, "batch", None),
                "quantity": 0,
                "physical_quantity": physical,
                "outside_allocated": outside,
                "unallocated_quantity": unallocated,
                "location": self._location_label(getattr(stock, "location", None)) or "Unknown",
                "packaging": packaging(stock) or "—",
                "recommended": False,
                "selectable": False,
                "warnings": [warning] + (["Variant stock — review required"] if is_variant else []),
                "reason": reason,
                "variant": is_variant,
                "stock_part": str(stock.part),
            })
        return options
