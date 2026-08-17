#!/usr/bin/env python3
"""Prune explicitly selected immutable release directories under the deploy lock."""

from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import shutil
import stat
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence


DEFAULT_ACTIVE_VENV = Path(
    "/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14"
)
DEFAULT_ACTIVE_STATIC = Path(
    "/home/qlknpodo/TWC/TwoComms_Site/twocomms/staticfiles"
)
DEFAULT_DEPLOY_LOCK = Path(
    "/home/qlknpodo/TWC/TwoComms_Site/releases/deploy.lock"
)


class PruneError(RuntimeError):
    """Release-artifact pruning could not be proven safe."""


@dataclass(frozen=True)
class PruneConfig:
    active_venv: Path
    active_static: Path
    deploy_lock: Path
    allowed_roots: tuple[Path, ...]


@dataclass(frozen=True)
class PruneResult:
    applied: bool
    active_target: Path
    candidates: tuple[Path, ...]


@dataclass(frozen=True)
class _PathIdentity:
    device: int
    inode: int


@dataclass(frozen=True)
class _AllowedRoot:
    path: Path
    resolved: Path
    identity: _PathIdentity


@dataclass(frozen=True)
class _Candidate:
    path: Path
    resolved: Path
    root: _AllowedRoot
    identity: _PathIdentity


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _identity(path: Path) -> _PathIdentity:
    metadata = path.lstat()
    return _PathIdentity(metadata.st_dev, metadata.st_ino)


