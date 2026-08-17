#!/usr/bin/env python3
"""Build an immutable CPython 3.14 manylinux wheelhouse for one Git SHA.

The builder is intended for the pinned manylinux CI image. Production only
verifies and consumes its output; it never compiles packages during deploy.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from email.parser import Parser
from pathlib import Path

try:
    from scripts.build_http_ece_wheel import main as build_http_ece_main
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from build_http_ece_wheel import main as build_http_ece_main


CFFI_VERSION = "2.1.1"
CFFI_SDIST_SHA256 = "dd31f52ea1086513bb9df30f8fcee9b8918323ae067a3d5b78bc826a000712be"
CFFI_SDIST_URL = (
    "https://files.pythonhosted.org/packages/9e/ef/"
    "008a1939e372c06329a3fce4279c02f328488f3526744906eeec3da7ad5f/"
    "cffi-2.1.1.tar.gz"
)
SETUPTOOLS_VERSION = "80.9.0"
SETUPTOOLS_WHEEL_SHA256 = "062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922"
SETUPTOOLS_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/a3/dc/"
    "17031897dae0efacfea57dfd3a82fdd2a2aeb58e0ff71b77b87e44edc772/"
    "setuptools-80.9.0-py3-none-any.whl"
)
MYSQLCLIENT_VERSION = "2.2.8"
MYSQLCLIENT_SDIST_SHA256 = "8ed20c5615a915da451bb308c7d0306648a4fd9a2809ba95c992690006306199"
MYSQLCLIENT_SDIST_URL = (
    "https://files.pythonhosted.org/packages/eb/b0/"
    "9df076488cb2e536d40ce6dbd4273c1f20a386e31ffe6e7cb613902b3c2a/"
    "mysqlclient-2.2.8.tar.gz"
)
MARIADB_CONNECTOR_C_VERSION = "3.3.19"
MARIADB_CONNECTOR_C_SOURCE_URL = (
    "https://dlm.mariadb.com/4751094/Connectors/c/connector-c-3.3.19/"
    "mariadb-connector-c-3.3.19-rhel8-amd64.tar.gz"
)
MARIADB_CONNECTOR_C_SOURCE_SHA256 = (
    "672bec76cfbb2fdb46ad4f681cd1e63c80721d7a07316e5849dc63e69d6ecdf7"
)
MARIADB_CONNECTOR_C_ARCHIVE = Path(
    "/opt/mariadb-connector-c-3.3.19-rhel8-amd64.tar.gz"
)
MARIADB_CONNECTOR_C_ROOT = Path("/opt/mariadb-connector-c-3.3.19")
MARIADB_CONNECTOR_C_INCLUDE = MARIADB_CONNECTOR_C_ROOT / "include" / "mariadb"
MARIADB_CONNECTOR_C_LIBRARY = MARIADB_CONNECTOR_C_ROOT / "lib" / "mariadb" / "libmariadb.so.3"
MARIADB_CONNECTOR_C_LIBRARY_SHA256 = (
    "5395b9398e16b3313ed3d799771ec33a4661beb91833648b457a0bfdb0fb36ee"
)
MARIADB_CONNECTOR_C_SONAME = "libmariadb.so.3"
SOURCE_DATE_EPOCH = 315532800
EXPECTED_PYTHON = (3, 14, 6)
EXPECTED_SOABI = "cpython-314-x86_64-linux-gnu"
EXPECTED_PLATFORM = "manylinux_2_28_x86_64"
EXPECTED_IMAGE_DIGEST = (
    "sha256:fdb9a9c223b215604dc7b6f7e8fff4b39bfea5fbaa7777a2e5544a60dfa437f8"
)
EXPECTED_LIBFFI_DEVEL = "libffi-devel-3.1-24.el8.x86_64"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HASH_RE = re.compile(r"^\s*--hash=sha256:([0-9a-f]{64})(?: \\)?$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_package_hashes(
    lock_text: str,
    *,
    package: str,
    version: str,
    required_source_hash: str,
    wheel_hash: str,
) -> str:
    """Replace one exact lock block with its verified source and built wheel hashes."""

    for value, label in (
        (required_source_hash, "verified source hash"),
        (wheel_hash, "wheel hash"),
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError(f"{label} must be 64 lowercase hex characters")
    lines = lock_text.splitlines(keepends=True)
    prefix = f"{package}=={version}"
    starts = [index for index, line in enumerate(lines) if line.startswith(prefix)]
    if len(starts) != 1:
        raise ValueError(f"lock must contain exactly one {prefix} entry")
    start = starts[0]
    end = start + 1
    existing: list[str] = []
    while end < len(lines) and lines[end].startswith("    --hash=sha256:"):
        match = _HASH_RE.match(lines[end].rstrip("\n"))
        if not match:
            raise ValueError(f"malformed {package} hash line")
        existing.append(match.group(1))
        end += 1
    if required_source_hash not in existing:
        raise ValueError(f"{package} lock block is missing the verified source hash")
    replacement = [
        f"{package}=={version} \\\n",
        f"    --hash=sha256:{required_source_hash} \\\n",
        f"    --hash=sha256:{wheel_hash}\n",
    ]
    return "".join(lines[:start] + replacement + lines[end:])


def build_manifest(
    wheelhouse: Path,
    *,
    target_sha: str,
    source_lock_sha256: str,
) -> Path:
    """Write the sorted artifact manifest consumed by the release orchestrator."""

    if not _SHA_RE.fullmatch(target_sha):
        raise ValueError("target SHA must be 40 lowercase hex characters")
    if not re.fullmatch(r"[0-9a-f]{64}", source_lock_sha256):
        raise ValueError("source lock SHA256 must be 64 lowercase hex characters")
    wheelhouse = Path(wheelhouse)
    manifest_path = wheelhouse / "manifest.sha256"
    if manifest_path.is_symlink():
        raise ValueError("wheelhouse manifest must not be a symlink")
    files: dict[str, str] = {}
    for artifact in sorted(wheelhouse.iterdir(), key=lambda path: path.name):
        if artifact == manifest_path:
            continue
        if (
            artifact.is_symlink()
            or not stat.S_ISREG(artifact.lstat().st_mode)
            or artifact.name in {".", ".."}
            or "/" in artifact.name
        ):
            raise ValueError("wheelhouse contains an unsafe non-regular artifact")
        files[artifact.name] = sha256(artifact)
    payload = {
        "files": files,
        "source_lock_sha256": source_lock_sha256,
        "target_sha": target_sha,
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(manifest_path, 0o644)
    return manifest_path


def _run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True, timeout=900)


def _download_verified(url: str, destination: Path, expected_hash: str) -> Path:
    allowed = {
        CFFI_SDIST_URL: CFFI_SDIST_SHA256,
        SETUPTOOLS_WHEEL_URL: SETUPTOOLS_WHEEL_SHA256,
        MYSQLCLIENT_SDIST_URL: MYSQLCLIENT_SDIST_SHA256,
    }
    if allowed.get(url) != expected_hash or not url.startswith("https://files.pythonhosted.org/"):
        raise ValueError("build dependency URL/hash is not pinned")
    with urllib.request.urlopen(url, timeout=60) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    actual = sha256(destination)
    if actual != expected_hash:
        raise ValueError(f"build dependency SHA256 mismatch: expected {expected_hash}, got {actual}")
    return destination


def _validate_cffi_source(sdist: Path) -> None:
    try:
        with tarfile.open(sdist, "r:gz") as archive:
            member = archive.getmember("cffi-2.1.1/PKG-INFO")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError("cffi sdist metadata is unreadable")
            metadata = Parser().parsestr(extracted.read().decode("utf-8"))
    except (KeyError, OSError, tarfile.TarError, UnicodeError) as exc:
        raise ValueError("cffi sdist metadata is invalid") from exc
    if metadata.get("Name", "").lower() != "cffi" or metadata.get("Version") != CFFI_VERSION:
        raise ValueError("cffi sdist metadata name/version mismatch")


def _validate_mysqlclient_source(sdist: Path) -> None:
    try:
        with tarfile.open(sdist, "r:gz") as archive:
            member = archive.getmember("mysqlclient-2.2.8/PKG-INFO")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError("mysqlclient sdist metadata is unreadable")
            metadata = Parser().parsestr(extracted.read().decode("utf-8"))
    except (KeyError, OSError, tarfile.TarError, UnicodeError) as exc:
        raise ValueError("mysqlclient sdist metadata is invalid") from exc
    if metadata.get("Name", "").lower() != "mysqlclient" or metadata.get("Version") != MYSQLCLIENT_VERSION:
        raise ValueError("mysqlclient sdist metadata name/version mismatch")


def _assert_builder_environment(image_digest: str) -> dict[str, str]:
    if image_digest != EXPECTED_IMAGE_DIGEST:
        raise ValueError("builder image digest mismatch")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("wheelhouse builder requires Linux x86_64")
    if sys.version_info[:3] != EXPECTED_PYTHON:
        raise ValueError("wheelhouse builder requires CPython 3.14.6")
    soabi = str(sysconfig.get_config_var("SOABI") or "")
    if soabi != EXPECTED_SOABI:
        raise ValueError("wheelhouse builder SOABI mismatch")
    libc_name, libc_version = platform.libc_ver()
    if libc_name != "glibc" or libc_version != "2.28":
        raise ValueError("wheelhouse builder requires glibc 2.28")
    return {
        "builder_image_digest": image_digest,
        "glibc": f"{libc_name} {libc_version}",
        "python": platform.python_version(),
        "soabi": soabi,
    }


def _build_cffi_once(
    python: Path,
    auditwheel: str,
    sdist: Path,
    destination: Path,
    *,
    label: str,
) -> Path:
    raw = destination / f"raw-{label}"
    repaired = destination / f"repaired-{label}"
    raw.mkdir()
    repaired.mkdir()
    env = dict(os.environ)
    env.update(
        {
            "CFLAGS": "-O2 -g0 -ffile-prefix-map=/tmp=.",
            "CXXFLAGS": "-O2 -g0 -ffile-prefix-map=/tmp=.",
            "LDFLAGS": "-Wl,--build-id=sha1",
            "PYTHONHASHSEED": "0",
            "SOURCE_DATE_EPOCH": str(SOURCE_DATE_EPOCH),
        }
    )
    _run(
        [
            str(python),
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-deps",
            "--no-build-isolation",
            "--no-cache-dir",
            "--wheel-dir",
            str(raw),
            str(sdist),
        ],
        env=env,
    )
    wheels = tuple(raw.glob("cffi-2.1.1-*.whl"))
    if len(wheels) != 1:
        raise ValueError("cffi build did not produce exactly one wheel")
    _run(
        [
            auditwheel,
            "repair",
            "--plat",
            EXPECTED_PLATFORM,
            "--wheel-dir",
            str(repaired),
            str(wheels[0]),
        ],
        env=env,
    )
    repaired_wheels = tuple(repaired.glob("cffi-2.1.1-*.whl"))
    if len(repaired_wheels) != 1:
        raise ValueError("auditwheel did not produce exactly one cffi wheel")
    wheel = repaired_wheels[0]
    _normalize_wheel(wheel)
    return wheel


def _normalize_wheel(wheel: Path) -> None:
    """Rewrite an auditwheel artifact with stable payloads and ZIP metadata."""

    wheel = Path(wheel)
    temporary = wheel.with_name(f".{wheel.name}.normalized")
    try:
        with zipfile.ZipFile(wheel) as source:
            members = source.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)):
                raise ValueError("wheel contains duplicate archive members")
            payloads = {member.filename: source.read(member) for member in members}
            sbom_names = [
                name
                for name in names
                if name.endswith(".dist-info/sboms/auditwheel.cdx.json")
            ]
            if len(sbom_names) > 1:
                raise ValueError("wheel contains multiple auditwheel SBOM files")
            if sbom_names:
                sbom_name = sbom_names[0]
                payloads[sbom_name] = _canonicalize_auditwheel_sbom(payloads[sbom_name])
            record_names = [
                name for name in names if name.endswith(".dist-info/RECORD")
            ]
            if len(record_names) > 1:
                raise ValueError("wheel contains multiple RECORD files")
            if record_names:
                record_name = record_names[0]
                payloads[record_name] = _rebuild_record(
                    record_name,
                    payloads,
                )
            with zipfile.ZipFile(
                temporary,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
                strict_timestamps=True,
            ) as output:
                for member in sorted(members, key=lambda item: item.filename):
                    normalized = zipfile.ZipInfo(member.filename, date_time=(1980, 1, 1, 0, 0, 0))
                    normalized.compress_type = member.compress_type
                    normalized.create_system = 3
                    normalized.external_attr = _normalized_zip_external_attr(member)
                    output.writestr(
                        normalized,
                        payloads[member.filename],
                        compress_type=member.compress_type,
                        compresslevel=9 if member.compress_type == zipfile.ZIP_DEFLATED else None,
                    )
        os.replace(temporary, wheel)
    finally:
        if temporary.exists():
            temporary.unlink()


_SBOM_ORDER_INSENSITIVE_ARRAYS = frozenset(
    {"components", "dependencies", "dependsOn", "properties", "externalReferences"}
)


def _normalized_zip_external_attr(member: zipfile.ZipInfo) -> int:
    source_mode = (member.external_attr >> 16) & 0xFFFF
    if member.is_dir():
        return ((stat.S_IFDIR | 0o755) << 16) | 0x10
    if stat.S_ISLNK(source_mode):
        raise ValueError("wheel contains a symbolic link member")
    file_type = stat.S_IFMT(source_mode)
    if file_type not in (0, stat.S_IFREG):
        raise ValueError("wheel contains a non-regular archive member")
    permissions = 0o755 if source_mode & 0o111 else 0o644
    return (stat.S_IFREG | permissions) << 16


def _canonicalize_sbom_value(value: object, *, key: str | None = None) -> object:
    if isinstance(value, dict):
        return {
            name: _canonicalize_sbom_value(child, key=name)
            for name, child in value.items()
        }
    if isinstance(value, list):
        normalized = [_canonicalize_sbom_value(child) for child in value]
        if key in _SBOM_ORDER_INSENSITIVE_ARRAYS:
            normalized.sort(
                key=lambda child: json.dumps(
                    child,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        return normalized
    return value


def _canonicalize_auditwheel_sbom(payload: bytes) -> bytes:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("auditwheel SBOM is not valid JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("auditwheel SBOM must be a JSON object")
    normalized = _canonicalize_sbom_value(document)
    return (
        json.dumps(
            normalized,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _rebuild_record(record_name: str, payloads: dict[str, bytes]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    for name in sorted(payloads):
        if name == record_name:
            writer.writerow((name, "", ""))
            continue
        digest = base64.urlsafe_b64encode(hashlib.sha256(payloads[name]).digest())
        writer.writerow(
            (
                name,
                "sha256=" + digest.rstrip(b"=").decode("ascii"),
                str(len(payloads[name])),
            )
        )
    return output.getvalue().encode("utf-8")


def _validate_cffi_wheel(wheel: Path) -> None:
    prefix = "cffi-2.1.1-cp314-cp314-"
    platform_tags = (
        wheel.name[len(prefix) : -4].split(".")
        if wheel.name.startswith(prefix) and wheel.name.endswith(".whl")
        else []
    )
    if EXPECTED_PLATFORM not in platform_tags:
        raise ValueError("cffi wheel has an unexpected compatibility tag")
    try:
        with zipfile.ZipFile(wheel) as archive:
            metadata = Parser().parsestr(
                archive.read("cffi-2.1.1.dist-info/METADATA").decode("utf-8")
            )
            wheel_metadata = archive.read("cffi-2.1.1.dist-info/WHEEL").decode("utf-8")
            extension_names = [
                name for name in archive.namelist() if name.startswith("_cffi_backend") and name.endswith(".so")
            ]
    except (KeyError, OSError, UnicodeError, zipfile.BadZipFile) as exc:
        raise ValueError("cffi wheel metadata is invalid") from exc
    if metadata.get("Name", "").lower() != "cffi" or metadata.get("Version") != CFFI_VERSION:
        raise ValueError("cffi wheel metadata name/version mismatch")
    if f"Tag: cp314-cp314-{EXPECTED_PLATFORM}" not in wheel_metadata or len(extension_names) != 1:
        raise ValueError("cffi wheel contents or tag are invalid")


def _build_mysqlclient_once(
    python: Path,
    auditwheel: str,
    sdist: Path,
    destination: Path,
    *,
    label: str,
) -> Path:
    raw = destination / f"raw-mysqlclient-{label}"
    repaired = destination / f"repaired-mysqlclient-{label}"
    raw.mkdir()
    repaired.mkdir()
    env = dict(os.environ)
    env.update(
        {
            "CFLAGS": "-O2 -g0 -ffile-prefix-map=/tmp=.",
            "CXXFLAGS": "-O2 -g0 -ffile-prefix-map=/tmp=.",
            "LDFLAGS": "-Wl,--build-id=sha1",
            "MYSQLCLIENT_CFLAGS": f"-I{MARIADB_CONNECTOR_C_INCLUDE}",
            "MYSQLCLIENT_LDFLAGS": f"-L{MARIADB_CONNECTOR_C_LIBRARY.parent} -lmariadb",
            "PYTHONHASHSEED": "0",
            "SOURCE_DATE_EPOCH": str(SOURCE_DATE_EPOCH),
        }
    )
    _run(
        [
            str(python),
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-deps",
            "--no-build-isolation",
            "--no-cache-dir",
            "--wheel-dir",
            str(raw),
            str(sdist),
        ],
        env=env,
    )
    wheels = tuple(raw.glob(f"mysqlclient-{MYSQLCLIENT_VERSION}-*.whl"))
    if len(wheels) != 1:
        raise ValueError("mysqlclient build did not produce exactly one wheel")
    _run(
        [
            auditwheel,
            "repair",
            "--plat",
            EXPECTED_PLATFORM,
            "--wheel-dir",
            str(repaired),
            str(wheels[0]),
        ],
        env=env,
    )
    repaired_wheels = tuple(repaired.glob(f"mysqlclient-{MYSQLCLIENT_VERSION}-*.whl"))
    if len(repaired_wheels) != 1:
        raise ValueError("auditwheel did not produce exactly one mysqlclient wheel")
    wheel = repaired_wheels[0]
    _normalize_wheel(wheel)
    return wheel


def _read_elf_dynamic(path: Path) -> tuple[str | None, tuple[str, ...]]:
    try:
        result = subprocess.run(
            ["readelf", "-d", os.fspath(path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"ELF dynamic metadata is unreadable: {path}") from exc
    soname = None
    needed: list[str] = []
    for line in result.stdout.splitlines():
        if "(SONAME)" in line:
            match = re.search(r"\[([^]]+)\]", line)
            if match:
                soname = match.group(1)
        elif "(NEEDED)" in line:
            match = re.search(r"\[([^]]+)\]", line)
            if match:
                needed.append(match.group(1))
    return soname, tuple(needed)


def _read_elf_soname(path: Path) -> str:
    soname, _ = _read_elf_dynamic(path)
    if not soname:
        raise ValueError(f"ELF library has no SONAME: {path}")
    return soname


def _read_wheel_elf_dynamic(wheel: Path, member_name: str) -> tuple[str | None, tuple[str, ...]]:
    with tempfile.TemporaryDirectory(prefix="wheel-elf-") as directory:
        extracted = Path(directory) / Path(member_name).name
        try:
            with zipfile.ZipFile(wheel) as archive:
                extracted.write_bytes(archive.read(member_name))
        except (KeyError, OSError, zipfile.BadZipFile) as exc:
            raise ValueError(f"wheel ELF member is unreadable: {member_name}") from exc
        return _read_elf_dynamic(extracted)


def _read_wheel_elf_soname(wheel: Path, member_name: str) -> str:
    soname, _ = _read_wheel_elf_dynamic(wheel, member_name)
    if not soname:
        raise ValueError(f"wheel library has no SONAME: {member_name}")
    return soname


def _validate_mariadb_connector_c(
    root: Path,
    *,
    source_archive: Path = MARIADB_CONNECTOR_C_ARCHIVE,
) -> dict[str, str]:
    root = Path(root)
    archive = Path(source_archive)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("MariaDB Connector/C root is not a regular directory")
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("MariaDB Connector/C source archive is missing")
    if sha256(archive) != MARIADB_CONNECTOR_C_SOURCE_SHA256:
        raise ValueError("MariaDB Connector/C source archive hash mismatch")
    header = root / "include" / "mariadb" / "mariadb_version.h"
    library = root / "lib" / "mariadb" / "libmariadb.so.3"
    if header.is_symlink() or not header.is_file():
        raise ValueError("MariaDB Connector/C version header is missing")
    if library.is_symlink() or not library.is_file():
        raise ValueError("MariaDB Connector/C shared library is missing")
    header_text = header.read_text(encoding="ascii")
    if f'#define MARIADB_PACKAGE_VERSION "{MARIADB_CONNECTOR_C_VERSION}"' not in header_text:
        raise ValueError("MariaDB Connector/C version header mismatch")
    library_hash = sha256(library)
    if library_hash != MARIADB_CONNECTOR_C_LIBRARY_SHA256:
        raise ValueError("MariaDB Connector/C shared library hash mismatch")
    soname = _read_elf_soname(library)
    if soname != MARIADB_CONNECTOR_C_SONAME:
        raise ValueError("MariaDB Connector/C shared library SONAME mismatch")
    return {
        "mariadb_connector_c_library_sha256": library_hash,
        "mariadb_connector_c_soname": soname,
        "mariadb_connector_c_source_sha256": MARIADB_CONNECTOR_C_SOURCE_SHA256,
        "mariadb_connector_c_source_url": MARIADB_CONNECTOR_C_SOURCE_URL,
        "mariadb_connector_c_version": MARIADB_CONNECTOR_C_VERSION,
    }


def _validate_mysqlclient_wheel(wheel: Path) -> dict[str, str]:
    prefix = f"mysqlclient-{MYSQLCLIENT_VERSION}-cp314-cp314-"
    platform_tags = (
        wheel.name[len(prefix) : -4].split(".")
        if wheel.name.startswith(prefix) and wheel.name.endswith(".whl")
        else []
    )
    if EXPECTED_PLATFORM not in platform_tags:
        raise ValueError("mysqlclient wheel has an unexpected compatibility tag")
    try:
        with zipfile.ZipFile(wheel) as archive:
            metadata = Parser().parsestr(
                archive.read(f"mysqlclient-{MYSQLCLIENT_VERSION}.dist-info/METADATA").decode("utf-8")
            )
            wheel_metadata = archive.read(f"mysqlclient-{MYSQLCLIENT_VERSION}.dist-info/WHEEL").decode("utf-8")
            extension_names = [
                name
                for name in archive.namelist()
                if Path(name).name.startswith("_mysql") and name.endswith(".so")
            ]
            bundled_libraries = [
                name
                for name in archive.namelist()
                if re.fullmatch(r"mysqlclient\.libs/libmariadb-[0-9a-f]+\.so\.3", name)
            ]
    except (KeyError, OSError, UnicodeError, zipfile.BadZipFile) as exc:
        raise ValueError("mysqlclient wheel contents are invalid") from exc
    if metadata.get("Name", "").lower() != "mysqlclient" or metadata.get("Version") != MYSQLCLIENT_VERSION:
        raise ValueError("mysqlclient wheel metadata name/version mismatch")
    if f"Tag: cp314-cp314-{EXPECTED_PLATFORM}" not in wheel_metadata or len(extension_names) != 1:
        raise ValueError("mysqlclient wheel contents or tag are invalid")
    if len(bundled_libraries) != 1:
        raise ValueError("mysqlclient wheel must contain exactly one bundled MariaDB library")
    bundled_name = bundled_libraries[0]
    bundled_soname = _read_wheel_elf_soname(wheel, bundled_name)
    if bundled_soname != Path(bundled_name).name:
        raise ValueError("bundled MariaDB library SONAME does not match its wheel name")
    _, extension_needed = _read_wheel_elf_dynamic(wheel, extension_names[0])
    if bundled_soname not in extension_needed:
        raise ValueError("mysqlclient extension is not mapped to the bundled MariaDB library")
    with zipfile.ZipFile(wheel) as archive:
        bundled_hash = hashlib.sha256(archive.read(bundled_name)).hexdigest()
    return {
        "mysqlclient_bundled_library_name": bundled_name,
        "mysqlclient_bundled_library_sha256": bundled_hash,
        "mysqlclient_bundled_library_soname": bundled_soname,
    }


def _tool_version(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
    return (result.stdout or result.stderr).strip().splitlines()[0][:160]


def build_wheelhouse(
    *,
    target_sha: str,
    lock_path: Path,
    wheelhouse: Path,
    python: Path,
    auditwheel: str,
    image_digest: str,
) -> Path:
    """Build, verify and atomically publish one target-bound wheelhouse."""

    if not _SHA_RE.fullmatch(target_sha):
        raise ValueError("target SHA must be 40 lowercase hex characters")
    lock_path = Path(lock_path).resolve(strict=True)
    wheelhouse = Path(wheelhouse)
    if wheelhouse.exists():
        raise ValueError("immutable wheelhouse target already exists")
    metadata = _assert_builder_environment(image_digest)
    libffi_devel = _tool_version(["rpm", "-q", "libffi-devel"])
    if libffi_devel != EXPECTED_LIBFFI_DEVEL:
        raise ValueError("builder libffi-devel package mismatch")
    connector_evidence = _validate_mariadb_connector_c(MARIADB_CONNECTOR_C_ROOT)
    metadata.update(
        {
            "auditwheel": _tool_version([auditwheel, "--version"]),
            "libffi_devel": libffi_devel,
            "pip": _tool_version([str(python), "-m", "pip", "--version"]),
            **connector_evidence,
        }
    )
    source_lock_sha256 = sha256(lock_path)
    wheelhouse.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".tmp-{target_sha}-", dir=wheelhouse.parent)
    )
    try:
        seed = temporary / "seed"
        final = temporary / "final"
        build = temporary / "build"
        seed.mkdir()
        final.mkdir()
        build.mkdir()
        cffi_sdist = _download_verified(
            CFFI_SDIST_URL,
            build / "cffi-2.1.1.tar.gz",
            CFFI_SDIST_SHA256,
        )
        _validate_cffi_source(cffi_sdist)
        mysqlclient_sdist = _download_verified(
            MYSQLCLIENT_SDIST_URL,
            build / "mysqlclient-2.2.8.tar.gz",
            MYSQLCLIENT_SDIST_SHA256,
        )
        _validate_mysqlclient_source(mysqlclient_sdist)
        setuptools_wheel = _download_verified(
            SETUPTOOLS_WHEEL_URL,
            build / "setuptools-80.9.0-py3-none-any.whl",
            SETUPTOOLS_WHEEL_SHA256,
        )
        build_venv = temporary / "build-venv"
        _run([str(python), "-m", "venv", str(build_venv)])
        build_python = build_venv / "bin" / "python"
        backend_lock = build / "setuptools-build.lock"
        backend_lock.write_text(
            f"setuptools=={SETUPTOOLS_VERSION} --hash=sha256:{SETUPTOOLS_WHEEL_SHA256}\n",
            encoding="utf-8",
        )
        _run(
            [
                str(build_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-index",
                "--find-links",
                str(setuptools_wheel.parent),
                "--only-binary",
                ":all:",
                "--require-hashes",
                "-r",
                str(backend_lock),
            ]
        )
        first = _build_cffi_once(build_python, auditwheel, cffi_sdist, build, label="one")
        second = _build_cffi_once(build_python, auditwheel, cffi_sdist, build, label="two")
        _validate_cffi_wheel(first)
        _validate_cffi_wheel(second)
        if first.name != second.name or first.read_bytes() != second.read_bytes():
            raise ValueError("cffi wheel build is not byte-for-byte reproducible")
        cffi_wheel = seed / first.name
        shutil.copy2(first, cffi_wheel)
        mysqlclient_first = _build_mysqlclient_once(
            build_python, auditwheel, mysqlclient_sdist, build, label="one"
        )
        mysqlclient_second = _build_mysqlclient_once(
            build_python, auditwheel, mysqlclient_sdist, build, label="two"
        )
        first_mysqlclient_evidence = _validate_mysqlclient_wheel(mysqlclient_first)
        second_mysqlclient_evidence = _validate_mysqlclient_wheel(mysqlclient_second)
        if first_mysqlclient_evidence != second_mysqlclient_evidence:
            raise ValueError("mysqlclient wheel metadata is not reproducible")
        if (
            mysqlclient_first.name != mysqlclient_second.name
            or mysqlclient_first.read_bytes() != mysqlclient_second.read_bytes()
        ):
            raise ValueError("mysqlclient wheel build is not byte-for-byte reproducible")
        mysqlclient_wheel = seed / mysqlclient_first.name
        shutil.copy2(mysqlclient_first, mysqlclient_wheel)
        install_lock = final / "requirements.install.lock"
        install_lock_text = replace_package_hashes(
            lock_path.read_text(encoding="utf-8"),
            package="cffi",
            version=CFFI_VERSION,
            required_source_hash=CFFI_SDIST_SHA256,
            wheel_hash=sha256(cffi_wheel),
        )
        install_lock.write_text(
            replace_package_hashes(
                install_lock_text,
                package="mysqlclient",
                version=MYSQLCLIENT_VERSION,
                required_source_hash=MYSQLCLIENT_SDIST_SHA256,
                wheel_hash=sha256(mysqlclient_wheel),
            ),
            encoding="utf-8",
        )
        http_status = build_http_ece_main(
            [
                "--wheel-dir",
                str(seed),
                "--lock",
                str(install_lock),
                "--source-date-epoch",
                str(SOURCE_DATE_EPOCH),
            ]
        )
        if http_status != 0:
            raise ValueError("http-ece wheel build failed")
        _run(
            [
                str(python),
                "-m",
                "pip",
                "download",
                "--disable-pip-version-check",
                "--no-deps",
                "--dest",
                str(final),
                "--find-links",
                str(seed),
                "--only-binary",
                ":all:",
                "--require-hashes",
                "-r",
                str(install_lock),
            ]
        )
        unexpected = [path.name for path in final.iterdir() if path != install_lock and path.suffix != ".whl"]
        if unexpected:
            raise ValueError(f"wheelhouse contains non-wheel artifacts: {unexpected}")
        verify_venv = temporary / "verify-venv"
        _run([str(python), "-m", "venv", str(verify_venv)])
        verify_python = verify_venv / "bin" / "python"
        _run(
            [
                str(verify_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-index",
                "--find-links",
                str(final),
                "--only-binary",
                ":all:",
                "--require-hashes",
                "-r",
                str(install_lock),
            ]
        )
        _run([str(verify_python), "-m", "pip", "check"])
        _run(
            [
                str(verify_python),
                "-c",
                "import MySQLdb; assert tuple(MySQLdb.version_info) >= (2, 2, 1)",
            ]
        )
        verifier = lock_path.parents[1] / "scripts" / "verify_locked_requirements.py"
        _run([str(verify_python), str(verifier), "--lock", str(lock_path)])
        metadata.update(
            {
                "cffi_sdist_sha256": CFFI_SDIST_SHA256,
                "cffi_wheel_sha256": sha256(cffi_wheel),
                "mysqlclient_sdist_sha256": MYSQLCLIENT_SDIST_SHA256,
                "mysqlclient_wheel_sha256": sha256(mysqlclient_wheel),
                **first_mysqlclient_evidence,
                "setuptools_version": SETUPTOOLS_VERSION,
                "setuptools_wheel_sha256": SETUPTOOLS_WHEEL_SHA256,
                "source_lock_sha256": source_lock_sha256,
                "target_sha": target_sha,
            }
        )
        (final / "builder-evidence.json").write_text(
            json.dumps(metadata, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        build_manifest(
            final,
            target_sha=target_sha,
            source_lock_sha256=source_lock_sha256,
        )
        os.replace(final, wheelhouse)
        return wheelhouse
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--auditwheel", default="auditwheel")
    parser.add_argument("--image-digest", required=True)
    args = parser.parse_args(argv)
    try:
        result = build_wheelhouse(
            target_sha=args.target_sha,
            lock_path=args.lock,
            wheelhouse=args.wheelhouse,
            python=args.python,
            auditwheel=args.auditwheel,
            image_digest=args.image_digest,
        )
        print(result)
        return 0
    except (
        OSError,
        ValueError,
        subprocess.SubprocessError,
        tarfile.TarError,
        urllib.error.URLError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
