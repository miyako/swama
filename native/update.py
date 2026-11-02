#!/usr/bin/env python3
"""Verify committed native resources or adopt a complete pinned source build."""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile

from build import ROOT, audit_binary, digest, run
from install import install
from smoke import smoke, verify

RESOURCE_PATH = "swama/Resources/bin/macOS"
GIT_FILE_LIMIT = 100 * 1024 * 1024
REQUIRED_RESOURCES = (
    "swama", "mlx.metallib",
    "swama_SwamaCore.bundle/mlx-swift_Cmlx.bundle/Contents/Resources/default.metallib",
    "swama_SwamaCore.bundle/mlx-swift_Cmlx.bundle/Contents/Info.plist",
    "swift-nio_NIOPosix.bundle/PrivacyInfo.xcprivacy",
    "swift-crypto_Crypto.bundle/PrivacyInfo.xcprivacy",
    "swift-transformers_Hub.bundle/gpt2_tokenizer_config.json",
    "swift-transformers_Hub.bundle/t5_tokenizer_config.json",
    "LICENSE", "Package.resolved", "BUILD_INFO.json", "SHA256SUMS",
)


def check_sizes(directory):
    sizes = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Unexpected resource symlink: {path}")
        if path.is_file():
            size = path.stat().st_size
            if size >= GIT_FILE_LIMIT:
                raise RuntimeError(f"GitHub 100 MiB limit: {path} is {size} bytes; consult before using LFS or larger artifacts")
            sizes[path.relative_to(directory).as_posix()] = size
    return sizes


def validate_distribution(directory, pin):
    sizes = check_sizes(directory)
    if any(not sizes.get(path) for path in REQUIRED_RESOURCES):
        missing = [path for path in REQUIRED_RESOURCES if not sizes.get(path)]
        raise RuntimeError(f"Missing native provenance/resources: {missing}; run Update native resources")
    info = verify(directory)
    for field in ("repository", "revision", "version", "minimum_macos"):
        if info.get(field) != pin[field]:
            raise RuntimeError(f"Native {field} differs from native/upstream.json; refresh the complete pinned distribution")
    if info.get("platform") != "macos-arm64" or info.get("configuration") != "release":
        raise RuntimeError("Expected the complete macOS arm64 release target")
    if info.get("packaging_dirty") is not False or not re.fullmatch(r"[0-9a-f]{40}", info.get("packaging_revision", "")):
        raise RuntimeError("Native build must identify a clean packaging commit")
    for field in ("swift", "xcode", "sdk", "packaging_files", "binary", "metal"):
        if not info.get(field):
            raise RuntimeError(f"Missing build provenance: {field}")
    packaging_files = info["packaging_files"]
    if "native/build.py" not in packaging_files or any(
        not path.startswith("native/") or ".." in PurePosixPath(path).parts
        or "\\" in path or not re.fullmatch(r"[0-9a-f]{64}", checksum)
        for path, checksum in packaging_files.items()
    ):
        raise RuntimeError("Invalid packaging source-file provenance")
    if digest(directory / "Package.resolved") != info.get("package_resolved_sha256"):
        raise RuntimeError("Dependency lockfile does not match build provenance")
    dependencies = json.loads((directory / "Package.resolved").read_text())["pins"]
    if not dependencies or dependencies != info.get("dependencies"):
        raise RuntimeError("Incomplete dependency provenance")
    if any(not re.fullmatch(r"[0-9a-f]{40}", dependency["state"]["revision"]) for dependency in dependencies):
        raise RuntimeError("Dependencies must identify immutable source commits")
    metal = info["metal"]
    mlx = next((dependency for dependency in dependencies if dependency["identity"] == "mlx-swift"), None)
    if (
        mlx is None or metal.get("revision") != mlx["state"]["revision"]
        or not metal.get("compiler") or metal.get("target") != "air64-apple-macos14.0"
        or not metal.get("sources")
        or any(not re.fullmatch(r"[0-9a-f]{64}", checksum) for checksum in metal["sources"].values())
    ):
        raise RuntimeError("Incomplete or mismatched Metal source provenance")
    licensed = {path.name.lower(): path for path in (directory / "licenses").iterdir() if path.is_dir()}
    for dependency in dependencies:
        name = dependency["identity"]
        if name.lower() not in licensed or not any(
            path.is_file() and path.stat().st_size for path in licensed[name.lower()].rglob("*")
        ):
            raise RuntimeError(f"Missing dependency license: {name}")
    runtime = info.get("swift_runtime", {})
    libraries = runtime.get("libraries", {})
    if set(libraries) != {path.name for path in directory.glob("*.dylib")}:
        raise RuntimeError("Swift runtime set differs from build provenance")
    if libraries:
        if runtime.get("license") != pin["swift_runtime_license"] or digest(directory / "licenses/swift/LICENSE.txt") != pin["swift_runtime_license"]["sha256"]:
            raise RuntimeError("Swift redistributable runtime license differs from pin")
    for name, metadata in libraries.items():
        if PurePosixPath(name).name != name or digest(directory / name) != metadata["sha256"]:
            raise RuntimeError(f"Swift runtime was changed after vendor-signed copy: {name}")
        run("codesign", "--verify", "--strict", "-R=anchor apple", directory / name)
        audit_binary(directory / name)
    audit_binary(directory / "swama")
    smoke(directory)
    return info, sizes


