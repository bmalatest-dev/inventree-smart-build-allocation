from .plugin_v035 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.36: unrelated Out-for-Assembly stock informs manual-vs-shortage classification."""

    def _manual_intervention_stock_options(self, part_id, group_ids):
        """Return physical stock excluded from auto allocation but requiring operator review."""
        from build.models import BuildItem
        from stock.models import StockItem
        from .rules import (
            has_blocked_stock_status, is_consumed, is_out_for_assembly,
            is_unreceived, packaging,
        )

        options = []
        for stock in StockItem.objects.filter(
            part_id=part_id,
            consumed_by__isnull=True,
        ).select_related("location", "part"):
            if is_consumed(stock) or is_unreceived(stock) or has_blocked_stock_status(stock):
                continue

            physical = float(getattr(stock, "quantity", 0) or 0)
            if physical <= 0:
                continue

            outside = self._outside_group_allocated_quantity(stock, group_ids)
            unallocated = max(physical - outside, 0)
            group_use = self._currently_allocated_to_group(stock, group_ids)
            unrelated_out_for_assembly = is_out_for_assembly(stock) and not group_use

            # v0.2.35 already handled packages allocated to another BO. v0.2.36
            # also handles the still-unallocated remainder of packages physically
            # staged Out-for-Assembly for an unrelated project.
            if outside <= 0 and not unrelated_out_for_assembly:
                continue
            if unallocated <= 0 and outside <= 0:
                continue

            owners = sorted({
                str(item.build_line.build.reference)
                for item in BuildItem.objects.filter(stock_item=stock).select_related("build_line__build")
                if item.build_line and item.build_line.build_id not in group_ids
            })

            if unrelated_out_for_assembly and unallocated > 0:
                reason = (
                    f"OUT-FOR-ASSEMBLY FOR ANOTHER PROJECT: {unallocated:g} units are physically "
                    "unallocated but staged outside this Shared Allocation Group. Manual review is "
                    "required before this stock can be reassigned."
                )
                warning = "Out-for-Assembly for another project"
            else:
                reason = (
                    f"ALLOCATED TO ANOTHER BUILD ({', '.join(owners) or 'unknown BO'}): "
                    f"{outside:g} allocated; this physical package requires manual intervention "
                    "before it can be used by this Shared Allocation Group."
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
                "warnings": [warning],
                "reason": reason,
            })
        return options

    def _preview(self, build_id, overrides=None):
        # Call v0.2.32 directly so v0.2.35 does not prematurely reclassify rows;
        # this method supersedes that classification with the broader rule.
        result = super(SmartBuildAllocationPluginBase, self)._preview(build_id, overrides=overrides)
        group_ids = self._get_group(build_id)
        remaining_insufficient = []

        for row in result.get("insufficient", []):
            part_id = row.get("part_id")
            required = float(row.get("required") or row.get("allocate_qty") or 0)
            if not part_id or required <= 0:
                remaining_insufficient.append(row)
                continue

            intervention_options = self._manual_intervention_stock_options(part_id, group_ids)
            intervention_unallocated = sum(
                float(x.get("unallocated_quantity") or 0) for x in intervention_options
            )
            automatic_available = float(row.get("available") or 0)

            # Only the genuinely unallocated remainder counts toward satisfying the
            # requirement. Allocated quantities are shown for context but are not
            # treated as available. If enough stock exists after acknowledging
            # unrelated Out-for-Assembly stock, this is an operator decision.
            if intervention_options and automatic_available + intervention_unallocated + 1e-9 >= required:
                decision = dict(row)
                existing_options = list(row.get("stock_options") or [])
                known_ids = {x.get("stock_id") for x in existing_options}
                existing_options.extend(
                    x for x in intervention_options if x.get("stock_id") not in known_ids
                )
                decision["options"] = existing_options
                decision["stock_options"] = existing_options
                decision["available_automatic"] = automatic_available
                decision["available_manual_intervention"] = intervention_unallocated
                decision["message"] = (
                    "Manual intervention required. Enough unallocated physical stock exists, but some "
                    "of it is staged Out-for-Assembly for projects outside this Shared Allocation Group. "
                    "Review whether that stock can be returned/reassigned before allocating it here."
                )
                result["manual"].append(decision)
            else:
                remaining_insufficient.append(row)

        result["insufficient"] = remaining_insufficient
        return result
