#!/usr/bin/env python3
"""Install the pinned official Luau CLI used by controlled v108 tests."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path
from zipfile import ZipFile

VERSION = "0.745"
URL = f"https://github.com/luau-lang/luau/releases/download/{VERSION}/luau-ubuntu.zip"
SHA256 = "186e5ddaa2b048ebc7390c11ed1b00c04e7d3beaffed429250329e3575d2ece2"
MAX_ARCHIVE_BYTES = 10_000_000
BINARY_SHA256 = {
    "luau": "4b9e07f548afdfe4aeb9a7ef8386e927e085529ac5dc4b0d42f6963fdde46095",
    "luau-analyze": "f16fed21fa0d30ad3aac159ffc7fdd5712a06d0e55633aada9c9fef1eaa664ba",
    "luau-ast": "790d7be2ee80bd19709a4b00a90eb72e50c43c72407470ef95186b6f130bf378",
    "luau-compile": "49805c3bd6db1f2492aeb2217bdb4fa42817fcb992e87abe2889561f664760a7",
}
BINARIES = set(BINARY_SHA256)


def _download(url, output):
    request = urllib.request.Request(url, headers={"User-Agent": "Lycoles-v108-runtime-installer"})
    with urllib.request.urlopen(request, timeout=30) as response, output.open("wb") as target:
        total = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ARCHIVE_BYTES:
                raise ValueError("Luau archive exceeds size limit")
            target.write(chunk)


def _extract(archive, output, expected_hashes=None):
    expected_hashes = BINARY_SHA256 if expected_hashes is None else expected_hashes
    if not isinstance(expected_hashes, dict) or not expected_hashes:
        raise ValueError("invalid Luau executable hashes")
    expected_names = set(expected_hashes)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    existing = list(output.iterdir())
    if any(item.is_symlink() or not item.is_file() or item.name not in expected_names for item in existing):
        raise ValueError("unsafe Luau installation contents")
    for item in existing:
        item.unlink()
    with ZipFile(archive) as source:
        names = {item.filename for item in source.infolist() if not item.is_dir()}
        if names != expected_names:
            raise ValueError("unexpected Luau archive contents")
        for item in source.infolist():
            target = output / item.filename
            if item.is_dir() or output not in target.resolve().parents:
                raise ValueError("unsafe Luau archive path")
            with source.open(item) as incoming, target.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            if hashlib.sha256(target.read_bytes()).hexdigest() != expected_hashes[item.filename]:
                raise ValueError("Luau executable hash mismatch")
            target.chmod(0o755)
    return output / "luau"


def install(output):
    output = Path(output)
    if output.exists() and (output.is_symlink() or not output.is_dir()):
        raise ValueError("invalid Luau installation directory")
    with tempfile.TemporaryDirectory(prefix="lycoles-luau-install-") as directory:
        archive = Path(directory) / "luau.zip"
        _download(URL, archive)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != SHA256:
            raise ValueError("Luau archive hash mismatch")
        binary = _extract(archive, output)
    return {
        "version": VERSION,
        "url": URL,
        "archiveSha256": SHA256,
        "binary": str(binary),
        "binarySha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = install(args.output)
    print(json.dumps(result, sort_keys=True))
    if os.environ.get("GITHUB_ENV"):
        with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as handle:
            handle.write("LUAU_BIN=" + str(Path(result["binary"]).resolve()) + "\n")


if __name__ == "__main__":
    main()
