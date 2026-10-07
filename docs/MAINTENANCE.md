# Library maintenance and consumer handoff

This repository owns VLC/VLCKit source, EPTV's library patches, native build/audit
scripts, contrib inventories, packaging and native engineering qualification.
The EPTV application is a separate consumer. Never copy its implementation,
provider inputs, credentials or personal records here.

Current native inputs and engineering fingerprint are retained in
`compliance/vlckit-eptv-build.json`; exact source trees are restored on demand from the checksummed release archive.
The full qualification JSON and historical native records stay here. Historical logs, forensic helpers and recovery Git bundles are retained outside
this checkout in `../eptv-vlckit-retained`. Build caches and duplicate source
extractions are disposable; retrieve current archives into ignored `downloads/`.
The upstream CI inventory reader accepts `EPTV_APP_ROOT` only when an explicit
external app metadata checkout is needed for a historical investigation.

## Current dependency receipt

The qualified native archives have not been rebuilt or repackaged. The original
record keeps its historical EPTV-relative input names and fingerprint; the exporter
maps its old podspec input to `packaging/EPTVVLCKit.podspec` without changing identity.

```sh
python3 scripts/export-eptv-receipt.py \
  --artifacts downloads \
  --output releases/4.0.0a24.eptv2/EPTVVLCKit-dependency.json
python3 scripts/verify.py
python3 -m unittest discover -s scripts/compliance -v
```

Use `--published` only after actual public source/binary downloads have been
verified. The private GitHub repository/prerelease and moved evidence do not provide public source availability.
The current original logs and framework/debug symbols contain local creator paths;
prepare/review a sanitized public source package and decide the binary disclosure
before public uploading or changing repository visibility. Do not silently mutate the qualified archive ZIPs or their hashes.

## New native version

1. Restore source with `scripts/prepare-build.py`, then make the change in the
   writable source/build trees, preserving upstream notices. The prepared trees
   contain exact source bytes and modes, not the original private Git history;
   initialize Git and record new revisions deliberately for a new native version.
   Use `scripts/prepare-build.py` and `scripts/build-eptv-vlckit.sh`; record new
   source revisions/trees, patches, version, configuration and toolchain.
2. Update the qualified input recipe deliberately. Native source/patches,
   component sources and legal texts remain supplier inputs. New podspec inputs
   use `packaging/EPTVVLCKit.podspec` instead of any EPTV checkout path.
3. Use `scripts/package-eptv-vlckit.py` to assemble a pending binary/source
   candidate without raw build logs. Keep engineering evidence privately outside the
   package. Its audit is supplier-owned; it does not promote unknown binaries.
4. Collect fresh exact-artifact decode/audit evidence plus app integration and
   replacement acceptance from an external EPTV checkout. Store logs privately
   under this repository's ignored artifact directory and bind them by checksum.
   `--finalize` rejects mismatched binaries/source, incomplete platform/decode
   evidence, altered native inputs and changed source trees.
5. Prepare privacy-reviewed public source and binary downloads for a new immutable
   tag; publishing is a separate owner-authorized action. Never reuse a tag/ZIP
   digest for different bytes.
6. Export the consumer receipt. EPTV imports it, restores the prebuilt binary,
   updates its CocoaPods lock/notices and runs integration acceptance. App
   component/distribution decisions live in EPTV and reset for changed artifacts.

Native packaging is intentionally expensive and version-scoped. Ordinary EPTV
UI/app releases neither clone this repository nor compile/audit VLC. The supplier
integrity workflow tests source hashes and maintenance tooling; it does not yet
perform hosted macOS native builds or automatic release publication.
