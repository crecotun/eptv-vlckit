#!/bin/bash
# EPTV-owned ARM build entry point; leave generic upstream architecture code intact.
set -euo pipefail
[[ $# == 2 ]] || { echo "Usage: $0 /absolute/VLCKit /absolute/vlc" >&2; exit 64; }
wrapper=$(cd "$1" && pwd)
vlc=$(cd "$2" && pwd)
[[ $(uname -m) == arm64 ]] || { echo 'EPTV builds require an Apple Silicon host' >&2; exit 1; }
export PATH="${VLC_PATH:-$PATH}:$vlc/extras/tools/build/bin:$PATH"
export MAKEFLAGS="${MAKEFLAGS:--j8}"
for platform in macOS tvOS; do
  [[ ! -e "$wrapper/build/$platform/VLCKit.xcframework" ]] || {
    echo "Output already exists: use a fresh wrapper build directory" >&2; exit 1;
  }
done
mkdir -p "$wrapper/libvlc"
[[ -e "$wrapper/libvlc/vlc" ]] || ln -s "$vlc" "$wrapper/libvlc/vlc"
[[ $(cd "$wrapper/libvlc/vlc" && pwd -P) == "$vlc" ]] || { echo 'Wrong wrapper VLC source link' >&2; exit 1; }

# The wrapper's single-architecture option does not select an ARM TV simulator.
# Call the upstream engine builder explicitly, then copy each single static input.
# No universal assembly or binary thinning occurs, even with older builds nearby.
for sdk in macosx appletvos appletvsimulator; do
  build="$vlc/build-$sdk-arm64"
  mkdir -p "$build"
  (cd "$build" && ../extras/package/apple/build.sh --arch=aarch64 --sdk="$sdk$(xcrun --sdk "$sdk" --show-sdk-version)")
  binary="$build/static-lib/libvlc-full-static.a"
  [[ $(lipo -archs "$binary") == arm64 ]] || { echo "Non-ARM engine input: $binary" >&2; exit 1; }
  case "$sdk" in
    macosx) install=macosx-device; header=macosx-device; library=device ;;
    appletvos) install=appletv-device; header=appletv-device; library=device ;;
    appletvsimulator) install=appletv-simulator; header=appletv-simulator; library=simulator ;;
  esac
  mkdir -p "$vlc/install-$install"
  cp "$binary" "$vlc/install-$install/libvlc-$library-static.a"
  cp "$build/static-lib/static-module-list.c" "$wrapper/Headers/Internal/vlc-plugins-$header-arm64.h"
  # Upstream project lists generic header resources for both architectures.
  # Empty unused headers satisfy those resource references without Intel code.
  : > "$wrapper/Headers/Internal/vlc-plugins-$header-x86_64.h"
  [[ "$library" != simulator ]] || : > "$wrapper/Headers/Internal/vlc-plugins-appletv-simulator.h"
  platform=macOS
  deployment=MACOSX_DEPLOYMENT_TARGET
  [[ "$sdk" == macosx ]] || { platform=tvOS; deployment=TVOS_DEPLOYMENT_TARGET; }
  [[ "$sdk" != appletvsimulator ]] || platform='tvOS Simulator'
  (cd "$wrapper" && xcodebuild archive -project VLCKit.xcodeproj -scheme VLCKit \
    -sdk "$sdk" -configuration Debug -destination "generic/platform=$platform" \
    -archivePath "build/VLCKit-$sdk.xcarchive" -derivedDataPath "build/DerivedData-$sdk" ARCHS=arm64 "$deployment=26.0" \
    CODE_SIGNING_ALLOWED=NO SKIP_INSTALL=NO ONLY_ACTIVE_ARCH=NO)
done

for platform in macOS tvOS; do
  output="$wrapper/build/$platform/VLCKit.xcframework"
  [[ ! -e "$output" ]] || { echo "Output already exists: $output; use a fresh wrapper build directory" >&2; exit 1; }
  args=()
  if [[ "$platform" == macOS ]]; then sdks=(macosx); else sdks=(appletvos appletvsimulator); fi
  for sdk in "${sdks[@]}"; do
    archive="$wrapper/build/VLCKit-$sdk.xcarchive"
    binary="$archive/Products/Library/Frameworks/VLCKit.framework/VLCKit"
    [[ $(lipo -archs "$binary") == arm64 ]] || { echo "Non-ARM framework: $binary" >&2; exit 1; }
    args+=(-framework "$archive/Products/Library/Frameworks/VLCKit.framework"
           -debug-symbols "$archive/dSYMs/VLCKit.framework.dSYM")
  done
  xcodebuild -create-xcframework "${args[@]}" -output "$output"
done
