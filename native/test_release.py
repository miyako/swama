import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from release import (
    assert_unused, next_version, package, run, validate_notarization,
    validate_signature, verify_inventory, write_inventory,
)


class ReleaseTests(unittest.TestCase):
    def test_notary_exit_success_is_not_acceptance(self):
        accepted = {"id": "ef8ce145-9e0f-4f4b-8766-ec6518637c43", "status": "Accepted"}
        validate_notarization(accepted)
        for status in ("Invalid", "Rejected", "In Progress", "accepted", None):
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                validate_notarization(dict(accepted, status=status))
        with self.assertRaises((KeyError, ValueError)):
            validate_notarization({"status": "Accepted"})

    def test_signature_requires_team_developer_id_timestamp_and_runtime(self):
        details = "Authority=Developer ID Application: Example\nTeamIdentifier=EXAMPLE123\nTimestamp=Nov 2\nflags=0x10000(runtime)\n"
        validate_signature(details, "EXAMPLE123")
        for invalid in (
            details.replace("EXAMPLE123", "OTHER12345"),
            details.replace("Developer ID Application:", "Apple Development:"),
            details.replace("Timestamp=", "Signed Time="),
            details.replace("(runtime)", ""),
        ):
            with self.subTest(details=invalid), self.assertRaises(RuntimeError):
                validate_signature(invalid, "EXAMPLE123")

    def test_final_inventory_covers_nested_inventories_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "nested/SHA256SUMS").write_text("nested inventory")
            (root / "binary").write_bytes(b"final signed code")
            write_inventory(root)
            verify_inventory(root)
            self.assertIn("nested/SHA256SUMS", (root / "SHA256SUMS").read_text())
            (root / "binary").write_bytes(b"changed after signing")
            with self.assertRaises(RuntimeError):
                verify_inventory(root)
            write_inventory(root)
            (root / "unlisted").write_text("unlisted")
            with self.assertRaises(RuntimeError):
                verify_inventory(root)

    def test_existing_tags_or_releases_are_never_overwritten(self):
        for responses in (
            ["abc refs/tags/20.1.6", "[]"],
            ["", json.dumps([{"tagName": "20.1.6"}])],
            ["", json.dumps([{"tagName": "v20.1.6"}])],
        ):
            with patch("release.run", side_effect=responses), self.assertRaises(RuntimeError):
                assert_unused("20.1.6")
        self.assertEqual(next_version("20.1.5", "patch"), "20.1.6")
        self.assertEqual(next_version("20.1.5", "minor"), "20.2.0")
        self.assertEqual(next_version("20.1.5", "major"), "21.0.0")

    def test_command_failures_do_not_disclose_credential_arguments(self):
        with self.assertRaises(RuntimeError) as caught:
            run("false", "--password", "private-credential")
        self.assertNotIn("private-credential", str(caught.exception))

    def test_failed_codesign_prevents_notarization(self):
        with tempfile.TemporaryDirectory() as temporary:
            product = Path(temporary)
            (product / "Resources").mkdir()
            (product / "Resources/4D_COMPILE_RESULT.json").write_text('{"success":true,"errors":[]}')
            with (
                patch("release.required", return_value="configured"),
                patch("release.verify_inventory"),
                patch("release.Path.read_text", return_value='{"version":"20.1.6","success":true,"errors":[]}'),
                patch("release.OUTPUT", product / "out"),
                patch("release.code_paths", return_value=[product / "swama"]),
                patch("release.run", side_effect=RuntimeError("codesign failed")) as command,
            ):
                with self.assertRaisesRegex(RuntimeError, "codesign failed"):
                    package(product, "20.1.6")
                self.assertEqual(command.call_count, 1)
                self.assertEqual(command.call_args.args[0], "codesign")

    def test_both_production_paths_use_strict_release_gates(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/publish.yml").read_text()
        self.assertNotIn("deployment-codesign-product", workflow)
        self.assertNotIn("deployment-release-assets", workflow)
        self.assertEqual(workflow.count("python3 native/release.py package"), 2)
        self.assertEqual(workflow.count("python3 native/release.py publish"), 2)


if __name__ == "__main__":
    unittest.main()
