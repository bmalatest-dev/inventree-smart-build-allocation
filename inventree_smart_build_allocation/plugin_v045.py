from contextvars import ContextVar

from .plugin_v044 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase
from .rules import available_quantity


# Request-local set of StockItem IDs explicitly selected by the operator.
# ContextVar keeps concurrent preview / commit requests isolated.
_manual_outside_stock_ids = ContextVar("smartbuildallocation_manual_outside_stock_ids", default=frozenset())


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.45: allow explicit use of unallocated stock from shared packages.

    Automatic allocation behavior is unchanged: any StockItem allocated to a BO
    outside the Shared Allocation Group remains excluded from automatic choices.
    The only exception is an explicit operator selection in Manual Allocation,
    and that selection is limited to InvenTree's live available quantity.
    """

    VERSION = "0.2.45"

    def _actual_outside_group_allocated_quantity(self, stock, group_ids):
        """Return outside allocation without the request-local manual exception."""
        return super()._outside_group_allocated_quantity(stock, group_ids)

    def _outside_group_allocated_quantity(self, stock, group_ids):
        """Treat explicitly selected manual stock as eligible for this request only."""
        if getattr(stock, "pk", None) in _manual_outside_stock_ids.get():
            return 0
        return self._actual_outside_group_allocated_quantity(stock, group_ids)

    def _projected_start_quantity(self, stock, group_ids):
        """Never expose more than live unallocated quantity for a manual exception."""
        if getattr(stock, "pk", None) in _manual_outside_stock_ids.get():
            return max(float(available_quantity(stock) or 0), 0)
        return super()._projected_start_quantity(stock, group_ids)

    def _manual_intervention_stock_options(self, part_id, group_ids):
        """Expose genuinely unallocated remainder as an explicit manual choice."""
        options = super()._manual_intervention_stock_options(part_id, group_ids)
        for option in options:
            outside = float(option.get("outside_allocated") or 0)
            unallocated = float(option.get("unallocated_quantity") or 0)
            if outside > 0 and unallocated > 0:
                option["quantity"] = unallocated
                option["selectable"] = True
                option["reason"] = (
                    f"ALLOCATED TO ANOTHER BUILD: {outside:g} units are already allocated; "
                    f"{unallocated:g} units remain unallocated and may be explicitly selected here."
                )
                warnings = list(option.get("warnings") or [])
                if "Manual selection only" not in warnings:
                    warnings.append("Manual selection only")
                option["warnings"] = warnings
        return options

    @staticmethod
    def _override_stock_ids(overrides):
        ids = set()
        for rows in (overrides or {}).values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                try:
                    stock_id = int(row.get("stock_id"))
                except (TypeError, ValueError):
                    continue
                if float(row.get("quantity") or 0) > 0:
                    ids.add(stock_id)
        return frozenset(ids)

    def _preview(self, build_id, overrides=None):
        # Only explicit manual selections receive the outside-allocation exception.
        token = _manual_outside_stock_ids.set(self._override_stock_ids(overrides))
        try:
            return super()._preview(build_id, overrides=overrides)
        finally:
            _manual_outside_stock_ids.reset(token)

    def commit_view(self, request, build_id):
        """Permit only Preview-confirmed manual rows to reuse unallocated remainder."""
        stock_ids = set()
        try:
            import json
            payload = json.loads(request.body.decode("utf-8") or "{}")
            selected = {str(x) for x in (payload.get("selected") or [])}
            selected_rows = payload.get("selected_rows") or {}
            for key in selected:
                entry = selected_rows.get(key)
                row = entry.get("row") if isinstance(entry, dict) else None
                if not isinstance(row, dict) or not row.get("manual_override"):
                    continue
                if row.get("stock_id") is not None:
                    stock_ids.add(int(row["stock_id"]))
                for item in row.get("stock_items") or []:
                    stock_ids.add(int(item["stock_id"]))
        except Exception:
            # Let the inherited commit handler return the normal validation error.
            stock_ids = set()

        token = _manual_outside_stock_ids.set(frozenset(stock_ids))
        try:
            return super().commit_view(request, build_id)
        finally:
            _manual_outside_stock_ids.reset(token)
