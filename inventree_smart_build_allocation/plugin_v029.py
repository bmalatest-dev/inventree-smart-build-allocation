from decimal import Decimal

from .plugin import SmartBuildAllocationPlugin as SmartBuildAllocationPluginBase


class SmartBuildAllocationPlugin(SmartBuildAllocationPluginBase):
    """v0.2.29 hotfix for Decimal-safe allocation commits."""

    def _create_build_item(self, build, line, stock, quantity):
        """Create / extend an allocation using InvenTree native Decimal quantities."""
        from build.models import BuildItem

        quantity = Decimal(str(quantity))
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
