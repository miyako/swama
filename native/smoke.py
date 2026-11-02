#!/usr/bin/env python3
"""Exercise an extracted distribution without models, downloads or build-tree resources."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request


def verify(directory):
    directory = directory.resolve()
    listed = set()
    for entry in (directory / "SHA256SUMS").read_text().splitlines():
        expected, relative = entry.split("  ", 1)
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Checksum mismatch: {relative}")
        if relative in listed:
            raise RuntimeError(f"Duplicate checksum entry: {relative}")
        listed.add(relative)
    actual = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"Unexpected symlink in distribution: {path}")
        if path.is_file() and path != directory / "SHA256SUMS":
            actual.add(path.relative_to(directory).as_posix())
    if listed != actual:
        raise RuntimeError("Checksum inventory does not cover the complete distribution")
    if not os.access(directory / "swama", os.X_OK):
        raise RuntimeError("CLI executable permission was lost")
    return json.loads((directory / "BUILD_INFO.json").read_text())


def check_server(binary, subcommand, environment, home, model_name):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryFile(mode="w+") as log:
        server = subprocess.Popen(
            [binary, *subcommand, "--host", "127.0.0.1", "--port", str(port)],
            env=environment, cwd=home, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 60
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f"Server exited: {server.returncode}")
                try:
                    with opener.open(f"http://127.0.0.1:{port}/v1/models", timeout=2) as response:
                        models = json.load(response)
                    break
                except (OSError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Server did not become ready within 60 seconds")
                    time.sleep(0.2)
            if models.get("object") != "list" or not isinstance(models.get("data"), list):
                raise RuntimeError(f"Unexpected /v1/models response: {models}")
            if model_name not in [model.get("id") for model in models["data"]]:
                raise RuntimeError("HTTP model list is missing the locally registered fixture")
        except BaseException:
            log.seek(0)
            print(log.read())
            raise
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


def smoke(directory):
    directory = directory.resolve()
    info = verify(directory)
    binary = directory / "swama"
    with tempfile.TemporaryDirectory(prefix="swama-smoke-") as home:
        environment = dict(
            {key: value for key, value in os.environ.items() if not key.startswith("SWAMA_")},
            HOME=home, SWAMA_MODELS=f"{home}/models",
            SWAMA_DIAGNOSTICS_DISABLED="1",
        )
        version = subprocess.check_output(
            [binary, "--version"], env=environment, cwd=home, text=True,
        ).strip()
        if version != info["version"]:
            raise RuntimeError(f"CLI version {version} != manifest {info['version']}")
        subprocess.run([binary, "serve", "--help"], cwd=home, env=environment, check=True, stdout=subprocess.DEVNULL)
        fixture = Path(home) / "fixture"
        fixture.mkdir()
        (fixture / "config.json").write_text("{}")
        name = "swama-packaging-smoke"
        subprocess.run(
            [binary, "create", fixture, "--name", name],
            env=environment, cwd=home, check=True, stdout=subprocess.DEVNULL,
        )
        models = json.loads(subprocess.check_output(
            [binary, "list", "--format", "json"], env=environment, cwd=home, text=True,
        ))
        if name not in [model.get("id") for model in models]:
            raise RuntimeError("CLI model list is missing the locally registered fixture")
        # 4D uses the implicit default subcommand; standalone examples use explicit serve.
        check_server(binary, ["serve"], environment, home, name)
        check_server(binary, [], environment, home, name)
    print(f"PASS: extracted CLI {version}, create/list, explicit + implicit serve, HTTP /v1/models")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    smoke(parser.parse_args().directory)
