# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).parents[1] / "check-public-safety.py"
SPEC = importlib.util.spec_from_file_location("check_public_safety", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
SCANNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCANNER)


class PublicSafetyScannerTests(unittest.TestCase):
    def test_safe_placeholder_source_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "safe.py"
            source.write_text(
                'endpoint = "https://pantheon.example.com"\n'
                'address = "192.0.2.10"\n',
                encoding="utf-8",
            )
            self.assertEqual(SCANNER.scan([source], []), 0)

    def test_diagnostics_do_not_echo_private_value(self) -> None:
        private_value = "op://example-vault/example-item/password"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "unsafe.py"
            source.write_text(f'value = "{private_value}"\n', encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                findings = SCANNER.scan([source], [])
            self.assertEqual(findings, 1)
            self.assertIn("secret-manager-reference", output.getvalue())
            self.assertNotIn(private_value, output.getvalue())

    def test_exact_denylist_is_redacted(self) -> None:
        private_value = "private-identifier-for-test"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "unsafe.txt"
            source.write_text(private_value, encoding="utf-8")
            denylist = Path(directory) / "denylist.txt"
            denylist.write_text(private_value, encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                findings = SCANNER.scan(
                    [source], SCANNER.read_denylist(denylist)
                )
            self.assertEqual(findings, 1)
            self.assertIn("private-identifier-1", output.getvalue())
            self.assertNotIn(private_value, output.getvalue())

    def test_secret_key_file_is_blocked_without_reading_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "client.key"
            source.write_text("synthetic-key-material", encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                findings = SCANNER.scan([source], [])
            self.assertEqual(findings, 1)
            self.assertIn("blocked-file", output.getvalue())
            self.assertNotIn("synthetic-key-material", output.getvalue())


if __name__ == "__main__":
    unittest.main()
