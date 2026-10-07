"""Supplier qualification binds evidence to exact archives and source trees."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result

qualification = module('qualification', 'scripts/verify-vlckit-qualification.py')
package = module('package', 'scripts/package-eptv-vlckit.py')

class QualificationTests(unittest.TestCase):
    def test_evidence_for_another_archive_is_rejected_before_native_inspection(self):
        record = json.loads((ROOT / 'compliance/vlckit-eptv-build.json').read_text())
        record['status'] = 'PENDING_QUALIFICATION'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'candidate.json'; candidate.write_text(json.dumps(record))
            evidence = root / 'evidence.json'
            evidence.write_text(json.dumps({'status': 'ENGINEERING_QUALIFICATION_PASSED', 'artifact_sha256': '0' * 64}))
            with self.assertRaisesRegex(ValueError, 'Evidence is for another artifact'):
                package.finalize(argparse.Namespace(record=candidate, qualification_evidence=evidence))

    def test_archive_tree_preserves_modes_symlinks_and_directory_order(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'same').mkdir(); (source / 'same/file').write_bytes(b'binary\0content')
            (source / 'same.c').write_text('file beside directory')
            (source / 'run.sh').write_text('#!/bin/sh\n'); (source / 'run.sh').chmod(0o755)
            (source / 'link').symlink_to('same/file')
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
            expected = subprocess.check_output(['git', '-C', str(source), 'write-tree'], text=True).strip()
            shutil.rmtree(source / '.git')
            self.assertEqual(qualification.archive_tree(source), expected)
            (source / 'run.sh').chmod(0o644)
            self.assertNotEqual(qualification.archive_tree(source), expected)

if __name__ == '__main__':
    unittest.main()
