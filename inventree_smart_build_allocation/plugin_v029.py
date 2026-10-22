from decimal import Decimal

from .plugin import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.30 hotfixes layered on the validated allocation engine."""

    def _preview(self, build_id, overrides=None):
        """Keep resolvable decisions manual, but classify true quantity shortages as insufficient."""
        result = super()._preview(build_id, overrides=overrides)

        remaining_manual = []
        for row in result.get("manual", []):
            required = float(row.get("required") or row.get("allocate_qty") or 0)
            options = row.get("options") or []
            selectable_total = sum(
                float(option.get("quantity") or 0)
                for option in options
                if option.get("selectable", True)
            )

            if selectable_total + 1e-9 < required:
                shortage = max(required - selectable_total, 0)
                insufficient_row = dict(row)
                insufficient_row["available"] = selectable_total
                insufficient_row["shortage"] = shortage
                insufficient_row["message"] = (
                    f"Actual BOM quantity cannot be satisfied. Required {required:g}; "
                    f"selectable stock {selectable_total:g}; shortage {shortage:g}."
                )
                result["insufficient"].append(insufficient_row)
            else:
                remaining_manual.append(row)

        result["manual"] = remaining_manual
        return result

    def _create_build_item(self, build, line, stock, quantity):
        """Create / extend an allocation using InvenTree native Decimal quantities."""
        from build.models import BuildItem

        quantity = Decimal(str(quantity))
        build_item, created = BuildItem.objects.get_or_create(
            build_line=line,
            stock_item=stock,
            install_into=None,
        )
        if created:
            build_item.quantity = quantity
        else:
            build_item.quantity += quantity
        build_item.full_clean()
        build_item.save()
        return build_item
