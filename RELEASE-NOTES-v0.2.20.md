# Smart Build Allocation v0.2.20

## Change
When an existing allocation or earlier recommendation establishes a physical package within a sequential group, prefer that package for later BOs whenever it can satisfy their outstanding BOM quantity. If it cannot also accommodate planned spillage, show a Spillage Warning rather than automatically switching to another package merely to avoid the warning. Explicit Change Stock/manual overrides still take precedence. If the preferred package cannot satisfy BOM demand, use normal stock selection.

## Final regression test
1. Keep IC-Part-75 stock batch `20261001-3` at 110 physical units, with 50 allocated to BO-0026. Have another unallocated package of IC-Part-75 with sufficient inventory to satisfy a later BO including spillage.
2. From BO-0026 select sequential order BO-0026 -> BO-0024 -> BO-0025; BO-0024 requires 50 and BO-0025 requires 10. Analyze.
3. Expected: Prefer batch `20261001-3` for BO-0024 and BO-0025; classify missing planned spillage as warnings requiring approval. Do not switch automatically to the alternate package solely to avoid spillage warnings.
4. Change Stock manually to the alternate package and verify the override still works. Do not commit until the preview is verified.

The 110-unit example has zero total allowance for spillage across the three BOs. This is a planning exception, not guaranteed physical yield.
