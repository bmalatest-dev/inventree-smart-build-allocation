# Smart Build Allocation v0.2.6

Testing build for InvenTree 1.6.x.

## Implemented
- Shared Allocation Group selection
- Ordered / sequential BO sequence
- Sequence-aware projected package depletion
- BOM + spillage reserved for planning; BOM quantity remains the intended allocation quantity
- Analyze / Preview screen
- Easy Allocations
- Spillage Warnings
- Location Warnings
- Multiple Stock Item Warnings
- Insufficient Stock
- Hand Placement recognition
- Component Room / Rework / Storage logic
- low-cost reel and packaging preferences

## Safety
v0.2.6 preview is read-only. Commit is intentionally disabled until the proposed allocations and warning classification are validated in the local test database.

No database migration is required. Shared Allocation Groups are cached for seven days.

## v0.2.6
- Fix InvenTree 1.6 plugin import: `InvenTreePlugin` is imported from `plugin.base`.

## v0.2.6
- Match the proven InvenTree 1.6 plugin import pattern used by Part Quality Report: `from plugin import InvenTreePlugin`.

## v0.2.6
- Removed unsupported `AllocateMixin` dependency for the target InvenTree 1.6 installation.
- Removed the legacy `filter_build_allocation` hook.
- Retained the explicit Build Order panel/API workflow using `UrlsMixin`, `SettingsMixin`, and `UserInterfaceMixin`.
- Preview remains read-only; Commit remains intentionally disabled.

## v0.2.6
- Fix React INVE-E17 / minified error #310 by moving all React hooks into a dedicated component.
- `renderPanel` is now a hook-free renderer which returns the SmartAllocationPanel component.
- Add defensive endpoint checks and loading state.
- Preview remains read-only; Commit remains intentionally disabled.

## v0.2.6
- Exclude Complete / Cancelled BOs from Shared Allocation Group candidates.
- Separate same-parent active BOs from searchable other active BOs.
- Unknown locations are Location Warnings.
- Ordered / awaiting-receipt stock is never automatically selected.
- Out-for-assembly stock outside the selected group and unreceived stock can be surfaced under Stock Available for Manual Decision.
