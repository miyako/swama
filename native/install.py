#!/usr/bin/env python3
"""Verify and install a complete native archive into a 4D component resource directory."""

import argparse
from pathlib import Path
import shutil
import tarfile
import tempfile

from smoke import smoke


def install(archive, destination, component_package=False):
    destination = destination.resolve()
    if destination.parts[-2:] != ("bin", "macOS"):
        raise ValueError("Destination must be a bin/macOS resource directory")
    with tempfile.TemporaryDirectory(prefix="swama-install-") as temporary:
        root = Path(temporary)
        with tarfile.open(archive) as tar:
            tar.extractall(root, filter="data")
        entries = list(root.iterdir())
        if len(entries) != 1 or not entries[0].is_dir():
            raise RuntimeError("Expected exactly one distribution directory")
        smoke(entries[0])
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".swama-stage-", dir=destination.parent) as stage:
            staged = Path(stage) / "macOS"
            shutil.copytree(entries[0], staged)
            # Only replace after the extracted archive has passed checks and runtime smoke.
            if destination.exists():
                backup = Path(stage) / "previous"
                destination.rename(backup)
                try:
                    staged.rename(destination)
                except OSError:
                    backup.rename(destination)
                    raise
            else:
                staged.rename(destination)
    smoke(destination)
    if component_package:
        # The existing component signer may change Mach-O and bundle bytes later.
        (destination / "SHA256SUMS").rename(destination / "SOURCE_BUILD_SHA256SUMS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--component-package", action="store_true", help="Label checksums as pre-sign source-build input")
    args = parser.parse_args()
    install(args.archive, args.destination, args.component_package)
