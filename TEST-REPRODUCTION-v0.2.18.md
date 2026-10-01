# Smart Build Allocation v0.2.17 — fixes and reproducible tests

This document records the user's actual test sequence. Preserve the indicated stock setup for each test; changes in earlier steps affect later outcomes. Run Analyze/Preview first and do not commit unless the test explicitly requests it.

## Fixed: Warning approval (previous Test 4)
1. On BO-0019, select **Allocate this item** on a **Location Warning**.
2. Leave **Approve exception** unchecked.
3. Click **Commit Selected Allocations**.
4. Expected: no confirmation dialog; error near Commit instructs you to approve selected warning allocations.
5. Approve the exception and click Commit Selected Allocations again. Expected: confirmation dialog now appears. **Cancel**; do not commit.
6. Server also rejects an unapproved warning if a request bypasses the UI.

## Fixed: Allocated package outside selected group (previous Test 7)
1. Use `IC-Part-75`; restore physical stock to **60 units** in the package being tested.
2. Allocate **10 units** from that package to **BO-0025**.
3. Analyze **BO-0026 alone** (BO-0025 must not be in its Shared Allocation Group).
4. Previously: only a Spillage Warning, no indication that the physical package was committed to another BO.
5. Expected: the entire package is excluded from automatic selection; manual-review information identifies **ALLOCATED TO ANOTHER BUILD**, **BO-0025**, physical quantity and reserved quantity. Do not allow a manual override to allocate that package while BO-0025 is outside the group.
6. Repeat with a package fully allocated to another BO; expected same exclusion.

## Fixed: Three-BO sequencing, existing allocation (previous Test 8)
1. Set `IC-Part-75` package physical quantity to **100**; retain **10 units allocated to BO-0025**.
2. Ensure **BO-0024, BO-0025 and BO-0026** share the same parent build.
3. BO-0024 and BO-0026 each require **50** of `IC-Part-75`. Check BO-0025's **actual outstanding requirement** before comparing projections; the user did not explicitly state its full requirement in this test.
4. Set sequence **BO-0026 → BO-0025 → BO-0024** and Analyze.
5. The prior run showed BO-0026 Easy and BO-0024 Insufficient. Verify existing BO-0025 allocation is accounted for, and the BO sequence is respected. This scenario may genuinely be short depending on BO-0025's outstanding BOM quantity and spillage.
6. Reorder BO-0024 before BO-0025; reanalyze and verify the package projections follow the changed order.

## Fixed: Later BO wrongly marked insufficient due to earlier spillage (previous Test 9)
1. **Unallocate** the 10 units of `IC-Part-75` from BO-0025.
2. Set sequence **BO-0026 → BO-0024 → BO-0025**.
3. With physical quantity **100**, the prior optimizer showed Easy for BO-0026 and BO-0025, and Insufficient for BO-0024, despite BO-0024 being ahead of BO-0025. Expected: BOM demand follows the sequence; no earlier spillage reserve may take stock required by a later BO's BOM. The final outcome depends on BO-0025's actual outstanding BOM quantity.
4. Increase physical quantity to **110**. This was intended to cover 50 + 50 + 10 BOM units without spillage; verify BO-0025's outstanding BOM requirement is indeed **10** before applying that expectation.
5. Expected if outstanding BOM is 50 + 50 + 10: BO-0026 50, BO-0024 50, BO-0025 10; all three can satisfy BOM, but planned spillage is unavailable. Each should show a **Spillage Warning** where its full reserve cannot be made without depriving later BOM lines. No false Insufficient Stock on BO-0025.
6. Do not commit; capture all three Preview rows and package projections.

## Regression: Sequential package reuse (previous Test 10)
1. Analyze **BO-0025 and BO-0026 together**, in the intended sequence.
2. Allocate `IC-Part-75` from the StockItem with batch **20261001-4** to the earlier BO.
3. Add another StockItem for the same part: **100 units**, batch **20261001-3**.
4. Analyze again. Previously, the plugin correctly chose the already-allocated same package/batch for group reuse.
5. Expected: continue to prefer valid sequential reuse of batch **20261001-4** where it can meet the next BO's BOM, with projected balance and spillage shown. Do not confuse the alternate batch **20261001-3** with the reused package.

## Prior passed tests (retain as regressions)
- Test 1: Manual per-StockItem quantity validation — passed.
- Test 2: Manual split and spillage display — passed.
- Test 3: Restore Recommendation — passed.
- Test 5: Selective allocation confirmation shows only the selected BOM line — passed.
- Test 6: BO-0026 / IC-Part-75 insufficient spillage correctly generates a Spillage Warning — passed.
- v0.2.16 consumed-stock test: BO-0019 / IC-Part-25 consumed Stock #63 excluded from automatic and manual stock selection — passed.

## Not included in this build
- Incoming PO details on shortages.
- Partial allocation of a BOM line when full physical stock is unavailable.
- Approval alone must never override an outside-BO allocation conflict.

**Testing limitation:** The package is statically checked and unit tests run outside InvenTree; full ORM and multi-BO behaviour must be verified in your InvenTree test environment.
