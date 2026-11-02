import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from build import ROOT, digest, inventory, run
from update import (
    GIT_FILE_LIMIT, REQUIRED_RESOURCES, RESOURCE_PATH, adopt, check_sizes,
    commit_resources, freshness, validate_distribution, verify_committed,
)


def fixture(root):
    root.mkdir(parents=True, exist_ok=True)
    for relative in REQUIRED_RESOURCES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    (root / "swama").chmod(0o755)
    (root / "Package.resolved").write_text(json.dumps({"pins": [
        {"identity": "EventSource", "state": {"revision": "b" * 40}},
        {"identity": "mlx-swift", "state": {"revision": "f" * 40}},
    ]}))
    license_path = root / "licenses/EventSource/LICENSE"
    license_path.parent.mkdir(parents=True)
    license_path.write_text("license fixture")
    mlx_license = root / "licenses/mlx-swift/LICENSE"
    mlx_license.parent.mkdir()
    mlx_license.write_text("MLX license fixture")
    pin = {
        "repository": "https://example.invalid/swama.git", "revision": "a" * 40,
        "version": "2.5.1", "minimum_macos": "15.4",
        "swift_runtime_license": {"url": "fixture", "sha256": "c" * 64},
    }
    info = dict(
        pin, platform="macos-arm64", configuration="release",
        packaging_revision="d" * 40, packaging_dirty=False,
        swift="Swift fixture", xcode="Xcode fixture", sdk="SDK fixture",
        packaging_files={"native/build.py": "e" * 64}, binary={"imports": "fixture"},
        metal={"revision": "f" * 40, "compiler": "Metal fixture",
               "target": "air64-apple-macos14.0", "sources": {"kernel.metal": "f" * 64}},
        package_resolved_sha256=digest(root / "Package.resolved"),
        dependencies=json.loads((root / "Package.resolved").read_text())["pins"],
        swift_runtime={"libraries": {}},
    )
    (root / "BUILD_INFO.json").write_text(json.dumps(info))
    rehash(root)
    return pin, info


def rehash(root):
    (root / "SHA256SUMS").write_text("".join(
        f"{checksum}  {path}\n" for path, checksum in inventory(root).items()
    ))


