# Build 4.0.0a24.eptv2

Use an Apple Silicon Mac, Xcode 27.0 (27A266a), its macOS/tvOS SDKs, GNU Make
4.4.1 and a Python supported by Meson 1.12. Keep the source build's Debug
configuration and OS 26.0 deployment targets when reproducing this version.

## Prepare the exact inputs

Download `EPTVVLCKit-source.zip` from the versioned release. The helper checks
its pinned SHA-256, extracts and verifies every packaged file, restores the exact
VLC/VLCKit trees, and copies contrib/tool archives into the upstream cache paths.
It does not install system tools or start a native build.

```sh
python3 scripts/prepare-build.py --archive /absolute/path/EPTVVLCKit-source.zip \
  --destination work
```

The resulting `work/source/` contains the verified build inputs, excluding raw logs; `work/VLC` and
`work/VLCKit` are the writable build trees. The native command builds local tools
and contrib dependencies. Some upstream tools may still require installed host
prerequisites documented in `work/VLC/extras/tools/bootstrap` and upstream INSTALL.

## Build GNU Make and the ARM frameworks

GNU Make's source archive is included and pinned. Build it into VLC's local tool
prefix first. Run from the repository root, replacing the Python/host-tool path
below with the appropriate absolute directories on your machine:

```sh
TASK_ROOT="$PWD/work"
mkdir "$TASK_ROOT/make"
tar -xzf "$TASK_ROOT/source/tools/make-4.4.1.tar.gz" \
  -C "$TASK_ROOT/make" --strip-components=1
(cd "$TASK_ROOT/make" && ./configure --prefix="$TASK_ROOT/VLC/extras/tools/build" && make -j8 && make install)
VLC_PATH=/absolute/path/to/python/bin:/absolute/path/to/host/tools MAKEFLAGS=-j8 \
  ./scripts/build-eptv-vlckit.sh "$TASK_ROOT/VLCKit" "$TASK_ROOT/VLC"
```

The entry point creates separate Mac and TV XCFrameworks at:

- `work/VLCKit/build/macOS/VLCKit.xcframework`
- `work/VLCKit/build/tvOS/VLCKit.xcframework`

Keep the `.xcarchive` outputs and dSYMs. The distributed dependency combines
Mac, TV device and TV Simulator frameworks into one three-slice XCFramework;
the retained binary ZIP already contains that assembled payload. Applications
sign their embedded framework themselves.

Exact source is identified by the release ZIP digest and Git tree hashes. Build
in ignored `work/`; source snapshots are not duplicated in Git. A rebuild
may differ in paths, timestamps and binary bytes. The existing release checksums
identify the original qualified archives, not arbitrary locally rebuilt outputs.

See [the preserved package instructions](CORRESPONDING_SOURCE.md) for native
policy, removed features, source provenance and review limits. The complete
historical package includes original build logs and host-tool archives. Source preparation
omits logs; future source packaging does not include raw engineering logs. A new dependency
release must receive fresh binary identity, component audit and decode/build
qualification; repository CI only checks publication/source integrity.
