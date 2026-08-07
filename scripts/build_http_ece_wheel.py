#!/usr/bin/env python3
"""Build the pinned ``http-ece`` sdist as a reproducible universal wheel.

This is a CI/build-time tool.  The production deploy path consumes the wheel
and its hash from the immutable wheelhouse; it never executes this module.
Only the standard library is used so the builder can run before the runtime
environment exists.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import os
import re
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from email.parser import Parser
from pathlib import Path, PurePosixPath


PACKAGE_NAME = "http_ece"
VERSION = "1.2.1"
WHEEL_NAME = "http_ece-1.2.1-py2.py3-none-any.whl"
DIST_INFO = "http_ece-1.2.1.dist-info"
DEFAULT_SOURCE_DATE_EPOCH = 315532800  # 1980-01-01, the ZIP epoch
EXPECTED_SDIST_SHA256 = "8c6ab23116bbf6affda894acfd5f2ca0fb8facbcbb72121c11c75c33e7ce8cff"
EXPECTED_WHEEL_SHA256 = "4ee99a46e0ae3f8230632457b935ce953bbf0d8b5a8c3030bbf2b9bbfa6533a8"
DEFAULT_SDIST_URL = (
    "https://files.pythonhosted.org/packages/source/h/http-ece/"
    "http_ece-1.2.1.tar.gz"
)
_HASH_RE = re.compile(r"^\s*--hash=sha256:([0-9a-f]{64})(?: \\)?$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_date_epoch(value: int | str | None) -> int:
    if value is None:
        value = os.environ.get("SOURCE_DATE_EPOCH", DEFAULT_SOURCE_DATE_EPOCH)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("SOURCE_DATE_EPOCH must be an integer") from exc
    if parsed < DEFAULT_SOURCE_DATE_EPOCH:
        raise ValueError("SOURCE_DATE_EPOCH must be at least 315532800")
    return parsed


def _safe_member_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe archive member: {name!r}")
    return path


def _read_source_files(sdist: Path) -> tuple[bytes, bytes]:
    try:
        archive = tarfile.open(sdist, mode="r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise ValueError(f"unable to read http-ece sdist: {sdist}") from exc

    files: dict[str, bytes] = {}
    with archive:
        for member in archive.getmembers():
            path = _safe_member_name(member.name)
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError(f"http-ece sdist contains non-file member: {member.name!r}")
            if len(path.parts) < 2 or path.parts[0] != "http_ece-1.2.1":
                raise ValueError(f"unexpected http-ece archive root: {member.name!r}")
            key = "/".join(path.parts)
            if key in files:
                raise ValueError(f"duplicate archive member: {member.name!r}")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"unable to read archive member: {member.name!r}")
            files[key] = extracted.read()

    try:
        metadata = files["http_ece-1.2.1/PKG-INFO"]
        package_init = files["http_ece-1.2.1/http_ece/__init__.py"]
    except KeyError as exc:
        raise ValueError(f"http-ece sdist is missing {exc.args[0]}") from exc

    parsed = Parser().parsestr(metadata.decode("utf-8"))
    if parsed.get("Name", "").replace("-", "_").lower() != PACKAGE_NAME:
        raise ValueError("http-ece sdist metadata has an unexpected name")
    if parsed.get("Version") != VERSION:
        raise ValueError("http-ece sdist metadata has an unexpected version")
    if "cryptography>=2.5" not in parsed.get_all("Requires-Dist", []):
        raise ValueError("http-ece sdist metadata is missing cryptography>=2.5")
    return package_init, metadata


def _record_hash(content: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
    return f"sha256={encoded.decode('ascii')}"


def _zip_entry(name: str, content: bytes, *, timestamp: tuple[int, int, int, int, int, int]) -> zipfile.ZipInfo:
    entry = zipfile.ZipInfo(name, date_time=timestamp)
    entry.create_system = 3
    entry.external_attr = 0o100644 << 16
    entry.compress_type = zipfile.ZIP_STORED
    entry.flag_bits = 0
    return entry


def build_wheel(
    sdist: Path,
    wheel_dir: Path,
    *,
    expected_sdist_sha256: str = EXPECTED_SDIST_SHA256,
    source_date_epoch: int | str | None = None,
) -> Path:
    """Build and atomically publish a deterministic wheel from a verified sdist."""

    sdist = Path(sdist)
    if not sdist.is_file():
        raise ValueError(f"http-ece sdist does not exist: {sdist}")
    expected = expected_sdist_sha256.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("expected sdist SHA256 must be 64 lowercase hex characters")
    actual = _sha256(sdist)
    if actual != expected:
        raise ValueError(f"sdist SHA256 mismatch: expected {expected}, got {actual}")

    package_init, source_metadata = _read_source_files(sdist)
    epoch = _source_date_epoch(source_date_epoch)
    timestamp = datetime.fromtimestamp(epoch, tz=timezone.utc)
    zip_timestamp = (
        timestamp.year,
        timestamp.month,
        timestamp.day,
        timestamp.hour,
        timestamp.minute,
        timestamp.second,
    )
    wheel_metadata = (
        "Wheel-Version: 1.0\n"
        "Generator: twocomms-http-ece-wheel-builder 1\n"
        "Root-Is-Purelib: true\n"
        "Tag: py2-none-any\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")
    entries = {
        "http_ece/__init__.py": package_init,
        f"{DIST_INFO}/METADATA": source_metadata,
        f"{DIST_INFO}/WHEEL": wheel_metadata,
    }
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name in sorted(entries):
        content = entries[name]
        writer.writerow((name, _record_hash(content), str(len(content))))
    writer.writerow((f"{DIST_INFO}/RECORD", "", ""))
    entries[f"{DIST_INFO}/RECORD"] = record.getvalue().encode("utf-8")

    wheel_dir = Path(wheel_dir)
    wheel_dir.mkdir(parents=True, exist_ok=True)
    destination = wheel_dir / WHEEL_NAME
    with tempfile.NamedTemporaryFile(
        mode="wb", prefix=f".{WHEEL_NAME}.", suffix=".tmp", dir=wheel_dir, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        try:
            with zipfile.ZipFile(temporary, mode="w", compression=zipfile.ZIP_STORED) as wheel:
                for name in (
                    "http_ece/__init__.py",
                    f"{DIST_INFO}/METADATA",
                    f"{DIST_INFO}/WHEEL",
                    f"{DIST_INFO}/RECORD",
                ):
                    wheel.writestr(_zip_entry(name, entries[name], timestamp=zip_timestamp), entries[name])
            temporary.flush()
            os.fsync(temporary.fileno())
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    os.replace(temporary_path, destination)
    os.chmod(destination, 0o644)
    return destination


def update_lock_hashes(
    lock_path: Path,
    wheel: Path,
    *,
    expected_sdist_sha256: str = EXPECTED_SDIST_SHA256,
) -> str:
    """Add the verified wheel hash to the exact ``http-ece`` lock block."""

    lock_path = Path(lock_path)
    wheel = Path(wheel)
    wheel_hash = _sha256(wheel)
    text = lock_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.startswith("http-ece==1.2.1")]
    if len(starts) != 1:
        raise ValueError("requirements lock must contain exactly one http-ece==1.2.1 entry")
    start = starts[0]
    end = start + 1
    hashes: list[str] = []
    while end < len(lines) and lines[end].startswith("    --hash=sha256:"):
        match = _HASH_RE.match(lines[end].rstrip("\n"))
        if not match:
            raise ValueError("malformed http-ece hash line")
        hashes.append(match.group(1))
        end += 1
    if expected_sdist_sha256 not in hashes:
        raise ValueError("requirements lock does not contain the verified http-ece sdist hash")
    allowed = {expected_sdist_sha256, wheel_hash}
    if set(hashes) - allowed:
        raise ValueError("requirements lock contains an unexpected http-ece hash")
    replacement = [
        "http-ece==1.2.1 \\\n",
        f"    --hash=sha256:{expected_sdist_sha256} \\\n",
        f"    --hash=sha256:{wheel_hash}\n",
    ]
    updated = "".join(lines[:start] + replacement + lines[end:])
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix=f".{lock_path.name}.", suffix=".tmp", dir=lock_path.parent, delete=False
    ) as temporary:
        temporary.write(updated)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, lock_path)
    return wheel_hash


def _download_sdist(destination: Path, url: str = DEFAULT_SDIST_URL) -> Path:
    if url != DEFAULT_SDIST_URL or not url.startswith("https://files.pythonhosted.org/"):
        raise ValueError("http-ece source URL must be the pinned Python-hosted URL")
    with urllib.request.urlopen(url, timeout=60) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdist", type=Path, help="verified source archive; downloads the pinned archive when omitted")
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--source-date-epoch", type=int, default=None)
    args = parser.parse_args(argv)

    temporary_sdist: Path | None = None
    try:
        sdist = args.sdist
        if sdist is None:
            with tempfile.NamedTemporaryFile(prefix="http-ece-", suffix=".tar.gz", delete=False) as temporary:
                temporary_sdist = Path(temporary.name)
            sdist = _download_sdist(temporary_sdist)
        wheel = build_wheel(sdist, args.wheel_dir, source_date_epoch=args.source_date_epoch)
        wheel_hash = _sha256(wheel)
        if EXPECTED_WHEEL_SHA256 != "0" * 64 and wheel_hash != EXPECTED_WHEEL_SHA256:
            raise ValueError(
                f"deterministic http-ece wheel SHA256 mismatch: expected {EXPECTED_WHEEL_SHA256}, got {wheel_hash}"
            )
        update_lock_hashes(args.lock, wheel)
        print(f"http-ece wheel sha256={wheel_hash}")
        return 0
    except (OSError, ValueError, tarfile.TarError, urllib.error.URLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if temporary_sdist is not None:
            temporary_sdist.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
