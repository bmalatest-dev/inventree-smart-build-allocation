# Smart Build Allocation v0.2.3

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
v0.2.3 preview is read-only. Commit is intentionally disabled until the proposed allocations and warning classification are validated in the local test database.

No database migration is required. Shared Allocation Groups are cached for seven days.

## v0.2.3
- Fix InvenTree 1.6 plugin import: `InvenTreePlugin` is imported from `plugin.base`.

## v0.2.3
- Match the proven InvenTree 1.6 plugin import pattern used by Part Quality Report: `from plugin import InvenTreePlugin`.
