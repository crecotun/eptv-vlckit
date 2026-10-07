import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "build_evidence", Path(__file__).resolve().parents[1] / "verify-vlckit-build.py"
)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class BuildEvidenceTests(unittest.TestCase):
    def test_raw_log_integrity_and_terminal_decoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "job.log"
            raw = b"2026-08-31T13:26:59Z 01O \x1b[32;1mJob succeeded\x1b[0;m\n"
            path.write_bytes(raw)
            record = {"raw_log_sha256": hashlib.sha256(raw).hexdigest()}
            self.assertEqual(evidence.read_log(path, record), ["Job succeeded"])
            path.write_bytes(raw.replace(b"succeeded", b"failed"))
            with self.assertRaisesRegex(ValueError, "checksum"):
                evidence.read_log(path, record)

    def test_platform_scope_does_not_borrow_another_builds_fingerprint(self):
        lines = ["$ ./compileAndBuildVLCKit.sh -ft", "TV fingerprint",
                 "$ ./compileAndBuildVLCKit.sh -xf", "Mac fingerprint"]
        self.assertEqual(evidence.platform_block(lines, "-ft"), lines[:2])
        with self.assertRaisesRegex(ValueError, "exactly one"):
            evidence.platform_block(lines + lines, "-ft")

    def test_checksum_input_is_derived_from_recipe_and_successful_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checksum = "a" * 128
            recipe = root / "contrib/src/example"
            recipe.mkdir(parents=True)
            (recipe / "SHA512SUMS").write_text(checksum + "  example-1.tar.xz\n")
            block = ["To-be-built packages:", "  example", "Building contribs",
                     'grep -- " example-1.tar.xz$" "../src/example/SHA512SUMS"',
                     checksum + "  example-1.tar.xz", "example-1.tar.xz: OK"]
            result = evidence.inventory(block, root)
            self.assertEqual(result["sources"]["example"]["sha512"], checksum)
            with self.assertRaisesRegex(ValueError, "successful source check"):
                evidence.inventory(block[:-1], root)

    def test_differing_architecture_contrib_lists_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "differing"):
            evidence.inventory(["To-be-built packages:", "  one", "Build",
                                "To-be-built packages:", "  two", "Build"], Path("unused"))

    def test_missing_git_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe = root / "contrib/src/example"
            recipe.mkdir(parents=True)
            (recipe / "rules.mak").write_text("EXAMPLE_HASH := " + "b" * 40)
            with self.assertRaisesRegex(ValueError, "Git revision check"):
                evidence.inventory(["To-be-built packages:", "  example", "Build"], root)


if __name__ == "__main__":
    unittest.main()
