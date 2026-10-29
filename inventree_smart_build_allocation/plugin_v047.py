from django.db.models import F

from .plugin_v046 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase
from .plugin_v045 import _manual_outside_stock_ids
from .plugin import _batch_id, _num
from .rules import is_out_for_assembly, location_name, packaging


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.47: make Manual Allocation follow native InvenTree availability.

    Smart automatic allocation remains conservative. Manual Allocation is an
    operator override, so its candidate list follows the same stock eligibility
    and remaining-quantity calculation as InvenTree's normal Allocate Stock form:
    the BOM item's native stock filter, StockItem.IN_STOCK_FILTER, and
    quantity > annotated allocated quantity.
    """

    VERSION = "0.2.47"

    @staticmethod
    def _native_annotated_stock(queryset):
        """Apply the same `allocated` annotation used by InvenTree StockItem API."""
        from stock.serializers import StockItemSerializer

        return StockItemSerializer.annotate_queryset(queryset)

    def _native_available_quantity(self, stock):
        """Return InvenTree-native remaining allocatable quantity for one StockItem."""
        from stock.models import StockItem

        annotated = self._native_annotated_stock(
            StockItem.objects.filter(pk=stock.pk)
        ).first()
        if annotated is None:
            return 0
        return max(
            _num(getattr(annotated, "quantity", 0), 0)
            - _num(getattr(annotated, "allocated", 0), 0),
            0,
        )

    def _projected_start_quantity(self, stock, group_ids):
        """Explicit manual overrides are limited to native InvenTree availability."""
        if getattr(stock, "pk", None) in _manual_outside_stock_ids.get():
            return self._native_available_quantity(stock)
        return super()._projected_start_quantity(stock, group_ids)

    def _native_manual_stock_options(self, line_id, group_ids, recommended_ids=None):
        """Return the StockItems shown by InvenTree's normal build allocation flow."""
        from build.models import BuildItem, BuildLine
        from stock.models import StockItem

        try:
            line = BuildLine.objects.select_related("bom_item").get(pk=line_id)
        except BuildLine.DoesNotExist:
            return []

        bom_item = getattr(line, "bom_item", None)
        if bom_item is None:
            return []

        # Native Allocate Stock uses the StockItem list with `available=true` and
        # `bom_item=<id>`. Reproduce those backend filters directly so this remains
        # independent of the smart allocator's conservative package projection.
        queryset = StockItem.objects.filter(bom_item.get_stock_filter())
        queryset = self._native_annotated_stock(queryset)
        queryset = queryset.filter(StockItem.IN_STOCK_FILTER).filter(
            quantity__gt=F("allocated")
        ).select_related("location", "part")

        recommended_ids = set(recommended_ids or [])
        group = set(int(x) for x in (group_ids or []))
        options = []

        for stock in queryset:
            physical = _num(getattr(stock, "quantity", 0), 0)
            allocated = _num(getattr(stock, "allocated", 0), 0)
            available = max(physical - allocated, 0)
            if available <= 0:
                continue

            build_allocations = list(
                BuildItem.objects.filter(stock_item=stock).select_related("build_line__build")
            )
            outside = sum(
                _num(getattr(item, "quantity", 0), 0)
                for item in build_allocations
                if getattr(getattr(item, "build_line", None), "build_id", None) not in group
            )
            owners = sorted({
                str(item.build_line.build.reference)
                for item in build_allocations
                if item.build_line
                and item.build_line.build_id not in group
            })

            warnings = []
            if allocated > 0:
                if owners:
                    warnings.append(
                        f"Partially allocated ({allocated:g} total; outside BOs: {', '.join(owners)})"
                    )
                else:
                    warnings.append(f"Partially allocated ({allocated:g})")
            if is_out_for_assembly(stock):
                warnings.append("Out-for-Assembly")

            loc = location_name(stock)
            options.append({
                "stock_id": stock.pk,
                "batch_id": _batch_id(stock),
                "quantity": available,
                "physical_quantity": physical,
                "allocated_quantity": allocated,
                "outside_allocated": outside,
                "unallocated_quantity": available,
                "location": loc or "Unknown",
                "packaging": packaging(stock) or "—",
                "recommended": stock.pk in recommended_ids,
                "selectable": True,
                "warnings": warnings,
                "stock_part": str(stock.part),
            })

        return sorted(
            options,
            key=lambda x: (
                not x["recommended"],
                len(x["warnings"]),
                x["quantity"],
                x["stock_id"],
            ),
        )

    def _preview(self, build_id, overrides=None):
        result = super()._preview(build_id, overrides=overrides)
        group_ids = self._get_group(build_id)

        # The UI exposes Manual Allocation from actionable rows in multiple
        # sections, not only the dedicated `manual` section. Give every row with
        # a BuildLine the native InvenTree candidate list.
        for section in ("easy", "variant", "spillage", "location", "multi", "manual", "insufficient"):
            for row in result.get(section, []):
                line_id = row.get("line_id")
                if not line_id:
                    continue

                recommended_ids = []
                if row.get("stock_id") is not None:
                    recommended_ids.append(row["stock_id"])
                recommended_ids.extend(
                    item.get("stock_id")
                    for item in (row.get("stock_items") or [])
                    if item.get("stock_id") is not None
                )

                native_options = self._native_manual_stock_options(
                    line_id, group_ids, recommended_ids=recommended_ids
                )
                if native_options:
                    row["stock_options"] = native_options
                    row["options"] = native_options

        return result
