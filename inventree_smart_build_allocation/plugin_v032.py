import json

from django.core.cache import cache
from django.http import JsonResponse
from django.urls import path

from .plugin_v029 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


EASY_LOCATION_TTL = 60 * 60 * 24 * 7


def _easy_location_key(build_id):
    return f"smartbuildallocation:easy-location:v0232:{int(build_id)}"


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.32: selectable Default Easy Location plus selected-group allocation reuse."""

    def setup_urls(self):
        return super().setup_urls() + [
            path("easy-location/<int:build_id>/", self.easy_location_view, name="smart-allocation-easy-location"),
        ]

    def _default_component_room_id(self):
        from stock.models import StockLocation
        location = StockLocation.objects.filter(name__iexact="Component Room").order_by("pk").first()
        if location is None:
            location = StockLocation.objects.filter(name__icontains="Component Room").order_by("pk").first()
        return location.pk if location is not None else None

    def _easy_location_id(self, build_id):
        value = cache.get(_easy_location_key(build_id))
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
        return self._default_component_room_id()

    def _location_label(self, location):
        for attr in ("get_path_string", "get_path"):
            fn = getattr(location, attr, None)
            if callable(fn):
                try:
                    value = fn()
                    if value:
                        return str(value)
                except Exception:
                    pass
        return str(location)

    def _location_is_within(self, location, selected_location_id):
        """True for the selected location itself or any descendant location."""
        if location is None or selected_location_id is None:
            return False
        seen = set()
        current = location
        while current is not None and getattr(current, "pk", None) not in seen:
            current_id = getattr(current, "pk", None)
            if current_id == selected_location_id:
                return True
            if current_id is not None:
                seen.add(current_id)
            current = getattr(current, "parent", None)
        return False

    def _currently_allocated_to_group(self, stock, group_ids):
        """Use live BuildItem allocations as the authority for sequential reuse."""
        from build.models import BuildItem
        return BuildItem.objects.filter(
            stock_item=stock,
            build_line__build_id__in=[int(x) for x in (group_ids or [])],
        ).exists()

    def easy_location_view(self, request, build_id):
        from stock.models import StockLocation

        group_ids = self._get_group(build_id)
        if request.method == "POST":
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
                location_id = int(payload.get("location_id"))
                location = StockLocation.objects.get(pk=location_id)
            except (TypeError, ValueError, StockLocation.DoesNotExist):
                return JsonResponse({"error": "Select a valid stock location."}, status=400)
            except Exception:
                return JsonResponse({"error": "Invalid JSON"}, status=400)

            for bid in group_ids:
                cache.set(_easy_location_key(bid), location.pk, EASY_LOCATION_TTL)

        selected_id = self._easy_location_id(build_id)
        locations = [
            {"pk": location.pk, "label": self._location_label(location)}
            for location in StockLocation.objects.select_related("parent").all().order_by("name", "pk")
        ]
        selected = next((x for x in locations if x["pk"] == selected_id), None)
        return JsonResponse({
            "build_id": int(build_id),
            "group_ids": group_ids,
            "location_id": selected_id,
            "location": selected,
            "locations": locations,
        })

    def group_view(self, request, build_id):
        """Carry the run's selected Easy Location when group membership changes."""
        selected_id = self._easy_location_id(build_id)
        response = super().group_view(request, build_id)
        if request.method == "POST" and getattr(response, "status_code", 500) < 400 and selected_id is not None:
            try:
                payload = json.loads(response.content.decode("utf-8"))
                for bid in payload.get("build_ids", []):
                    cache.set(_easy_location_key(bid), selected_id, EASY_LOCATION_TTL)
            except Exception:
                pass
        return response

    def _preview(self, build_id, overrides=None):
        """Easy means selected location hierarchy OR live allocation to a selected BO."""
        from stock.models import StockItem, StockLocation
        from . import plugin as plugin_module
        from .rules import (
            LOW_COST_REEL_THRESHOLD, available_quantity, has_blocked_stock_status,
            is_consumed, is_hand_placement, is_out_for_assembly, is_reel,
            is_rework_room, is_storage_room, is_unreceived, packaging_rank,
            purchase_price, relation_rank,
        )

        group_ids = self._get_group(build_id)
        selected_location_id = self._easy_location_id(build_id)
        original_rank = plugin_module.rank_stock_items

        def run_rank(stock_items, required_part=None, required_qty=0, group_build_ids=None, projected_quantities=None):
            """v0.2 ranking with the hard-coded Component Room preference replaced."""
            req = max(float(required_qty or 0), 0.0)
            projected_quantities = projected_quantities or {}
            hand = is_hand_placement(required_part)
            candidates = []
            for stock in list(stock_items):
                group_use = self._currently_allocated_to_group(stock, group_ids)
                easy_location = self._location_is_within(getattr(stock, "location", None), selected_location_id)
                if is_consumed(stock) or is_unreceived(stock) or has_blocked_stock_status(stock):
                    continue
                # Out-for-Assembly naming is no longer authoritative. Such stock is
                # automatic only when its actual allocation belongs to this group or
                # the user explicitly selected its location as Default Easy.
                if is_out_for_assembly(stock) and not group_use and not easy_location:
                    continue
                candidates.append(stock)

            def key(stock):
                q = projected_quantities.get(getattr(stock, "pk", None), available_quantity(stock))
                enough = q >= req if req > 0 else True
                group_use = self._currently_allocated_to_group(stock, group_ids)
                easy_location = self._location_is_within(getattr(stock, "location", None), selected_location_id)
                price = purchase_price(stock)
                cheap_reel = price is not None and price < LOW_COST_REEL_THRESHOLD and is_reel(stock)
                if hand:
                    loc_rank = 0 if easy_location else (1 if is_rework_room(stock) else (2 if is_storage_room(stock) else 3))
                    package_choice = (0 if enough else 1, q if enough else -q)
                else:
                    loc_rank = 0 if easy_location else 1
                    package_choice = (0 if enough else 1, q if enough else -q)
                return (
                    0 if group_use else 1,
                    relation_rank(stock, required_part),
                    loc_rank,
                    0 if cheap_reel else 1,
                    packaging_rank(stock) if not hand else 0,
                    *package_choice,
                    getattr(stock, "pk", 0) or 0,
                )

            return sorted(candidates, key=key)

        # Keep the validated engine intact while supplying this run's location-aware
        # ranking function for the duration of the preview.
        plugin_module.rank_stock_items = run_rank
        try:
            result = super()._preview(build_id, overrides=overrides)
        finally:
            plugin_module.rank_stock_items = original_rank

        # Replace the old hard-coded location classification. Only Easy/Location
        # rows are reconsidered; variant, spillage, multi and shortage behavior stays intact.
        reconsider = list(result.get("easy", [])) + list(result.get("location", []))
        result["easy"] = []
        result["location"] = []
        selected_location = StockLocation.objects.filter(pk=selected_location_id).first() if selected_location_id else None
        selected_label = self._location_label(selected_location) if selected_location is not None else "selected Default Easy Location"

        for row in reconsider:
            stock = None
            stock_id = row.get("stock_id")
            if stock_id is not None:
                try:
                    stock = StockItem.objects.select_related("location", "location__parent").get(pk=stock_id)
                except StockItem.DoesNotExist:
                    pass

            in_default_location = stock is not None and self._location_is_within(getattr(stock, "location", None), selected_location_id)
            allocated_to_group = stock is not None and self._currently_allocated_to_group(stock, group_ids)

            if in_default_location or allocated_to_group:
                if allocated_to_group and not in_default_location:
                    row["message"] = "Stock is already allocated to a Build Order in this Shared Allocation Group and is eligible for sequential reuse."
                else:
                    row.pop("message", None)
                result["easy"].append(row)
            else:
                row["message"] = (
                    f"Stock is outside the Default Easy Location ({selected_label}) and is not currently "
                    "allocated to a Build Order in this Shared Allocation Group."
                )
                result["location"].append(row)

        result["default_easy_location"] = {
            "pk": selected_location_id,
            "label": selected_label if selected_location is not None else "",
        }
        return result

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)
        for panel in panels:
            target_id = (panel.get("context") or {}).get("build_id")
            if target_id:
                panel["source"] = self.plugin_static_file("smart_allocation_v032.js:renderPanel")
                panel["context"]["easy_location_url"] = f"/plugin/{self.SLUG}/easy-location/{int(target_id)}/"
                panel["context"]["version"] = self.VERSION
        return panels
