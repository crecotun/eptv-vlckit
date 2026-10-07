#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright 2026 Alexei Crecotun
"""Prepare verified, writable build trees from the exact corresponding-source ZIP."""
import argparse
import json
import shutil
import tarfile
from pathlib import Path
import sys
import zipfile
from verify import ROOT, RELEASE, digest, verify_manifest
import importlib.util

def safe_path(name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe archive path: " + name)
    return path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads((RELEASE / "manifest.json").read_text())["assets"]["EPTVVLCKit-source.zip"]
    if args.archive.stat().st_size != expected["bytes"] or digest(args.archive) != expected["sha256"]:
        raise ValueError("Source ZIP differs from the pinned release")
    if args.destination.exists():
        raise ValueError("Use a new destination; existing build trees will not be overwritten")
    args.destination.mkdir(parents=True)
    with zipfile.ZipFile(args.archive) as archive:
        for name in archive.namelist():
            path = safe_path(name)
            if not path.parts or path.parts[0] != "source":
                raise ValueError("Unexpected source ZIP layout")
        archive.extractall(args.destination)
    package = args.destination / "source"
    count, _ = verify_manifest(package, package / "SHA256SUMS")
    for name, target in [("VLC-source.tar.gz", "VLC"), ("VLCKit-source.tar.gz", "VLCKit")]:
        output = args.destination / target
        output.mkdir()
        with tarfile.open(package / name) as archive:
            for entry in archive.getmembers():
                safe_path(entry.name)
                if entry.islnk() or entry.isdev() or entry.isfifo():
                    raise ValueError("Unsupported source entry: " + entry.name)
                if entry.issym():
                    safe_path(entry.linkname)
            # Only pinned archives are accepted; their entries have been validated.
            archive.extractall(output)
    spec = importlib.util.spec_from_file_location('qualification', ROOT / 'scripts/verify-vlckit-qualification.py')
    qualification = importlib.util.module_from_spec(spec); spec.loader.exec_module(qualification)
    record = json.loads((ROOT / 'compliance/vlckit-eptv-build.json').read_text())
    for name, key, excluded in [('VLC', 'vlc_tree', ('src/revision.txt',)), ('VLCKit', 'vlckit_tree', ())]:
        if qualification.archive_tree(args.destination / name, excluded) != record[key]:
            raise ValueError('Restored source tree differs: ' + name)
    # Original immutable archives contain logs; prepared build inputs do not need them.
    shutil.rmtree(package / 'build-logs', ignore_errors=True)
    vlc = args.destination / "VLC"
    for source, target in [(package / "contrib", vlc / "contrib/tarballs"), (package / "tools", vlc / "extras/tools")]:
        target.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            if item.is_file() and item.name != "make-4.4.1.tar.gz":
                shutil.copy2(item, target / item.name)
    print("Prepared writable VLC/VLCKit trees at " + str(args.destination.resolve()))
    print("Verified %d packaged files; see docs/BUILD.md for native build commands" % count)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        print("Preparation failed: " + str(error), file=sys.stderr)
        sys.exit(1)
