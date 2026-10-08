# Smart Build Allocation v0.2.21

- Explicitly blocks Stock Items whose current status is **Attention Needed** or **Damaged**.
- Block applies to automatic ranking and manual overrides.
- Blocked items are shown as non-selectable with a status warning where stock options are displayed.
- Commit re-checks the live Stock Item status under the existing database lock, preventing allocation if status changed after Preview.
- No database migration required.
