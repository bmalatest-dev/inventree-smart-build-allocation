# v0.2.23

## Variant stock review
- Exact BOM stock remains the automatic first choice.
- If exact stock cannot satisfy the outstanding BOM quantity, direct variant StockItems are included as candidates.
- Any proposed allocation using variant stock is placed in a new **Variants Available — Review Required** section, never **Easy Allocations**.
- Variant substitutions require explicit approval before commit.
- Commit-time validation re-checks that the selected stock is either the exact BOM part or a direct variant of it.

## Collapsible preview sections
- Preview result sections can now be independently collapsed / expanded.
- **Easy Allocations** is collapsed by default.
- Review/problem sections are expanded by default so exceptions are visible immediately.
