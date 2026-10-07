# VLCKit supplier repository

Own VLC/VLCKit source, patches, native build/audit tooling, component inventories,
qualified native releases and consumer receipt export here. EPTV is a separate
application consumer; never copy its app implementation or provider data here.

Keep Git compact: no upstream source snapshots, binary archives, raw logs, build
caches or duplicate component legal directories. Restore exact source on demand
from pinned release archives and build in ignored `work/`. Retain necessary
engineering evidence outside the checkout; future source packages exclude logs. Publishing requires the human's explicit
public visibility/payload authorization; do not interpret a local source/build
change as permission to publish. Review local creator paths before release upload.

Use docs/BUILD.md for reproduction and docs/MAINTENANCE.md for upgrades. Export
qualified receipts using scripts/export-eptv-receipt.py; EPTV imports those and
installs prebuilt binaries. No EPTV app source or native qualification tooling
should be copied into the application repository.
