# v0.2.26

Presentation-only update to the Smart Build Allocation preview.

- Keeps the tested v0.2.25 allocation backend logic unchanged.
- Replaces dense preview text with compact tables.
- Automatic / warning allocations show Build Order, Component, Batch / Stock, Location, Allocate, Spillage, Projected Qty, and Actions.
- Manual review / insufficient-stock sections use stock-decision columns: Physical, Outside Group, Unallocated, Auto Available, and Reason.
- Groups component identity with its description and keeps existing links and allocation controls.
- Moves the manual-review summary out of the final stock line for easier scanning.
- Adds and loads `smart_allocation_v0226.js`.
