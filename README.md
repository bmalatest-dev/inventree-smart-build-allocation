# Smart Build Allocation v0.2.12

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
v0.2.12 preview is read-only. Commit is intentionally disabled until the proposed allocations and warning classification are validated in the local test database.

No database migration is required. Shared Allocation Groups are cached for seven days.

## v0.2.12
- Fix InvenTree 1.6 plugin import: `InvenTreePlugin` is imported from `plugin.base`.

## v0.2.12
- Match the proven InvenTree 1.6 plugin import pattern used by Part Quality Report: `from plugin import InvenTreePlugin`.

## v0.2.12
- Removed unsupported `AllocateMixin` dependency for the target InvenTree 1.6 installation.
- Removed the legacy `filter_build_allocation` hook.
- Retained the explicit Build Order panel/API workflow using `UrlsMixin`, `SettingsMixin`, and `UserInterfaceMixin`.
- Preview remains read-only; Commit remains intentionally disabled.

## v0.2.12
- Fix React INVE-E17 / minified error #310 by moving all React hooks into a dedicated component.
- `renderPanel` is now a hook-free renderer which returns the SmartAllocationPanel component.
- Add defensive endpoint checks and loading state.
- Preview remains read-only; Commit remains intentionally disabled.

## v0.2.12
- Exclude Complete / Cancelled BOs from Shared Allocation Group candidates.
- Separate same-parent active BOs from searchable other active BOs.
- Unknown locations are Location Warnings.
- Ordered / awaiting-receipt stock is never automatically selected.
- Out-for-assembly stock outside the selected group and unreceived stock can be surfaced under Stock Available for Manual Decision.

## v0.2.12
- BO references are clickable and always show the part being built.
- BOM component part names are clickable.
- Preview rows support Change Stock and alternate StockItem review.
- Manual StockItem selection recalculates the Shared Allocation Group preview downstream.
- Restore Recommendation returns a line to optimizer selection.
- Commit remains disabled.

## v0.2.12
- Display StockItem Batch ID throughout preview, manual stock selection, and commit results.
- Add per-allocation checkboxes plus Select All / Deselect All controls by section.
- Warning allocations require explicit exception approval.
- Enable Commit Selected Allocations.
- Commit actual BOM quantity only; planned spillage is never written as allocation quantity.
- Recalculate and revalidate the preview at commit time.
- Lock Build, BuildLine, and StockItem records during commit and write selected allocations atomically.
- Manual-decision and insufficient-stock rows remain non-committable.
- Refresh Preview after commit to show remaining outstanding requirements.


## v0.2.12
- Fix commit to mirror native InvenTree BuildAllocationSerializer BuildItem get_or_create semantics.
- Add mandatory confirmation before writing allocations.
- Show exact success details for every allocation created / updated.
- Automatically refresh Preview after a successful commit.

## v0.2.12
- Existing BuildItem allocations are now the source of truth for outstanding BOM quantity.
- Commit-time outstanding validation uses the same BuildItem calculation.
- Analyze / Preview automatically saves the currently displayed Shared Allocation Group and sequence.
- Confirm Stock Allocation is shown at the bottom beside the Commit workflow.

## v0.2.12
- Fix sequential package projection when a StockItem is already allocated to an earlier BO in the Shared Allocation Group.
- Projection now starts from physical StockItem quantity minus allocations belonging to BOs outside the selected group.
- Existing allocations inside the group are then consumed in BO sequence, including one expected-spillage reserve per existing BuildLine.
- This allows an already allocated package to be intentionally reused by a later sequential BO without incorrectly resetting to the full physical package quantity.
- Commit confirmation remains at the bottom of the workflow.

## v0.2.12
- Fix false stale-preview rejection when committing allocations from a sequential Shared Allocation Group.
- Commit now submits the exact selected Preview rows the user confirmed instead of re-running the optimizer and requiring identical recommendations.
- Backend still revalidates every selected row under database locks against the live Build Order, BuildLine, outstanding BOM quantity, StockItem part, and actual InvenTree available quantity.
- Each BuildItem write is immediately read back and verified inside the atomic transaction; verification failure rolls back the complete commit.
