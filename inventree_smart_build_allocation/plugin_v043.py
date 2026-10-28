import json

from django.core.cache import cache

from .plugin import _group_key
from .plugin_v041 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.43: keep Shared Allocation Group cache entries mutually consistent.

    A group is cached under every member BO so it can be opened from any member.
    Older versions only overwrote keys for BOs which remained in the newly-saved
    group. Removed BOs therefore retained stale copies of the old group and could
    later resurrect removed members.

    Before saving, clear the entire connected set of old cache entries touched by
    either the current BO or any BO submitted in the new group. The inherited
    POST handler then validates the submitted IDs and writes one identical ordered
    sequence for every member of the new group.
    """

    VERSION = "0.2.43"

    @staticmethod
    def _cached_group_members(seed_ids):
        """Return all BO IDs connected to seed_ids through cached group entries."""
        pending = []
        for value in seed_ids:
            try:
                pending.append(int(value))
            except (TypeError, ValueError):
                continue

        members = set()
        while pending:
            bid = pending.pop()
            if bid in members:
                continue
            members.add(bid)

            cached = cache.get(_group_key(bid)) or []
            for value in cached:
                try:
                    member_id = int(value)
                except (TypeError, ValueError):
                    continue
                if member_id not in members:
                    pending.append(member_id)

        return members

    def group_view(self, request, build_id):
        if request.method == "POST":
            try:
                data = json.loads(request.body.decode("utf-8") or "{}")
            except Exception:
                # Preserve the base handler's normal Invalid JSON response.
                return super().group_view(request, build_id)

            submitted = data.get("build_ids", [])
            seeds = [build_id, *submitted]

            # Clear every stale copy of any old group connected to the BOs being
            # saved. This is deliberately done before the inherited handler writes
            # the new canonical sequence under each new member key.
            stale_members = self._cached_group_members(seeds)
            if stale_members:
                cache.delete_many([_group_key(bid) for bid in stale_members])

        return super().group_view(request, build_id)

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)
        for panel in panels:
            panel_context = panel.get("context") or {}
            if panel_context.get("build_id"):
                panel_context["version"] = self.VERSION
                panel["context"] = panel_context
        return panels