def _overlaps(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


@contextmanager
def _deployment_lock(path: Path) -> Iterator[None]:
    lock_path = _absolute(path)
    if lock_path.is_symlink():
        raise PruneError("deploy lock must not be a symlink")
    if lock_path.parent.is_symlink() or not lock_path.parent.is_dir():
        raise PruneError("deploy lock parent must be a real directory")

    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise PruneError(f"deploy lock could not be opened: {exc}") from exc

    handle = os.fdopen(descriptor, "a+", encoding="utf-8")
    try:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise PruneError("deploy lock must be a regular file")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise PruneError("another deployment is already running") from exc
            raise PruneError(f"deploy lock could not be acquired: {exc}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _active_target(active_path: Path, *, label: str) -> tuple[Path, _PathIdentity]:
    active_path = _absolute(active_path)
    if not active_path.is_symlink():
        raise PruneError(f"{label} must be a symlink")
    active_identity = _identity(active_path)
    try:
        target = active_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PruneError(f"{label} symlink target is not resolvable") from exc
    if not target.is_dir():
        raise PruneError(f"{label} symlink target must be a directory")
    return target, active_identity


def _active_bindings(config: PruneConfig) -> tuple[tuple[Path, Path, _PathIdentity, str], ...]:
    bindings = []
    for path, label in (
        (config.active_venv, "active venv"),
        (config.active_static, "active static"),
    ):
        target, identity = _active_target(path, label=label)
        bindings.append((_absolute(path), target, identity, label))
    return tuple(bindings)


def _allowed_roots(paths: Sequence[Path]) -> tuple[_AllowedRoot, ...]:
    if not paths:
        raise PruneError("at least one allowed release root is required")

    roots: list[_AllowedRoot] = []
    seen: set[Path] = set()
    for configured in paths:
        path = _absolute(configured)
        if path.is_symlink():
            raise PruneError(f"allowed release root must not be a symlink: {path}")
        if not path.is_dir():
            raise PruneError(f"allowed release root must be a real directory: {path}")
        resolved = path.resolve(strict=True)
        if resolved == Path(resolved.anchor):
            raise PruneError("filesystem root cannot be an allowed release root")
        if resolved in seen:
            raise PruneError(f"duplicate allowed release root: {resolved}")
        if any(_overlaps(resolved, root.resolved) for root in roots):
            raise PruneError("allowed release roots must not overlap")
        seen.add(resolved)
        roots.append(_AllowedRoot(path, resolved, _identity(path)))
    return tuple(roots)


def _matching_root(candidate: Path, roots: Sequence[_AllowedRoot]) -> _AllowedRoot:
    direct = [root for root in roots if candidate.parent == root.path]
    if direct:
        return direct[0]

    for root in roots:
        try:
            candidate.relative_to(root.path)
        except ValueError:
            continue
        raise PruneError(
            f"candidate must be a direct child of an allowed release root: {candidate}"
        )
    raise PruneError(f"candidate is outside every allowed release root: {candidate}")


def _reject_lock_candidate_overlap(deploy_lock: Path, candidates: Sequence[Path]) -> None:
    lock_path = _absolute(deploy_lock)
    for configured in candidates:
        candidate = _absolute(configured)
        if _overlaps(candidate, lock_path):
            raise PruneError(f"candidate overlaps the deploy lock: {candidate}")


def _validate_candidates(
    paths: Sequence[Path],
    *,
    roots: Sequence[_AllowedRoot],
    active_bindings: Sequence[tuple[Path, Path, _PathIdentity, str]],
    deploy_lock: Path,
) -> tuple[_Candidate, ...]:
    if not paths:
        raise PruneError("at least one release artifact candidate is required")

    lock_path = _absolute(deploy_lock)
    candidates: list[_Candidate] = []
    seen: set[Path] = set()
    for configured in paths:
        path = _absolute(configured)
        if path.is_symlink():
            raise PruneError(f"candidate must not be a symlink: {path}")
        if not path.is_dir():
            raise PruneError(f"candidate must be a real directory: {path}")
        if os.path.ismount(path):
            raise PruneError(f"candidate must not be a mount point: {path}")

        root = _matching_root(path, roots)
        resolved = path.resolve(strict=True)
        if resolved.parent != root.resolved:
            raise PruneError(f"candidate escapes its allowed release root: {path}")
        if resolved in seen:
            raise PruneError(f"duplicate release artifact candidate: {resolved}")
        for active_path, active_target, _active_identity, label in active_bindings:
            if _overlaps(resolved, active_target) or _overlaps(path, active_path):
                raise PruneError(f"candidate overlaps the {label}: {path}")
        if _overlaps(path, lock_path) or _overlaps(resolved, lock_path):
            raise PruneError(f"candidate overlaps the deploy lock: {path}")

        for previous in candidates:
            if _overlaps(resolved, previous.resolved):
                raise PruneError("release artifact candidates must not overlap")
        seen.add(resolved)
        candidates.append(_Candidate(path, resolved, root, _identity(path)))
    return tuple(candidates)


def _assert_unchanged(
    *,
    config: PruneConfig,
    active_bindings: Sequence[tuple[Path, Path, _PathIdentity, str]],
    candidate: _Candidate,
) -> None:
    current_bindings = _active_bindings(config)
    for (_, active_target, active_identity, label), (
        _current_path,
        current_target,
        current_active_identity,
        _current_label,
    ) in zip(active_bindings, current_bindings):
        if current_target != active_target or current_active_identity != active_identity:
            raise PruneError(f"{label} changed while pruning was locked")
    if candidate.root.path.is_symlink() or not candidate.root.path.is_dir():
        raise PruneError("allowed release root changed while pruning was locked")
    if _identity(candidate.root.path) != candidate.root.identity:
        raise PruneError("allowed release root changed while pruning was locked")
    if candidate.path.is_symlink() or not candidate.path.is_dir():
        raise PruneError("candidate changed while pruning was locked")
    if _identity(candidate.path) != candidate.identity:
        raise PruneError("candidate changed while pruning was locked")
    if candidate.path.resolve(strict=True) != candidate.resolved:
        raise PruneError("candidate changed while pruning was locked")
    if candidate.path.parent.resolve(strict=True) != candidate.root.resolved:
        raise PruneError("candidate escaped its allowed release root")


def prune(
    config: PruneConfig,
    candidates: Sequence[Path],
    *,
    apply: bool = False,
) -> PruneResult:
    """Validate a prune batch and remove it only when ``apply`` is explicit."""
    _reject_lock_candidate_overlap(config.deploy_lock, candidates)
    with _deployment_lock(config.deploy_lock):
        active_bindings = _active_bindings(config)
        active_target = active_bindings[0][1]
        roots = _allowed_roots(config.allowed_roots)
        validated = _validate_candidates(
            candidates,
            roots=roots,
            active_bindings=active_bindings,
            deploy_lock=config.deploy_lock,
        )
        if apply:
            if not shutil.rmtree.avoids_symlink_attacks:
                raise PruneError("platform does not provide symlink-safe directory pruning")
            for candidate in validated:
                _assert_unchanged(
                    config=config,
                    active_bindings=active_bindings,
                    candidate=candidate,
                )
            for candidate in validated:
                _assert_unchanged(
                    config=config,
                    active_bindings=active_bindings,
                    candidate=candidate,
                )
                shutil.rmtree(candidate.path)

        return PruneResult(
            applied=apply,
            active_target=active_target,
            candidates=tuple(candidate.resolved for candidate in validated),
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="validate release artifact paths and optionally prune them"
    )
    parser.add_argument("candidates", nargs="+", type=Path)
    parser.add_argument(
        "--allowed-root",
        action="append",
        required=True,
        type=Path,
        dest="allowed_roots",
        help="real directory whose direct children may be pruned; repeat as needed",
    )
    parser.add_argument("--active-venv", type=Path, default=DEFAULT_ACTIVE_VENV)
    parser.add_argument("--active-static", type=Path, default=DEFAULT_ACTIVE_STATIC)
    parser.add_argument("--deploy-lock", type=Path, default=DEFAULT_DEPLOY_LOCK)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="remove the validated directories; omission is a dry run",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    config = PruneConfig(
        active_venv=args.active_venv,
        active_static=args.active_static,
        deploy_lock=args.deploy_lock,
        allowed_roots=tuple(args.allowed_roots),
    )
    try:
        result = prune(config, args.candidates, apply=args.apply)
    except PruneError as exc:
        print(f"[prune_release_artifacts] ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "active_target": os.fspath(result.active_target),
                "candidates": [os.fspath(path) for path in result.candidates],
                "mode": "apply" if result.applied else "dry-run",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
