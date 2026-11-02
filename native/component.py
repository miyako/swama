#!/usr/bin/env python3
"""Install pinned 4D build dependencies and require a clean structured compile result."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import zipfile

from build import ROOT, digest, run


def download(url, destination, expected):
    if not destination.exists():
        run("curl", "--fail", "--location", "--retry", "3", "--silent", "--show-error", url, "--output", destination)
    if digest(destination) != expected:
        raise RuntimeError(f"Dependency checksum mismatch: {destination}")


def validate_compile_result(result):
    if result.get("success") is not True or not isinstance(result.get("errors"), list) or result["errors"]:
        raise RuntimeError(f"4D compilation did not succeed without diagnostics:\n{json.dumps(result, indent=2)}")


def prepare_components(project, pins, work):
    declarations = json.loads((project.parent / "Sources/dependencies.json").read_text())["dependencies"]
    if set(declarations) != set(pins):
        raise RuntimeError("4D dependency declarations and native/components.json differ")
    destination = project.parent.parent / "Components"
    destination.mkdir(exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    compiled = []
    for name, pin in pins.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise RuntimeError(f"Invalid component name: {name}")
        declaration = declarations[name]
        if declaration["github"] != pin["repository"] or declaration["version"] not in ("latest", pin["version"]):
            raise RuntimeError(f"4D dependency pin does not satisfy its declaration: {name}")
        archive = work / f"{name}-{pin['version']}.zip"
        download(pin["url"], archive, pin["sha256"])
        target = destination / f"{name}.4dbase"
        with zipfile.ZipFile(archive) as package:
            for entry in package.infolist():
                path = (destination / entry.filename).resolve()
                if not path.is_relative_to(destination.resolve()) or stat.S_ISLNK(entry.external_attr >> 16):
                    raise RuntimeError(f"Unsafe component archive member: {entry.filename}")
                apple_metadata = Path(entry.filename).name.startswith("._") or entry.filename.startswith("__MACOSX/")
                if target.exists() and not entry.is_dir() and not apple_metadata:
                    if not path.is_file() or digest(path) != hashlib.sha256(package.read(entry)).hexdigest():
                        raise RuntimeError(f"Existing component differs from pinned archive; refusing to overwrite: {path}")
        if not target.exists():
            run("ditto", "-x", "-k", archive, destination)
        candidates = [path for path in target.iterdir() if path.suffix.lower() == ".4dz"]
        if len(candidates) != 1:
            raise RuntimeError(f"Expected one compiled project in {target}")
        compiled.append(str(candidates[0]))
        license_file = work / f"{name}-LICENSE"
        license_url = f"https://raw.githubusercontent.com/{pin['repository']}/{pin['revision']}/LICENSE"
        download(license_url, license_file, pin["license_sha256"])
        license_target = project.parent.parent / "Resources/licenses/4d-components" / name / "LICENSE"
        license_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(license_file, license_target)
    resources = project.parent.parent / "Resources"
    (resources / "4D_COMPONENTS.json").write_text(json.dumps(pins, indent=2) + "\n")
    return compiled


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=ROOT / "swama/Project/swama.4DProject")
    parser.add_argument("--work-dir", type=Path, default=ROOT / ".native-build/4d-components")
    args = parser.parse_args()
    tool, project, work = args.tool.resolve(), args.project.resolve(), args.work_dir.resolve()
    if not tool.is_file():
        parser.error(f"tool4d executable not found: {tool}")
    pins = json.loads((ROOT / "native/components.json").read_text())
    components = prepare_components(project, pins, work)
    guard = work / "guard"
    shutil.copytree(ROOT / "native/compile-guard", guard, dirs_exist_ok=True)
    report = work / "compile-result.json"
    report.unlink(missing_ok=True)
    parameters = json.dumps({"project": str(project), "report": str(report), "components": components})
    run(
        tool, guard / "Project/verify.4DProject", "--skip-onstartup", "--startup-method=verify",
        f"--user-param={parameters}", "--dataless",
    )
    if not report.is_file():
        raise RuntimeError("tool4d did not produce the required structured compilation report")
    result = json.loads(report.read_text())
    validate_compile_result(result)
    shutil.copy2(report, project.parent.parent / "Resources/4D_COMPILE_RESULT.json")
    print("PASS: pinned 4D dependencies and structured compile result (success=true, errors=[])")


if __name__ == "__main__":
    main()
