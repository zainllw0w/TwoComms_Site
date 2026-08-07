#!/usr/bin/env python3
"""Prepare an immutable release without changing the live application.

The switch/rollback phase is intentionally separate.  This module only runs
read-only source checks and builds isolated release artifacts, so an install or
application check failure cannot leave Passenger, the bot, or stable paths in a
partially updated state.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVIEWED_LOCK_SHA256 = "e7d03c919785fe20991a3b27d3228d50ffeafda6a8abbfd36419007f267bd575"
Command = Sequence[str | os.PathLike[str]]
Runner = Callable[..., "CommandResult"]


class ReleaseError(RuntimeError):
    """A release preparation gate failed."""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandFailure(ReleaseError):
    def __init__(self, command: Sequence[str], returncode: int, stderr: str = ""):
        self.command = tuple(command)
        self.returncode = returncode
        self.stderr = stderr
        rendered = " ".join(self.command)
        super().__init__(f"command failed ({returncode}): {rendered}")


@dataclass(frozen=True)
class ReleaseConfig:
    live_checkout: Path = Path("/home/qlknpodo/TWC/TwoComms_Site/twocomms")
    release_root: Path = Path("/home/qlknpodo/TWC/TwoComms_Site/releases")
    active_venv: Path = Path("/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14")
    active_static: Path = Path("/home/qlknpodo/TWC/TwoComms_Site/twocomms/staticfiles")
    system_python: Path = Path("/opt/alt/python314/bin/python3.14")
    deploy_lock: Path = Path("/home/qlknpodo/TWC/TwoComms_Site/releases/deploy.lock")
    evidence_root: Path = Path("/home/qlknpodo/TWC/TwoComms_Site/releases/evidence")
    wheelhouse_root: Path = Path("/home/qlknpodo/TWC/TwoComms_Site/releases/wheelhouse")
    reviewed_lock_sha256: str | None = REVIEWED_LOCK_SHA256


@dataclass(frozen=True)
class PreparedRelease:
    target_sha: str
    worktree: Path
    venv: Path
    static_root: Path
    wheelhouse: Path
    lock_sha256: str


def subprocess_runner(
    command: Command,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    argv = [os.fspath(part) for part in command]
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=dict(env) if env is not None else None,
        capture_output=True,
        text=True,
    )
    result = CommandResult(completed.returncode, completed.stdout, completed.stderr)
    if result.returncode:
        raise CommandFailure(argv, result.returncode, result.stderr)
    return result


def _run(
    run: Runner,
    command: Command,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    label: str = "command",
) -> CommandResult:
    try:
        result = run(command, cwd=cwd, env=env)
    except CommandFailure:
        raise
    except OSError as exc:
        raise ReleaseError(f"{label} could not start: {exc}") from exc
    if result.returncode:
        raise CommandFailure([os.fspath(part) for part in command], result.returncode, result.stderr)
    return result


def _stdout(run: Runner, command: Command, *, cwd: Path, label: str) -> str:
    return _run(run, command, cwd=cwd, label=label).stdout.strip()


def _validate_sha(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if not SHA_RE.fullmatch(normalized):
        raise ReleaseError(f"{label} must be a 40-character commit SHA")
    return normalized


def _acquire_deploy_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise ReleaseError("another deployment is already running") from exc
        return handle
    except Exception:
        handle.close()
        raise


def _manifest_and_wheelhouse(config: ReleaseConfig, target_sha: str) -> Path:
    wheelhouse = config.wheelhouse_root / target_sha
    manifest_path = wheelhouse / "manifest.sha256"
    if not manifest_path.is_file():
        raise ReleaseError("immutable wheelhouse manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseError("immutable wheelhouse manifest is invalid") from exc
    if manifest.get("target_sha") != target_sha or not isinstance(manifest.get("files"), dict):
        raise ReleaseError("immutable wheelhouse target binding is invalid")
    files: dict[str, str] = manifest["files"]
    listed = set(files)
    actual = {path.name for path in wheelhouse.iterdir() if path.name != manifest_path.name}
    if listed != actual or not listed:
        raise ReleaseError("immutable wheelhouse manifest file set is invalid")
    for name, expected in sorted(files.items()):
        if Path(name).name != name or not HEX_SHA256_RE.fullmatch(str(expected)):
            raise ReleaseError("immutable wheelhouse manifest contains an unsafe entry")
        artifact = wheelhouse / name
        if not artifact.is_file() or artifact.is_symlink():
            raise ReleaseError("immutable wheelhouse artifact is missing or not regular")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest != expected:
            raise ReleaseError(f"immutable wheelhouse hash mismatch for {name}")
    return wheelhouse


def _validate_static_artifacts(static_root: Path) -> None:
    manifest_candidates = (
        static_root / "staticfiles.json",
        static_root / "CACHE" / "manifest.json",
        static_root / "manifest.json",
    )
    if not any(path.is_file() and path.stat().st_size > 0 for path in manifest_candidates):
        raise ReleaseError("collectstatic produced no non-empty current manifest")
    if not any(path.is_file() and path.stat().st_size > 0 for path in static_root.rglob("*.html")):
        raise ReleaseError("compress produced no representative compressed page")


def _cleanup_owned(paths: Sequence[Path]) -> None:
    for path in paths:
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path)


def prepare(
    config: ReleaseConfig,
    target_sha: str,
    *,
    run: Runner = subprocess_runner,
    env: Mapping[str, str] | None = None,
) -> PreparedRelease:
    """Run every pre-switch gate and return isolated release paths."""

    target_sha = _validate_sha(target_sha, label="target SHA")
    live = config.live_checkout
    if not live.is_dir():
        raise ReleaseError("live checkout does not exist")
    lock_handle = _acquire_deploy_lock(config.deploy_lock)
    worktree = config.release_root / "worktrees" / target_sha
    venv = config.release_root / "venvs" / target_sha
    static_root = config.release_root / "static" / target_sha
    created: list[Path] = []
    try:
        status = _stdout(run, ("git", "status", "--porcelain", "--untracked-files=no"), cwd=live, label="git status")
        if status:
            raise ReleaseError("live checkout has tracked changes")
        branch = _stdout(run, ("git", "symbolic-ref", "--short", "HEAD"), cwd=live, label="git branch")
        if branch != "main":
            raise ReleaseError("live checkout must be on main")
        live_sha = _validate_sha(
            _stdout(run, ("git", "rev-parse", "HEAD"), cwd=live, label="live SHA"),
            label="live SHA",
        )
        _run(run, ("git", "fetch", "origin", "main"), cwd=live, label="git fetch")
        origin_sha = _validate_sha(
            _stdout(run, ("git", "rev-parse", "origin/main"), cwd=live, label="origin SHA"),
            label="origin SHA",
        )
        if origin_sha != target_sha:
            raise ReleaseError("target SHA is not the fetched origin/main")
        _run(run, ("git", "merge-base", "--is-ancestor", live_sha, target_sha), cwd=live, label="fast-forward check")
        wheelhouse = _manifest_and_wheelhouse(config, target_sha)
        if worktree.exists() or venv.exists() or static_root.exists():
            raise ReleaseError("immutable release target already exists")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        venv.parent.mkdir(parents=True, exist_ok=True)
        static_root.parent.mkdir(parents=True, exist_ok=True)
        _run(run, ("git", "worktree", "add", "--detach", str(worktree), target_sha), cwd=live, label="git worktree")
        worktree.mkdir(parents=True, exist_ok=True)
        created.append(worktree)
        _run(run, (os.fspath(config.system_python), "-m", "venv", str(venv)), cwd=worktree, label="create venv")
        venv.mkdir(parents=True, exist_ok=True)
        created.append(venv)
        python = venv / "bin" / "python"
        requirements = worktree / "twocomms" / "requirements.lock"
        if not requirements.is_file():
            requirements = worktree / "requirements.lock"
        if not requirements.is_file():
            raise ReleaseError("staged requirements.lock is missing")
        lock_sha = hashlib.sha256(requirements.read_bytes()).hexdigest()
        if config.reviewed_lock_sha256 is not None:
            expected_lock_sha = str(config.reviewed_lock_sha256).lower()
            if not HEX_SHA256_RE.fullmatch(expected_lock_sha) or lock_sha != expected_lock_sha:
                raise ReleaseError("staged requirements.lock does not match the reviewed lock digest")
        command_env = dict(env or os.environ)
        command_env["PYTHONNOUSERSITE"] = "1"
        command_env["STATIC_ROOT"] = os.fspath(static_root)
        _run(
            run,
            (
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheelhouse),
                "--only-binary",
                ":all:",
                "--require-hashes",
                "-r",
                str(requirements),
            ),
            cwd=worktree,
            env=command_env,
            label="locked dependency install",
        )
        _run(run, (str(python), "-m", "pip", "check"), cwd=worktree, env=command_env, label="pip check")
        verifier = worktree / "scripts" / "verify_locked_requirements.py"
        _run(
            run,
            (str(python), str(verifier), "--lock", str(requirements)),
            cwd=worktree,
            env=command_env,
            label="strict lock verification",
        )
        _run(
            run,
            (
                str(python),
                "-c",
                "import socket; socket.getaddrinfo = lambda *args, **kwargs: "
                "(_ for _ in ()).throw(AssertionError('network disabled'))",
            ),
            cwd=worktree,
            env=command_env,
            label="no-network baseline",
        )
        manage = worktree / "twocomms" / "manage.py"
        if not manage.is_file():
            manage = worktree / "manage.py"
        _run(
            run,
            (str(python), str(manage), "test", "--settings=test_settings", "management.tests_dependency_runtime"),
            cwd=worktree,
            env=command_env,
            label="runtime contracts",
        )
        _run(
            run,
            (str(python), str(manage), "check", "--deploy"),
            cwd=worktree,
            env=command_env,
            label="Django deploy check",
        )
        _run(
            run,
            (str(python), str(manage), "migrate", "--check", "--noinput"),
            cwd=worktree,
            env=command_env,
            label="migration drift check",
        )
        created.append(static_root)
        _run(
            run,
            (str(python), str(manage), "collectstatic", "--noinput", "--clear", "--verbosity", "0"),
            cwd=worktree,
            env=command_env,
            label="collectstatic",
        )
        _run(
            run,
            (str(python), str(manage), "compress", "--force", "--verbosity", "0"),
            cwd=worktree,
            env=command_env,
            label="compress",
        )
        _validate_static_artifacts(static_root)
        return PreparedRelease(target_sha, worktree, venv, static_root, wheelhouse, lock_sha)
    except Exception:
        if worktree in created:
            try:
                _run(
                    run,
                    ("git", "worktree", "remove", "--force", str(worktree)),
                    cwd=live,
                    label="staged worktree cleanup",
                )
            except ReleaseError:
                # Preserve the original gate failure; the next run will reject
                # the retained target rather than touching an unknown tree.
                pass
        _cleanup_owned([path for path in created if path != worktree])
        raise
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


def _default_config() -> ReleaseConfig:
    return ReleaseConfig()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="prepare a verified immutable release")
    parser.add_argument("--target-sha", required=True)
    args = parser.parse_args(argv)
    prepared = prepare(_default_config(), args.target_sha)
    print(
        json.dumps(
            {
                "status": "prepared",
                "target_sha": prepared.target_sha,
                "lock_sha256": prepared.lock_sha256,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
