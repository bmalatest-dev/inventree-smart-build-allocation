import json
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.urls import path
from plugin import InvenTreePlugin
from plugin.mixins import  SettingsMixin, UserInterfaceMixin, UrlsMixin
from . import PLUGIN_VERSION
from .rules import rank_stock_items, planned_spillage, is_hand_placement, location_name, available_quantity, is_unreceived

GROUP_TTL = 60 * 60 * 24 * 7

def _group_key(build_id):
    return f"smartbuildallocation:shared-group:v0215:{int(build_id)}"

def _build_label(build):
    ref = getattr(build, "reference", None) or f"BO-{build.pk}"
    title = getattr(build, "title", None) or ""
    return f"{ref} — {title}" if title else str(ref)

def _num(value, default=0.0):
    try:
        return float(getattr(value, "amount", value))
    except (TypeError, ValueError):
        return default

def _status_text(obj):
    status = getattr(obj, "status", None)
    for candidate in (
        getattr(obj, "status_text", None),
        getattr(status, "label", None),
        getattr(status, "name", None),
        status,
    ):
        if candidate not in (None, ""):
            return str(candidate).strip().lower()
    return ""

def _closed_build(build):
    text = _status_text(build)
    return any(word in text for word in ("complete", "completed", "cancel", "cancelled", "canceled"))

def _parent_id(build):
    for attr in ("parent", "parent_build"):
        value = getattr(build, attr, None)
        if value is not None:
            return getattr(value, "pk", value)
    for attr in ("parent_id", "parent_build_id"):
        value = getattr(build, attr, None)
        if value:
            return value
    return None

def _part_label(build):
    part = getattr(build, "part", None)
    return str(part) if part is not None else ""

def _build_qty(build):
    return _num(getattr(build, "quantity", 0), 0)

def _build_url(build):
    return f"/web/manufacturing/build-order/{build.pk}/"

def _part_url(part):
    return f"/web/part/{part.pk}/"

def _batch_id(stock):
    """Human-facing package identifier used by Per Vices."""
    for attr in ("batch", "batch_code", "batch_id"):
        value = getattr(stock, attr, None)
        if value not in (None, ""):
            return str(value)
    return ""

