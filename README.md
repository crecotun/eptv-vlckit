# EPTV VLCKit

Small maintenance repository for EPTV's independent VLCKit/libVLC build.
This is not an official VideoLAN release. Current dependency: **4.0.0a25.eptv1**,
ARM-only macOS/tvOS/tvOS Simulator, minimum OS 26.0, unchanged `VLCKit` API.
The deferred iOS app uses a separate upstream pod.

## What lives here

- EPTV patches, native build/audit/packaging tools and tests.
- One canonical source-input/build/qualification record and the app consumer receipt.
- LGPL/GPL texts and the complete consolidated third-party notices.
- Exact archive hashes and source-tree identities.

Full upstream source, contrib/tool archives, binaries and symbols live in the
[private engineering release](https://github.com/crecotun/eptv-vlckit/releases/tag/4.0.0a25.eptv1),
not Git. There are no vendored upstream source snapshots, binaries, raw build logs,
duplicate component license directories or build caches in this checkout.

## Retrieve only what you need

```sh
# App development needs only this binary ZIP and the pinned consumer receipt.
gh release download 4.0.0a25.eptv1 --repo crecotun/eptv-vlckit \
  --pattern EPTVVLCKit.zip --dir downloads

# Native library maintenance additionally needs corresponding source.
gh release download 4.0.0a25.eptv1 --repo crecotun/eptv-vlckit \
  --pattern EPTVVLCKit-source.zip --dir downloads
python3 scripts/verify.py --archives downloads
python3 scripts/prepare-build.py --archive downloads/EPTVVLCKit-source.zip --destination work
```

`prepare-build.py` verifies the archive and exact Git trees, then creates writable
build trees and caches in ignored `work/`. It omits the old archive's build logs.
Build only when changing the native dependency; EPTV restores prebuilt binaries.
See [build instructions](docs/BUILD.md) and [maintenance/handoff](docs/MAINTENANCE.md).

```sh
python3 scripts/verify.py
python3 -m unittest discover -s scripts/compliance -v
```

The current a25 source/binary ZIPs were built and qualified from pinned upstream
source. Historical a24 ZIPs stay unchanged at their old tag. Current source
packages exclude raw logs; final binaries and symbols contain no creator
home-directory paths. The repository and engineering releases remain private;
public source availability and app distribution approval are pending. Native CI
checks tooling/input integrity; hosted native builds are not configured.

## License

EPTV-authored scripts, patches and docs: LGPL-2.1-or-later, copyright 2026 Alexei
Crecotun. [LICENSE](LICENSE), [licensing details](docs/LICENSING.md) and
[third-party notices](releases/4.0.0a25.eptv1/TransitiveNotices.txt) preserve applicable
terms. Upstream/component source licenses remain in the exact release archive;
this repository does not relicense the complete VLC tree or the EPTV application.
