#!/usr/bin/env python3
"""Package qualified EPTV framework slices and their corresponding source.

All artifacts are local review candidates until the separate distribution and
transitive review record is approved. Never downloads or publishes artifacts.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import re
import struct
import zipfile
import tempfile
import urllib.parse
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('license_audit', ROOT / 'scripts/audit-vlckit-licenses.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()


def require(value, message):
    if not value:
        raise ValueError(message)


def source_archive(source, target, revision, include_revision=False):
    raw = subprocess.check_output(['git', '-C', str(source), 'archive', '--format=tar', revision])
    with tarfile.open(fileobj=io.BytesIO(raw)) as input, tarfile.open(target, 'w:gz') as output:
        for member in input:
            output.addfile(member, input.extractfile(member) if member.isfile() else None)
        if include_revision:
            # Archives lack .git; VLC's stamp-revision falls back to this file.
            data = (git(source, 'describe', '--tags', '--long', '--match', '?.*.*', '--always') + '\n').encode()
            member = tarfile.TarInfo('src/revision.txt')
            member.size, member.mode, member.mtime = len(data), 0o644, 1791244800
            output.addfile(member, io.BytesIO(data))


def package(args):
    record_path = args.record or ROOT / 'compliance/vlckit-eptv-build.json'
    record = json.loads(record_path.read_text())
    for label, source in [('vlckit', args.vlckit_source), ('vlc', args.vlc_source)]:
        require(git(source, 'rev-parse', 'HEAD') == record[label + '_revision'], label + ' revision differs')
        require(git(source, 'rev-parse', 'HEAD^{tree}') == record[label + '_tree'], label + ' tree differs')
        require(not git(source, 'status', '--porcelain', '--untracked-files=no'), label + ' source is modified')
    for name, checksum in record['patches'].items():
        require(sha(ROOT / name) == checksum, 'Patch checksum differs: ' + name)
    inputs_path = ROOT / args.source_inventory
    require(sha(inputs_path) == record['source_inputs_sha256'], 'Source input record differs')
    inputs = json.loads(inputs_path.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    source_root = args.output / 'source'
    source_root.mkdir()
    frameworks = [
        ('macos-arm64', 'macOS', ['arm64']),
        ('tvos-arm64', 'tvOS', ['arm64']),
        ('tvos-arm64-simulator', 'tvOS', ['arm64']),
    ]
    reports, xc_args = {}, []
    for identifier, folder, expected_archs in frameworks:
        base = args.vlckit_source / 'build' / folder / 'VLCKit.xcframework' / identifier
        framework = base / 'VLCKit.framework'
        binary = framework / 'VLCKit'
        archs = subprocess.check_output(['lipo', '-archs', str(binary)], text=True).split()
        require(set(archs) == set(expected_archs), 'Unexpected architectures: ' + identifier)
        slices = [audit.audit(binary, arch) for arch in archs]
        require(all(s['status'] == 'FOCUSED_CHECK_PASSED' for s in slices), 'GPL/unknown licensing in ' + identifier)
        require(all(re.fullmatch('[0-9a-f]{7,40}', s['runtime_changeset']) and
                    record['vlc_revision'].startswith(s['runtime_changeset']) for s in slices),
                'Wrong engine revision in ' + identifier)
        reports[identifier] = {'status': 'FOCUSED_CHECK_PASSED', 'slices': slices}
        dsym = base / 'dSYMs' / 'VLCKit.framework.dSYM'
        require(dsym.is_dir(), 'Missing debug symbols: ' + identifier)
        xc_args += ['-framework', str(framework.resolve()), '-debug-symbols', str(dsym.resolve())]
    subprocess.run(['xcodebuild', '-create-xcframework', *xc_args, '-output', str((args.output / 'VLCKit.xcframework').resolve())], check=True)
    for identifier, report in reports.items():
        (source_root / (identifier + '-license-audit.json')).write_text(json.dumps(report, indent=2) + '\n')
    source_archive(args.vlckit_source, source_root / 'VLCKit-source.tar.gz', record['vlckit_revision'])
    source_archive(args.vlc_source, source_root / 'VLC-source.tar.gz', record['vlc_revision'], True)
    contrib = source_root / 'contrib'
    contrib.mkdir()
    for component, item in inputs['sources'].items():
        archive = args.source_inputs / item['filename']
        require(sha(archive) == item['sha256'], 'Source archive differs: ' + component)
        shutil.copy2(archive, contrib / archive.name)
        if item.get('git_revision'):
            (contrib / archive.name.replace('.tar.xz', '.githash')).write_text(
                item['git_revision'] + ' ../tarballs/' + archive.name + '\n')
        for legal in item['license_files']:
            path = args.source_inputs / 'licenses' / component / legal['path']
            require(sha(path) == legal['sha256'], 'Legal text differs: ' + str(path))
            target = source_root / 'legal' / component / legal['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    shutil.copy2(inputs_path, source_root / 'source-inputs.json')
    patches = source_root / 'eptv-patches'
    patches.mkdir()
    for name in record['patches']:
        shutil.copy2(ROOT / name, patches / Path(name).name)
    tools = source_root / 'tools'
    tools.mkdir()
    tool_checksums = {}
    expected = {row.split()[1]: row.split()[0] for row in
                (args.vlc_source / 'extras/tools/SHA512SUMS').read_text().splitlines()}
    for archive in (args.vlc_source / 'extras/tools').glob('*.tar.*'):
        if archive.name not in expected:
            continue
        require(hashlib.sha512(archive.read_bytes()).hexdigest() == expected[archive.name],
                'Build-tool archive differs: ' + archive.name)
        shutil.copy2(archive, tools / archive.name)
        tool_checksums[archive.name] = sha(archive)
    make = args.vlc_source.parent / Path(urllib.parse.urlsplit(record['gnu_make']['url']).path).name
    require(sha(make) == record['gnu_make']['sha256'], 'GNU Make source differs')
    shutil.copy2(make, tools / make.name)
    tool_checksums[make.name] = sha(make)
    (tools / 'SHA256SUMS').write_text(''.join(digest + '  ' + name + '\n'
                                           for name, digest in sorted(tool_checksums.items())))
    # Build logs are private engineering evidence, not corresponding-source inputs.
    # Keep them outside release packages; qualification still binds retained evidence.
    for archive in tools.iterdir():
        if archive.is_file():
            require(archive.stat().st_size > 0, 'Empty tool source')
    record['toolchain'] = subprocess.check_output(['xcodebuild', '-version'], text=True).strip()
    shutil.copy2(args.vlckit_source / 'COPYING', args.output / 'COPYING')
    # A newly assembled candidate has no ZIP digests until final archiving.
    record.pop('artifact_sha256', None)
    record.pop('source_archive_sha256', None)
    for key in ['qualification_fingerprint', 'qualification_evidence', 'qualification_date', 'qualification_inputs', 'retained_artifacts', 'license_review_record']:
        record.pop(key, None)
    for arrangement in record['distribution_arrangements'].values():
        arrangement.update(status='PENDING_NAMED_REVIEW', replacement='PENDING_NEW_DEPENDENCY_ACCEPTANCE')
        for key in ['reviewer', 'reviewed_on', 'approval_record']:
            arrangement.pop(key, None)
    record.update(status='QUALIFIED_BINARY_CANDIDATE', license_review='NAMED_REVIEW_REQUIRED', slices=reports)
    (args.output / 'build-record.json').write_text(json.dumps(record, indent=2) + '\n')
    shutil.copy2(args.output / 'build-record.json', source_root / 'build-record.json')
    shutil.copy2(ROOT / 'compliance/vlckit-source-readme.md', source_root / 'README.md')
    shutil.copy2(ROOT / 'scripts/build-eptv-vlckit.sh', source_root / 'build-eptv-vlckit.sh')
    notices = args.notices.read_bytes()
    require(hashlib.sha256(notices).hexdigest() == record['transitive_notices_sha256'],
            'Bundled transitive notices differ from the qualified record')
    (source_root / 'TransitiveNotices.txt').write_bytes(notices)
    (args.output / 'TransitiveNotices.txt').write_bytes(notices)
    checksums = [(path.relative_to(source_root).as_posix(), sha(path))
                 for path in source_root.rglob('*') if path.is_file()]
    (source_root / 'SHA256SUMS').write_text(''.join(checksum + '  ' + name + '\n'
                                                for name, checksum in sorted(checksums)))
    # One compact record, detailed inventories remain inside the source package.
    compact = dict(record)
    compact['slices'] = {identifier: {'status': report['status'], 'architectures': {
        item['audited_architecture']: dict(audit.identity(args.output / 'VLCKit.xcframework' / identifier /
            'VLCKit.framework/VLCKit', item['audited_architecture']),
            runtime_changeset=item['runtime_changeset'], runtime_version=item['runtime_version'],
            module_count=len(item['module_declarations'])) for item in report['slices']}}
        for identifier, report in reports.items()}
    compact['schema_version'] = 2
    compact['status'] = 'PENDING_QUALIFICATION'
    # Retain archives outside Git; installing never trusts their nominal version.
    payload = args.output / 'EPTVVLCKit'
    payload.mkdir()
    for name in ['VLCKit.xcframework', 'TransitiveNotices.txt', 'COPYING', 'build-record.json']:
        shutil.move(str(args.output / name), payload / name)
    shutil.copy2(ROOT / 'packaging/EPTVVLCKit.podspec', payload / 'EPTVVLCKit.podspec')
    for folder, name in [(payload, 'EPTVVLCKit.zip'), (source_root, 'EPTVVLCKit-source.zip')]:
        subprocess.run(['ditto', '--norsrc', '-c', '-k', '--keepParent', str(folder), str(args.output / name)], check=True)
    compact['artifact_sha256'] = sha(args.output / 'EPTVVLCKit.zip')
    compact['source_archive_sha256'] = sha(args.output / 'EPTVVLCKit-source.zip')
    compact['retained_artifacts'] = {kind: {'path': str((args.output / name).resolve()),
        'url': '', 'publication': 'LOCAL_REVIEW_CANDIDATE'} for kind, name in
        [('binary', 'EPTVVLCKit.zip'), ('source', 'EPTVVLCKit-source.zip')]}
    compact['qualification_inputs'] = {str(path): sha(ROOT / path) for path in
        ['packaging/EPTVVLCKit.podspec', 'compliance/vlckit-source-readme.md', 'scripts/build-eptv-vlckit.sh']}
    compact['source_inventory'] = args.source_inventory
    for arrangement in compact['distribution_arrangements'].values():
        arrangement.update(status='PENDING_NAMED_REVIEW', replacement='PENDING_NEW_DEPENDENCY_ACCEPTANCE')
        arrangement.pop('reviewer', None)
        arrangement.pop('reviewed_on', None)
    (args.output / 'candidate.json').write_text(json.dumps(compact, indent=2) + '\n')
    print('[MEDIA PACKAGING] PASS: ' + str(args.output / 'candidate.json'))
    print('[MEDIA QUALIFICATION] PENDING: run playback/app/replacement checks, then --finalize with retained evidence')


def finalize(args):
    """Promote only a deeply checked package with fresh artifact-bound evidence."""
    spec = importlib.util.spec_from_file_location('verify', ROOT / 'scripts/verify-vlckit-qualification.py')
    verify = importlib.util.module_from_spec(spec); spec.loader.exec_module(verify)
    record = json.loads(args.record.read_text())
    evidence = json.loads(args.qualification_evidence.read_text())
    require(record['status'] == 'PENDING_QUALIFICATION', 'Expected packaged pending candidate')
    require(set(record['slices']) == {'macos-arm64', 'tvos-arm64', 'tvos-arm64-simulator'} and
            all(set(item['architectures']) == {'arm64'} for item in record['slices'].values()),
            'Qualification requires exactly three ARM platform slices')
    require(evidence['status'] == 'ENGINEERING_QUALIFICATION_PASSED', 'Engineering evidence is incomplete')
    for field in ['artifact_sha256', 'source_archive_sha256']:
        require(evidence[field] == record[field], 'Evidence is for another artifact: ' + field)
    for label in ['macos_arm64_release', 'tvos_arm64_device_release']:
        require(evidence['app_builds'][label] == 'PASSED', 'Missing app build evidence: ' + label)
    for platform in ['macos', 'tvos']:
        require(evidence['unit_tests'][platform]['count'] > 0 and evidence['unit_tests'][platform]['failures'] == 0,
                'Missing platform unit test evidence: ' + platform)
    for label in ['macos-playback.json', 'tvos-playback.json']:
        require(evidence['decode'][label].get('video_frames', 0) > 0 and evidence['decode'][label].get('audio_frames', 0) > 0,
                'Missing real synthetic decode: ' + label)
    require(evidence['macos_replacement'] == 'PASSED_LOCAL_RESIGNED_REPLACEMENT', 'Missing Mac replacement evidence')
    require(evidence['embedded_binary_identity'] == 'PASSED_MAC_ARM64_AND_TV_DEVICE', 'Missing embedded identity evidence')
    require(evidence['evidence_sha256'], 'Retain test/build/playback logs and their checksums')
    for path, digest in evidence['evidence_sha256'].items():
        require(sha(ROOT / path) == digest, 'Qualification evidence missing or changed: ' + path)
    for path, digest in record['patches'].items():
        require(sha(ROOT / path) == digest, 'Modified patch: ' + path)
    require(sha(ROOT / record['source_inventory']) == record['source_inputs_sha256'], 'Modified component/source inventory')
    for path, digest in record['qualification_inputs'].items():
        require(sha(ROOT / path) == digest, 'Modified qualification input: ' + path)
    binary_archive = Path(record['retained_artifacts']['binary']['path'])
    source_archive = Path(record['retained_artifacts']['source']['path'])
    require(sha(binary_archive) == record['artifact_sha256'], 'Binary archive checksum differs')
    require(sha(source_archive) == record['source_archive_sha256'], 'Source archive checksum differs')
    with tempfile.TemporaryDirectory(prefix='eptv-qualification-') as folder:
        folder = Path(folder)
        for archive, directory in [(binary_archive, folder / 'binary'), (source_archive, folder / 'sources')]:
            subprocess.run(['ditto', '-x', '-k', str(archive), str(directory)], check=True)
        source = folder / 'sources/source'
        for row in (source / 'SHA256SUMS').read_text().splitlines():
            digest, path = row.split('  ', 1)
            require(sha(source / path) == digest, 'Packaged source file differs: ' + path)
        for label in ['vlckit', 'vlc']:
            tree = folder / label
            tree.mkdir()
            with tarfile.open(source / ('VLCKit-source.tar.gz' if label == 'vlckit' else 'VLC-source.tar.gz')) as archive:
                # Compatible with Xcode's Python 3.9; reject escaping links/paths.
                for member in archive:
                    destination = tree / member.name
                    require(destination.resolve().is_relative_to(tree.resolve()), 'Unsafe source archive path')
                    if member.issym() or member.islnk():
                        link = destination.parent / member.linkname if member.issym() else tree / member.linkname
                        require(link.resolve().is_relative_to(tree.resolve()), 'Unsafe source archive link')
                    require(member.isfile() or member.isdir() or member.issym() or member.islnk(), 'Unsupported source entry')
                    archive.extract(member, tree)
            excluded = ('src/revision.txt',) if label == 'vlc' else ()
            require(verify.archive_tree(tree, excluded) == record[label + '_tree'], 'Packaged source tree differs: ' + label)
            if label == 'vlc':
                require((tree / 'src/revision.txt').read_text().strip() == record['vlc_revision'][:7], 'Wrong VLC revision stamp')
        payload = folder / 'binary/EPTVVLCKit'
        require(sha(payload / 'TransitiveNotices.txt') == record['transitive_notices_sha256'], 'Wrong dependency notices')
        require(sha(source / 'TransitiveNotices.txt') == record['transitive_notices_sha256'], 'Source/binary notices differ')
        for identifier, item in record['slices'].items():
            binary = payload / 'VLCKit.xcframework' / identifier / 'VLCKit.framework/VLCKit'
            architectures = subprocess.check_output(['lipo', '-archs', str(binary)], text=True).split()
            require(set(architectures) == set(item['architectures']), 'Architecture set differs: ' + identifier)
            for arch, expected in item['architectures'].items():
                report = audit.audit(binary, arch)
                require(report['status'] == 'FOCUSED_CHECK_PASSED', 'GPL/module check failed: ' + identifier)
                require(all(value == expected[key] for key, value in audit.identity(binary, arch).items()), 'Candidate identity differs')
                require(record['vlc_revision'].startswith(report['runtime_changeset']), 'Wrong engine revision')
    for artifact in record['retained_artifacts'].values():
        retained_path = Path(artifact['path']).resolve()
        require(retained_path.is_relative_to(ROOT), 'Retain the immutable package under ComplianceArtifacts before finalizing')
        artifact['path'] = str(retained_path.relative_to(ROOT))
    require(args.output, '--finalize requires --output canonical-record-path')
    require(args.qualification_evidence.resolve().is_relative_to(ROOT), 'Retain evidence JSON inside the repository')
    record.update(status='ENGINEERING_QUALIFICATION_PASSED', qualification_date=date.today().isoformat(),
                  qualification_evidence=str(args.qualification_evidence.resolve().relative_to(ROOT)))
    record['qualification_inputs'][record['qualification_evidence']] = sha(args.qualification_evidence)
    record['distribution_arrangements']['macos']['replacement'] = evidence['macos_replacement']
    record['qualification_fingerprint'] = verify.qualification_fingerprint(record)
    args.output.write_text(json.dumps(record, indent=2) + '\n')
    print('[MEDIA QUALIFICATION] PASS: ' + str(args.output))
    print('[HUMAN/LEGAL] PENDING: publication and named platform decisions are separate')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--finalize', action='store_true')
    p.add_argument('--record', type=Path, help='Build-input record, or packaged candidate for --finalize')
    p.add_argument('--qualification-evidence', type=Path)
    p.add_argument('--source-inventory', default='compliance/vlckit-a24-source-inputs.json')
    p.add_argument('--notices', type=Path, help='Reviewed dependency legal texts for this candidate')
    p.add_argument('--vlckit-source', type=Path)
    p.add_argument('--vlc-source', type=Path)
    p.add_argument('--source-inputs', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    try:
        if args.finalize:
            require(args.record and args.qualification_evidence, '--finalize requires --record and --qualification-evidence')
            finalize(args)
        else:
            require(args.vlckit_source and args.vlc_source and args.source_inputs and args.notices,
                    'Packaging requires --vlckit-source, --vlc-source, --source-inputs and --notices')
            package(args)
    except (ValueError, KeyError, struct.error, OSError, subprocess.CalledProcessError) as error:
        p.exit(1, '[MEDIA QUALIFICATION] BLOCKED: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
