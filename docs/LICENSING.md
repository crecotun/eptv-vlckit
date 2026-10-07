# Licensing and source access

This repository distributes VideoLAN's VLCKit/libVLC source and the exact EPTV
changes. Original source notices and copyright headers are preserved.

- VLCKit: `work/VLCKit/COPYING` after source preparation (LGPL 2.1 or later; see source headers).
- libVLC and LGPL engine/library files: `work/VLC/COPYING.LIB` and file headers.
- Other VLC files: `work/VLC/COPYING` and individual source notices; the complete
  tree contains GPL modules/tools, including modules excluded from our binary.
- Contrib and host tools: their archive source headers and the collected legal
  texts under `source/legal` inside the release source package. Consolidated
  legal texts are retained as `releases/4.0.0a24.eptv2/TransitiveNotices.txt`.
- EPTV-authored patches, build/support scripts and documentation: LGPL 2.1 or
  later, copyright 2026 Alexei Crecotun.

The LGPL text is reproduced in root `LICENSE`; `licenses/GPL-2.0.txt` also retains
VLC's GPL text. These do not replace any component's original terms. Full collected
notices are in `releases/4.0.0a24.eptv2/`; detailed audits stay in the source archive.

The chosen binary excludes zvbi/both teletext decoders and these plugin archives:
`file_logger`, `syslog`, `rotate`, `sap`, `stream_out_cycle`, `stream_out_rtp`,
and `dummy`. Source/input archives conservatively include excluded and optional
components. Their presence in the source package does not mean they are linked
into the released framework.

Exact machine-readable corresponding source is retained in the private versioned
GitHub release, including complete patched source, contrib/tool inputs and original
license texts. Authentication is required until public publication is authorized.
Preparing source verifies the pinned archive and both source-tree identities. Git
stores only the maintenance recipe, changes, legal notices and compact manifests;
its auto-generated ZIP is not the complete corresponding-source package.

Applications consuming this library must satisfy the applicable licenses,
including notices, corresponding-source access and LGPL modification/debugging
and replacement rights. Source publication alone does not establish that an
application's signing, store terms or distribution arrangements meet those terms.
This repository does not license the proprietary EPTV application source.
