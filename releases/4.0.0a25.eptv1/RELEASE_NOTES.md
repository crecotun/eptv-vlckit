EPTV VLCKit 4.0.0a25.eptv1 engineering prerelease

Built from published upstream VLCKit 4.0.0a25 (8f5ce02), VLC 005e69e67, 12 wrapper patches and the unchanged EPTV module policy. Includes only Mac ARM, TV device ARM and TV Simulator ARM, minimum OS 26.0. The iOS dependency remains separate.

Three slice audits pass (293/288/288 modules); synthetic H.264/AAC decoding passes on Mac and TV Simulator. EPTV passes 78 Mac tests, 161 TV tests with one opt-in skip, and 459 shared tests. Mac/TV ARM Release builds and archives, embedded identity and local Mac framework replacement pass. Source inventory covers 62 inputs and 176 legal texts. Native source ZIP excludes logs and app code; final binaries/dSYMs contain no creator home-directory paths.

This is a private engineering prerelease of an alpha upstream dependency. Named transitive/platform review, public corresponding-source availability, physical/provider playback and final App Store signing/acceptance remain pending. Historical a24 release assets are unchanged.
