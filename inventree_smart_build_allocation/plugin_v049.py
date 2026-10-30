from .plugin_v048 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase
from .plugin import _num
from .rules import planned_spillage


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.49: never treat live BuildItem allocations as free stock.

    A Shared Allocation Group may influence package affinity, but it must not make
    quantity reserved to another Build Order available to a later Build Order.
    Current StockItem.quantity already reflects previously consumed / returned
    stock, so historical consumption is not subtracted again. Only live BuildItem
    allocations are deducted from the current physical quantity.
    """

    VERSION = "0.2.49"

    def _projected_start_quantity(self, stock, group_ids):
        """Return current physical quantity minus every live BuildItem allocation.

        Group membership deliberately does not change this calculation. Existing
        allocations already satisfy the BOs which own them through BuildLine's
        outstanding quantity, while only the genuinely unallocated remainder may
        be proposed as a new allocation.
        """
        from build.models import BuildItem
        from .rules import is_consumed

        if is_consumed(stock):
            return 0

        physical = _num(getattr(stock, "quantity", 0), 0)
        allocated = sum(
            _num(getattr(item, "quantity", 0), 0)
            for item in BuildItem.objects.filter(stock_item=stock)
        )
        return max(physical - allocated, 0)

    def _apply_existing_group_allocations(self, build, projected, group_ids, future_demand=None):
        """Account for existing allocations without subtracting them twice.

        _projected_start_quantity() has already removed every live BuildItem
        allocation from the usable pool. Existing allocations therefore must not
        be deducted again while walking the Shared Allocation Group. We retain the
        existing spillage-planning behavior by reserving only discretionary spill
        from the genuinely unallocated remainder.
        """
        from build.models import BuildItem

        items = list(
            BuildItem.objects.filter(build_line__build=build)
            .select_related(
                "build_line",
                "build_line__bom_item",
                "build_line__bom_item__sub_part",
                "stock_item",
            )
            .order_by("build_line_id", "pk")
        )

        spill_applied = set()
        for item in items:
            stock = getattr(item, "stock_item", None)
            line = getattr(item, "build_line", None)
            if stock is None or line is None:
                continue

            if stock.pk not in projected:
                projected[stock.pk] = self._projected_start_quantity(stock, group_ids)

            # Existing BuildItem quantity is already excluded by
            # _projected_start_quantity(). Only reserve optional spillage here,
            # and only once per BuildLine.
            if line.pk in spill_applied:
                continue

            part = getattr(getattr(line, "bom_item", None), "sub_part", None)
            if part is None:
                part = getattr(line, "part", None)

            if part is not None:
                spill, _ = planned_spillage(part, getattr(build, "quantity", 1))
                later = (future_demand or {}).get(part.pk, 0)
                if projected[stock.pk] >= spill + later:
                    projected[stock.pk] = max(projected[stock.pk] - spill, 0)

            spill_applied.add(line.pk)
