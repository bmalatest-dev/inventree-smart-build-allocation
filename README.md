# Smart Build Allocation — v0.1.0

Per Vices test plugin for InvenTree Build Order stock allocation.

## First test build
V0.1.0 uses InvenTree's supported `AllocateMixin`. When **Auto Allocate** is triggered, InvenTree builds its normal valid candidate list and this plugin reorders it:

1. Existing manual allocations remain untouched.
2. Prefer locations containing `component room` (case-insensitive).
3. Put `out-for-assembly*` locations last.
4. Prefer exact parts over variant/substitute candidates.
5. For purchase price below $0.15/pc, prefer reel/spool packaging.
6. Prefer the smallest stock item that can satisfy the outstanding requirement.
7. Allow InvenTree to split across stock items when needed.

The agreed ASR spillage policy is included in `rules.py`, but v0.1.0 does **not** silently allocate extra quantity beyond the BO requirement. The Preview / Review / Commit stage will add spillage after candidate ordering is verified.

## GitHub / installation
Expected repo: `bmalatest-dev/inventree-smart-build-allocation`

Upload the ZIP contents to the repo root, then install using:

`git+https://github.com/bmalatest-dev/inventree-smart-build-allocation`

Do not append `.git` or a trailing space.

Enable the plugin. If you want the informational Smart Allocation panel, also ensure InvenTree's plugin interface support is enabled. Restart/reload the container if required.

## Recommended first test
For one BO line requiring 60 pcs:

- Component Room: 500 pcs
- Component Room: 75 pcs
- Storage Room: 65 pcs
- out-for-assembly - test: 60 pcs

Expected first choice: **Component Room / 75 pcs**.

For a part under $0.15/pc with Component Room cut tape 75 pcs and reel 500 pcs, expected first choice is **reel**.
