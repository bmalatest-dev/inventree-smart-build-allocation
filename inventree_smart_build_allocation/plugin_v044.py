import json

from django.db import transaction
from django.http import JsonResponse

from .plugin_v041 import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


GROUP_METADATA_KEY = "smartbuildallocation_shared_group"


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.44: persist Shared Allocation Groups in the InvenTree database.

    Django cache is not suitable for this state because production may serve
    requests from multiple workers with independent local caches. Store the
    ordered group in Build.metadata instead, which is shared by every worker and
    survives worker restarts.
    """

    VERSION = "0.2.44"

    @staticmethod
    def _metadata_group(build):
        metadata = getattr(build, "metadata", None) or {}
        raw = metadata.get(GROUP_METADATA_KEY, [])
        group = []
        seen = set()
        if isinstance(raw, list):
            for value in raw:
                try:
                    bid = int(value)
                except (TypeError, ValueError):
                    continue
                if bid not in seen:
                    group.append(bid)
                    seen.add(bid)
        return group

    def _get_group(self, build_id):
        from build.models import Build

        try:
            build = Build.objects.only("pk", "metadata").get(pk=build_id)
        except Build.DoesNotExist:
            return [int(build_id)]

        group = self._metadata_group(build)
        return group or [int(build_id)]

    def _connected_metadata_members(self, seed_ids):
        """Find all BOs connected through previously stored group metadata."""
        from build.models import Build

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

            try:
                build = Build.objects.only("pk", "metadata").get(pk=bid)
            except Build.DoesNotExist:
                continue

            for member_id in self._metadata_group(build):
                if member_id not in members:
                    pending.append(member_id)

        return members

    def group_view(self, request, build_id):
        from build.models import Build

        if request.method != "POST":
            # The inherited GET path calls self._get_group(), so it now reads the
            # database-backed metadata rather than the Django cache.
            return super().group_view(request, build_id)

        try:
            Build.objects.only("pk").get(pk=build_id)
        except Build.DoesNotExist:
            return JsonResponse({"error": f"Build Order {build_id} was not found"}, status=404)

        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        raw = data.get("build_ids", [])
        ordered = [int(build_id)]
        seen = {int(build_id)}
        if isinstance(raw, list):
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

        # Include every member referenced by either the old or new group so a
        # removed BO cannot retain stale membership metadata.
        old_members = self._connected_metadata_members(ordered)
        affected = old_members | set(ordered)

        with transaction.atomic():
            builds = {
                build.pk: build
                for build in Build.objects.select_for_update().filter(pk__in=affected)
            }

            for bid, build in builds.items():
                metadata = dict(getattr(build, "metadata", None) or {})
                if bid in ordered:
                    metadata[GROUP_METADATA_KEY] = list(ordered)
                else:
                    metadata.pop(GROUP_METADATA_KEY, None)
                build.metadata = metadata
                build.save(update_fields=["metadata"])

        return JsonResponse({"ok": True, "build_ids": ordered})

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)
        for panel in panels:
            panel_context = panel.get("context") or {}
            if panel_context.get("build_id"):
                panel_context["version"] = self.VERSION
                panel["context"] = panel_context
        return panels