class UpdateTests(unittest.TestCase):
    def test_exact_github_file_limit_is_rejected_before_hashing(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "oversized.dylib"
            with path.open("wb") as stream:
                stream.truncate(GIT_FILE_LIMIT)
            with self.assertRaisesRegex(RuntimeError, "100 MiB"):
                check_sizes(path.parent)
            with path.open("wb") as stream:
                stream.truncate(GIT_FILE_LIMIT - 1)
            self.assertEqual(check_sizes(path.parent)[path.name], GIT_FILE_LIMIT - 1)

    def test_complete_source_and_resource_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pin, expected = fixture(root)
            with patch("update.audit_binary"), patch("update.smoke") as smoke:
                actual, sizes = validate_distribution(root, pin)
                self.assertEqual(actual, expected)
                self.assertEqual(sizes["swama"], 7)
                smoke.assert_called_once_with(root)
            for field in ("revision", "version", "repository", "minimum_macos"):
                with self.subTest(field=field), patch("update.smoke") as smoke:
                    with self.assertRaisesRegex(RuntimeError, field):
                        validate_distribution(root, dict(pin, **{field: "different"}))
                    smoke.assert_not_called()

    def test_missing_resource_is_not_fixed_by_regenerating_checksums(self):
        for resource in REQUIRED_RESOURCES:
            with self.subTest(resource=resource), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin, _ = fixture(root)
                (root / resource).unlink()
                if resource != "SHA256SUMS":
                    rehash(root)
                with self.assertRaisesRegex(RuntimeError, "Missing native provenance/resources"):
                    validate_distribution(root, pin)

    def test_dependency_license_and_lock_must_be_present(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pin, _ = fixture(root)
            (root / "licenses/EventSource/LICENSE").unlink()
            rehash(root)
            with self.assertRaisesRegex(RuntimeError, "Missing dependency license"):
                validate_distribution(root, pin)
            (root / "Package.resolved").write_text('{"pins":[]}')
            rehash(root)
            with self.assertRaisesRegex(RuntimeError, "lockfile"):
                validate_distribution(root, pin)

    def test_dirty_and_incomplete_build_provenance_is_rejected(self):
        for change in (
            {"packaging_dirty": True}, {"packaging_revision": "main"},
            {"platform": "macos-x64"}, {"dependencies": []}, {"swift": ""},
            {"metal": {"revision": "f" * 40}}, {"packaging_files": {"native/build.py": "invalid"}},
        ):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin, info = fixture(root)
                (root / "BUILD_INFO.json").write_text(json.dumps(dict(info, **change)))
                rehash(root)
                with self.assertRaises(RuntimeError):
                    validate_distribution(root, pin)

    def test_runtime_requires_exact_vendor_copy_and_apple_signature(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pin, info = fixture(root)
            library = root / "libswiftFixture.dylib"
            library.write_bytes(b"vendor signed fixture")
            license_file = root / "licenses/swift/LICENSE.txt"
            license_file.parent.mkdir()
            license_file.write_text("Swift license fixture")
            pin["swift_runtime_license"]["sha256"] = digest(license_file)
            info["swift_runtime"] = {
                "libraries": {library.name: {"sha256": digest(library)}},
                "license": pin["swift_runtime_license"],
            }
            (root / "BUILD_INFO.json").write_text(json.dumps(info))
            rehash(root)
            with patch("update.run") as command, patch("update.audit_binary"), patch("update.smoke"):
                validate_distribution(root, pin)
                command.assert_called_once_with("codesign", "--verify", "--strict", "-R=anchor apple", library)
            library.write_bytes(b"modified runtime")
            rehash(root)
            with self.assertRaisesRegex(RuntimeError, "changed after vendor-signed copy"):
                validate_distribution(root, pin)

    def make_repository(self, root):
        remote = root / "remote.git"
        repo = root / "repo"
        run("git", "init", "--quiet", "--bare", remote)
        run("git", "init", "--quiet", "-b", "main", repo)
        run("git", "config", "user.name", "Fixture", cwd=repo)
        run("git", "config", "user.email", "fixture@example.invalid", cwd=repo)
        resource = repo / RESOURCE_PATH
        resource.mkdir(parents=True)
        (resource / "old.bundle").write_text("old")
        (repo / "unrelated.txt").write_text("preserved")
        run("git", "add", "--", RESOURCE_PATH + "/old.bundle", "unrelated.txt", cwd=repo)
        run("git", "commit", "--quiet", "-m", "Initial", cwd=repo)
        run("git", "remote", "add", "origin", remote, cwd=repo)
        run("git", "push", "--quiet", "origin", "HEAD:refs/heads/main", cwd=repo)
        return repo, run("git", "rev-parse", "HEAD", cwd=repo, capture=True)

    def test_exact_changed_files_deletions_commit_and_real_fast_forward_push(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, expected = self.make_repository(Path(temporary))
            resource = repo / RESOURCE_PATH
            (resource / "old.bundle").unlink()
            (resource / "new.bundle").mkdir()
            (resource / "new.bundle/data").write_text("new")
            commit_resources(expected, repo=repo)
            self.assertEqual(run("git", "status", "--porcelain", cwd=repo, capture=True), "")
            paths = run("git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD", cwd=repo, capture=True).splitlines()
            self.assertEqual(set(paths), {RESOURCE_PATH + "/old.bundle", RESOURCE_PATH + "/new.bundle/data"})
            self.assertEqual(run("git", "rev-parse", "HEAD", cwd=repo, capture=True), run("git", "ls-remote", "origin", "refs/heads/main", cwd=repo, capture=True).split()[0])
            self.assertEqual((repo / "unrelated.txt").read_text(), "preserved")

    def test_unrelated_changes_or_advanced_default_branch_fail_without_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, expected = self.make_repository(Path(temporary))
            (repo / "unrelated.txt").write_text("unexpected")
            with self.assertRaisesRegex(RuntimeError, "outside the exact native"):
                commit_resources(expected, repo=repo)
            self.assertEqual(run("git", "diff", "--cached", "--name-only", cwd=repo, capture=True), "")
            other = Path(temporary) / "other"
            run("git", "clone", "--quiet", "-b", "main", repo.parent / "remote.git", other)
            run("git", "-c", "user.name=Other", "-c", "user.email=other@example.invalid",
                "commit", "--quiet", "--allow-empty", "-m", "Concurrent default change", cwd=other)
            run("git", "push", "--quiet", "origin", "HEAD:refs/heads/main", cwd=other)
            with self.assertRaisesRegex(RuntimeError, "Default branch advanced"):
                freshness(expected, repo=repo)

    def test_push_rejects_default_branch_race_after_freshness_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, expected = self.make_repository(root)
            other = root / "other"
            run("git", "clone", "--quiet", "-b", "main", root / "remote.git", other)
            (repo / RESOURCE_PATH / "old.bundle").write_text("updated")

            def racing_run(*args, **kwargs):
                if args[:2] == ("git", "push"):
                    run("git", "-c", "user.name=Other", "-c", "user.email=other@example.invalid",
                        "commit", "--quiet", "--allow-empty", "-m", "Concurrent commit", cwd=other)
                    run("git", "push", "--quiet", "origin", "HEAD:refs/heads/main", cwd=other)
                return run(*args, **kwargs)

            with patch("update.run", side_effect=racing_run), self.assertRaises(subprocess.CalledProcessError):
                commit_resources(expected, repo=repo)
            remote = run("git", "ls-remote", "origin", "refs/heads/main", cwd=repo, capture=True).split()[0]
            self.assertEqual(remote, run("git", "rev-parse", "HEAD", cwd=other, capture=True))
            self.assertNotEqual(remote, run("git", "rev-parse", "HEAD", cwd=repo, capture=True))

    def test_resource_and_pin_checkout_bytes_survive_crlf_conversion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = self.make_repository(root)
            shutil.copy2(ROOT / ".gitattributes", repo / ".gitattributes")
            resource = repo / RESOURCE_PATH / "LICENSE"
            resource.write_bytes(b"resource license\nexact bytes\n")
            (repo / "native").mkdir()
            (repo / "native/upstream.json").write_bytes(b'{"pin":"fixture"}\n')
            (repo / "control.txt").write_bytes(b"conversion control\n")
            run("git", "add", "--", ".gitattributes", RESOURCE_PATH + "/LICENSE",
                "native/upstream.json", "control.txt", cwd=repo)
            run("git", "commit", "--quiet", "-m", "Checkout bytes", cwd=repo)
            checkout = root / "crlf"
            run("git", "clone", "--quiet", "-c", "core.autocrlf=true", "-c", "core.eol=crlf", repo, checkout)
            self.assertEqual((checkout / RESOURCE_PATH / "LICENSE").read_bytes(), resource.read_bytes())
            self.assertEqual((checkout / "native/upstream.json").read_bytes(), (repo / "native/upstream.json").read_bytes())
            self.assertEqual((checkout / "control.txt").read_bytes(), b"conversion control\r\n")

    def test_committed_verification_rejects_untracked_or_modified_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, _ = self.make_repository(Path(temporary))
            resource = repo / RESOURCE_PATH
            (resource / "old.bundle").unlink()
            pin, _ = fixture(resource)
            (repo / "native").mkdir()
            (repo / "native/upstream.json").write_text(json.dumps(pin))
            paths = [str(path.relative_to(repo)) for path in repo.rglob("*") if path.is_file() and ".git" not in path.parts]
            run("git", "add", "--", *paths, RESOURCE_PATH + "/old.bundle", cwd=repo)
            run("git", "commit", "--quiet", "-m", "Complete resource fixture", cwd=repo)
            with patch("update.audit_binary"), patch("update.smoke"):
                verify_committed(repo)
                (resource / "extra").write_text("extra")
                rehash(resource)
                with self.assertRaisesRegex(RuntimeError, "COMMITTED"):
                    verify_committed(repo)

    def test_invalid_archive_never_replaces_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, expected = self.make_repository(Path(temporary))
            archive = Path(temporary) / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                member = tarfile.TarInfo("distribution/huge")
                member.type = tarfile.SYMTYPE
                member.linkname = "/outside"
                package.addfile(member)
            (repo / "native").mkdir()
            (repo / "native/upstream.json").write_text("{}")
            with patch("update.freshness"), patch("update.run", return_value=""):
                with self.assertRaisesRegex(RuntimeError, "Unsafe or oversized"):
                    adopt(archive, expected, repo=repo)
            self.assertEqual((repo / RESOURCE_PATH / "old.bundle").read_text(), "old")

    def test_complete_adoption_validates_before_replacement_and_pushes_one_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, _ = self.make_repository(root)
            distribution = root / "distribution"
            pin, info = fixture(distribution)
            (repo / "native").mkdir()
            (repo / "native/upstream.json").write_text(json.dumps(pin))
            run("git", "add", "--", "native/upstream.json", cwd=repo)
            run("git", "commit", "--quiet", "-m", "Pin upstream", cwd=repo)
            run("git", "push", "--quiet", "origin", "HEAD:refs/heads/main", cwd=repo)
            expected = run("git", "rev-parse", "HEAD", cwd=repo, capture=True)
            archive = root / "native.tar.gz"
            # An artifact from a different packaging commit must leave the legacy target intact.
            with tarfile.open(archive, "w:gz") as package:
                package.add(distribution, arcname="distribution")
            with patch("update.audit_binary"), patch("update.smoke"):
                with self.assertRaisesRegex(RuntimeError, "this dispatched packaging commit"):
                    adopt(archive, expected, repo=repo)
            self.assertTrue((repo / RESOURCE_PATH / "old.bundle").is_file())
            info["packaging_revision"] = expected
            info["packaging_files"] = {"native/upstream.json": digest(repo / "native/upstream.json")}
            # The adoption fixture includes the packaging entry point just as real builds do.
            (repo / "native/build.py").write_text("packaging fixture\n")
            run("git", "add", "--", "native/build.py", cwd=repo)
            run("git", "commit", "--quiet", "-m", "Packaging entry point", cwd=repo)
            run("git", "push", "--quiet", "origin", "HEAD:refs/heads/main", cwd=repo)
            expected = run("git", "rev-parse", "HEAD", cwd=repo, capture=True)
            info["packaging_revision"] = expected
            info["packaging_files"]["native/build.py"] = digest(repo / "native/build.py")
            (distribution / "BUILD_INFO.json").write_text(json.dumps(info))
            rehash(distribution)
            with tarfile.open(archive, "w:gz") as package:
                package.add(distribution, arcname="distribution")
            with patch("update.audit_binary"), patch("update.smoke"), patch("install.smoke"):
                adopt(archive, expected, repo=repo)
                verify_committed(repo)
            self.assertFalse((repo / RESOURCE_PATH / "old.bundle").exists())
            self.assertEqual(inventory(repo / RESOURCE_PATH), inventory(distribution))
            self.assertEqual(run("git", "rev-parse", "HEAD^", cwd=repo, capture=True), expected)

    def test_workflow_trust_and_dispatch_boundaries(self):
        workflow = (ROOT / ".github/workflows/native-update.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertIn("if: inputs.commit_update && github.ref == 'refs/heads/main'", workflow)
        self.assertIn("if: inputs.commit_update && inputs.publish_component", workflow)
        self.assertEqual(workflow.count("contents: write"), 1)
        self.assertEqual(workflow.count("actions: write"), 1)
        self.assertIn("group: swama-component-publish", workflow)
        self.assertIn('= "$EXPECTED_REVISION"', workflow)
        self.assertNotIn("--force", workflow)
        publish = (ROOT / ".github/workflows/publish.yml").read_text()
        self.assertNotIn("needs: native", publish)
        self.assertNotIn("uses: ./.github/workflows/native-build.yml", publish)
        self.assertNotIn("actions/download-artifact", publish)
        self.assertNotIn("native/install.py", publish)
        self.assertNotIn("write-all", publish)


if __name__ == "__main__":
    unittest.main()