def verify_committed(repo=ROOT):
    directory = repo / RESOURCE_PATH
    pin = json.loads((repo / "native/upstream.json").read_text())
    info, sizes = validate_distribution(directory, pin)
    tracked = set(run("git", "ls-files", "--", RESOURCE_PATH, cwd=repo, capture=True).splitlines())
    expected = {f"{RESOURCE_PATH}/{path}" for path in sizes}
    if tracked != expected or run("git", "status", "--porcelain", "--untracked-files=all", "--", RESOURCE_PATH, cwd=repo, capture=True):
        raise RuntimeError("Publish requires exactly the clean COMMITTED resource set; commit a complete native update first")
    return info, sizes


def freshness(expected, branch="main", repo=ROOT):
    if not re.fullmatch(r"[0-9a-f]{40}", expected) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch):
        raise RuntimeError("Expected a full base commit and a valid default branch")
    run("git", "fetch", "--no-tags", "origin", f"refs/heads/{branch}", cwd=repo)
    remote = run("git", "rev-parse", "FETCH_HEAD", cwd=repo, capture=True)
    head = run("git", "rev-parse", "HEAD", cwd=repo, capture=True)
    if remote != expected or head != expected:
        raise RuntimeError("Default branch advanced or checkout differs from dispatch SHA; rerun from current main (no rebase/force push)")


def adopt(archive, expected, branch="main", repo=ROOT):
    freshness(expected, branch, repo)
    if run("git", "status", "--porcelain", "--untracked-files=all", cwd=repo, capture=True):
        raise RuntimeError("Native update requires a clean working tree and index")
    pin = json.loads((repo / "native/upstream.json").read_text())
    with tempfile.TemporaryDirectory(prefix="swama-update-") as temporary:
        root = Path(temporary)
        with tarfile.open(archive) as package:
            for entry in package.getmembers():
                path = PurePosixPath(entry.name)
                if (
                    not (entry.isfile() or entry.isdir()) or entry.size >= GIT_FILE_LIMIT
                    or path.is_absolute() or ".." in path.parts or "\\" in entry.name
                ):
                    raise RuntimeError(f"Unsafe or oversized native archive member: {entry.name}")
            package.extractall(root, filter="data")
        entries = list(root.iterdir())
        if len(entries) != 1 or not entries[0].is_dir():
            raise RuntimeError("Expected one complete native distribution")
        info, sizes = validate_distribution(entries[0], pin)
        if info["packaging_revision"] != expected:
            raise RuntimeError("Native artifact was not built by this dispatched packaging commit")
        packaging_files = {
            path.relative_to(repo).as_posix(): digest(path)
            for path in sorted((repo / "native").glob("*")) if path.is_file()
        }
        if info["packaging_files"] != packaging_files:
            raise RuntimeError("Native artifact packaging files differ from this dispatched checkout")
    # No resource changes occur before the entire target passes validation and size gates.
    install(archive, repo / RESOURCE_PATH)
    commit_resources(expected, branch, repo)
    return info, sizes


def commit_resources(expected, branch="main", repo=ROOT):
    freshness(expected, branch, repo)
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all"], cwd=repo,
    )
    paths = [entry[3:].decode() for entry in status.split(b"\0") if entry]
    if any(not path.startswith(RESOURCE_PATH + "/") for path in paths):
        raise RuntimeError("Refusing to commit changes outside the exact native resource target")
    check_sizes(repo / RESOURCE_PATH)
    if not paths:
        return
    run("git", "add", "--", *paths, cwd=repo)
    run("git", "-c", "user.name=github-actions[bot]",
        "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit", "-m", "Update complete pinned Swama native resources\n\nCo-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>", cwd=repo)
    # Ordinary fast-forward push still rejects a race after the explicit freshness check.
    run("git", "push", "origin", f"HEAD:refs/heads/{branch}", cwd=repo)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("verify", "prepare-component"):
        commands.add_parser(command)
    fresh = commands.add_parser("freshness")
    fresh.add_argument("--expected", required=True)
    update = commands.add_parser("adopt")
    update.add_argument("archive", type=Path)
    update.add_argument("--expected", required=True)
    for command in (fresh, update):
        command.add_argument("--branch", default="main")
    args = parser.parse_args()
    if args.command == "freshness":
        freshness(args.expected, args.branch)
    elif args.command == "adopt":
        if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or os.environ.get("GITHUB_REF") != f"refs/heads/{args.branch}" or os.environ.get("GITHUB_SHA") != args.expected:
            parser.error("Git resource updates require a trusted default-branch workflow_dispatch")
        adopt(args.archive, args.expected, args.branch)
        sha = run("git", "rev-parse", "HEAD", cwd=ROOT, capture=True)
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            output.write(f"revision={sha}\n")
    else:
        info, sizes = verify_committed()
        if args.command == "prepare-component":
            directory = ROOT / RESOURCE_PATH
            (directory / "SHA256SUMS").rename(directory / "SOURCE_BUILD_SHA256SUMS")
        print(f"PASS: committed native {info['revision']}, {len(sizes)} files, {sum(sizes.values())} bytes; largest {max(sizes.values())} bytes")


if __name__ == "__main__":
    main()
