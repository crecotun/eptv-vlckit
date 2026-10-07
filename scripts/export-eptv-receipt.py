#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright 2026 Alexei Crecotun
"""Export a qualified, binary-only dependency receipt for EPTV consumers."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('qualification', ROOT / 'scripts/verify-vlckit-qualification.py')
qualification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualification)

def sha(path):
    return qualification.sha(path)

def export(record, artifact_directory, published=False):
    qualification.require(record['status'] == 'ENGINEERING_QUALIFICATION_PASSED', 'Qualify the native dependency first')
    qualification.require(record['qualification_fingerprint'] == qualification.qualification_fingerprint(record), 'Native qualification fingerprint mismatch')
    for name, digest in record['patches'].items():
        qualification.require(sha(ROOT / name) == digest, 'Native patch changed: ' + name)
    qualification.require(sha(ROOT / record['source_inventory']) == record['source_inputs_sha256'], 'Source inventory changed')
    for name, digest in record['qualification_inputs'].items():
        source = ROOT / ('packaging/EPTVVLCKit.podspec' if name == 'apps/apple/Vendor/EPTVVLCKit/EPTVVLCKit.podspec' else name)
        qualification.require(sha(source) == digest, 'Qualified input changed: ' + name)
    for name, key in [('EPTVVLCKit.zip', 'artifact_sha256'), ('EPTVVLCKit-source.zip', 'source_archive_sha256')]:
        qualification.require(sha(artifact_directory / name) == record[key], 'Release archive changed: ' + name)
    keys = ['pod_name', 'pod_version', 'vlckit_upstream_revision', 'vlckit_revision', 'vlc_base_revision',
            'vlc_revision', 'vlc_tree', 'minimum_os', 'configuration', 'status', 'toolchain', 'slices',
            'transitive_notices_sha256', 'podspec_checksum', 'artifact_sha256', 'source_archive_sha256']
    receipt = {key: record[key] for key in keys}
    receipt['schema_version'] = 1
    receipt['supplier'] = {'repository': 'https://github.com/crecotun/eptv-vlckit', 'release': record['pod_version'],
                           'qualification_fingerprint': record['qualification_fingerprint']}
    with zipfile.ZipFile(artifact_directory / 'EPTVVLCKit.zip') as archive:
        receipt['installed_files'] = {name: hashlib.sha256(archive.read('EPTVVLCKit/' + name)).hexdigest()
                                      for name in ['EPTVVLCKit.podspec', 'COPYING', 'TransitiveNotices.txt']}
    receipt['retained_artifacts'] = {kind: {
        'url': 'https://github.com/crecotun/eptv-vlckit/releases/download/' + record['pod_version'] + '/' + name,
        'publication': 'PUBLISHED' if published else 'LOCAL_REVIEW_CANDIDATE'} for kind, name in
        [('binary', 'EPTVVLCKit.zip'), ('source', 'EPTVVLCKit-source.zip')]}
    receipt['receipt_sha256'] = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return receipt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, default=ROOT / 'compliance/vlckit-eptv-build.json')
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--published', action='store_true', help='Use only after public source/binary URLs are verified')
    args = parser.parse_args()
    try:
        receipt = export(json.loads(args.record.read_text()), args.artifacts, args.published)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, 'Receipt export failed: ' + str(error) + '\n')
    print('Exported qualified consumer receipt: ' + str(args.output))

if __name__ == '__main__':
    main()
