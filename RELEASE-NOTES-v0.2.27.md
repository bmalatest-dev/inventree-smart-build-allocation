# v0.2.27

Presentation-only update based on operator feedback.

- Reworks preview output into compact, spreadsheet-style tables.
- Groups manual-review stock candidates under a clear Build + Component header instead of repeating large blank cells.
- Uses dedicated quantity columns for warning candidates: Physical, Allocated Elsewhere, Unallocated, and Auto Available.
- Keeps batch, stock ID, location, reason/action, allocation quantity, spillage and projected quantity visually separated.
- Adds stronger cell borders, alternating row shading and horizontal scrolling for narrow screens.
- Allocation logic is unchanged from v0.2.25/v0.2.26.
- Adds and loads `smart_allocation_v0227.js`.
