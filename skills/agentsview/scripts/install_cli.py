#!/usr/bin/env python3
"""Install the official AgentsView CLI release with checksum verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPOSITORY = "kenn-io/agentsview"
LATEST_URL = f"https://github.com/{REPOSITORY}/releases/latest"
USER_AGENT = "fullsend-agentsview-skill/1"


class InstallError(RuntimeError):
    """Expected installation failure with actionable context."""


def detect_platform() -> tuple[str, str, str]:
    """Return release OS, architecture, and binary filename."""
    os_name = platform.system().lower()
    os_map = {"darwin": "darwin", "linux": "linux", "windows": "windows"}
    if os_name not in os_map:
        raise InstallError(f"unsupported operating system: {platform.system()}")

    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }
    if machine not in arch_map:
        raise InstallError(f"unsupported architecture: {platform.machine()}")

    binary = "agentsview.exe" if os_name == "windows" else "agentsview"
    return os_map[os_name], arch_map[machine], binary


def request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})


def latest_version() -> str:
    """Resolve the current stable GitHub release tag."""
    try:
        with urllib.request.urlopen(request(LATEST_URL), timeout=30) as response:
            final_url = response.geturl()
    except (OSError, urllib.error.URLError) as exc:
        raise InstallError(
            f"could not resolve latest AgentsView release: {exc}"
        ) from exc

    marker = "/releases/tag/"
    if marker not in final_url:
        raise InstallError(
            f"latest release redirect did not contain a tag: {final_url}"
        )
    return final_url.rsplit(marker, 1)[1]


def download(url: str, destination: Path) -> None:
    """Download one release file without loading it into model context."""
    try:
        with urllib.request.urlopen(request(url), timeout=120) as response:
            with destination.open("wb") as output:
                shutil.copyfileobj(response, output)
    except (OSError, urllib.error.URLError) as exc:
        raise InstallError(f"download failed for {url}: {exc}") from exc


def expected_checksum(checksums: str, asset_name: str) -> str:
    for line in checksums.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1].lstrip("*") == asset_name:
            return fields[0].lower()
    raise InstallError(f"SHA256SUMS has no entry for {asset_name}")


def verify_checksum(archive: Path, expected: str) -> str:
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    if actual != expected:
        raise InstallError(
            f"checksum mismatch for {archive.name}: expected {expected}, got {actual}"
        )
    return actual


def extract_binary(archive: Path, binary_name: str, destination: Path) -> None:
    """Extract only the expected binary, never arbitrary archive paths."""
    member_data: bytes | None = None
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            names = [
                name
                for name in bundle.namelist()
                if PurePosixPath(name).name == binary_name and not name.endswith("/")
            ]
            if len(names) == 1:
                member_data = bundle.read(names[0])
    else:
        with tarfile.open(archive, "r:gz") as bundle:
            members = [
                member
                for member in bundle.getmembers()
                if member.isfile() and PurePosixPath(member.name).name == binary_name
            ]
            if len(members) == 1:
                stream = bundle.extractfile(members[0])
                member_data = stream.read() if stream else None

    if member_data is None:
        raise InstallError(f"archive did not contain exactly one {binary_name}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    try:
        temporary.write_bytes(member_data)
        temporary.chmod(
            temporary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def installed_version(binary: Path) -> str | None:
    if not binary.is_file() or not os.access(binary, os.X_OK):
        return None
    try:
        result = subprocess.run(
            [str(binary), "version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def install(version: str, destination_dir: Path, force: bool) -> dict[str, object]:
    os_name, architecture, binary_name = detect_platform()
    binary = destination_dir.expanduser().resolve() / binary_name
    existing = installed_version(binary)

    if existing and not force:
        return {
            "installed": False,
            "already_present": True,
            "binary": str(binary),
            "version": existing,
            "requested_release": version or None,
            "checksum": None,
            "remediation": "Use --force to replace the existing CLI release.",
        }

    tag = version or latest_version()
    normalized = tag if tag.startswith("v") else f"v{tag}"
    version_number = normalized.removeprefix("v")
    extension = "zip" if os_name == "windows" else "tar.gz"
    asset_name = f"agentsview_{version_number}_{os_name}_{architecture}.{extension}"

    base_url = f"https://github.com/{REPOSITORY}/releases/download/{normalized}"
    with tempfile.TemporaryDirectory(prefix="agentsview-install-") as temp:
        temp_dir = Path(temp)
        archive = temp_dir / asset_name
        checksums_file = temp_dir / "SHA256SUMS"
        download(f"{base_url}/{asset_name}", archive)
        download(f"{base_url}/SHA256SUMS", checksums_file)
        checksums = checksums_file.read_text(encoding="utf-8")
        checksum = verify_checksum(archive, expected_checksum(checksums, asset_name))
        extract_binary(archive, binary_name, binary)

    if os_name == "darwin" and shutil.which("codesign"):
        subprocess.run(
            ["codesign", "-s", "-", str(binary)],
            capture_output=True,
            check=False,
            timeout=30,
        )

    verified_version = installed_version(binary)
    if verified_version is None:
        raise InstallError(f"installed binary failed its version probe: {binary}")
    return {
        "installed": True,
        "already_present": False,
        "binary": str(binary),
        "version": verified_version,
        "requested_release": normalized,
        "checksum": checksum,
        "remediation": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install the official AgentsView CLI release with SHA256 verification. "
            "This does not start a daemon, modify AgentsView data, or sync sessions."
        )
    )
    parser.add_argument(
        "--version",
        default="",
        help="Release tag such as v0.38.1 (default: latest stable release)",
    )
    parser.add_argument(
        "--dest-dir",
        type=Path,
        default=Path("~/.local/bin"),
        help="Installation directory (default: ~/.local/bin)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing AgentsView binary in the destination",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit compact JSON for agent consumption"
    )
    args = parser.parse_args(argv)

    try:
        result = install(args.version, args.dest_dir, args.force)
    except InstallError as exc:
        result = {"installed": False, "error": str(exc)}
        if args.json:
            json.dump(result, sys.stdout, separators=(",", ":"))
            sys.stdout.write("\n")
        else:
            print(f"AgentsView CLI installation failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        json.dump(result, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
    else:
        action = "Installed" if result["installed"] else "Already present"
        print(f"{action}: {result['binary']}")
        print(f"Version: {result['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
