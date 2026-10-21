# Smart Build Allocation v0.2.28

Replica test release bundling operator workflow feedback.

- Reorders review sections from easiest to most effort: Easy Allocations, Stock Available for Manual Decision, Variants, Spillage, Location Warnings, Multiple Stock Item Warnings.
- Adds Required Qty and Packaging to allocation/review displays.
- Adds in-plugin manual allocation to manual-decision rows and preserves manual allocation controls in warning rows.
- Replaces ambiguous stock-split `? -> ?` presentation with explicit allocate / available-before / remaining-after wording.
- Fixes bulk warning approval so only currently selected rows are approved.
- Adds per-line allocation commits; successful lines are immediately re-previewed and disappear when fully allocated.
- Keeps batch commit for selected rows / easy allocations.
- Fixes manual-decision candidate presentation: zero projected-availability packages no longer displace usable candidates, and all useful StockItem candidates are shown for manual decisions.
- Retains v0.2.25+ native BuildLine.unallocated_quantity() handling for already allocated / consumed build lines.
