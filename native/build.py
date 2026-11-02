#!/usr/bin/env python3
"""Build and package the upstream Apple Silicon CLI without modifying 4D resources."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=None, capture=False, env=None):
    result = subprocess.run(
        [str(arg) for arg in args], cwd=cwd, env=env, check=True,
        text=True, stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else None


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(directory):
    return {
        path.relative_to(directory).as_posix(): digest(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    }


def audit_binary(binary):
    architectures = run("lipo", "-archs", binary, capture=True).split()
    if "arm64" not in architectures or (binary.name == "swama" and architectures != ["arm64"]):
        raise RuntimeError(f"Expected arm64 executable: {binary}")
    imports = run("otool", "-arch", "arm64", "-L", binary, capture=True)
    for line in imports.splitlines()[1:]:
        dependency = line.strip().split(" (", 1)[0]
        if dependency.startswith(("/usr/lib/", "/System/Library/")):
            continue
        prefix, _, relative = dependency.partition("/")
        if prefix in ("@rpath", "@loader_path", "@executable_path"):
            resolved = (binary.parent / relative).resolve()
            if resolved.parent == binary.parent.resolve() and resolved.is_file():
                continue
        raise RuntimeError(f"Unbundled runtime dependency: {dependency}")
    load_commands = run("otool", "-arch", "arm64", "-l", binary, capture=True)
    minimums = re.findall(
        r"cmd LC_BUILD_VERSION\s+cmdsize \d+\s+platform 1\s+minos (\d+\.\d+(?:\.\d+)?)",
        load_commands,
    )
    if len(minimums) != 1 or tuple(map(int, minimums[0].split(".")[:2])) > (15, 4):
        raise RuntimeError(f"Mach-O does not target macOS 15.4 or earlier: {binary}")
    rpaths = re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.+) \(offset", load_commands)
    if any(path not in ("/usr/lib/swift", "@loader_path", "@executable_path") for path in rpaths):
        raise RuntimeError(f"Unexpected runtime search path: {rpaths}")
    run("codesign", "--verify", "--strict", binary)
    return {"imports": imports, "minimum_macos": minimums[0]}


def bundle_swift_runtime(destination, license_pin):
    binary = destination / "swama"
    arguments = ["--scan-executable", binary, "--platform", "macosx"]
    sources = run("xcrun", "swift-stdlib-tool", "--print", *arguments, capture=True).splitlines()
    run("xcrun", "swift-stdlib-tool", "--copy", *arguments, "--destination", destination)
    libraries = {}
    for source in sources:
        source = Path(source)
        copied = destination / source.name
        if source.suffix != ".dylib" or not copied.is_file() or digest(source) != digest(copied):
            raise RuntimeError(f"Swift runtime was not copied unmodified: {source}")
        libraries[source.name] = {"source": str(source), "sha256": digest(copied)}
    if libraries:
        with urllib.request.urlopen(license_pin["url"], timeout=60) as response:
            license_text = response.read()
        if hashlib.sha256(license_text).hexdigest() != license_pin["sha256"]:
            raise RuntimeError("Swift runtime license checksum mismatch")
        license_file = destination / "licenses/swift/LICENSE.txt"
        license_file.parent.mkdir(parents=True, exist_ok=True)
        license_file.write_bytes(license_text)
    load_commands = run("otool", "-arch", "arm64", "-l", binary, capture=True)
    rpaths = re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.+) \(offset", load_commands)
    for path in rpaths:
        if path not in ("/usr/lib/swift", "@loader_path", "@executable_path"):
            run("install_name_tool", "-delete_rpath", path, binary)
    run("codesign", "--force", "--sign", "-", binary)
    return {"libraries": libraries, "license": license_pin}


def copy_products(bin_path, destination):
    if destination.exists():
        raise RuntimeError(f"Output already exists; choose a fresh directory: {destination}")
    destination.mkdir(parents=True)
    shutil.copy2(bin_path / "swama", destination / "swama")
    bundles = sorted(bin_path.glob("*.bundle"))
    if not bundles:
        raise RuntimeError("SwiftPM resource bundles are missing")
    for bundle in bundles:
        shutil.copytree(bundle, destination / bundle.name)
    metal = destination / "swama_SwamaCore.bundle/mlx-swift_Cmlx.bundle/Contents/Resources/default.metallib"
    if not metal.is_file() or metal.stat().st_size == 0:
        raise RuntimeError("Upstream SwamaCore Metal resource is missing")


def build_metal(checkouts, work, destination):
    mlx = checkouts / "mlx-swift"
    sources = sorted((mlx / "Source/Cmlx/mlx-generated/metal").rglob("*.metal"))
    if not sources:
        raise RuntimeError("Resolved MLX checkout has no generated Metal sources")
    air_dir = work / "metal"
    air_dir.mkdir(exist_ok=True)
    air_files = []
    for index, source in enumerate(sources):
        air = air_dir / f"{index:04d}.air"
        run(
            "xcrun", "-sdk", "macosx", "metal", "-c",
            "-target", "air64-apple-macos14.0",
            "-fmetal-math-mode=fast", "-fmetal-math-fp32-functions=fast",
            source, "-o", air,
        )
        air_files.append(air)
    run("xcrun", "-sdk", "macosx", "metallib", *air_files, "-o", destination / "mlx.metallib")
    return {
        "revision": run("git", "rev-parse", "HEAD", cwd=mlx, capture=True),
        "compiler": run("xcrun", "-sdk", "macosx", "metal", "--version", capture=True),
        "target": "air64-apple-macos14.0",
        "sources": {str(p.relative_to(mlx)): digest(p) for p in sources},
    }


def copy_licenses(source, checkouts, destination):
    shutil.copy2(source / "LICENSE", destination / "LICENSE")
    for checkout in sorted(checkouts.iterdir()):
        if not checkout.is_dir():
            continue
        found = False
        for path in sorted(checkout.rglob("*")):
            if ".git" in path.parts or not path.is_file() or path.is_symlink():
                continue
            if path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                target = destination / "licenses" / checkout.name / path.relative_to(checkout)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                found = True
        if not found:
            raise RuntimeError(f"No dependency license found: {checkout.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-ref", default="", help="Upstream tag, branch or SHA; default: checked-in pin")
    parser.add_argument("--work-dir", type=Path, default=ROOT / ".native-build")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/native")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("Upstream supports Apple Silicon macOS only")
    pin = json.loads((ROOT / "native/upstream.json").read_text())
    ref = args.upstream_ref or pin["revision"]
    if ref.startswith("-") or any(c.isspace() for c in ref):
        parser.error("Invalid upstream ref")
    work = args.work_dir.resolve()
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Output already exists; choose a fresh directory: {output}")
    work.mkdir(parents=True, exist_ok=True)
    source = work / "upstream"
    if not source.exists():
        run("git", "clone", "--no-checkout", pin["repository"], source)
    if run("git", "remote", "get-url", "origin", cwd=source, capture=True) != pin["repository"]:
        raise RuntimeError("Build checkout origin does not match the pinned upstream repository")
    if run("git", "status", "--porcelain", "--untracked-files=no", cwd=source, capture=True):
        raise RuntimeError("Build checkout has tracked modifications")
    run("git", "fetch", "--depth", "1", "origin", ref, cwd=source)
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=source)
    revision = run("git", "rev-parse", "HEAD", cwd=source, capture=True)
    version = (source / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", version):
        raise RuntimeError(f"Invalid upstream version: {version}")
    if not args.upstream_ref and version != pin["version"]:
        raise RuntimeError("Pinned version does not match upstream VERSION")
    package = source / "swama"
    lock = package / "Package.resolved"
    lock_hash = digest(lock)
    environment = dict(os.environ, MACOSX_DEPLOYMENT_TARGET=pin["minimum_macos"])
    build_args = [
        "xcrun", "swift", "build", "--package-path", package,
        "--force-resolved-versions", "-c", "release",
    ]
    run(*build_args, "--product", "swama", "-j", "4", env=environment)
    if digest(lock) != lock_hash:
        raise RuntimeError("SwiftPM changed the upstream dependency lockfile")
    bin_path = Path(run(*build_args, "--show-bin-path", capture=True, env=environment))
    name = f"swama-{version}-{revision[:12]}-macos-arm64"
    destination = output / name
    copy_products(bin_path, destination)
    checkouts = package / ".build/checkouts"
    metal = build_metal(checkouts, work, destination)
    runtime = bundle_swift_runtime(destination, pin["swift_runtime_license"])
    audit = audit_binary(destination / "swama")
    runtime_audits = {
        library.name: audit_binary(library) for library in sorted(destination.glob("*.dylib"))
    }
    copy_licenses(source, checkouts, destination)
    shutil.copy2(lock, destination / "Package.resolved")
    info = {
        "repository": pin["repository"], "requested_ref": ref,
        "revision": revision, "version": version, "platform": "macos-arm64",
        "minimum_macos": audit["minimum_macos"], "configuration": "release",
        "signing": "CLI ad-hoc signed after rpath cleanup; Swift runtime copied unmodified from Xcode; distribution not Developer ID signed or notarized",
        "packaging_revision": run("git", "rev-parse", "HEAD", cwd=ROOT, capture=True),
        "packaging_dirty": bool(run("git", "status", "--porcelain", cwd=ROOT, capture=True)),
        "packaging_files": {
            str(path.relative_to(ROOT)): digest(path)
            for path in sorted((ROOT / "native").glob("*")) if path.is_file()
        },
        "swift": run("xcrun", "swift", "--version", capture=True),
        "xcode": run("xcodebuild", "-version", capture=True),
        "sdk": run("xcrun", "--sdk", "macosx", "--show-sdk-version", capture=True),
        "package_resolved_sha256": lock_hash, "metal": metal, "binary": audit,
        "swift_runtime": runtime, "swift_runtime_audits": runtime_audits,
        "dependencies": json.loads(lock.read_text())["pins"],
    }
    (destination / "BUILD_INFO.json").write_text(json.dumps(info, indent=2) + "\n")
    (destination / "SHA256SUMS").write_text("".join(
        f"{checksum}  {path}\n" for path, checksum in inventory(destination).items()
    ))
    archive = output / f"{name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(destination, arcname=name)
    (output / f"{archive.name}.sha256").write_text(f"{digest(archive)}  {archive.name}\n")
    # Validate the delivered archive, not the original build directory or its resource fallbacks.
    extracted = output / "smoke"
    with tarfile.open(archive) as tar:
        tar.extractall(extracted, filter="data")
    run("python3", ROOT / "native/smoke.py", extracted / name)
    shutil.rmtree(extracted)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write(f"release_tag=native-v{version}-{revision[:12]}\n")
            stream.write(f"revision={revision}\n")
    print(f"Packaged {archive}")


if __name__ == "__main__":
    main()
