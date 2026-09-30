# Smart Build Allocation — v0.2.0

Test build implementing the first usable version of the updated Feature #19088 workflow.

## Terminology: Shared Allocation Group
A **Shared Allocation Group** is the user-selected set of Build Orders which are being assembled at the **same physical location sequentially, not concurrently**. A physical package may intentionally be shared across BOs in this group.

Do not group BOs which are being assembled at different locations or concurrently.

## Implemented in v0.2.0
- Build Order panel for selecting and saving a Shared Allocation Group before allocation.
- Group choice is temporary server cache (7 days) and requires no database migration.
- Existing InvenTree Auto Allocate remains the commit mechanism.
- Prefer a StockItem already used by another BO in the selected group when InvenTree still considers it a valid candidate.
- Component Room preference for standard parts.
- Hand Placement parameter support (`Hand Placement = Yes`).
- Hand-placement stock may consider Component Room, Rework Room, Storage Room, then other locations; smaller suitable packages are preferred.
- Standard packaging ranking: Reel, Tray, Tube, Cut Tape, Other.
- Low-cost Send-a-Reel preference retained.
- Out-for-Assembly stock outside the selected group is excluded from automatic allocation.
- Existing spillage policy remains available in rules.py.

## Deliberately not complete yet
The final Preview / Review / Sign-off / Commit workflow is not implemented in v0.2.0. As a result, SPILLAGE WARNING, LOCATION WARNING and MULTI-STOCKITEM WARNING are not yet interactive. V0.2.0 is for local workflow and ranking tests only.

## Recommended test sequence
1. Open the primary BO and the Smart Allocation panel.
2. Select zero or more sequential same-location BOs and save the Shared Allocation Group.
3. Run normal InvenTree Auto Allocate.
4. Verify package reuse across the group, Component Room priority, Hand Placement behaviour, packaging preference, and Out-for-Assembly exclusion.
