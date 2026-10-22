import json

from django.core.cache import cache
from django.http import JsonResponse
from django.urls import path

from .plugin_v029 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


EASY_LOCATION_TTL = 60 * 60 * 24 * 7


def _easy_location_key(build_id):
    return f"smartbuildallocation:easy-location:v0232:{int(build_id)}"


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.32: per-run Default Easy Location plus exact selected-group allocation reuse."""

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
        """True for the selected location itself or any of its descendants."""
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
        """Use live BuildItem allocations, not location names or historical relation guesses."""
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
        locations = []
        for location in StockLocation.objects.select_related("parent").all().order_by("name", "pk"):
            locations.append({"pk": location.pk, "label": self._location_label(location)})

        selected = next((x for x in locations if x["pk"] == selected_id), None)
        return JsonResponse({
            "build_id": int(build_id),
            "group_ids": group_ids,
            "location_id": selected_id,
            "location": selected,
            "locations": locations,
        })

    def group_view(self, request, build_id):
        """Keep the selected Easy Location attached when the group membership changes."""
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
        """Use selected location hierarchy or live selected-group allocation as the Easy rule."""
        from stock.models import StockItem
        from . import plugin as plugin_module

        group_ids = self._get_group(build_id)
        selected_location_id = self._easy_location_id(build_id)
        original_rank = plugin_module.rank_stock_items

        def run_rank(stock_items, required_part=None, required_qty=0, group_build_ids=None, projected_quantities=None):
            ranked = original_rank(
                stock_items,
                required_part,
                required_qty,
                group_build_ids=group_build_ids,
                projected_quantities=projected_quantities,
            )
            original_position = {getattr(stock, "pk", None): i for i, stock in enumerate(ranked)}
            return sorted(
                ranked,
                key=lambda stock: (
                    0 if self._currently_allocated_to_group(stock, group_ids) else 1,
                    0 if self._location_is_within(getattr(stock, "location", None), selected_location_id) else 1,
                    original_position.get(getattr(stock, "pk", None), 10**9),
                ),
            )

        # The validated allocation engine remains unchanged; only location preference
        # is supplied for this preview invocation.
        plugin_module.rank_stock_items = run_rank
        try:
            result = super()._preview(build_id, overrides=overrides)
        finally:
            plugin_module.rank_stock_items = original_rank

        # Reclassify only rows whose distinction is location. Variant, spillage,
        # multi-package and shortage decisions retain their existing behavior.
        location_rows = list(result.get("location", []))
        easy_rows = list(result.get("easy", []))
        reconsider = easy_rows + location_rows
        result["easy"] = []
        result["location"] = []

        for row in reconsider:
            stock = None
            stock_id = row.get("stock_id")
            if stock_id is not None:
                try:
                    stock = StockItem.objects.select_related("location", "location__parent").get(pk=stock_id)
                except StockItem.DoesNotExist:
                    stock = None

            in_default_location = stock is not None and self._location_is_within(
                getattr(stock, "location", None), selected_location_id
            )
            allocated_to_group = stock is not None and self._currently_allocated_to_group(stock, group_ids)

            if in_default_location or allocated_to_group:
                if allocated_to_group and not in_default_location:
                    row["message"] = "Stock is already allocated to a Build Order in this Shared Allocation Group and is eligible for sequential reuse."
                else:
                    row.pop("message", None)
                result["easy"].append(row)
            else:
                selected_label = "selected Default Easy Location"
                if selected_location_id is not None:
                    from stock.models import StockLocation
                    selected_location = StockLocation.objects.filter(pk=selected_location_id).first()
                    if selected_location is not None:
                        selected_label = self._location_label(selected_location)
                row["message"] = (
                    f"Stock is outside the Default Easy Location ({selected_label}) and is not currently "
                    "allocated to a Build Order in this Shared Allocation Group."
                )
                result["location"].append(row)

        result["default_easy_location"] = {
            "pk": selected_location_id,
            "label": next((self._location_label(x) for x in __import__("stock.models", fromlist=["StockLocation"]).StockLocation.objects.filter(pk=selected_location_id)), "") if selected_location_id is not None else "",
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
