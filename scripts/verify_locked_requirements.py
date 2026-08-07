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
from typing import Iterable, Mapping, NamedTuple


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
_MARKER_VARIABLES = frozenset(
    {
        "dependency_groups",
        "extra",
        "extras",
        "implementation_name",
        "implementation_version",
        "os.name",
        "os_name",
        "platform_machine",
        "platform.machine",
        "platform_python_implementation",
        "platform.python_implementation",
        "platform_release",
        "platform_system",
        "platform_version",
        "platform.version",
        "python_full_version",
        "python_implementation",
        "python_version",
        "sys_platform",
        "sys.platform",
    }
)
_SYMBOLIC_MARKER_OPERATORS = ("===", "~=", "<=", "!=", "==", ">=", "<", ">")
_MARKER_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
_MARKER_HASH = re.compile(r"--hash(?:=|\s+)([^\s]+)", re.I)


class LockParseError(ValueError):
    """Raised when a lock contains anything other than exact requirements."""


class _MarkerToken(NamedTuple):
    kind: str
    value: str = ""


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


def _tokenize_marker(marker: str, line_number: int) -> list[_MarkerToken]:
    tokens: list[_MarkerToken] = []
    index = 0
    while index < len(marker):
        if marker[index].isspace():
            index += 1
            continue

        hash_match = _MARKER_HASH.match(marker, index)
        if hash_match:
            if index == 0 or not marker[index - 1].isspace():
                raise LockParseError(f"line {line_number}: marker hash requires leading whitespace")
            tokens.append(_MarkerToken("HASH"))
            index = hash_match.end()
            continue

        character = marker[index]
        if character in {"'", '"'}:
            quote = character
            index += 1
            value: list[str] = []
            while index < len(marker) and marker[index] != quote:
                if marker[index] == "\\":
                    run_start = index
                    while index < len(marker) and marker[index] == "\\":
                        index += 1
                    run_length = index - run_start
                    if index < len(marker) and marker[index] == quote and run_length % 2:
                        raise LockParseError(f"line {line_number}: backslash escapes marker delimiter")
                    value.extend("\\" * run_length)
                    continue
                value.append(marker[index])
                index += 1
            if index >= len(marker):
                raise LockParseError(f"line {line_number}: unterminated marker string")
            index += 1
            tokens.append(_MarkerToken("OPERAND", "".join(value)))
            continue

        if character == "(":
            tokens.append(_MarkerToken("LPAREN"))
            index += 1
            continue
        if character == ")":
            tokens.append(_MarkerToken("RPAREN"))
            index += 1
            continue

        operator = next(
            (candidate for candidate in _SYMBOLIC_MARKER_OPERATORS if marker.startswith(candidate, index)),
            None,
        )
        if operator:
            tokens.append(_MarkerToken("OPERATOR", operator))
            index += len(operator)
            continue

        identifier_match = _MARKER_IDENTIFIER.match(marker, index)
        if identifier_match:
            identifier = identifier_match.group(0)
            index = identifier_match.end()
            if identifier in _MARKER_VARIABLES:
                tokens.append(_MarkerToken("OPERAND", identifier))
            elif identifier == "and":
                tokens.append(_MarkerToken("AND"))
            elif identifier == "or":
                tokens.append(_MarkerToken("OR"))
            elif identifier == "in":
                tokens.append(_MarkerToken("IN"))
            elif identifier == "not":
                tokens.append(_MarkerToken("NOT"))
            else:
                raise LockParseError(f"line {line_number}: invalid marker identifier")
            continue

        raise LockParseError(f"line {line_number}: invalid environment marker token")
    return tokens


class _MarkerParser:
    def __init__(self, tokens: list[_MarkerToken], line_number: int) -> None:
        self.tokens = tokens
        self.line_number = line_number
        self.index = 0

    def parse(self) -> None:
        if not self.tokens:
            self._fail("empty environment marker")
        self._parse_or()
        while self._accept("HASH"):
            pass
        if self.index != len(self.tokens):
            self._fail("unsupported marker option or trailing token")

    def _parse_or(self) -> None:
        self._parse_and()
        while self._accept("OR"):
            self._parse_and()

    def _parse_and(self) -> None:
        self._parse_atom()
        while self._accept("AND"):
            self._parse_atom()

    def _parse_atom(self) -> None:
        if self._accept("LPAREN"):
            self._parse_or()
            self._expect("RPAREN", "unbalanced environment marker")
            return
        self._expect("OPERAND", "environment marker requires a quoted string or variable")
        self._parse_operator()
        self._expect("OPERAND", "environment marker requires a quoted string or variable")

    def _parse_operator(self) -> None:
        if self._accept("OPERATOR") or self._accept("IN"):
            return
        if self._accept("NOT"):
            self._expect("IN", "invalid environment marker operator")
            return
        self._fail("invalid environment marker operator")

    def _accept(self, kind: str) -> bool:
        if self.index < len(self.tokens) and self.tokens[self.index].kind == kind:
            self.index += 1
            return True
        return False

    def _expect(self, kind: str, message: str) -> None:
        if not self._accept(kind):
            self._fail(message)

    def _fail(self, message: str) -> None:
        raise LockParseError(f"line {self.line_number}: {message}")


def _validate_marker(marker: str, line_number: int) -> None:
    _MarkerParser(_tokenize_marker(marker, line_number), line_number).parse()


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
        _reject_unsupported(line.split(";", 1)[0].rstrip(), line_number)

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
                _validate_marker(remainder[1:], line_number)
                remainder = ""
            else:
                remainder = _HASH_OPTION.sub("", remainder).strip()
            if remainder and not remainder.startswith("#"):
                raise LockParseError(f"line {line_number}: unsupported requirement options")

        previous = requirements.get(name)
        if previous is not None and previous != version:
            raise LockParseError(f"line {line_number}: conflicting versions for {name}")
        requirements[name] = version
    if not requirements:
        raise LockParseError("lock contains no exact requirements")
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
