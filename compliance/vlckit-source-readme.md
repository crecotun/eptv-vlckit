# EPTV VLCKit 4.0.0a25.eptv1 corresponding-source candidate

This package contains the exact source used for the EPTV Mac/TV framework,
upstream contrib archives and legal texts, EPTV patches, local tool sources,
and license audits. Build logs remain private engineering evidence. No proprietary EPTV application code or
provider inputs are included. Distribution approval is recorded separately.

The wrapper starts at VideoLAN 8f5ce02f09a7da5d061a24ddac3cb432f2a9b332.
The VLC source starts at public 005e69e67a8730f128e44bde68437fbb048cf45f,
with the 12 wrapper patches and the EPTV GPL-removal/metadata patch applied.
Exact resulting commits/trees, patch checksums, toolchain and slice audit
reports are in build-record.json. Runtime libvlc_get_changeset is b8e875d.

Restore VLCKit-source.tar.gz into VLCKit/ and VLC-source.tar.gz into vlc/.
Copy contrib/ archives and .githash files into vlc/contrib/tarballs/.
Copy tools/ archives (except GNU Make) into vlc/extras/tools/. GNU Make 4.4.1
is built first and installed into vlc/extras/tools/build/; its source SHA-256
is pinned in build-record.json. Tool sources retain their upstream licenses.
The packaged src/revision.txt preserves the engine fingerprint without Git.

Use Xcode 27.0, a Python supported by Meson 1.12, and the upstream bootstrap
requirements. The source build was run with eight jobs. Set VLC_PATH to the
Python and host tool directories; build-eptv-vlckit.sh includes the local
VLC tool prefix in PATH. Tools and contribs build into the source directory;
no system installation is needed. Link VLCKit/libvlc/vlc to ../../vlc so the
Xcode project finds the external source and installed static libraries.

Run the packaged EPTV entry point (substitute absolute restored paths):

```
VLC_PATH=/path/to/python/bin:/path/to/host/tools MAKEFLAGS=-j8 \
  ./build-eptv-vlckit.sh /absolute/path/to/VLCKit /absolute/path/to/vlc
```

The entry point calls the upstream VLC Apple builder with aarch64 for Mac,
TV device and TV Simulator, copies each ARM static library directly, and archives
arm64 frameworks at OS 26 without dependency signing. It bypasses the generic
wrapper's architecture loops and universal aggregation. No thinning occurs.
Generic upstream Intel branches remain in the source but are never invoked.
The app signs the embedded framework. Libraries retain the qualified Debug
configuration; keep dSYMs. Packaging combines platform frameworks, not CPU slices.

The EPTV patch disables zvbi and both teletext decoders; excludes file_logger,
syslog, rotate, sap, stream_out_cycle, stream_out_rtp and dummy plugins before
static aggregation; and retains module license getters for binary inspection.
RTP input and ordinary subtitle/codec paths remain. Every framework slice
must pass the focused module/teletext binary check before packaging.
Qualification audits all three ARM slices and requires real synthetic H.264/AAC decoding on Mac and TV Simulator. Historical results are separate.

Contrib archives are retained conservatively, including build tools, headers
and excluded/optional source. The presence of GPL source/license alternatives
in these archives does not identify them as linked binary code. Selected
alternatives, where applicable, are Apache-2.0 for Mbed TLS, BSD-3-Clause for Libgcrypt jitter
entropy files, the FreeType License for FreeType, and LGPL-2.1 for TagLib and
libnfs libraries. The separate named transitive/distribution review remains
required. Review full source headers, legal documents and actual build inputs.

Build from a neutral absolute directory and provide Python through a neutral
host-bin path. The entry point keeps Xcode DerivedData within the build tree.
Inspect binaries and dSYMs for creator paths before release packaging.
