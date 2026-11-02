from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from component import download, validate_compile_result


class ComponentTests(unittest.TestCase):
    def test_requires_explicit_success_and_empty_diagnostics(self):
        validate_compile_result({"success": True, "errors": []})
        for result in (
            {"success": False, "errors": []},
            {"success": True, "errors": [{"message": "The class event is unknown.", "isError": False}]},
            {"success": True},
            {},
        ):
            with self.subTest(result=result), self.assertRaises(RuntimeError):
                validate_compile_result(result)

    def test_corrupt_cached_dependency_is_not_used_or_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "component.zip"
            archive.write_bytes(b"unexpected archive")
            with patch("component.run") as run:
                with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                    download("https://example.invalid/component.zip", archive, "0" * 64)
                run.assert_not_called()

    def test_all_component_build_paths_require_preflight(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/publish.yml").read_text()
        self.assertEqual(workflow.count("python3 native/component.py --tool"), 3)
        self.assertIn("-iname '*.4dz'", workflow)


if __name__ == "__main__":
    unittest.main()
