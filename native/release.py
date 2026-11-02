#!/usr/bin/env python3
"""Fail-closed signing, notarization and publication of the 4D component."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

from component import validate_compile_result
from smoke import smoke


OUTPUT = Path("dist/component")
MACHO_MAGIC = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}


def run(*arguments):
    # Never include arguments in exceptions: notarytool receives credentials.
    result = subprocess.run(
        [str(argument) for argument in arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        details = "notarytool submission/authentication failed (credentials redacted)" if "notarytool" in arguments else result.stderr.strip()
        raise RuntimeError(f"{Path(arguments[0]).name} failed (exit {result.returncode}): {details}")
    return result.stdout + result.stderr


def required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required release credential/configuration is missing: {name}")
    return value


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def inventory(root, excluded="SHA256SUMS"):
    entries = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Unexpected symlink in component: {path}")
        if path.is_file() and path != root / excluded:
            entries[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return entries


def write_inventory(root):
    (root / "SHA256SUMS").write_text("".join(
        f"{checksum}  {path}\n" for path, checksum in inventory(root).items()
    ))


def verify_inventory(root, filename="SHA256SUMS"):
    entries = [line.split("  ", 1) for line in (root / filename).read_text().splitlines()]
    expected = {path: checksum for checksum, path in entries}
    if len(entries) != len(expected) or expected != inventory(root, filename):
        raise RuntimeError(f"Incomplete or mismatched final-byte inventory: {root / filename}")


def code_paths(product):
    code = []
    containers = []
    for path in product.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                if stream.read(4) in MACHO_MAGIC:
                    code.append(path)
        elif path.suffix in {".app", ".framework", ".bundle", ".plugin", ".xpc"}:
            # Flat SwiftPM resource-only bundles are not code-signable bundles.
            if any(path.glob("Contents/MacOS/*")) or (path / "Versions").is_dir():
                containers.append(path)
    if product / "Resources/bin/macOS/swama" not in code:
        raise RuntimeError("Component does not contain its native Mach-O CLI")
    return sorted(code) + sorted(containers, key=lambda path: len(path.parts), reverse=True)


def validate_signature(details, team, hardened=True):
    if (
        f"TeamIdentifier={team}\n" not in details
        or "Authority=Developer ID Application:" not in details
        or "Timestamp=" not in details
        or (hardened and not re.search(r"flags=.*\bruntime\b", details))
    ):
        raise RuntimeError("Code lacks expected Developer ID team, secure timestamp or hardened runtime")


def verify_code(product, team):
    report = []
    for path in code_paths(product):
        run("codesign", "--verify", "--strict", "--all-architectures", path)
        details = run("codesign", "--display", "--verbose=4", path)
        validate_signature(details, team)
        report.append({
            "path": path.relative_to(product).as_posix(),
            "cdhashes": re.findall(r"^CDHash=(.+)$", details, re.MULTILINE),
            "expected_team_verified": True,
            "developer_id_timestamped_hardened_runtime": True,
        })
    return report


def validate_notarization(result):
    if result.get("status") != "Accepted":
        raise RuntimeError(f"Notarization was not Accepted: {result.get('status')}")
    uuid.UUID(result["id"])


def next_version(current, mode):
    if not re.fullmatch(r"\d+\.\d+\.\d+", current):
        raise RuntimeError(f"Unsupported component version: {current}")
    major, minor, patch = map(int, current.split("."))
    if mode == "major":
        return f"{major + 1}.0.0"
    if mode == "minor":
        return f"{major}.{minor + 1}.0"
    if mode == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise RuntimeError(f"Unsupported version mode: {mode}")


def assert_unused(version):
    tags = run("git", "ls-remote", "--tags", "origin", f"refs/tags/{version}", f"refs/tags/v{version}")
    releases = json.loads(run("gh", "release", "list", "--limit", "1000", "--json", "tagName"))
    if tags.strip() or any(release["tagName"] in {version, f"v{version}"} for release in releases):
        raise RuntimeError(f"Refusing to overwrite an existing release or tag: {version}")


def prepare_version(mode):
    if run("git", "status", "--porcelain", "--untracked-files=no").strip():
        raise RuntimeError("Version preparation requires a clean tracked working tree")
    current = json.loads(Path("package.json").read_text())["version"]
    version = next_version(current, mode)
    assert_unused(version)
    run("npm", "version", version, "--no-git-tag-version")
    run("git", "add", "package.json")
    run(
        "git", "-c", "user.name=GitHub Action", "-c", "user.email=action@github.com",
        "commit", "-m", f"Release component {version}\n\nCo-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>",
    )
    with Path(required("GITHUB_OUTPUT")).open("a") as stream:
        stream.write(f"version={version}\n")
    print(f"Prepared {version}; branch/tag push is deferred until signed artifacts pass verification")


def verify_product(product, team):
    verify_inventory(product)
    report = verify_code(product, team)
    smoke(product / "Resources/bin/macOS")
    return report


def package(product, version):
    product = product.resolve()
    identity = required("SIGN_IDENTITY")
    team = required("NOTARY_TEAM")
    keychain = required("SIGN_KEYCHAIN")
    credentials = [
        "--apple-id", required("NOTARY_APPLE_ID"),
        "--team-id", team, "--password", required("NOTARY_PASSWORD"),
    ]
    if json.loads(Path("package.json").read_text())["version"] != version:
        raise RuntimeError("Release version does not match package.json")
    native = product / "Resources/bin/macOS"
    verify_inventory(native, "SOURCE_BUILD_SHA256SUMS")
    validate_compile_result(json.loads((product / "Resources/4D_COMPILE_RESULT.json").read_text()))
    OUTPUT.mkdir(parents=True, exist_ok=False)
    for path in code_paths(product):
        run("codesign", "--force", "--options", "runtime", "--timestamp",
            "--sign", identity, "--keychain", keychain, path)
    signing = verify_code(product, team)
    write_inventory(native)
    write_json(product / "Resources/RELEASE_INFO.json", {
        "component_version": version,
        "component_revision": run("git", "rev-parse", "HEAD").strip(),
        "workflow_revision": required("GITHUB_SHA"),
        "run_url": f"https://github.com/{required('GITHUB_REPOSITORY')}/actions/runs/{required('GITHUB_RUN_ID')}",
        "native_input": "bin/macOS/BUILD_INFO.json and SOURCE_BUILD_SHA256SUMS describe pre-sign bytes",
        "signed_inventory": "../SHA256SUMS covers final component bytes, including nested inventories",
        "notarization": "See release NOTARIZATION.json for the subsequently notarized disk image",
    })
    write_inventory(product)
    verify_product(product, team)
    dmg = (OUTPUT / "swama.dmg").resolve()
    archive = (OUTPUT / "swama.zip").resolve()
    with tempfile.TemporaryDirectory(prefix="swama-release-") as temporary:
        staging = Path(temporary) / "image"
        staging.mkdir()
        run("ditto", product, staging / product.name)
        run("hdiutil", "create", "-format", "UDZO", "-volname", "swama", "-srcfolder", staging, dmg)
        run("codesign", "--sign", identity, "--keychain", keychain, "--timestamp", dmg)
        result = json.loads(run("xcrun", "notarytool", "submit", dmg, *credentials,
                                "--wait", "--timeout", "30m", "--output-format", "json"))
        write_json(OUTPUT / "NOTARIZATION.json", {key: result.get(key) for key in ("id", "status")})
        validate_notarization(result)
        run("xcrun", "stapler", "staple", dmg)
        run("xcrun", "stapler", "validate", dmg)
        run("codesign", "--verify", "--strict", dmg)
        validate_signature(run("codesign", "--display", "--verbose=4", dmg), team, hardened=False)
        run("spctl", "--assess", "--type", "open", "--context", "context:primary-signature", dmg)
        mount = Path(temporary) / "mounted"
        run("hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mount, dmg)
        try:
            verify_product(mount / product.name, team)
            run("ditto", "-c", "-k", "--keepParent", mount / product.name, archive)
        finally:
            run("hdiutil", "detach", mount)
        extracted = Path(temporary) / "unzipped"
        run("ditto", "-x", "-k", archive, extracted)
        verify_product(extracted / product.name, team)
    write_json(OUTPUT / "SIGNING_REPORT.json", {"component_version": version, "code": signing})
    write_json(OUTPUT / "NOTARIZATION.json", {
        "id": result["id"], "status": result["status"],
        "stapler_validation": "passed", "gatekeeper_assessment": "accepted",
        "dmg_and_zip_nested_signature_and_final_byte_verification": "passed",
    })
    write_inventory(OUTPUT)
    print(f"PASS: Developer ID signatures, Accepted notarization {result['id']}, staple, Gatekeeper, DMG/ZIP final bytes and CLI/server smoke")


def publish(version):
    verify_inventory(OUTPUT)
    notarization = json.loads((OUTPUT / "NOTARIZATION.json").read_text())
    validate_notarization(notarization)
    for field, expected in (
        ("stapler_validation", "passed"), ("gatekeeper_assessment", "accepted"),
        ("dmg_and_zip_nested_signature_and_final_byte_verification", "passed"),
    ):
        if notarization.get(field) != expected:
            raise RuntimeError(f"Missing completed publication gate: {field}")
    assert_unused(version)
    if json.loads(Path("package.json").read_text())["version"] != version:
        raise RuntimeError("Published tag must match the prepared component version")
    branch = required("GITHUB_REF_NAME")
    run("git", "-c", "user.name=GitHub Action", "-c", "user.email=action@github.com",
        "tag", "-a", version, "-m", f"Signed and notarized component {version}")
    # Atomic, fast-forward-only push: never overwrite a release tag or concurrent work.
    run("git", "push", "--atomic", "origin", f"HEAD:refs/heads/{branch}", f"refs/tags/{version}")
    files = sorted(path for path in OUTPUT.iterdir() if path.is_file())
    notes = OUTPUT.parent / "component-release-notes.md"
    notes.write_text(
        f"4D component {version}, containing the source-built Apple Silicon Swama CLI.\n\n"
        f"Developer ID signed; Apple notarization **Accepted** (`{notarization['id']}`); "
        "DMG ticket stapled and validated. Both DMG and ZIP contents passed nested signature, "
        "final-byte checksum and CLI/HTTP smoke checks. Install the complete `swama.4dbase` folder.\n\n"
        "Requires Apple Silicon and macOS 15.4+. Model weights are not included. "
        "See `Resources/RELEASE_INFO.json` and `Resources/bin/macOS/BUILD_INFO.json` for provenance. "
        "Verify downloaded assets against `SHA256SUMS`; details accompany the release in "
        "`NOTARIZATION.json` and `SIGNING_REPORT.json`. The ZIP preserves the same signed component; "
        "the stapled offline notarization ticket is attached to the DMG.\n"
    )
    run("gh", "release", "create", version, "--verify-tag", "--draft",
        "--title", version, "--notes-file", notes, *files)
    with tempfile.TemporaryDirectory(prefix="swama-upload-check-") as temporary:
        downloaded = Path(temporary)
        run("gh", "release", "download", version, "--dir", downloaded)
        if inventory(downloaded, excluded="") != inventory(OUTPUT, excluded=""):
            raise RuntimeError("Uploaded release assets differ from verified final bytes; release remains draft")
    run("gh", "release", "edit", version, "--draft=false", "--latest")
    print(f"Published https://github.com/{required('GITHUB_REPOSITORY')}/releases/tag/{version}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("version")
    prepare.add_argument("--mode", choices=["patch", "minor", "major"], required=True)
    signing = commands.add_parser("package")
    signing.add_argument("product", type=Path)
    signing.add_argument("version")
    publishing = commands.add_parser("publish")
    publishing.add_argument("version")
    args = parser.parse_args()
    if args.command == "version":
        prepare_version(args.mode)
    elif args.command == "package":
        package(args.product, args.version)
    else:
        publish(args.version)
