# v0.2.22

- Keeps **Attention Needed** and **Damaged** Stock Items excluded from automatic allocation.
- Allows those statuses to be selected through an explicit **Manual Allocation**.
- Displays a warning instead of a hard block in manual stock selection.
- Commit still re-checks live stock status: blocked statuses are rejected for automatic allocations but permitted when the allocation is explicitly manual.
- Existing safeguards for consumed, unreceived, or stock allocated to another Build Order are unchanged.
- No database migration required.
