#!/usr/bin/env python3
"""Verify that the running Python environment matches an exact requirements lock.

The verifier intentionally has no third-party dependencies.  Its JSON output is
an operational status record only; it does not echo lock lines, paths, or
installed-environment details.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import platform
import re
import sys
from pathlib import Path
from typing import Iterable, Mapping


LOCKED_REQUIREMENT = re.compile(
    r"^([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_. ,-]+\])?==([^\s;\\]+)"
)
_INCLUDE_DIRECTIVE = re.compile(r"^(?:-r|--requirement|-c|--constraint)(?:\s+|=)", re.I)
_EDITABLE_DIRECTIVE = re.compile(r"^(?:-e|--editable)(?:\s+|=)", re.I)
_HASH_ONLY = re.compile(r"^--hash(?:=|\s)", re.I)
_HASH_OPTION = re.compile(r"--hash(?:=|\s+)\S+", re.I)
_VCS_SCHEME = re.compile(r"(?:^|\s|@)(?:git|hg|svn|bzr)\+", re.I)
_URL_REFERENCE = re.compile(r"\s@\s*(?:https?|ftp|file)://", re.I)
_LOCAL_REFERENCE = re.compile(r"(?:^|\s)(?:file://|(?:\.\.?/)|/)", re.I)
_INLINE_COMMENT = re.compile(r"\s+#.*$")

# Fresh virtual environments may contain these packaging tools in addition to
# the project lock.  Nothing else is implicitly trusted.
BOOTSTRAP_ALLOWLIST = frozenset({"pip", "setuptools", "wheel"})


class LockParseError(ValueError):
    """Raised when a lock contains anything other than exact requirements."""


def canonicalize_name(value: str) -> str:
    """Return the PEP 503 form of a distribution name."""

    if not isinstance(value, str):
        raise TypeError("distribution name must be a string")
    name = re.sub(r"[-_.]+", "-", value).lower()
    if not name:
        raise ValueError("distribution name must not be empty")
    return name


def _logical_lines(text: str) -> Iterable[str]:
    """Join backslash continuations while retaining no comments or blanks."""

    buffer = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if buffer:
            buffer = f"{buffer} {line}"
        else:
            buffer = line
        if buffer.endswith("\\"):
            buffer = buffer[:-1].rstrip()
            continue
        yield buffer
        buffer = ""
    if buffer:
        yield buffer.rstrip("\\").rstrip()


def _reject_unsupported(line: str, line_number: int) -> None:
    lowered = line.lower()
    if _INCLUDE_DIRECTIVE.match(line):
        raise LockParseError(f"line {line_number}: recursive requirement includes are not allowed")
    if _EDITABLE_DIRECTIVE.match(line):
        raise LockParseError(f"line {line_number}: editable requirements are not allowed")
    if _VCS_SCHEME.search(line) or _URL_REFERENCE.search(line):
        raise LockParseError(f"line {line_number}: VCS and URL references are not allowed")
    if _LOCAL_REFERENCE.search(line) and (" @ " in line or lowered.startswith(("./", "../", "/", "file:"))):
        raise LockParseError(f"line {line_number}: local requirements are not allowed")


def parse_lock(text: str) -> dict[str, str]:
    """Parse exact ``name==version`` entries from lock text.

    Hash options and their backslash continuations are ignored.  A package may
    appear more than once only when all occurrences resolve to the same exact
    version after name canonicalization.
    """

    requirements: dict[str, str] = {}
    for line_number, line in enumerate(_logical_lines(text), start=1):
        # Standalone hash continuation lines are harmless lock metadata.
        if _HASH_ONLY.match(line):
            continue
        line = _INLINE_COMMENT.sub("", line).strip()
        if not line:
            continue
        _reject_unsupported(line, line_number)

        match = LOCKED_REQUIREMENT.match(line)
        if not match:
            if line.startswith(("-", "--")):
                raise LockParseError(f"line {line_number}: unsupported lock directive")
            raise LockParseError(f"line {line_number}: requirement is not exactly pinned")

        name = canonicalize_name(match.group(1))
        version = match.group(2)
        remainder = line[match.end() :].strip()
        if remainder:
            if remainder.startswith(";"):
                # Markers are allowed only because the requirement itself was
                # already matched by the exact-pin expression above.
                remainder = remainder[1:].strip()
                if not remainder:
                    raise LockParseError(f"line {line_number}: empty environment marker")
                # The marker expression is intentionally opaque to this
                # verifier.  Hash options may follow it on a continuation.
                remainder = ""
            else:
                remainder = _HASH_OPTION.sub("", remainder).strip()
            if remainder and not remainder.startswith("#"):
                raise LockParseError(f"line {line_number}: unsupported requirement options")

        previous = requirements.get(name)
        if previous is not None and previous != version:
            raise LockParseError(f"line {line_number}: conflicting versions for {name}")
        requirements[name] = version
    return requirements


def parse_lock_file(path: str | Path) -> dict[str, str]:
    """Read and parse a UTF-8 lock file."""

    return parse_lock(Path(path).read_text(encoding="utf-8"))


def _distribution_names(distributions: Iterable[object]) -> set[str]:
    names: set[str] = set()
    for distribution in distributions:
        package_metadata = getattr(distribution, "metadata", None)
        name = None
        if package_metadata is not None:
            try:
                name = package_metadata.get("Name")
            except AttributeError:
                name = None
        if not name:
            name = getattr(distribution, "name", None)
        if name:
            names.add(canonicalize_name(str(name)))
    return names


def verify_environment(
    requirements: Mapping[str, str],
    *,
    bootstrap_allowlist: Iterable[str] = BOOTSTRAP_ALLOWLIST,
) -> dict[str, object]:
    """Compare exact lock versions against installed distributions.

    Difference arrays contain canonical distribution names only, preventing
    versions, paths, URLs, or other environment data from entering the report.
    """

    expected = {canonicalize_name(name): str(version) for name, version in requirements.items()}
    installed_names = _distribution_names(metadata.distributions())
    missing: list[str] = []
    mismatched: list[str] = []
    for name, expected_version in expected.items():
        if name not in installed_names:
            missing.append(name)
            continue
        try:
            actual_version = metadata.version(name)
        except (KeyError, metadata.PackageNotFoundError):
            missing.append(name)
            continue
        if str(actual_version) != expected_version:
            mismatched.append(name)

    allowed = {canonicalize_name(name) for name in bootstrap_allowlist}
    unexpected = sorted(installed_names - set(expected) - allowed)
    missing.sort()
    mismatched.sort()
    return {
        "status": "ok" if not (missing or mismatched or unexpected) else "failed",
        "missing": missing,
        "mismatched": mismatched,
        "unexpected": unexpected,
    }


def verify_locked_environment(
    lock_path: str | Path,
    *,
    bootstrap_allowlist: Iterable[str] = BOOTSTRAP_ALLOWLIST,
) -> dict[str, object]:
    """Build the sanitized JSON-compatible lock verification report."""

    path = Path(lock_path)
    raw = path.read_bytes()
    requirements = parse_lock(raw.decode("utf-8"))
    result = verify_environment(requirements, bootstrap_allowlist=bootstrap_allowlist)
    return {
        "status": result["status"],
        "python": platform.python_version(),
        "lock_sha256": hashlib.sha256(raw).hexdigest(),
        "requirement_count": len(requirements),
        "missing": result["missing"],
        "mismatched": result["mismatched"],
        "unexpected": result["unexpected"],
    }


def _failure_report(lock_bytes: bytes | None) -> dict[str, object]:
    """Return the fixed schema used when parsing cannot reach environment checks."""

    return {
        "status": "failed",
        "python": platform.python_version(),
        "lock_sha256": hashlib.sha256(lock_bytes).hexdigest() if lock_bytes is not None else "",
        "requirement_count": 0,
        "missing": [],
        "mismatched": [],
        "unexpected": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify installed distributions against an exact lock")
    parser.add_argument("--lock", required=True, type=Path, help="path to the requirements lock")
    args = parser.parse_args(argv)
    raw: bytes | None = None
    try:
        raw = args.lock.read_bytes()
        report = verify_locked_environment(args.lock)
    except (OSError, UnicodeError, LockParseError) as exc:
        print(f"lock verification failed: {type(exc).__name__}", file=sys.stderr)
        print(json.dumps(_failure_report(raw), sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
