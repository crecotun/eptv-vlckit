EPTV's ARM-only source build of VLCKit 4.0.0a24, preserving the `VLCKit` API.

Includes macOS arm64, tvOS device arm64 and tvOS Simulator arm64, minimum OS 26.0.
No iOS slice is included. Independent EPTV distribution, not an official VideoLAN release.

`EPTVVLCKit.zip` contains the unsigned framework payload and notices.
`EPTVVLCKit-source.zip` contains exact patched VLC/VLCKit source, 62 contrib input
identities, tool sources, 175 collected legal texts, patches, audits and build logs.
Verify both ZIPs against `SHA256SUMS` and the repository release manifest.

Identified GPL plugin archives and zvbi/teletext code are excluded from the binary;
the complete corresponding-source package preserves excluded/optional source and
its original license texts. Applicable LGPL, GPL and other component terms remain
in force; see repository licensing documentation.

These are the existing engineering-qualified archives, privately retained without rebuilding
or repackaging. They retain the alpha's Debug library configuration. Private storage does not establish public source availability; final application distribution
approval, signed App Store acceptance and physical provider/device validation
remain separate. A rebuild is not guaranteed to reproduce the same ZIP bytes.
