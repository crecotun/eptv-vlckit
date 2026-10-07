import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('audit', Path(__file__).parents[1] / 'audit-vlckit-licenses.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class LicenseAuditTests(unittest.TestCase):
    def test_arm64_getter_with_and_without_bti(self):
        getter = struct.pack('<III', 0xB0000000, 0x91048C00, 0xD65F03C0)
        self.assertEqual(audit.arm64_constant_address(getter, 0x12345000), 0x12346123)
        self.assertEqual(audit.arm64_constant_address(struct.pack('<I', 0xD503245F) + getter, 0x12345000), 0x12346123)

    def test_negative_page_offset(self):
        getter = struct.pack('<III', 0xF0FFFFE0, 0x91000000, 0xD65F03C0)
        self.assertEqual(audit.arm64_constant_address(getter, 0x10002000), 0x10001000)

    def test_unknown_instructions_fail(self):
        with self.assertRaises(ValueError):
            audit.arm64_constant_address(b'\0' * 16, 0)

    def test_x86_getter_relative_address_and_optional_frame(self):
        getter = b'\x48\x8d\x05' + struct.pack('<i', -0x107) + b'\xc3'
        self.assertEqual(audit.x86_constant_address(getter, 0x1000), 0xf00)
        framed = b'\x55\x48\x89\xe5' + getter[:-1] + b'\x5d\xc3'
        self.assertEqual(audit.x86_constant_address(framed, 0x1000), 0xf04)
        with self.assertRaises(ValueError):
            audit.x86_constant_address(b'\0' * 16, 0)

    def test_stripped_license_getters_do_not_hide_gpl(self):
        symbols = {'_vlc_entry__logger_file', '_vbi_decode_teletext_8302_cni'}
        gpl, entries, zvbi, status = audit.classify({}, symbols, [])
        self.assertEqual(status, 'BLOCKED_GPL_CODE')
        self.assertEqual(entries, ['logger_file'])
        self.assertEqual(zvbi, ['_vbi_decode_teletext_8302_cni'])

    def test_missing_or_undecodable_declarations_fail_closed(self):
        self.assertEqual(audit.classify({}, set(), [])[-1], 'INCOMPLETE')
        self.assertEqual(audit.classify({'ok': 'GNU Lesser General Public License'}, set(), ['bad'])[-1], 'INCOMPLETE')
        self.assertEqual(audit.classify({'ok': 'GNU Lesser General Public License'}, set(), [])[-1], 'FOCUSED_CHECK_PASSED')
        self.assertEqual(audit.classify({'bad': 'GNU General Public License'}, set(), [])[-1], 'BLOCKED_GPL_CODE')


if __name__ == '__main__':
    unittest.main()
