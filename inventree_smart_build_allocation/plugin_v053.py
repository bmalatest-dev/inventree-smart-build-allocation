from contextvars import ContextVar

from .plugin_v052 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase
from . import rules


# Ranking is called deep inside the inherited preview planner. Keep the current
# BO's earlier-package preference request-local so concurrent previews cannot
# affect one another.
_historical_stock_ids = ContextVar(
    "smartbuildallocation_historical_stock_ids", default=frozenset()
)


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.53: prefer packages used by earlier BOs in the shared sequence.

    Historical affinity changes ranking only. It never changes the quantity which
    is available: v0.2.49 still deducts every live BuildItem allocation before a
    package can be proposed for a new allocation.
    """

    VERSION = "0.2.53"

    def _historical_stock_ids_for_build(self, build_id, group_ids):
        """StockItems used by earlier group BOs for parts required by build_id."""
        from build.models import BuildItem, BuildLine

        ordered = [int(x) for x in (group_ids or [])]
        try:
            position = ordered.index(int(build_id))
        except ValueError:
            return frozenset()

        earlier_ids = ordered[:position]
        if not earlier_ids:
            return frozenset()

        part_ids = set()
        for line in BuildLine.objects.filter(build_id=build_id).select_related(
            "bom_item", "bom_item__sub_part"
        ):
            part = getattr(getattr(line, "bom_item", None), "sub_part", None)
            if part is None:
                part = getattr(line, "part", None)
            if part is not None:
                part_ids.add(int(part.pk))

        if not part_ids:
            return frozenset()

        historical = set()
        items = BuildItem.objects.filter(
            build_line__build_id__in=earlier_ids,
            stock_item__isnull=False,
        ).select_related(
            "build_line__bom_item",
            "build_line__bom_item__sub_part",
            "stock_item",
            "stock_item__part",
        )

        for item in items:
            stock = getattr(item, "stock_item", None)
            if stock is None:
                continue

            line = getattr(item, "build_line", None)
            part = getattr(getattr(line, "bom_item", None), "sub_part", None)
            if part is None:
                part = getattr(line, "part", None)

            # Exact BOM-part history is the normal case. Also retain a stock item
            # whose own part is one of the current BOM parts; this is useful where
            # older InvenTree records expose the stock relation more reliably than
            # the historical BuildLine relation.
            line_part_id = getattr(part, "pk", None)
            stock_part_id = getattr(getattr(stock, "part", None), "pk", None)
            if line_part_id in part_ids or stock_part_id in part_ids:
                historical.add(int(stock.pk))

        return frozenset(historical)

    def _preview(self, build_id, overrides=None):
        group_ids = self._get_group(build_id)
        historical_ids = self._historical_stock_ids_for_build(build_id, group_ids)
        token = _historical_stock_ids.set(historical_ids)
        try:
            return super()._preview(build_id, overrides=overrides)
        finally:
            _historical_stock_ids.reset(token)


# Preserve the existing ranking implementation and insert historical package
# affinity immediately after live same-group use and exact/variant relationship,
# but before location. This is intentionally ranking-only: all inherited stock
# eligibility and projected-quantity safeguards still run unchanged.
_base_rank_stock_items = rules.rank_stock_items


def _rank_stock_items_v053(
    stock_items,
    required_part=None,
    required_qty=0,
    group_build_ids=None,
    projected_quantities=None,
):
    ranked = _base_rank_stock_items(
        stock_items,
        required_part=required_part,
        required_qty=required_qty,
        group_build_ids=group_build_ids,
        projected_quantities=projected_quantities,
    )
    historical = _historical_stock_ids.get()
    if not historical or len(ranked) < 2:
        return ranked

    # Stable partition only candidates with the same exact-vs-variant relation.
    # This means historical use cannot make a variant outrank an eligible exact
    # BOM part, but it can make an earlier exact package outrank a fresh exact
    # package merely because the latter is in the Component Room.
    return sorted(
        ranked,
        key=lambda stock: (
            rules.relation_rank(stock, required_part),
            0 if getattr(stock, "pk", None) in historical else 1,
            ranked.index(stock),
        ),
    )


# plugin.py imports rank_stock_items directly, so update that module binding as
# well as rules.rank_stock_items. The wrapper is active only while v0.2.53 is the
# installed entry point.
rules.rank_stock_items = _rank_stock_items_v053
from . import plugin as _plugin_module
_plugin_module.rank_stock_items = _rank_stock_items_v053
