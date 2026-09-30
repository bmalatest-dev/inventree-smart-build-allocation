import json
from django.core.cache import cache
from django.http import JsonResponse
from django.urls import path
from plugin import InvenTreePlugin
from plugin.mixins import  SettingsMixin, UserInterfaceMixin, UrlsMixin
from . import PLUGIN_VERSION
from .rules import rank_stock_items, planned_spillage, is_hand_placement, location_name, available_quantity

GROUP_TTL = 60 * 60 * 24 * 7

def _group_key(build_id):
    return f"smartbuildallocation:shared-group:v024:{int(build_id)}"

def _build_label(build):
    ref = getattr(build, "reference", None) or f"BO-{build.pk}"
    title = getattr(build, "title", None) or ""
    return f"{ref} — {title}" if title else str(ref)

def _num(value, default=0.0):
    try:
        return float(getattr(value, "amount", value))
    except (TypeError, ValueError):
        return default

class SmartBuildAllocationPlugin(UrlsMixin, SettingsMixin, UserInterfaceMixin, InvenTreePlugin):
    NAME = "SmartBuildAllocation"
    SLUG = "smartbuildallocation"
    TITLE = "Smart Build Allocation"
    DESCRIPTION = "Preview and sequence-aware stock allocation for Build Orders"
    VERSION = PLUGIN_VERSION
    AUTHOR = "Per Vices Corporation"
    LICENSE = "MIT"

    SETTINGS = {
        "COMPONENT_ROOM_TEXT": {
            "name": "Component Room location text",
            "description": "Preferred stock location text (case-insensitive)",
            "default": "component room",
        },
        "LOW_COST_REEL_THRESHOLD": {
            "name": "Low-cost reel preference threshold",
            "description": "Prefer reel packaging below this unit purchase price",
            "default": 0.15,
            "validator": float,
        },
    }

    def setup_urls(self):
        return [
            path("group/<int:build_id>/", self.group_view, name="smart-allocation-group"),
            path("preview/<int:build_id>/", self.preview_view, name="smart-allocation-preview"),
        ]

    def _get_group(self, build_id):
        group = cache.get(_group_key(build_id))
        if not group:
            group = [int(build_id)]
        return [int(x) for x in group]

    def group_view(self, request, build_id):
        from build.models import Build

        try:
            current = Build.objects.get(pk=build_id)
        except Build.DoesNotExist:
            return JsonResponse({"error": f"Build Order {build_id} was not found"}, status=404)

        if request.method == "POST":
            try:
                data = json.loads(request.body.decode("utf-8") or "{}")
            except Exception:
                return JsonResponse({"error": "Invalid JSON"}, status=400)

            raw = data.get("build_ids", [])
            ordered = [int(build_id)]
            seen = {int(build_id)}
            for value in raw:
                try:
                    bid = int(value)
                except (TypeError, ValueError):
                    continue
                if bid not in seen:
                    ordered.append(bid)
                    seen.add(bid)

            valid = set(Build.objects.filter(pk__in=ordered).values_list("pk", flat=True))
            ordered = [bid for bid in ordered if bid in valid]
            if int(build_id) not in ordered:
                ordered.insert(0, int(build_id))

            # Store the same ordered sequence for every BO in the group.
            for bid in ordered:
                cache.set(_group_key(bid), ordered, GROUP_TTL)

            return JsonResponse({"ok": True, "build_ids": ordered})

        group = self._get_group(build_id)
        builds = []
        for b in Build.objects.all().order_by("-pk")[:250]:
            builds.append({
                "pk": b.pk,
                "label": _build_label(b),
                "selected": b.pk in group,
                "current": b.pk == build_id,
                "sequence": group.index(b.pk) + 1 if b.pk in group else None,
            })

        return JsonResponse({
            "build_id": build_id,
            "build_ids": group,
            "builds": builds,
            "term": "Shared Allocation Group",
        })

    def _required_lines(self, build):
        """Return outstanding component requirements using current InvenTree models."""
        rows = []
        try:
            from build.models import BuildLine
            lines = BuildLine.objects.filter(build=build).select_related("bom_item", "bom_item__sub_part")
            for line in lines:
                part = getattr(getattr(line, "bom_item", None), "sub_part", None)
                if part is None:
                    part = getattr(line, "part", None)
                required = _num(getattr(line, "quantity", 0), 0)
                allocated = _num(getattr(line, "allocated", 0), 0)
                # Some versions expose allocated as a method/property elsewhere.
                if allocated == 0:
                    for attr in ("allocated_quantity", "allocation_count"):
                        val = getattr(line, attr, None)
                        if val is not None and not callable(val):
                            allocated = _num(val, 0)
                            break
                outstanding = max(required - allocated, 0)
                if part is not None and outstanding > 0:
                    rows.append((line, part, outstanding))
            if rows:
                return rows
        except Exception:
            pass

        # Compatibility fallback: Build.required_parts.
        try:
            for item in list(build.required_parts):
                part = item.get("part")
                required = _num(item.get("quantity"), 0)
                allocated = _num(item.get("allocated"), 0)
                outstanding = max(required - allocated, 0)
                if part is not None and outstanding > 0:
                    rows.append((None, part, outstanding))
        except Exception:
            pass
        return rows

    def _stock_for_part(self, part):
        from stock.models import StockItem
        qs = StockItem.objects.filter(part=part).select_related("location", "part")
        # Keep preview broad; rules.py will rank / flag candidates.
        return list(qs)

    def _preview(self, build_id):
        from build.models import Build

        group_ids = self._get_group(build_id)
        builds = list(Build.objects.filter(pk__in=group_ids))
        by_id = {b.pk: b for b in builds}
        ordered_builds = [by_id[x] for x in group_ids if x in by_id]

        projected = {}  # stock pk -> projected quantity remaining after prior BOs + spillage
        result = {
            "group": [{"pk": b.pk, "label": _build_label(b), "sequence": i + 1} for i, b in enumerate(ordered_builds)],
            "easy": [],
            "spillage": [],
            "location": [],
            "multi": [],
            "insufficient": [],
            "notes": [],
        }

        for seq, build in enumerate(ordered_builds, start=1):
            for line, part, outstanding in self._required_lines(build):
                stock_items = self._stock_for_part(part)
                if not stock_items:
                    result["insufficient"].append({
                        "build": _build_label(build), "build_id": build.pk,
                        "part": str(part), "part_id": part.pk,
                        "required": outstanding, "message": "No StockItems exist for this part.",
                    })
                    continue

                spill, spill_source = planned_spillage(part, getattr(build, "quantity", 1))
                ranked = rank_stock_items(
                    stock_items, part, outstanding,
                    group_build_ids=group_ids,
                    projected_quantities=projected,
                )

                # First prefer a single package that satisfies BOM + spillage.
                chosen = None
                warning = None
                for stock in ranked:
                    q = projected.get(stock.pk, available_quantity(stock))
                    if q >= outstanding + spill:
                        chosen = stock
                        break

                # BOM can be met, but not full spillage.
                if chosen is None:
                    for stock in ranked:
                        q = projected.get(stock.pk, available_quantity(stock))
                        if q >= outstanding:
                            chosen = stock
                            warning = "spillage"
                            break

                if chosen is not None:
                    before = projected.get(chosen.pk, available_quantity(chosen))
                    reserve = outstanding + (spill if before >= outstanding + spill else 0)
                    after = max(before - reserve, 0)
                    projected[chosen.pk] = after
                    loc = location_name(chosen)
                    row = {
                        "build": _build_label(build), "build_id": build.pk, "sequence": seq,
                        "part": str(part), "part_id": part.pk,
                        "stock_id": chosen.pk, "location": loc,
                        "bom_qty": outstanding, "spillage": spill,
                        "spillage_source": spill_source,
                        "projected_before": before, "projected_after": after,
                        "allocate_qty": outstanding,
                        "hand_placement": is_hand_placement(part),
                    }
                    lowloc = (loc or "").lower()
                    if warning == "spillage":
                        row["message"] = "BOM quantity can be satisfied, but full spillage cannot be reserved."
                        result["spillage"].append(row)
                    elif is_hand_placement(part) and ("component room" not in lowloc):
                        row["message"] = f"Hand Placement stock selected from non-standard location: {loc or 'Unknown'}."
                        result["location"].append(row)
                    elif lowloc.startswith("out-for-assembly"):
                        row["message"] = f"Stock is currently Out-for-Assembly at {loc}."
                        result["location"].append(row)
                    else:
                        result["easy"].append(row)
                    continue

                # No single package. Determine whether multiple packages can cover BOM.
                remaining = outstanding
                picks = []
                for stock in ranked:
                    q = projected.get(stock.pk, available_quantity(stock))
                    if q <= 0:
                        continue
                    take = min(q, remaining)
                    if take > 0:
                        picks.append((stock, take, q))
                        remaining -= take
                    if remaining <= 0:
                        break

                if remaining <= 0 and picks:
                    for stock, take, before in picks:
                        projected[stock.pk] = max(before - take, 0)
                    row = {
                        "build": _build_label(build), "build_id": build.pk, "sequence": seq,
                        "part": str(part), "part_id": part.pk,
                        "bom_qty": outstanding, "spillage": spill,
                        "allocate_qty": outstanding,
                        "hand_placement": is_hand_placement(part),
                        "stock_items": [
                            {"stock_id": s.pk, "qty": take, "location": location_name(s)}
                            for s, take, _ in picks
                        ],
                    }
                    if is_hand_placement(part):
                        row["message"] = "Multiple StockItems intentionally proposed for Hand Placement / use-up-stock behavior."
                        result["easy"].append(row)
                    else:
                        row["message"] = "Standard component requires multiple StockItems; review required."
                        result["multi"].append(row)
                else:
                    result["insufficient"].append({
                        "build": _build_label(build), "build_id": build.pk,
                        "part": str(part), "part_id": part.pk,
                        "required": outstanding,
                        "available": outstanding - remaining,
                        "message": "Actual BOM quantity cannot be satisfied.",
                    })

        return result

    def preview_view(self, request, build_id):
        if request.method != "GET":
            return JsonResponse({"error": "Preview is read-only in v0.2.1"}, status=405)
        try:
            return JsonResponse(self._preview(build_id))
        except Exception as exc:
            return JsonResponse({"error": f"Preview failed: {type(exc).__name__}: {exc}"}, status=500)


    def get_ui_panels(self, request, context, **kwargs):
        context = context or {}
        target_model = str(
            context.get("target_model") or context.get("model") or context.get("model_type") or ""
        ).lower()
        target_id = context.get("target_id") or context.get("pk") or context.get("id")
        if target_model and "build" not in target_model:
            return []
        if not target_id:
            return []
        return [{
            "key": "smart-build-allocation",
            "title": "Smart Allocation",
            "description": "Shared Allocation Group, sequence and allocation preview",
            "icon": "ti:arrows-sort",
            "source": self.plugin_static_file("smart_allocation_v024.js:renderPanel"),
            "context": {
                "version": self.VERSION,
                "build_id": int(target_id),
                "group_url": f"/plugin/{self.SLUG}/group/{int(target_id)}/",
                "preview_url": f"/plugin/{self.SLUG}/preview/{int(target_id)}/",
            },
        }]