def _build_part(build):
    part = getattr(build, "part", None)
    if part is None:
        return {"pk": None, "label": "", "url": ""}
    return {"pk": part.pk, "label": str(part), "url": _part_url(part)}

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
            path("commit/<int:build_id>/", self.commit_view, name="smart-allocation-commit"),
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
        current_parent = _parent_id(current)
        builds = []
        related = []
        other = []

        # Do not offer completed / cancelled BOs as candidates. Keep current BO visible.
        for b in Build.objects.select_related("part").all().order_by("-pk")[:500]:
            if b.pk != build_id and _closed_build(b):
                continue

            item = {
                "pk": b.pk,
                "label": _build_label(b),
                "url": _build_url(b),
                "part": _part_label(b),
                "part_detail": _build_part(b),
                "quantity": _build_qty(b),
                "status": _status_text(b),
                "parent_id": _parent_id(b),
                "selected": b.pk in group,
                "current": b.pk == build_id,
                "sequence": group.index(b.pk) + 1 if b.pk in group else None,
            }
            builds.append(item)

            if b.pk == build_id or b.pk in group:
                continue
            if current_parent is not None and _parent_id(b) == current_parent:
                related.append(item)
            else:
                other.append(item)

        return JsonResponse({
            "build_id": build_id,
            "build_ids": group,
            "builds": builds,
            "related_builds": related,
            "other_builds": other,
            "parent_id": current_parent,
            "term": "Shared Allocation Group",
        })

    def _required_lines(self, build):
        """Return outstanding component requirements from native BuildItem allocations."""
        from build.models import BuildItem, BuildLine

        rows = []
        lines = BuildLine.objects.filter(build=build).select_related(
            "bom_item", "bom_item__sub_part"
        )
        for line in lines:
            part = getattr(getattr(line, "bom_item", None), "sub_part", None)
            if part is None:
                part = getattr(line, "part", None)

            required = _num(getattr(line, "quantity", 0), 0)
            allocated = sum(
                _num(getattr(item, "quantity", 0), 0)
                for item in BuildItem.objects.filter(build_line=line)
            )
            outstanding = max(required - allocated, 0)

            if part is not None and outstanding > 0:
                rows.append((line, part, outstanding))

        return rows

    def _outside_group_allocated_quantity(self, stock, group_ids):
        """Quantity already reserved for builds outside this Shared Allocation Group."""
        from build.models import BuildItem

        group = set(int(x) for x in (group_ids or []))
        total = 0
        for item in BuildItem.objects.filter(stock_item=stock).select_related("build_line__build"):
            line = getattr(item, "build_line", None)
            build = getattr(line, "build", None) if line is not None else None
            build_id = getattr(build, "pk", None)
            if build_id is None or int(build_id) not in group:
                total += _num(getattr(item, "quantity", 0), 0)
        return total

    def _projected_start_quantity(self, stock, group_ids):
        """Physical package quantity available to the selected sequential group.

        Existing allocations to builds inside the group are intentionally not
        subtracted here; they are consumed in sequence by
        _apply_existing_group_allocations().
        """
        from .rules import is_consumed
        if is_consumed(stock):
            return 0
        physical = _num(getattr(stock, "quantity", 0), 0)
        outside = self._outside_group_allocated_quantity(stock, group_ids)
        # The entire physical package travels with its outside BO; the
        # unallocated balance is not available to this independent group.
        return 0 if outside > 0 else max(physical, 0)

    def _apply_existing_group_allocations(self, build, projected, group_ids, future_demand=None):
        """Carry existing allocations for this BO through the package projection.

        Existing BOM allocations are real reservations, but because selected BOs
        run sequentially the same physical package can continue to later BOs.
        Apply the existing BOM allocation plus one planned spillage reserve per
        BuildLine before evaluating the next BO in the sequence.
        """
        from build.models import BuildItem

        items = list(
            BuildItem.objects.filter(build_line__build=build)
            .select_related("build_line", "build_line__bom_item", "build_line__bom_item__sub_part", "stock_item")
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

            qty = _num(getattr(item, "quantity", 0), 0)
            reserve = qty

            # Spillage is a planning reserve for the BOM line, not an InvenTree
            # allocation. Apply it once to the first package used by this line.
            if line.pk not in spill_applied:
                part = getattr(getattr(line, "bom_item", None), "sub_part", None)
                if part is None:
                    part = getattr(line, "part", None)
                if part is not None:
                    spill, _ = planned_spillage(part, getattr(build, "quantity", 1))
                    # Do not consume stock needed to satisfy later BO BOM lines.
                    later = (future_demand or {}).get(part.pk, 0)
                    if projected[stock.pk] >= qty + spill + later:
                        reserve += spill
                spill_applied.add(line.pk)

            projected[stock.pk] = max(projected[stock.pk] - reserve, 0)

    def _stock_for_part(self, part):
        from stock.models import StockItem
        # Historical StockItems consumed by a BO retain their original quantity.
        # They must not enter recommendations, overrides or projections.
        qs = StockItem.objects.filter(part=part, consumed_by__isnull=True).select_related("location", "part")
        return list(qs)

    def _stock_option(self, stock, group_ids, recommended=False):
        from .rules import is_unreceived, is_consumed, is_out_for_assembly, stock_used_by_group
        loc = location_name(stock)
        low = (loc or "").lower()
        warnings = []
        selectable = True
        if is_consumed(stock):
            warnings.append("Already consumed by a Build Order")
            selectable = False
        outside = self._outside_group_allocated_quantity(stock, group_ids)
        if outside > 0:
            warnings.append(f"ALLOCATED TO ANOTHER BUILD: {outside:g} units; entire package unavailable")
            selectable = False
        if is_unreceived(stock):
            warnings.append("Ordered / awaiting receipt")
            selectable = False
        if is_out_for_assembly(stock) and not stock_used_by_group(stock, group_ids):
            warnings.append("Out-for-Assembly outside this group")
        if not loc:
            warnings.append("Unknown location")
        elif "component room" not in low and not low.startswith("out-for-assembly"):
            warnings.append("Non-preferred location")
        return {
            "stock_id": stock.pk,
            "batch_id": _batch_id(stock),
            "quantity": self._projected_start_quantity(stock, group_ids),
            "physical_quantity": _num(getattr(stock, "quantity", 0)),
            "outside_allocated": outside,
            "location": loc or "Unknown",
            "recommended": recommended,
            "selectable": selectable,
            "warnings": warnings,
        }

    def _stock_options(self, stock_items, group_ids, recommended_ids=None):
        recommended_ids = set(recommended_ids or [])
        return sorted(
            [self._stock_option(s, group_ids, s.pk in recommended_ids)
             for s in stock_items if available_quantity(s) > 0],
            key=lambda x: (not x["recommended"], not x["selectable"], len(x["warnings"]),
                           x["quantity"], x["stock_id"]),
        )

    def _manual_stock_options(self, stock_items, group_ids):
        """Stock which exists but must never be selected automatically."""
        from .rules import is_unreceived, is_consumed, is_out_for_assembly, stock_used_by_group
        options = []
        for stock in stock_items:
            loc = location_name(stock)
            if is_consumed(stock):
                continue
            outside = self._outside_group_allocated_quantity(stock, group_ids)
            if outside > 0:
                from build.models import BuildItem
                owners = sorted({str(item.build_line.build.reference) for item in BuildItem.objects.filter(stock_item=stock).select_related("build_line__build") if item.build_line and item.build_line.build_id not in group_ids})
                reason = f"ALLOCATED TO ANOTHER BUILD ({', '.join(owners)}): {outside:g} allocated; entire physical package reserved. Release allocation or establish valid sequential reuse."
            elif is_unreceived(stock):
                reason = "Stock is ordered / awaiting receipt and requires a user decision."
            elif is_out_for_assembly(stock) and not stock_used_by_group(stock, group_ids):
                reason = "Stock is Out-for-Assembly for a BO outside this Shared Allocation Group."
            else:
                continue
            options.append({
                "stock_id": stock.pk,
                "batch_id": _batch_id(stock),
                "quantity": self._projected_start_quantity(stock, group_ids),
                "physical_quantity": _num(getattr(stock, "quantity", 0)),
                "outside_allocated": outside,
                "location": loc or "Unknown",
                "reason": reason,
            })
        return options

    def _preview(self, build_id, overrides=None):
        from build.models import Build

        overrides = overrides or {}
        group_ids = self._get_group(build_id)
        builds = list(Build.objects.filter(pk__in=group_ids))
        by_id = {b.pk: b for b in builds}
        ordered_builds = [by_id[x] for x in group_ids if x in by_id]

        projected = {}  # stock pk -> projected quantity remaining after prior BOs + spillage
        result = {
            "group": [{
                "pk": b.pk, "label": _build_label(b), "url": _build_url(b),
                "part": _build_part(b), "sequence": i + 1
            } for i, b in enumerate(ordered_builds)],
            "easy": [],
            "spillage": [],
            "location": [],
            "multi": [],
            "manual": [],
            "insufficient": [],
            "notes": [],
        }

        # Track outstanding BOM demand on later builds. Planned spillage must
        # never make an otherwise satisfiable later BOM appear short.
        future_demand = {}
        for b in ordered_builds:
            for _, part, qty in self._required_lines(b):
                future_demand[part.pk] = future_demand.get(part.pk, 0) + qty

        for seq, build in enumerate(ordered_builds, start=1):
            # First account for allocations which already exist on this BO.
            # This preserves the physical package for later BOs in the group,
            # while carrying forward BOM consumption + expected spillage.
            # The current BO's existing allocations count as its own demand;
            # preserve only future BO demand when reserving discretionary spill.
            this_demand = {}
            for _, current_part, qty in self._required_lines(build):
                this_demand[current_part.pk] = this_demand.get(current_part.pk, 0) + qty
            later_demand = {part_id: max(qty - this_demand.get(part_id, 0), 0)
                            for part_id, qty in future_demand.items()}
            self._apply_existing_group_allocations(build, projected, group_ids, later_demand)

            for line, part, outstanding in self._required_lines(build):
                stock_items = self._stock_for_part(part)
                if not stock_items:
                    result["insufficient"].append({
                        "build": _build_label(build), "build_id": build.pk, "build_url": _build_url(build),
                        "build_part": _build_part(build),
                        "part": str(part), "part_id": part.pk, "part_url": _part_url(part),
                        "line_id": getattr(line, "pk", None),
                        "required": outstanding, "message": "No StockItems exist for this part.",
                    })
                    continue

                spill, spill_source = planned_spillage(part, getattr(build, "quantity", 1))
                future_demand[part.pk] = max(future_demand.get(part.pk, 0) - outstanding, 0)
                # Only reserve discretionary spillage from stock in excess of
                # all outstanding BOM requirements for this part.
                usable_total = sum(max(projected.get(s.pk, self._projected_start_quantity(s, group_ids)), 0)
                                   for s in self._stock_for_part(part)
                                   if self._outside_group_allocated_quantity(s, group_ids) <= 0
                                   and not is_unreceived(s))
                spillage_budget = max(usable_total - outstanding - future_demand[part.pk], 0)
                reservable_spill = min(spill, spillage_budget)
                ranked = rank_stock_items(
                    [s for s in stock_items if self._outside_group_allocated_quantity(s, group_ids) <= 0],
                    part, outstanding,
                    group_build_ids=group_ids,
                    projected_quantities=projected,
                )

                line_id = getattr(line, "pk", None)
                override_key = f"{build.pk}:{line_id or ('part-' + str(part.pk))}"
                commit_key = override_key
                override_rows = overrides.get(override_key, [])
                override_by_id = {
                    int(x.get("stock_id")): _num(x.get("quantity"), 0)
                    for x in override_rows
                    if x.get("stock_id") is not None and _num(x.get("quantity"), 0) > 0
                }
                if override_by_id:
                    by_stock_id = {s.pk: s for s in stock_items}
                    ranked = [by_stock_id[sid] for sid in override_by_id
                              if sid in by_stock_id and
                              self._outside_group_allocated_quantity(by_stock_id[sid], group_ids) <= 0]

                # Explicit multi-package selection takes precedence over optimization.
                if override_by_id and len(override_by_id) > 1:
                    from .rules import is_unreceived, is_consumed
                    if abs(sum(override_by_id.values()) - outstanding) > 1e-6:
                        result["insufficient"].append({
                            "build": _build_label(build), "build_id": build.pk,
                            "build_url": _build_url(build), "build_part": _build_part(build),
                            "part": str(part), "part_id": part.pk, "part_url": _part_url(part),
                            "override_key": override_key, "line_id": line_id,
                            "required": outstanding, "available": sum(override_by_id.values()),
                            "message": "Manual selection must total the outstanding BOM quantity.",
                            "stock_options": self._stock_options(stock_items, group_ids),
                        })
                        continue
                    by_stock = {s.pk: s for s in stock_items}
                    picks = []
                    for sid, qty in override_by_id.items():
                        stock = by_stock.get(sid)
                        if stock is None or is_consumed(stock) or is_unreceived(stock):
                            picks = []
                            break
                        before = projected.get(sid, self._projected_start_quantity(stock, group_ids))
                        if qty > before or qty <= 0:
                            picks = []
                            break
                        picks.append((stock, qty, before))
                    if not picks:
                        result["insufficient"].append({
                            "build": _build_label(build), "build_id": build.pk,
                            "build_url": _build_url(build), "build_part": _build_part(build),
                            "part": str(part), "part_id": part.pk, "part_url": _part_url(part),
                            "override_key": override_key, "line_id": line_id,
                            "required": outstanding,
                            "message": "Manual StockItem selection exceeds available stock or includes unreceived stock.",
                            "stock_options": self._stock_options(stock_items, group_ids),
                        })
                        continue
                    # Reserve planned spillage once per BOM line across split packages.
                    spare = {s.pk: max(before - qty, 0) for s, qty, before in picks}
                    spill_by_stock = {s.pk: 0 for s, _, _ in picks}
                    spill_left = spill
                    if spillage_budget < spill:
                        spill_left = spill - min(spill, spillage_budget)
                    to_reserve = min(spill, spillage_budget)
                    spill_to_allocate = to_reserve
                    for stock, qty, before in picks:
                        if spare[stock.pk] >= spill_to_allocate:
                            spill_by_stock[stock.pk] = spill_to_allocate
                            spill_to_allocate = 0
                            break
                    if spill_to_allocate:
                        for stock, qty, before in picks:
                            take = min(spare[stock.pk], spill_to_allocate)
                            spill_by_stock[stock.pk] += take
                            spill_to_allocate -= take
                            if spill_to_allocate <= 0:
                                break
                    spill_left += spill_to_allocate
                    for stock, qty, before in picks:
                        projected[stock.pk] = before - qty - spill_by_stock[stock.pk]
                    row = {
                        "build": _build_label(build), "build_id": build.pk,
                        "build_url": _build_url(build), "build_part": _build_part(build),
                        "sequence": seq, "part": str(part), "part_id": part.pk,
                        "part_url": _part_url(part), "line_id": line_id,
                        "override_key": override_key, "commit_key": commit_key,
                        "manual_override": True, "bom_qty": outstanding,
                        "allocate_qty": outstanding, "spillage": spill,
                        "stock_options": self._stock_options(stock_items, group_ids),
                        "stock_items": [
                            {"stock_id": s.pk, "batch_id": _batch_id(s),
                             "qty": qty, "location": location_name(s),
                             "projected_before": before,
                             "spillage_reserved": spill_by_stock[s.pk],
                             "projected_after": projected[s.pk]}
                            for s, qty, before in picks
                        ],
                        "spillage_reserved": spill - spill_left,
                        "spillage_shortfall": spill_left,
                        "message": ("Manual split: spillage shortfall remains. " if spill_left
                                    else "Manual split: full spillage reserve planned. ")
                                   + "Review package locations and projections before committing.",
                    }
                    result["multi"].append(row)
                    continue

                if override_by_id and not ranked:
                    result["insufficient"].append({
                        "build": _build_label(build), "build_id": build.pk, "build_url": _build_url(build),
                        "build_part": _build_part(build), "part": str(part), "part_id": part.pk,
                        "part_url": _part_url(part), "override_key": override_key, "line_id": line_id,
                        "required": outstanding, "stock_options": self._stock_options(stock_items, group_ids),
                        "message": "Selected StockItem is reserved for a Build Order outside this group or is otherwise unavailable."})
                    continue
                # First prefer a single package that satisfies BOM + spillage.
                chosen = None
                warning = None
                for stock in ranked:
                    q = projected.get(stock.pk, self._projected_start_quantity(stock, group_ids))
                    target = override_by_id.get(stock.pk, outstanding) if override_by_id else outstanding
                    if q >= target + spill and spillage_budget >= spill and target >= outstanding:
                        chosen = stock
                        break

                # BOM can be met, but not full spillage.
                if chosen is None:
                    for stock in ranked:
                        q = projected.get(stock.pk, self._projected_start_quantity(stock, group_ids))
                        target = override_by_id.get(stock.pk, outstanding) if override_by_id else outstanding
                        if q >= target and target >= outstanding:
                            chosen = stock
                            warning = "spillage"
                            break

                if chosen is not None:
                    before = projected.get(chosen.pk, self._projected_start_quantity(chosen, group_ids))
                    reserve = outstanding + (spill if warning != "spillage" and before >= outstanding + spill and spillage_budget >= spill else 0)
                    after = max(before - reserve, 0)
                    projected[chosen.pk] = after
                    loc = location_name(chosen)
                    row = {
                        "build": _build_label(build), "build_id": build.pk, "build_url": _build_url(build),
                        "build_part": _build_part(build), "sequence": seq,
                        "part": str(part), "part_id": part.pk, "part_url": _part_url(part),
                        "line_id": line_id,
                        "stock_id": chosen.pk, "batch_id": _batch_id(chosen), "location": loc,
                        "override_key": override_key, "commit_key": commit_key,
                        "manual_override": bool(override_by_id),
                        "bom_qty": outstanding, "spillage": spill,
                        "spillage_source": spill_source,
                        "projected_before": before, "projected_after": after,
                        "allocate_qty": outstanding,
                        "hand_placement": is_hand_placement(part),
                    }
                    if reserve < outstanding + spill:
                        warning = "spillage"
                        row["spillage_reserved"] = reserve - outstanding
                        row["spillage_shortfall"] = spill - (reserve - outstanding)
                    row["stock_options"] = self._stock_options(
                        stock_items, group_ids, recommended_ids=[chosen.pk]
                    )
                    lowloc = (loc or "").lower()
                    if warning == "spillage":
                        row["message"] = "BOM quantity can be satisfied, but full spillage cannot be reserved."
                        result["spillage"].append(row)
                    elif not lowloc:
                        row["message"] = "Stock location is unknown; user review is required."
                        result["location"].append(row)
                    elif is_hand_placement(part) and ("component room" not in lowloc):
                        row["message"] = f"Hand Placement stock selected from non-standard location: {loc or 'Unknown'}."
                        result["location"].append(row)
                    elif lowloc.startswith("out-for-assembly"):
                        row["message"] = f"Stock is currently Out-for-Assembly at {loc}."
                        result["location"].append(row)
                    elif (not is_hand_placement(part)) and ("component room" not in lowloc):
                        row["message"] = f"Stock is outside the preferred Component Room location: {loc}."
                        result["location"].append(row)
                    else:
                        result["easy"].append(row)
                    continue

                # No single package. Determine whether multiple packages can cover BOM.
                remaining = outstanding
                picks = []
                for stock in ranked:
                    q = projected.get(stock.pk, self._projected_start_quantity(stock, group_ids))
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
                        "build": _build_label(build), "build_id": build.pk, "build_url": _build_url(build),
                        "build_part": _build_part(build), "sequence": seq,
                        "part": str(part), "part_id": part.pk, "part_url": _part_url(part),
                        "line_id": line_id,
                        "override_key": override_key, "commit_key": commit_key,
                        "bom_qty": outstanding, "spillage": spill,
                        "allocate_qty": outstanding,
                        "hand_placement": is_hand_placement(part),
                        "stock_items": [
                            {"stock_id": s.pk, "batch_id": _batch_id(s), "qty": take, "location": location_name(s)}
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
                    manual_options = self._manual_stock_options(stock_items, group_ids)
                    if manual_options:
                        result["manual"].append({
                            "build": _build_label(build), "build_id": build.pk, "build_url": _build_url(build),
                            "build_part": _build_part(build),
                            "part": str(part), "part_id": part.pk, "part_url": _part_url(part),
                            "override_key": override_key, "line_id": line_id,
                            "required": outstanding,
                            "available_automatic": outstanding - remaining,
                            "options": manual_options,
                            "stock_options": self._stock_options(stock_items, group_ids),
                            "message": "Automatic allocation cannot satisfy the requirement, but stock exists which requires a user decision.",
                        })
                    else:
                        result["insufficient"].append({
                            "build": _build_label(build), "build_id": build.pk, "build_url": _build_url(build),
                            "build_part": _build_part(build),
                            "part": str(part), "part_id": part.pk, "part_url": _part_url(part),
                            "override_key": override_key, "line_id": line_id,
                            "required": outstanding,
                            "available": outstanding - remaining,
                            "stock_options": self._stock_options(stock_items, group_ids),
                            "message": "Actual BOM quantity cannot be satisfied.",
                        })

        return result

    def _allocation_rows(self, preview):
        rows = {}
        for section in ("easy", "spillage", "location", "multi"):
            for row in preview.get(section, []):
                key = row.get("commit_key")
                if key:
                    rows[key] = (section, row)
        return rows

    def _create_build_item(self, build, line, stock, quantity):
        """Create / extend an allocation using InvenTree native semantics."""
        from build.models import BuildItem

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

    def commit_view(self, request, build_id):
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        selected = set(str(x) for x in (payload.get("selected") or []))
        approved = set(str(x) for x in (payload.get("approved") or []))
        overrides = payload.get("overrides") or {}
        selected_rows_payload = payload.get("selected_rows") or {}

        if not selected:
            return JsonResponse({"error": "No allocations are selected."}, status=400)

        try:
            # Use the exact rows from the Preview the user confirmed. Re-running
            # the optimizer here can legitimately produce a different recommendation
            # for a sequential Shared Allocation Group and caused false "stale"
            # failures in v0.2.11.
            #
            # Safety does not depend on trusting these rows: every selected row is
            # revalidated below under database locks against the live BuildLine,
            # StockItem part, outstanding BOM quantity and actual InvenTree
            # availability before anything is written.
            available_rows = {}
            for key in selected:
                entry = selected_rows_payload.get(key)
                if not isinstance(entry, dict):
                    return JsonResponse({
                        "error": "Selected Preview details are missing. Run Analyze / Preview again.",
                        "stale": [key],
                    }, status=409)
                section = str(entry.get("section") or "")
                row = entry.get("row")
                if section not in ("easy", "spillage", "location", "multi") or not isinstance(row, dict):
                    return JsonResponse({
                        "error": "Selected Preview details are invalid. Run Analyze / Preview again.",
                        "stale": [key],
                    }, status=409)
                if str(row.get("commit_key") or "") != key:
                    return JsonResponse({
                        "error": "Selected Preview no longer matches the confirmed allocation.",
                        "stale": [key],
                    }, status=409)
                available_rows[key] = (section, row)

            # Warning rows require explicit approval at the time of commit.
            unapproved = sorted(
                key for key in selected
                if available_rows[key][0] != "easy" and key not in approved
            )
            if unapproved:
                return JsonResponse({
                    "error": "One or more selected warning allocations have not been approved.",
                    "unapproved": unapproved,
                }, status=400)

            from build.models import Build, BuildLine
            from stock.models import StockItem

            created = []
            skipped = 0

            # Atomic commit: either all selected allocations are created, or none are.
            with transaction.atomic():
                # Lock all relevant rows before final validation.
                build_ids = {int(available_rows[k][1]["build_id"]) for k in selected}
                builds = {
                    b.pk: b for b in Build.objects.select_for_update().filter(pk__in=build_ids)
                }

                stock_ids = set()
                for key in selected:
                    row = available_rows[key][1]
                    if row.get("stock_id"):
                        stock_ids.add(int(row["stock_id"]))
                    for s in row.get("stock_items") or []:
                        stock_ids.add(int(s["stock_id"]))

                stocks = {
                    s.pk: s for s in StockItem.objects.select_for_update().filter(pk__in=stock_ids)
                }

                # Track quantities within this transaction so two selected rows cannot
                # over-allocate the same physical package.
                remaining = {sid: available_quantity(stock) for sid, stock in stocks.items()}

                for key in selected:
                    section, row = available_rows[key]
                    build = builds.get(int(row["build_id"]))
                    if build is None or _closed_build(build):
                        raise ValueError(f"{row.get('build')} is complete, cancelled, or unavailable.")

                    line_id = row.get("line_id")
                    if not line_id:
                        raise ValueError(
                            f"Cannot commit {row.get('build')} / {row.get('part')}: build line is unavailable."
                        )
                    line = BuildLine.objects.select_for_update().select_related(
                        "bom_item", "bom_item__sub_part"
                    ).get(pk=line_id, build=build)

                    # Recalculate current outstanding BOM quantity after locking.
                    required = _num(getattr(line, "quantity", 0), 0)
                    from build.models import BuildItem
                    allocated = sum(
                        _num(getattr(item, "quantity", 0), 0)
                        for item in BuildItem.objects.filter(build_line=line)
                    )
                    outstanding = max(required - allocated, 0)

                    requested = _num(row.get("allocate_qty"), 0)
                    if requested <= 0 or outstanding + 1e-9 < requested:
                        raise ValueError(
                            f"{row.get('build')} / {row.get('part')} changed since Preview. "
                            "Run Analyze / Preview again."
                        )

                    allocations = []
                    if row.get("stock_id"):
                        allocations = [(int(row["stock_id"]), requested)]
                    else:
                        allocations = [
                            (int(x["stock_id"]), _num(x.get("qty"), 0))
                            for x in (row.get("stock_items") or [])
                        ]

                    if abs(sum(q for _, q in allocations) - requested) > 1e-6:
                        raise ValueError(
                            f"Allocation quantities for {row.get('build')} / {row.get('part')} no longer match."
                        )

                    for sid, qty in allocations:
                        stock = stocks.get(sid)
                        if stock is None:
                            raise ValueError(f"Stock #{sid} no longer exists.")
                        from .rules import is_consumed, is_unreceived
                        if is_consumed(stock) or is_unreceived(stock):
                            raise ValueError(
                                f"Stock #{sid} has been consumed or is awaiting receipt. "
                                "Run Analyze / Preview again."
                            )
                        if self._outside_group_allocated_quantity(stock, group_ids) > 0:
                            raise ValueError(f"Stock #{sid} is allocated to another Build Order outside this group. Release it or establish valid sequential reuse.")
                        if getattr(stock, "part_id", None) != int(row["part_id"]):
                            raise ValueError(
                                f"Stock #{sid} no longer matches {row.get('part')}."
                            )
                        if qty <= 0 or remaining.get(sid, 0) + 1e-9 < qty:
                            raise ValueError(
                                f"Stock #{sid} no longer has sufficient available quantity. "
                                "Run Analyze / Preview again."
                            )

                        before_allocated = sum(
                            _num(getattr(existing, "quantity", 0), 0)
                            for existing in BuildItem.objects.filter(build_line=line, stock_item=stock)
                        )
                        item = self._create_build_item(build, line, stock, qty)

                        # Verify the database write immediately. If this does not
                        # read back exactly, the surrounding atomic transaction rolls
                        # back all selected allocations.
                        item.refresh_from_db()
                        after_allocated = sum(
                            _num(getattr(existing, "quantity", 0), 0)
                            for existing in BuildItem.objects.filter(build_line=line, stock_item=stock)
                        )
                        if after_allocated + 1e-9 < before_allocated + qty:
                            raise ValueError(
                                f"Allocation verification failed for {row.get('build')} / "
                                f"{row.get('part')} / Stock #{sid}. No allocations were committed."
                            )

                        remaining[sid] -= qty
                        created.append({
                            "pk": item.pk,
                            "build": _build_label(build),
                            "part": row.get("part"),
                            "stock_id": sid,
                            "batch_id": _batch_id(stock),
                            "quantity": qty,
                        })

            skipped = max(len(available_rows) - len(selected), 0)
            return JsonResponse({
                "ok": True,
                "created_count": len(created),
                "selected_lines": len(selected),
                "skipped_lines": skipped,
                "created": created,
                "message": f"Commit successful — {len(created)} allocation record(s) created / updated across {len(selected)} selected BOM line(s).",
            })

        except (ValueError, BuildLine.DoesNotExist) as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except Exception as exc:
            return JsonResponse(
                {"error": f"Commit failed; no selected allocations were written: {type(exc).__name__}: {exc}"},
                status=500,
            )

    def preview_view(self, request, build_id):
        if request.method not in ("GET", "POST"):
            return JsonResponse({"error": "Preview supports allocation review in v0.2.12"}, status=405)
        overrides = {}
        if request.method == "POST":
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
                overrides = payload.get("overrides") or {}
            except Exception:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
        try:
            return JsonResponse(self._preview(build_id, overrides=overrides))
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
            "source": self.plugin_static_file("smart_allocation_v0217.js:renderPanel"),
            "context": {
                "version": self.VERSION,
                "build_id": int(target_id),
                "group_url": f"/plugin/{self.SLUG}/group/{int(target_id)}/",
                "preview_url": f"/plugin/{self.SLUG}/preview/{int(target_id)}/",
                "commit_url": f"/plugin/{self.SLUG}/commit/{int(target_id)}/",
            },
        }]
