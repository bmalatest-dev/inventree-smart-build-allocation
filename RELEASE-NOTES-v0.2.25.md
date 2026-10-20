# v0.2.25

## Fixes

- Uses InvenTree's native `BuildLine.unallocated_quantity()` as the source of truth for outstanding BOM demand.
- Prevents already-satisfied Build Order lines (including consumed or fully allocated lines) from being proposed for allocation again.
- Preserves Shared Allocation Group behavior so existing packages can still provide sequential package context for later selected Build Orders.
- Keeps spillage planning separate from BOM fulfillment.

## Packaging

- Synchronizes the Python package metadata and plugin version at `0.2.25`.
- Adds and loads the versioned `smart_allocation_v0225.js` UI asset.
- Updates the UI version label to `V0.2.25`.
