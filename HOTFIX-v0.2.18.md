# v0.2.18 hotfix
Fix preview NameError: a conditional local import of is_unreceived made it a function-local variable, so ordinary preview paths referenced it before assignment. Move the import to module scope. No intended allocation-policy changes from v0.2.17.

Regression check: open BO-0026 and run Analyze / Preview before adding related BOs. Then repeat BO-0026 → BO-0024 → BO-0025 tests described in TEST-REPRODUCTION-v0.2.17.md. Do not commit until preview results are verified.
