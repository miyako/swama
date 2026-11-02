import hashlib
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch

from build import audit_binary, checkout_source, copy_products, inventory, run
from install import install
from smoke import verify


class PackagingTests(unittest.TestCase):
    def test_fresh_clone_and_cached_checkout_preserve_pin_and_reject_dirty_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            origin = root / "origin"
            run("git", "init", "--quiet", origin)
            source_file = origin / "fixture.txt"
            source_file.write_text("source fixture\n")
            run("git", "add", "fixture.txt", cwd=origin)
            run(
                "git", "-c", "user.name=CI fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "--quiet", "-m", "Create source fixture", cwd=origin,
            )
            revision = run("git", "rev-parse", "HEAD", cwd=origin, capture=True)
            checkout = root / "checkout"
            self.assertEqual(checkout_source(checkout, str(origin), revision), revision)
            self.assertEqual(checkout_source(checkout, str(origin), revision), revision)
            (checkout / "fixture.txt").write_text("unexpected edit\n")
            with self.assertRaisesRegex(RuntimeError, "tracked modifications"):
                checkout_source(checkout, str(origin), revision)

    def test_binary_audit_requires_colocated_non_system_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "swama"
            imports = "swama:\n\t@rpath/libswiftCompatibilitySpan.dylib (compatibility version 0.0.0)\n"
            commands = "cmd LC_BUILD_VERSION\ncmdsize 32\nplatform 1\nminos 15.4\n"
            with patch("build.run", side_effect=["arm64", imports]):
                with self.assertRaisesRegex(RuntimeError, "Unbundled runtime dependency"):
                    audit_binary(binary)
            (root / "libswiftCompatibilitySpan.dylib").touch()
            with patch("build.run", side_effect=["arm64", imports, commands, None]):
                self.assertEqual(audit_binary(binary)["minimum_macos"], "15.4")
            commands += "cmd LC_RPATH\ncmdsize 120\npath /Applications/Xcode.app/runtime (offset 12)\n"
            with patch("build.run", side_effect=["arm64", imports, commands]):
                with self.assertRaisesRegex(RuntimeError, "Unexpected runtime search path"):
                    audit_binary(binary)

    def test_complete_swiftpm_bundle_tree_and_executable_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            products = root / "products"
            metal = products / "swama_SwamaCore.bundle/mlx-swift_Cmlx.bundle/Contents/Resources/default.metallib"
            metal.parent.mkdir(parents=True)
            metal.write_bytes(b"metal fixture")
            tokenizer = products / "swift-transformers_Hub.bundle/tokenizer.json"
            tokenizer.parent.mkdir()
            tokenizer.write_text("{}")
            (products / "swama").write_bytes(b"binary fixture")
            (products / "swama").chmod(0o755)
            destination = root / "distribution"
            copy_products(products, destination)
            self.assertEqual(inventory(products), inventory(destination))
            self.assertTrue((destination / "swama").stat().st_mode & 0o111)
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                copy_products(products, destination)

    def test_missing_metal_is_fatal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            products = root / "products"
            products.mkdir()
            (products / "swama").touch()
            (products / "other.bundle").mkdir()
            with self.assertRaisesRegex(RuntimeError, "Metal resource is missing"):
                copy_products(products, root / "distribution")

    def test_verify_rejects_tampering_extra_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "swama").write_bytes(b"binary fixture")
            (root / "swama").chmod(0o755)
            (root / "BUILD_INFO.json").write_text(json.dumps({"version": "2.5.1"}))
            (root / "SHA256SUMS").write_text("".join(
                f"{checksum}  {path}\n" for path, checksum in inventory(root).items()
            ))
            self.assertEqual(verify(root)["version"], "2.5.1")
            (root / "extra").touch()
            with self.assertRaisesRegex(RuntimeError, "complete distribution"):
                verify(root)
            (root / "extra").unlink()
            (root / "link").symlink_to(root / "swama")
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                verify(root)
            (root / "link").unlink()
            (root / "swama").write_bytes(b"modified")
            with self.assertRaisesRegex(RuntimeError, "Checksum mismatch"):
                verify(root)

    def test_verify_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "SHA256SUMS").write_text(f"{hashlib.sha256(b'').hexdigest()}  ../outside\n")
            with self.assertRaisesRegex(RuntimeError, "Checksum mismatch"):
                verify(root)

    def test_install_rejects_unscoped_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "bin/macOS"):
                install(Path("unused.tar.gz"), Path(temporary))

    def test_install_replaces_stale_resources_instead_of_overlaying(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "distribution"
            source.mkdir()
            (source / "fresh.bundle").mkdir()
            (source / "swama").write_bytes(b"new CLI")
            (source / "swama").chmod(0o755)
            (source / "SHA256SUMS").write_text("pre-sign fixture\n")
            archive = root / "native.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(source, arcname=source.name)
            destination = root / "Resources/bin/macOS"
            destination.mkdir(parents=True)
            (destination / "old.bundle").mkdir()
            with patch("install.smoke") as smoke:
                install(archive, destination, component_package=True)
                self.assertEqual(smoke.call_count, 2)
            self.assertFalse((destination / "old.bundle").exists())
            self.assertTrue((destination / "fresh.bundle").is_dir())
            self.assertEqual((destination / "swama").read_bytes(), b"new CLI")
            self.assertFalse((destination / "SHA256SUMS").exists())
            self.assertEqual((destination / "SOURCE_BUILD_SHA256SUMS").read_text(), "pre-sign fixture\n")

    def test_both_publish_jobs_install_after_version_before_component_build(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/publish.yml").read_text()
        hosted, self_hosted = workflow.split("  publish-locally:", 1)
        for job in (hosted, self_hosted):
            version = job.index("uses: miyako/4D/.github/actions/package-set-version@v1")
            install_step = job.index("python3 native/install.py")
            build = job.index("uses: miyako/4D/.github/actions/build-component@v1")
            self.assertLess(version, install_step)
            self.assertLess(install_step, build)


if __name__ == "__main__":
    unittest.main()
