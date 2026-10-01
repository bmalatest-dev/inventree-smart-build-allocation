# v0.2.19 — allocation visibility and sequential demand diagnostics

- Manual-decision stock now shows current physical quantity, allocated quantity outside the group, unallocated quantity, and usable quantity for automatic selection. The package remains excluded if allocated to an outside BO.
- Cache all BO outstanding requirements at the start of each Preview so future BOM demand is stable across the sequence. Calculate discretionary spillage only after accounting for later outstanding BOM demand.
- Include current and future BOM demand, usable stock and spillage budget in spillage/insufficient messages to diagnose the BO-0026 → BO-0024 → BO-0025 regression.

## Reproduce the reported tests
1. Test 7: single IC-Part-75 StockItem #70, batch 20261001-3, physical qty 100; allocate 50 to BO-0026. Analyze BO-0025 alone, excluding BO-0026 from the group. Expected manual decision: physical 100, allocated outside 50, unallocated 50, automatically selectable 0.
2. Test 9: release BO-0025 allocation; set StockItem batch 20261001-3 physical qty 110, with 50 already allocated to BO-0026. Group sequence BO-0026 → BO-0024 → BO-0025. Expected, **only if BO-0025's actual outstanding BOM requirement is 10**: BO-0026 existing 50, BO-0024 proposed 50, BO-0025 proposed 10, and spillage warnings for any unavailable reserve. If actual BO-0025 outstanding requirement differs, inspect the newly displayed BOM-demand diagnostics; do not assume 10.
3. Verify no selected unapproved warning can advance to confirmation. Do not Commit until all Preview quantities match the native Build Order requirements.

Note: Python and JS syntax checks do not constitute InvenTree integration testing.
