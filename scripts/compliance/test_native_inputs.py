"""Native source collection rejects substituted archives and incomplete coverage."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_inputs', ROOT / 'scripts/collect-native-vlckit-inputs.py')
collector = importlib.util.module_from_spec(spec); spec.loader.exec_module(collector)

class NativeInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.vlc = self.root / 'vlc'
        for name in ['demo', 'protobuf']:
            (self.vlc / 'contrib/src' / name).mkdir(parents=True)
        (self.vlc / 'contrib/src/protobuf/rules.mak').write_text('')
        cache = self.vlc / 'contrib/tarballs'; cache.mkdir()
        self.archive = cache / 'demo-1.tar.gz'
        with tarfile.open(self.archive, 'w:gz') as archive:
            content = b'Fixture upstream license\n'
            entry = tarfile.TarInfo('demo-1/COPYING'); entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
        checksum = hashlib.sha512(self.archive.read_bytes()).hexdigest()
        (self.vlc / 'contrib/src/demo/SHA512SUMS').write_text(checksum + '  demo-1.tar.gz\n')
        self.log = self.root / 'build.log'
        self.log.write_text('To-be-built packages:\n  demo meson-machinefile\nBuilding contribs\n'
            'grep -- " demo-1.tar.gz$" "../src/demo/SHA512SUMS"\ndemo-1.tar.gz: OK\n')
        self.previous = self.root / 'previous.json'; self.previous.write_text('{"sources": {}}')
        self.output = self.root / 'inputs'

    def collect(self):
        with patch.object(collector.subprocess, 'check_output', return_value='a' * 40):
            collector.collect(self.vlc, self.log, self.previous, self.output)

    def test_verified_archive_and_legal_text_are_retained(self):
        self.collect()
        manifest = json.loads((self.output / 'source-manifest.json').read_text())
        self.assertEqual(manifest['sources']['demo']['sha256'], hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertEqual((self.output / 'licenses/demo/COPYING').read_bytes(), b'Fixture upstream license\n')

    def test_archive_substitution_fails_before_manifest_is_created(self):
        self.archive.write_bytes(b'substituted input')
        with self.assertRaisesRegex(ValueError, 'checksum differs'):
            self.collect()
        self.assertFalse((self.output / 'source-manifest.json').exists())

    def test_unknown_build_input_fails_coverage(self):
        self.log.write_text(self.log.read_text().replace('demo meson-machinefile', 'demo missing-input'))
        with self.assertRaisesRegex(ValueError, 'Unresolved.*missing-input'):
            self.collect()

    def test_missing_native_checksum_result_is_not_promoted(self):
        self.log.write_text(self.log.read_text().replace('demo-1.tar.gz: OK', ''))
        with self.assertRaisesRegex(ValueError, 'Missing native build checksum'):
            self.collect()

if __name__ == '__main__':
    unittest.main()
