#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright 2026 Alexei Crecotun
"""Verify compact maintenance inputs and pinned release assets without native rebuilding."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
from importlib.util import spec_from_file_location, module_from_spec

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "releases/4.0.0a24.eptv2"

def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()

def verify_manifest(root, path):
    count = 0
    expected_paths = set()
    for line in path.read_text().splitlines():
        expected, name = line.split("  ", 1)
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe manifest path: " + name)
        target = root / relative
        if target.is_symlink():
            actual = hashlib.sha256(target.readlink().as_posix().encode()).hexdigest()
        else:
            actual = digest(target)
        if actual != expected:
            raise ValueError("Checksum mismatch: " + name)
        expected_paths.add(name)
        count += 1
    return count, expected_paths

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", type=Path, help="Directory containing both release ZIPs")
    parser.add_argument("--download", action="store_true", help="Download missing archives to --archives")
    args = parser.parse_args()
    if args.download and not args.archives:
        parser.error("--download requires --archives")
    count, _ = verify_manifest(ROOT, ROOT / "MAINTENANCE_SHA256SUMS")
    manifest = json.loads((RELEASE / "manifest.json").read_text())
    record = json.loads((ROOT / "compliance/vlckit-eptv-build.json").read_text())
    receipt = json.loads((RELEASE / "EPTVVLCKit-dependency.json").read_text())
    spec = spec_from_file_location('qualification', ROOT / 'scripts/verify-vlckit-qualification.py')
    qualification = module_from_spec(spec); spec.loader.exec_module(qualification)
    if record['qualification_fingerprint'] != qualification.qualification_fingerprint(record):
        raise ValueError('Native qualification fingerprint changed')
    if receipt['supplier']['qualification_fingerprint'] != record['qualification_fingerprint']:
        raise ValueError('Consumer receipt qualification mismatch')
    fields = {key: value for key, value in receipt.items() if key != 'receipt_sha256'}
    if hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':')).encode()).hexdigest() != receipt['receipt_sha256']:
        raise ValueError('Consumer receipt hash mismatch')
    for name, expected in record['patches'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Qualified patch changed: ' + name)
    if digest(ROOT / record['source_inventory']) != record['source_inputs_sha256']:
        raise ValueError('Qualified source inventory changed')
    for name, expected in record['qualification_inputs'].items():
        path = ROOT / ('packaging/EPTVVLCKit.podspec' if name.startswith('apps/apple/') else name)
        if digest(path) != expected:
            raise ValueError('Qualified input changed: ' + name)
    if digest(RELEASE / 'TransitiveNotices.txt') != record['transitive_notices_sha256']:
        raise ValueError('Qualified notices changed')
    for name, field in [("EPTVVLCKit.zip", "artifact_sha256"), ("EPTVVLCKit-source.zip", "source_archive_sha256")]:
        item = manifest["assets"][name]
        if item["sha256"] != record[field] or item["sha256"] != receipt[field]:
            raise ValueError("Release/build-record mismatch: " + name)
        if args.archives:
            args.archives.mkdir(parents=True, exist_ok=True)
            target = args.archives / name
            if args.download and not target.exists():
                partial = target.with_suffix(target.suffix + ".partial")
                try:
                    print("Downloading " + name, flush=True)
                    urllib.request.urlretrieve(item["url"], partial)
                    if partial.stat().st_size != item["bytes"] or digest(partial) != item["sha256"]:
                        raise ValueError("Downloaded archive checksum mismatch: " + name)
                    partial.replace(target)
                finally:
                    partial.unlink(missing_ok=True)
            if target.stat().st_size != item["bytes"] or digest(target) != item["sha256"]:
                raise ValueError("Release archive checksum/size mismatch: " + name)
            print("Verified archive: " + name)
    print("Verified %d maintenance files and the release manifest" % count)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print("Verification failed: " + str(error), file=sys.stderr)
        sys.exit(1)
