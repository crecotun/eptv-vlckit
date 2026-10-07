#!/usr/bin/env python3
"""Native source/tree/fingerprint helpers owned by the VLCKit supplier."""
import hashlib
import json
import os
from pathlib import Path
import stat

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def archive_tree(directory, excluded=()):
    """Hash a clean extracted source archive as a Git tree without a .git folder."""
    def object_hash(kind, data):
        return hashlib.sha1(kind + b' ' + str(len(data)).encode() + b'\0' + data).digest()
    def tree(folder):
        entries = []
        for path in folder.iterdir():
            relative = path.relative_to(directory).as_posix()
            if relative in excluded:
                continue
            mode = path.lstat().st_mode
            name = path.name.encode()
            if stat.S_ISLNK(mode):
                content, git_mode, order = os.readlink(path).encode(), b'120000', name
                digest = object_hash(b'blob', content)
            elif stat.S_ISDIR(mode):
                digest, git_mode, order = tree(path), b'40000', name + b'/'
            elif stat.S_ISREG(mode):
                digest = object_hash(b'blob', path.read_bytes())
                git_mode, order = (b'100755' if mode & 0o111 else b'100644'), name
            else:
                raise ValueError('Unsupported source archive entry: ' + str(path))
            entries.append((order, git_mode + b' ' + name + b'\0' + digest))
        return object_hash(b'tree', b''.join(item for _, item in sorted(entries)))
    return tree(directory).hex()


def qualification_fingerprint(record):
    """Native inputs/evidence only; app versions and distribution decisions excluded."""
    keys = ['pod_name', 'pod_version', 'podspec_checksum', 'vlckit_upstream_revision',
            'vlckit_revision', 'vlckit_tree', 'vlc_base_revision', 'vlc_upstream_patched_tree',
            'vlc_revision', 'vlc_tree', 'minimum_os', 'configuration', 'patches',
            'source_inputs_sha256', 'source_inventory', 'gnu_make', 'toolchain', 'slices',
            'artifact_sha256', 'source_archive_sha256', 'transitive_notices_sha256', 'qualification_inputs']
    payload = {key: record.get(key) for key in keys}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

