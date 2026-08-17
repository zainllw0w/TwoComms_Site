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
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

try:
    from scripts.verify_locked_requirements import LockParseError, parse_lock_file
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from verify_locked_requirements import LockParseError, parse_lock_file


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LEASE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
LEASE_RECEIPT_RE = re.compile(r"(?:^|\s)lease_id=([A-Za-z0-9._:-]{1,128})(?:\s|$)")
REVIEWED_LOCK_SHA256 = "b14d7a834c815ce4fff8fa08f784323fb506063990520a46020fbbf1bf5eaad0"
MAX_MAINTENANCE_WAIT_SECONDS = 300
MAINTENANCE_TIMEOUT_GRACE_SECONDS = 15
LIVE_BRANCH = "main"
CLOUDLINUX_STARTUP_FILE = "twocomms/wsgi.py"
CLOUDLINUX_GENERATED_ENTRYPOINT = "passenger_wsgi.py"
FAILURE_PHASES = frozenset(
    {
        "preflight",
        "maintenance_activation",
        "passenger_stop",
        "checkout_transition",
        "passenger_start",
        "site_health",
        "maintenance_release",
        "daemon_ensure",
        "bot_health",
    }
)
Command = Sequence[str | os.PathLike[str]]
Runner = Callable[..., "CommandResult"]


class ReleaseError(RuntimeError):
    """A release preparation gate failed."""


class MaintenanceActivationError(ReleaseError):
    """Activation failed while an owned lease may still be durable."""

    def __init__(self, message: str, *, owned_lease_id: str | None = None):
        self.owned_lease_id = owned_lease_id
        super().__init__(message)


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
    cloudlinux_python_wrapper: Path = Path("/usr/share/l.v.e-manager/utils/python_wrapper")
    cloudlinux_set_env_helper: Path = Path("/usr/share/l.v.e-manager/utils/set_env_vars.py")
    database_probe_iterations: int = 100
    deploy_lock: Path = Path("/home/qlknpodo/TWC/TwoComms_Site/releases/deploy.lock")
    evidence_root: Path = Path("/home/qlknpodo/TWC/TwoComms_Site/releases/evidence")
    wheelhouse_root: Path = Path("/home/qlknpodo/TWC/TwoComms_Site/releases/wheelhouse")
    reviewed_lock_sha256: str | None = REVIEWED_LOCK_SHA256
    cloudlinux_user: str = "qlknpodo"
    cloudlinux_app_root: str = "TWC/TwoComms_Site/twocomms"
    maintenance_path: Path | None = None
    maintenance_file: Path | None = None
    maintenance_duration_seconds: int = 15 * 60
    maintenance_wait_seconds: int = 180
    maintenance_timeout_seconds: int = 210
    command_timeout_seconds: int = 120
    site_health_url: str = "https://twocomms.shop/healthz/"
    bot_health_url: str = "https://management.twocomms.shop/bot/health/"
    http_timeout_seconds: int = 15
    health_retry_attempts: int = 3
    health_retry_delay_seconds: float = 1.0
    health_deadline_seconds: int = 60


@dataclass(frozen=True)
class PreparedRelease:
    target_sha: str
    worktree: Path
    venv: Path
    static_root: Path
    wheelhouse: Path
    lock_sha256: str
    previous_sha: str = ""


@dataclass(frozen=True)
class SwitchResult:
    target_sha: str
    previous_sha: str
    evidence_path: Path
    rolled_back: bool = False


def subprocess_runner(
    command: Command,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> CommandResult:
    argv = [os.fspath(part) for part in command]
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ReleaseError(
            f"command timed out after {timeout} seconds: {' '.join(argv)}"
        ) from exc
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
    timeout: float | None = None,
) -> CommandResult:
    try:
        result = run(command, cwd=cwd, env=env, timeout=timeout)
    except CommandFailure:
        raise
    except OSError as exc:
        raise ReleaseError(f"{label} could not start: {exc}") from exc
    if result.returncode:
        raise CommandFailure([os.fspath(part) for part in command], result.returncode, result.stderr)
    return result


def _stdout(
    run: Runner,
    command: Command,
    *,
    cwd: Path,
    label: str,
    timeout: float | None = None,
) -> str:
    return _run(run, command, cwd=cwd, label=label, timeout=timeout).stdout.strip()


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


def acquire_deploy_lock(path: Path):
    """Acquire the process-wide release lock for the whole switch boundary."""
    return _acquire_deploy_lock(path)


def maintenance_path(config: ReleaseConfig) -> Path:
    """Return the daemon's durable lease marker without reading its contents."""
    configured = config.maintenance_path or config.maintenance_file
    if configured is not None:
        return Path(configured)
    return _manage_path(config.live_checkout).parent / "tmp" / "ig_bot_maintenance.json"


def _manifest_and_wheelhouse(config: ReleaseConfig, target_sha: str) -> Path:
    wheelhouse_root = Path(config.wheelhouse_root)
    if wheelhouse_root.is_symlink() or not wheelhouse_root.is_dir():
        raise ReleaseError("immutable wheelhouse root must be a real directory")
    wheelhouse = config.wheelhouse_root / target_sha
    if wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise ReleaseError("immutable wheelhouse target must be a real directory")
    try:
        wheelhouse.resolve().relative_to(wheelhouse_root.resolve())
    except ValueError as exc:
        raise ReleaseError("immutable wheelhouse target escapes wheelhouse root") from exc
    manifest_path = wheelhouse / "manifest.sha256"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ReleaseError("immutable wheelhouse manifest must be a regular file")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseError("immutable wheelhouse manifest is invalid") from exc
    if (
        manifest.get("target_sha") != target_sha
        or not HEX_SHA256_RE.fullmatch(str(manifest.get("source_lock_sha256", "")))
        or not isinstance(manifest.get("files"), dict)
    ):
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


def _install_requirements(wheelhouse: Path, canonical_requirements: Path) -> Path:
    """Return the manifest-bound install lock after semantic equivalence proof."""

    install_requirements = wheelhouse / "requirements.install.lock"
    if not install_requirements.is_file():
        raise ReleaseError("immutable wheelhouse install lock is missing")
    manifest_path = wheelhouse / "manifest.sha256"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_source_lock = str(manifest["source_lock_sha256"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReleaseError("immutable wheelhouse install lock provenance is invalid") from exc
    canonical_digest = hashlib.sha256(canonical_requirements.read_bytes()).hexdigest()
    if expected_source_lock != canonical_digest:
        raise ReleaseError("immutable wheelhouse install lock source digest mismatch")
    try:
        canonical = parse_lock_file(canonical_requirements)
        install = parse_lock_file(install_requirements)
    except (OSError, UnicodeError, LockParseError) as exc:
        raise ReleaseError("immutable wheelhouse install lock is invalid") from exc
    if install != canonical:
        raise ReleaseError("immutable wheelhouse install lock changes package versions")
    return install_requirements


def _staged_environment(
    config: ReleaseConfig,
    static_root: Path,
    environment: Mapping[str, str] | None,
) -> dict[str, str]:
    command_env = dict(environment or os.environ)
    for key in (
        "VIRTUAL_ENV",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONEXECUTABLE",
        "__PYVENV_LAUNCHER__",
    ):
        command_env.pop(key, None)
    if not str(command_env.get("DJANGO_ENV_FILE") or "").strip():
        candidates = (
            config.live_checkout / ".env.production",
            config.live_checkout / ".env",
            config.live_checkout.parent / ".env.production",
            config.live_checkout.parent / ".env",
        )
        for candidate in candidates:
            if candidate.is_file() and not candidate.is_symlink():
                command_env["DJANGO_ENV_FILE"] = os.fspath(candidate.resolve())
                break
    command_env["PYTHONNOUSERSITE"] = "1"
    command_env["DJANGO_SETTINGS_MODULE"] = "twocomms.production_settings"
    command_env["DJANGO_ENV"] = "production"
    command_env["TWC_RELEASE_STATIC_ROOT"] = os.fspath(static_root)
    # The release wheel carries its own hash-pinned Connector/C.  Inheriting
    # or injecting CloudLinux's system provider would load two libmariadb
    # implementations into one worker and reintroduce MySQLdb 2006 failures.
    command_env.pop("LD_PRELOAD", None)
    return command_env


def _bind_cloudlinux_runtime(
    *,
    venv: Path,
    active_venv: Path,
    system_python: Path,
    python_wrapper: Path,
    set_env_helper: Path,
) -> None:
    """Make an immutable venv use the registered CloudLinux app environment."""

    version = active_venv.name
    if not re.fullmatch(r"\d+\.\d+", version):
        raise ReleaseError("active CloudLinux venv must end in a Python major.minor version")
    if system_python.name != f"python{version}":
        raise ReleaseError("system Python does not match the registered CloudLinux version")
    for path, label in (
        (python_wrapper, "CloudLinux Python wrapper"),
        (set_env_helper, "CloudLinux environment helper"),
    ):
        if path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
            raise ReleaseError(f"{label} must be a regular file")

    bin_dir = venv / "bin"
    activate = bin_dir / "activate"
    python = bin_dir / "python"
    python_aliases = (bin_dir / "python3", bin_dir / f"python{version}")
    if (
        activate.is_symlink()
        or not activate.is_file()
        or not python.is_symlink()
        or any(not alias.is_symlink() for alias in python_aliases)
    ):
        raise ReleaseError("fresh release venv has an unexpected runtime layout")
    activation = activate.read_text(encoding="utf-8")
    staged_path = os.fspath(venv)
    path_occurrences = activation.count(staged_path)
    if path_occurrences < 1 or path_occurrences > 4:
        raise ReleaseError("fresh release venv activation path is invalid")
    if any(character in os.fspath(active_venv) for character in ("'", "\n", "\r")):
        raise ReleaseError("active CloudLinux venv path is unsafe")

    activation = activation.replace(staged_path, os.fspath(active_venv))
    activate.write_text(activation, encoding="utf-8")
    python.unlink()
    python.symlink_to(python_wrapper)
    for alias in python_aliases:
        alias.unlink()
        alias.symlink_to("python")
    versioned_binary = bin_dir / f"python{version}_bin"
    versioned_binary.unlink(missing_ok=True)
    versioned_binary.symlink_to(system_python)
    environment_helper = bin_dir / "set_env_vars.py"
    environment_helper.unlink(missing_ok=True)
    environment_helper.symlink_to(set_env_helper)
    _assert_cloudlinux_runtime_binding(
        venv=venv,
        active_venv=active_venv,
        system_python=system_python,
        python_wrapper=python_wrapper,
        set_env_helper=set_env_helper,
    )


def _assert_cloudlinux_runtime_binding(
    *,
    venv: Path,
    active_venv: Path,
    system_python: Path,
    python_wrapper: Path,
    set_env_helper: Path,
) -> None:
    """Verify the immutable venv still resolves through the registered runtime."""

    version = active_venv.name
    if not re.fullmatch(r"\d+\.\d+", version):
        raise ReleaseError("CloudLinux runtime binding has an invalid Python version")
    if system_python.name != f"python{version}":
        raise ReleaseError("CloudLinux runtime binding has a mismatched system Python")
    for path, label in (
        (python_wrapper, "CloudLinux Python wrapper"),
        (set_env_helper, "CloudLinux environment helper"),
    ):
        if path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
            raise ReleaseError(f"CloudLinux runtime binding has an invalid {label}")

    bin_dir = venv / "bin"
    activate = bin_dir / "activate"
    expected_links = {
        "python": os.fspath(python_wrapper),
        "python3": "python",
        f"python{version}": "python",
        f"python{version}_bin": os.fspath(system_python),
        "set_env_vars.py": os.fspath(set_env_helper),
    }
    if not bin_dir.is_dir() or activate.is_symlink() or not activate.is_file():
        raise ReleaseError("CloudLinux runtime binding has an invalid activation script")
    activation = activate.read_text(encoding="utf-8")
    if os.fspath(active_venv) not in activation:
        raise ReleaseError("CloudLinux runtime binding activation path is missing")
    if os.fspath(venv) in activation:
        raise ReleaseError("CloudLinux runtime binding retains the staged activation path")
    for name, expected in expected_links.items():
        path = bin_dir / name
        if not path.is_symlink() or os.readlink(path) != expected:
            raise ReleaseError(f"CloudLinux runtime binding link is invalid: {name}")


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
        status = _stdout(
            run,
            ("git", "status", "--porcelain", "--untracked-files=no"),
            cwd=live,
            label="git status",
            timeout=config.command_timeout_seconds,
        )
        if status:
            raise ReleaseError("live checkout has tracked changes")
        branch = _stdout(
            run,
            ("git", "symbolic-ref", "--short", "HEAD"),
            cwd=live,
            label="git branch",
            timeout=config.command_timeout_seconds,
        )
        if branch != "main":
            raise ReleaseError("live checkout must be on main")
        live_sha = _validate_sha(
            _stdout(
                run,
                ("git", "rev-parse", "HEAD"),
                cwd=live,
                label="live SHA",
                timeout=config.command_timeout_seconds,
            ),
            label="live SHA",
        )
        _run(
            run,
            ("git", "fetch", "origin", "main"),
            cwd=live,
            label="git fetch",
            timeout=config.command_timeout_seconds,
        )
        origin_sha = _validate_sha(
            _stdout(
                run,
                ("git", "rev-parse", "origin/main"),
                cwd=live,
                label="origin SHA",
                timeout=config.command_timeout_seconds,
            ),
            label="origin SHA",
        )
        if origin_sha != target_sha:
            raise ReleaseError("target SHA is not the fetched origin/main")
        _run(
            run,
            ("git", "merge-base", "--is-ancestor", live_sha, target_sha),
            cwd=live,
            label="fast-forward check",
            timeout=config.command_timeout_seconds,
        )
        wheelhouse = _manifest_and_wheelhouse(config, target_sha)
        if worktree.exists() or venv.exists() or static_root.exists():
            raise ReleaseError("immutable release target already exists")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        venv.parent.mkdir(parents=True, exist_ok=True)
        static_root.parent.mkdir(parents=True, exist_ok=True)
        # Register the path before invoking Git so a partial worktree creation
        # is still removed when the command fails after creating its directory.
        created.append(worktree)
        _run(
            run,
            ("git", "worktree", "add", "--detach", str(worktree), target_sha),
            cwd=live,
            label="git worktree",
            timeout=config.command_timeout_seconds,
        )
        worktree.mkdir(parents=True, exist_ok=True)
        _run(
            run,
            (os.fspath(config.system_python), "-m", "venv", str(venv)),
            cwd=worktree,
            label="create venv",
            timeout=config.command_timeout_seconds,
        )
        venv.mkdir(parents=True, exist_ok=True)
        created.append(venv)
        _bind_cloudlinux_runtime(
            venv=venv,
            active_venv=config.active_venv,
            system_python=config.system_python,
            python_wrapper=config.cloudlinux_python_wrapper,
            set_env_helper=config.cloudlinux_set_env_helper,
        )
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
        install_requirements = _install_requirements(wheelhouse, requirements)
        command_env = _staged_environment(config, static_root, env)
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
                str(install_requirements),
            ),
            cwd=worktree,
            env=command_env,
            label="locked dependency install",
            timeout=config.command_timeout_seconds,
        )
        _run(
            run,
            (str(python), "-m", "pip", "check"),
            cwd=worktree,
            env=command_env,
            label="pip check",
            timeout=config.command_timeout_seconds,
        )
        verifier = worktree / "scripts" / "verify_locked_requirements.py"
        _run(
            run,
            (str(python), str(verifier), "--lock", str(requirements)),
            cwd=worktree,
            env=command_env,
            label="strict lock verification",
            timeout=config.command_timeout_seconds,
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
            timeout=config.command_timeout_seconds,
        )
        manage = worktree / "twocomms" / "manage.py"
        if not manage.is_file():
            manage = worktree / "manage.py"
        database_probe = _database_probe_path(worktree)
        _run(
            run,
            (
                str(python),
                os.fspath(database_probe),
                "--iterations",
                str(_database_probe_iterations(config)),
            ),
            cwd=worktree,
            env=command_env,
            label="typed production database probe",
            timeout=config.command_timeout_seconds,
        )
        _run(
            run,
            (str(python), str(manage), "test", "--settings=test_settings", "management.tests_dependency_runtime"),
            cwd=worktree,
            env=command_env,
            label="runtime contracts",
            timeout=config.command_timeout_seconds,
        )
        _run(
            run,
            (str(python), str(manage), "check", "--deploy"),
            cwd=worktree,
            env=command_env,
            label="Django deploy check",
            timeout=config.command_timeout_seconds,
        )
        _run(
            run,
            (str(python), str(manage), "migrate", "--check", "--noinput"),
            cwd=worktree,
            env=command_env,
            label="migration drift check",
            timeout=config.command_timeout_seconds,
        )
        created.append(static_root)
        _run(
            run,
            (str(python), str(manage), "collectstatic", "--noinput", "--clear", "--verbosity", "0"),
            cwd=worktree,
            env=command_env,
            label="collectstatic",
            timeout=config.command_timeout_seconds,
        )
        _run(
            run,
            (str(python), str(manage), "compress", "--force", "--verbosity", "0"),
            cwd=worktree,
            env=command_env,
            label="compress",
            timeout=config.command_timeout_seconds,
        )
        _validate_static_artifacts(static_root)
        return PreparedRelease(
            target_sha=target_sha,
            worktree=worktree,
            venv=venv,
            static_root=static_root,
            wheelhouse=wheelhouse,
            lock_sha256=lock_sha,
            previous_sha=live_sha,
        )
    except Exception:
        if worktree in created:
            try:
                _run(
                    run,
                    ("git", "worktree", "remove", "--force", str(worktree)),
                    cwd=live,
                    label="staged worktree cleanup",
                    timeout=config.command_timeout_seconds,
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


@dataclass
class _SwitchedPath:
    active: Path
    retained: Path | None


def _path_present(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _read_lease_id(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    lease_id = payload.get("lease_id") if isinstance(payload, dict) else None
    normalized = str(lease_id or "")
    return normalized if LEASE_ID_RE.fullmatch(normalized) else None


def _lease_id_from_receipt(stdout: str) -> str | None:
    match = LEASE_RECEIPT_RE.search(str(stdout or ""))
    return match.group(1) if match else None


def _manage_path(checkout: Path) -> Path:
    direct = checkout / "manage.py"
    return direct if direct.is_file() else checkout / "twocomms" / "manage.py"


def _runtime_root(config: ReleaseConfig) -> Path:
    manage = _manage_path(config.live_checkout)
    if not manage.is_file():
        raise ReleaseError("live manage.py is missing")
    root = manage.parent.resolve()
    if not root.is_dir() or not (root / "manage.py").is_file():
        raise ReleaseError("live runtime root is invalid")
    return root


def _maintenance_environment(config: ReleaseConfig) -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "twocomms.production_settings",
            "DJANGO_ENV": "production",
            "TWC_IG_RUNTIME_ROOT": os.fspath(_runtime_root(config)),
        }
    )
    environment.pop("LD_PRELOAD", None)
    return environment


def _prepared_manage_path(config: ReleaseConfig, prepared: PreparedRelease) -> Path:
    worktree = _validate_release_path(config, prepared.worktree, label="prepared worktree")
    # Keep the repository's supported nested/direct layouts. The prepared
    # boundary below rejects every untracked file before this path executes.
    manage = _manage_path(worktree)
    try:
        resolved_manage = manage.resolve(strict=True)
        resolved_manage.relative_to(worktree)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise ReleaseError("prepared release manage.py is outside its worktree") from exc
    if manage.is_symlink() or not manage.is_file():
        raise ReleaseError("prepared release manage.py must be a regular file")
    return manage


def _maintenance_wait_seconds(config: ReleaseConfig) -> int:
    try:
        wait_seconds = int(config.maintenance_wait_seconds)
    except (TypeError, ValueError) as exc:
        raise ReleaseError("maintenance lock wait must be an integer") from exc
    if not 0 <= wait_seconds <= MAX_MAINTENANCE_WAIT_SECONDS:
        raise ReleaseError(
            "maintenance lock wait must be between 0 and "
            f"{MAX_MAINTENANCE_WAIT_SECONDS} seconds"
        )
    return wait_seconds


def _maintenance_activation_timeout(config: ReleaseConfig) -> int:
    try:
        timeout_seconds = int(config.maintenance_timeout_seconds)
    except (TypeError, ValueError) as exc:
        raise ReleaseError("maintenance timeout must be an integer") from exc
    required = _maintenance_wait_seconds(config) + MAINTENANCE_TIMEOUT_GRACE_SECONDS
    if timeout_seconds < required:
        raise ReleaseError(
            "maintenance timeout must exceed maintenance lock wait by at least "
            f"{MAINTENANCE_TIMEOUT_GRACE_SECONDS} seconds"
        )
    return timeout_seconds


def _maintenance_command(
    config: ReleaseConfig,
    prepared: PreparedRelease,
    *arguments: str,
) -> tuple[str, ...]:
    # Structural validation is repeated at command construction to narrow the
    # interval in which a prepared path could be replaced before execution.
    manage = _prepared_manage_path(config, prepared)
    return (
        os.fspath(prepared.venv / "bin" / "python"),
        os.fspath(manage),
        "run_instagram_bot",
        *arguments,
    )


def _daemon_command(config: ReleaseConfig, *arguments: str) -> tuple[str, ...]:
    return (
        os.fspath(config.active_venv / "bin" / "python"),
        os.fspath(_manage_path(config.live_checkout)),
        "run_instagram_bot",
        *arguments,
    )


def _release_maintenance(
    config: ReleaseConfig,
    prepared: PreparedRelease,
    lease_id: str,
    *,
    run: Runner,
    tolerate_failure: bool = False,
) -> bool:
    if not LEASE_ID_RE.fullmatch(str(lease_id or "")):
        raise ReleaseError("maintenance lease receipt is invalid")
    try:
        _run(
            run,
            _maintenance_command(config, prepared, "--maintenance-off", lease_id),
            cwd=_prepared_manage_path(config, prepared).parent,
            env=_maintenance_environment(config),
            label="maintenance release",
            timeout=config.maintenance_timeout_seconds,
        )
        return True
    except ReleaseError:
        if tolerate_failure:
            return False
        raise


def _activate_maintenance(
    config: ReleaseConfig,
    prepared: PreparedRelease,
    *,
    run: Runner,
) -> str:
    lease_marker = maintenance_path(config)
    requested_id = f"deploy-{uuid.uuid4().hex}"
    result: CommandResult | None = None
    activation_error: ReleaseError | None = None
    activation_timeout = _maintenance_activation_timeout(config)
    wait_seconds = _maintenance_wait_seconds(config)
    try:
        result = _run(
            run,
            _maintenance_command(
                config,
                prepared,
                "--maintenance-on",
                str(max(30, int(config.maintenance_duration_seconds))),
                "--maintenance-wait-seconds",
                str(wait_seconds),
                "--maintenance-lease-id",
                requested_id,
            ),
            cwd=_prepared_manage_path(config, prepared).parent,
            env=_maintenance_environment(config),
            label="maintenance activation",
            timeout=activation_timeout,
        )
    except ReleaseError as exc:
        activation_error = exc

    receipt_id = _lease_id_from_receipt(result.stdout) if result is not None else None
    durable_id = _read_lease_id(lease_marker)
    if activation_error is not None:
        # A timeout may happen after the command atomically writes the lease.
        # Only the pre-authenticated token may be used for cleanup; a changed
        # marker with any other token belongs to a concurrent owner.
        if durable_id == requested_id:
            released = _release_maintenance(
                config,
                prepared,
                requested_id,
                run=run,
                tolerate_failure=True,
            )
            if not released:
                raise MaintenanceActivationError(
                    "maintenance activation failed and owned-lease cleanup failed",
                    owned_lease_id=requested_id,
                ) from activation_error
        raise activation_error

    if receipt_id != requested_id:
        if durable_id == requested_id:
            released = _release_maintenance(
                config,
                prepared,
                requested_id,
                run=run,
                tolerate_failure=True,
            )
            if not released:
                raise MaintenanceActivationError(
                    "maintenance activation returned an unauthenticated lease receipt; "
                    "owned-lease cleanup failed",
                    owned_lease_id=requested_id,
                )
        raise ReleaseError("maintenance activation returned an unauthenticated lease receipt")
    if durable_id != requested_id:
        released = _release_maintenance(
            config,
            prepared,
            requested_id,
            run=run,
            tolerate_failure=True,
        )
        if not released:
            raise MaintenanceActivationError(
                "maintenance lease receipt does not match the durable marker; "
                "owned-lease cleanup failed",
                owned_lease_id=requested_id,
            )
        raise ReleaseError("maintenance lease receipt does not match the durable marker")
    return requested_id


def _cloudlinux_command(config: ReleaseConfig, action: str) -> tuple[str, ...]:
    if action not in {"start", "stop"}:
        raise ReleaseError("unsupported CloudLinux action")
    return (
        "cloudlinux-selector",
        action,
        "--json",
        "--interpreter",
        "python",
        "--user",
        config.cloudlinux_user,
        "--app-root",
        config.cloudlinux_app_root,
    )


def _cloudlinux_set_startup_command(config: ReleaseConfig) -> tuple[str, ...]:
    return (
        "cloudlinux-selector",
        "set",
        "--json",
        "--interpreter",
        "python",
        "--user",
        config.cloudlinux_user,
        "--app-root",
        config.cloudlinux_app_root,
        "--startup-file",
        CLOUDLINUX_STARTUP_FILE,
    )


def _restore_cloudlinux_generated_entrypoint(
    config: ReleaseConfig,
    expected_sha: str,
    *,
    run: Runner,
) -> None:
    expected_sha = _validate_sha(expected_sha, label="expected live SHA")
    if _live_sha(config, run=run) != expected_sha:
        raise ReleaseError("cannot restore Passenger entrypoint from an unexpected live SHA")
    tracked_status = _stdout(
        run,
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=config.live_checkout,
        label="Passenger generated entrypoint status",
        timeout=config.command_timeout_seconds,
    )
    if not tracked_status:
        return
    status_prefix = _stdout(
        run,
        ("git", "rev-parse", "--show-prefix"),
        cwd=config.live_checkout,
        label="Passenger generated entrypoint status prefix",
        timeout=config.command_timeout_seconds,
    ).strip("/")
    expected_statuses = {f"M {CLOUDLINUX_GENERATED_ENTRYPOINT}"}
    if status_prefix:
        expected_statuses.add(f"M {status_prefix}/{CLOUDLINUX_GENERATED_ENTRYPOINT}")
    if tracked_status not in expected_statuses:
        raise ReleaseError(
            "Passenger entrypoint cleanup refused unexpected tracked drift"
        )
    _run(
        run,
        (
            "git",
            "restore",
            "--source",
            expected_sha,
            "--worktree",
            "--",
            CLOUDLINUX_GENERATED_ENTRYPOINT,
        ),
        cwd=config.live_checkout,
        label="Passenger generated entrypoint restore",
        timeout=config.command_timeout_seconds,
    )
    remaining_status = _stdout(
        run,
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=config.live_checkout,
        label="Passenger entrypoint restore verification",
        timeout=config.command_timeout_seconds,
    )
    if remaining_status:
        raise ReleaseError("Passenger generated entrypoint restore left tracked drift")


def _start_passenger(
    config: ReleaseConfig,
    expected_sha: str,
    *,
    run: Runner,
    label: str,
) -> None:
    try:
        _run(
            run,
            _cloudlinux_set_startup_command(config),
            cwd=config.live_checkout,
            label=f"{label} startup file",
            timeout=config.command_timeout_seconds,
        )
        _run(
            run,
            _cloudlinux_command(config, "start"),
            cwd=config.live_checkout,
            label=label,
            timeout=config.command_timeout_seconds,
        )
    except Exception:
        try:
            _restore_cloudlinux_generated_entrypoint(config, expected_sha, run=run)
        except Exception as restore_error:
            raise ReleaseError(
                f"{label} failed and Passenger entrypoint cleanup failed"
            ) from restore_error
        raise
    _restore_cloudlinux_generated_entrypoint(config, expected_sha, run=run)


def _validate_release_path(config: ReleaseConfig, path: Path, *, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(config.release_root.resolve())
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise ReleaseError(f"{label} is outside the immutable release root") from exc
    if not resolved.is_dir() or path.is_symlink():
        raise ReleaseError(f"{label} must be a real release directory")
    return resolved


def _assert_prepared_release_boundary(
    config: ReleaseConfig,
    prepared: PreparedRelease,
    *,
    run: Runner,
) -> None:
    worktree = _validate_release_path(config, prepared.worktree, label="prepared worktree")
    _prepared_manage_path(config, prepared)
    _assert_cloudlinux_runtime_binding(
        venv=prepared.venv,
        active_venv=config.active_venv,
        system_python=config.system_python,
        python_wrapper=config.cloudlinux_python_wrapper,
        set_env_helper=config.cloudlinux_set_env_helper,
    )
    head = _stdout(
        run,
        ("git", "rev-parse", "HEAD"),
        cwd=worktree,
        label="prepared release HEAD",
        timeout=config.command_timeout_seconds,
    )
    if head != prepared.target_sha:
        raise ReleaseError("prepared worktree HEAD differs from the target SHA")
    tracked_status = _stdout(
        run,
        ("git", "status", "--porcelain", "--untracked-files=all"),
        cwd=worktree,
        label="prepared release tracked status",
        timeout=config.command_timeout_seconds,
    )
    if tracked_status:
        raise ReleaseError("prepared worktree has tracked or untracked changes")
    ref = _stdout(
        run,
        ("git", "rev-parse", "--abbrev-ref", "HEAD"),
        cwd=worktree,
        label="prepared release ref",
        timeout=config.command_timeout_seconds,
    )
    if ref != "HEAD":
        raise ReleaseError("prepared worktree must be detached")


def _atomic_switch_path(active: Path, target: Path, retained: Path) -> _SwitchedPath:
    active.parent.mkdir(parents=True, exist_ok=True)
    retained.parent.mkdir(parents=True, exist_ok=True)
    temporary_link = active.parent / f".{active.name}.switch-{uuid.uuid4().hex}"
    old_path: Path | None = None
    try:
        os.symlink(os.fspath(target), temporary_link, target_is_directory=True)
        if _path_present(active):
            if _path_present(retained):
                raise ReleaseError(f"retained rollback target already exists: {retained}")
            if active.is_symlink():
                link_target = os.readlink(active)
                if not os.path.isabs(link_target):
                    link_target = os.path.relpath(
                        os.path.abspath(os.path.join(os.fspath(active.parent), link_target)),
                        start=os.fspath(retained.parent),
                    )
                os.symlink(link_target, retained, target_is_directory=True)
            else:
                os.replace(active, retained)
            old_path = retained
        os.replace(temporary_link, active)
        return _SwitchedPath(active=active, retained=old_path)
    except Exception:
        temporary_link.unlink(missing_ok=True)
        if old_path is not None and _path_present(old_path):
            if not _path_present(active):
                os.replace(old_path, active)
            elif old_path.is_symlink():
                old_path.unlink(missing_ok=True)
        raise


def _restore_switched_path(state: _SwitchedPath) -> None:
    if _path_present(state.active):
        if state.active.is_dir() and not state.active.is_symlink():
            raise ReleaseError(f"refusing to replace unexpected real directory: {state.active}")
        state.active.unlink()
    if state.retained is not None:
        if not _path_present(state.retained):
            raise ReleaseError(f"retained rollback target is missing: {state.retained}")
        os.replace(state.retained, state.active)


def _write_switch_evidence(
    config: ReleaseConfig,
    prepared: PreparedRelease,
    *,
    status: str,
    rolled_back: bool,
    original_error: Exception | None = None,
    rollback_errors: Sequence[Exception] = (),
    health_summary: Mapping[str, object] | None = None,
    failure_phase: str = "",
    rollback_needed: bool = False,
    maintenance_lease_retained: bool = False,
) -> Path:
    if failure_phase and failure_phase not in FAILURE_PHASES:
        raise ReleaseError("release evidence contains an unsupported failure phase")
    rollback_needed = bool(rollback_needed and original_error is not None)
    config.evidence_root.mkdir(parents=True, exist_ok=True)
    created_at = int(time.time())
    evidence_path = config.evidence_root / (
        f"release-{prepared.target_sha}-{created_at}-{uuid.uuid4().hex}.json"
    )
    payload = {
        "version": 1,
        "status": status,
        "target_sha": prepared.target_sha,
        "previous_sha": prepared.previous_sha,
        "lock_sha256": prepared.lock_sha256,
        "rolled_back": bool(rolled_back),
        "failure_phase": failure_phase,
        "rollback_needed": rollback_needed,
        "rollback_status": (
            "not_needed"
            if not rollback_needed
            else "complete"
            if rolled_back and not rollback_errors
            else "incomplete"
        ),
        "maintenance_lease_retained": bool(maintenance_lease_retained),
        "original_error": type(original_error).__name__ if original_error else "",
        "rollback_errors": sorted({type(error).__name__ for error in rollback_errors}),
        "created_at": created_at,
    }
    if health_summary:
        queues = health_summary.get("queues") if isinstance(health_summary, dict) else None
        if isinstance(queues, dict):
            payload["health"] = {
                "status": str(health_summary.get("status") or ""),
                "queues": {
                    key: int(queues.get(key) or 0)
                    for key in (
                        "dangerous_backlog",
                        "inbound_pending",
                        "reply_pending",
                        "notification_unresolved",
                        "analysis_pending",
                        "recovery_unresolved",
                        "analysis_failed",
                    )
                    if key in queues
                },
            }
    descriptor = os.open(evidence_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as evidence_file:
            json.dump(payload, evidence_file, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            evidence_file.write("\n")
            evidence_file.flush()
            os.fsync(evidence_file.fileno())
    except Exception:
        evidence_path.unlink(missing_ok=True)
        raise
    return evidence_path


def _live_sha(config: ReleaseConfig, *, run: Runner) -> str:
    return _validate_sha(
        _stdout(
            run,
            ("git", "rev-parse", "HEAD"),
            cwd=config.live_checkout,
            label="live SHA",
            timeout=config.command_timeout_seconds,
        ),
        label="live SHA",
    )


def _assert_live_checkout_boundary(
    config: ReleaseConfig,
    expected_sha: str,
    *,
    run: Runner,
) -> None:
    tracked_status = _stdout(
        run,
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=config.live_checkout,
        label="live tracked status",
        timeout=config.command_timeout_seconds,
    )
    if tracked_status:
        raise ReleaseError("live checkout has tracked worktree changes")
    branch = _stdout(
        run,
        ("git", "symbolic-ref", "--short", "HEAD"),
        cwd=config.live_checkout,
        label="live branch",
        timeout=config.command_timeout_seconds,
    )
    if branch != LIVE_BRANCH:
        raise ReleaseError(f"live checkout branch drifted from {LIVE_BRANCH}")
    if _live_sha(config, run=run) != expected_sha:
        raise ReleaseError("prepared release is stale relative to the live checkout")


def _assert_active_target(active: Path, expected: Path, *, label: str) -> None:
    try:
        active.lstat()
    except FileNotFoundError as exc:
        raise ReleaseError(f"{label} symlink is missing") from exc
    if not active.is_symlink() or active.resolve(strict=True) != expected.resolve(strict=True):
        raise ReleaseError(f"{label} does not point at the prepared release")


def _requirements_path(checkout: Path) -> Path:
    direct = checkout / "requirements.lock"
    return direct if direct.is_file() else checkout / "twocomms" / "requirements.lock"


def _verifier_path(checkout: Path) -> Path:
    direct = checkout / "scripts" / "verify_locked_requirements.py"
    return direct if direct.is_file() else checkout.parent / "scripts" / "verify_locked_requirements.py"


def _database_probe_path(checkout: Path) -> Path:
    probe = checkout / "scripts" / "verify_production_database.py"
    if probe.is_symlink() or not probe.is_file():
        raise ReleaseError("production database probe is missing")
    return probe


def _database_probe_iterations(config: ReleaseConfig) -> int:
    value = config.database_probe_iterations
    if not isinstance(value, int) or isinstance(value, bool) or not (1 <= value <= 1000):
        raise ReleaseError("database probe iterations must be between 1 and 1000")
    return value


def _cloudlinux_probe_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.pop("LD_PRELOAD", None)
    environment["DJANGO_SETTINGS_MODULE"] = "twocomms.production_settings"
    environment["DJANGO_ENV"] = "production"
    return environment


def _run_active_database_probe(config: ReleaseConfig, *, run: Runner) -> None:
    _run(
        run,
        (
            os.fspath(config.active_venv / "bin" / "python"),
            os.fspath(_database_probe_path(config.live_checkout)),
            "--iterations",
            str(_database_probe_iterations(config)),
        ),
        cwd=config.live_checkout,
        env=_cloudlinux_probe_environment(),
        label="active production database probe",
        timeout=config.command_timeout_seconds,
    )


def _http_health_command(
    config: ReleaseConfig,
    url: str,
    *,
    require_queues: bool = False,
) -> tuple[str, ...]:
    script = (
        "import json,sys,urllib.request\n"
        "r=urllib.request.urlopen(sys.argv[1],timeout=float(sys.argv[2]))\n"
        "p=json.load(r)\n"
        "queues=p.get('queues') or {}\n"
        "if r.status != 200 or p.get('status') != 'ok' or (\n"
        "    sys.argv[3] == '1' and (\n"
        "        queues.get('available') is not True or\n"
        "        queues.get('dangerous_backlog') != 0\n"
        "    )\n"
        "):\n"
        "    raise SystemExit('health check failed')"
        "\n"
        "print(json.dumps({'status': p.get('status'), 'queues': queues, "
        "'analysis_failed': queues.get('analysis_failed', 0)}, sort_keys=True))"
    )
    return (
        os.fspath(config.active_venv / "bin" / "python"),
        "-c",
        script,
        url,
        str(max(1, int(config.http_timeout_seconds))),
        "1" if require_queues else "0",
    )


def _verify_release_health(
    config: ReleaseConfig,
    prepared: PreparedRelease,
    *,
    run: Runner,
    include_bot: bool,
) -> dict:
    if _live_sha(config, run=run) != prepared.target_sha:
        raise ReleaseError("live checkout did not reach the prepared target SHA")
    _assert_active_target(config.active_venv, prepared.venv, label="active venv")
    _assert_active_target(config.active_static, prepared.static_root, label="active static root")
    requirements = _requirements_path(config.live_checkout)
    if not requirements.is_file():
        raise ReleaseError("live requirements.lock is missing")
    if hashlib.sha256(requirements.read_bytes()).hexdigest() != prepared.lock_sha256:
        raise ReleaseError("live requirements.lock differs from the prepared release")
    python = config.active_venv / "bin" / "python"
    manage = _manage_path(config.live_checkout)
    _run(
        run,
        (os.fspath(python), "-m", "pip", "check"),
        cwd=config.live_checkout,
        label="active pip check",
        timeout=config.command_timeout_seconds,
    )
    _run(
        run,
        (
            os.fspath(python),
            os.fspath(_verifier_path(config.live_checkout)),
            "--lock",
            os.fspath(requirements),
        ),
        cwd=config.live_checkout,
        label="active lock verification",
        timeout=config.command_timeout_seconds,
    )
    _run_active_database_probe(config, run=run)
    _run(
        run,
        (os.fspath(python), os.fspath(manage), "check", "--deploy"),
        cwd=config.live_checkout,
        label="active Django check",
        timeout=config.command_timeout_seconds,
    )
    _validate_static_artifacts(config.active_static)
    health_command = _http_health_command(
        config,
        config.bot_health_url if include_bot else config.site_health_url,
        require_queues=include_bot,
    )
    attempts = max(1, int(config.health_retry_attempts))
    deadline = time.monotonic() + max(1.0, float(config.health_deadline_seconds))
    last_error: Exception | None = None
    for attempt in range(attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            health_result = _run(
                run,
                health_command,
                cwd=config.live_checkout,
                label="bot health" if include_bot else "site health",
                timeout=max(1.0, min(float(config.http_timeout_seconds + 5), remaining)),
            )
            try:
                summary = json.loads(health_result.stdout or "{}")
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ReleaseError("health check returned invalid summary") from exc
            if not isinstance(summary, dict):
                raise ReleaseError("health check returned an invalid summary object")
            return summary
        except ReleaseError as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                raise
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        delay = min(max(0.0, float(config.health_retry_delay_seconds)), remaining)
        if delay:
            time.sleep(delay)
    if last_error is not None:
        raise last_error
    raise ReleaseError("health check deadline expired")


def _restore_checkout(config: ReleaseConfig, prepared: PreparedRelease, *, run: Runner) -> None:
    branch = _stdout(
        run,
        ("git", "symbolic-ref", "--short", "HEAD"),
        cwd=config.live_checkout,
        label="live rollback branch",
        timeout=config.command_timeout_seconds,
    )
    if branch != LIVE_BRANCH:
        raise ReleaseError(f"live checkout branch drifted from {LIVE_BRANCH} during rollback")
    current_sha = _live_sha(config, run=run)
    if current_sha not in {prepared.previous_sha, prepared.target_sha}:
        raise ReleaseError("live checkout moved outside the owned release transition")

    def assert_clean_before_rollback_mutation() -> None:
        tracked_status = _stdout(
            run,
            ("git", "status", "--porcelain", "--untracked-files=no"),
            cwd=config.live_checkout,
            label="live rollback tracked status",
            timeout=config.command_timeout_seconds,
        )
        if tracked_status:
            raise ReleaseError("live checkout has tracked worktree changes during rollback")

    def assert_target_snapshot_before_restore() -> None:
        commands = (
            ("git", "diff", "--quiet", prepared.target_sha, "--", "."),
            ("git", "diff", "--cached", "--quiet", prepared.target_sha, "--", "."),
        )
        for command in commands:
            try:
                _run(
                    run,
                    command,
                    cwd=config.live_checkout,
                    label="live rollback target snapshot",
                    timeout=config.command_timeout_seconds,
                )
            except CommandFailure as exc:
                if exc.returncode == 1:
                    raise ReleaseError(
                        "live checkout has tracked worktree changes during rollback"
                    ) from exc
                raise

    if current_sha == prepared.target_sha:
        assert_clean_before_rollback_mutation()
        _run(
            run,
            (
                "git",
                "update-ref",
                "refs/heads/main",
                prepared.previous_sha,
                prepared.target_sha,
            ),
            cwd=config.live_checkout,
            label="checkout ref rollback",
            timeout=config.command_timeout_seconds,
        )
        assert_target_snapshot_before_restore()
    else:
        assert_clean_before_rollback_mutation()
    _run(
        run,
        (
            "git",
            "restore",
            "--source",
            prepared.previous_sha,
            "--staged",
            "--worktree",
            "--",
            ".",
        ),
        cwd=config.live_checkout,
        label="checkout tree rollback",
        timeout=config.command_timeout_seconds,
    )
    if _live_sha(config, run=run) != prepared.previous_sha:
        raise ReleaseError("checkout rollback did not restore the previous SHA")


def switch(
    config: ReleaseConfig,
    prepared: PreparedRelease,
    *,
    run: Runner = subprocess_runner,
) -> SwitchResult:
    """Atomically activate a prepared release and roll back every failed boundary."""

    target_sha = _validate_sha(prepared.target_sha, label="target SHA")
    previous_sha = _validate_sha(prepared.previous_sha, label="previous SHA")
    if target_sha == previous_sha:
        raise ReleaseError("target SHA must differ from the live SHA")
    if not HEX_SHA256_RE.fullmatch(prepared.lock_sha256):
        raise ReleaseError("prepared lock digest is invalid")
    _validate_release_path(config, prepared.worktree, label="prepared worktree")
    venv = _validate_release_path(config, prepared.venv, label="prepared venv")
    static_root = _validate_release_path(config, prepared.static_root, label="prepared static root")
    _validate_static_artifacts(static_root)

    lock_handle = acquire_deploy_lock(config.deploy_lock)
    lease_id: str | None = None
    stop_attempted = False
    stop_succeeded = False
    start_attempted = False
    passenger_running = True
    checkout_transition_attempted = False
    switched_paths: list[_SwitchedPath] = []
    failure_phase = "preflight"
    try:
        _assert_prepared_release_boundary(config, prepared, run=run)
        _assert_live_checkout_boundary(config, previous_sha, run=run)
        failure_phase = "maintenance_activation"
        lease_id = _activate_maintenance(config, prepared, run=run)
        stop_attempted = True
        failure_phase = "passenger_stop"
        _run(
            run,
            _cloudlinux_command(config, "stop"),
            cwd=config.live_checkout,
            label="Passenger stop",
            timeout=config.command_timeout_seconds,
        )
        stop_succeeded = True
        passenger_running = False
        checkout_transition_attempted = True
        failure_phase = "checkout_transition"
        _run(
            run,
            ("git", "merge", "--ff-only", target_sha),
            cwd=config.live_checkout,
            label="live fast-forward",
            timeout=config.command_timeout_seconds,
        )
        if _live_sha(config, run=run) != target_sha:
            raise ReleaseError("live fast-forward did not reach the prepared target")
        retained_root = config.release_root / "retained" / previous_sha
        switched_paths.append(
            _atomic_switch_path(config.active_venv, venv, retained_root / "venv")
        )
        switched_paths.append(
            _atomic_switch_path(config.active_static, static_root, retained_root / "static")
        )
        _run_active_database_probe(config, run=run)
        failure_phase = "passenger_start"
        start_attempted = True
        _start_passenger(
            config,
            target_sha,
            run=run,
            label="Passenger start",
        )
        passenger_running = True
        _assert_live_checkout_boundary(config, target_sha, run=run)
        failure_phase = "site_health"
        _verify_release_health(config, prepared, run=run, include_bot=False)
        failure_phase = "maintenance_release"
        _release_maintenance(config, prepared, lease_id, run=run)
        lease_id = None
        failure_phase = "daemon_ensure"
        _run(
            run,
            _daemon_command(config, "--ensure"),
            cwd=config.live_checkout,
            env=_maintenance_environment(config),
            label="daemon ensure",
            timeout=config.command_timeout_seconds,
        )
        failure_phase = "bot_health"
        bot_health_summary = _verify_release_health(config, prepared, run=run, include_bot=True)
        evidence_path = _write_switch_evidence(
            config,
            prepared,
            status="activated",
            rolled_back=False,
            health_summary=bot_health_summary,
        )
        return SwitchResult(target_sha, previous_sha, evidence_path)
    except Exception as original_error:
        rollback_errors: list[Exception] = []
        if lease_id is None:
            owned_lease_id = getattr(original_error, "owned_lease_id", None)
            if isinstance(owned_lease_id, str) and LEASE_ID_RE.fullmatch(owned_lease_id):
                lease_id = owned_lease_id
        must_restore_runtime = bool(stop_attempted)
        can_restore_runtime = must_restore_runtime
        if must_restore_runtime and lease_id is None:
            try:
                lease_id = _activate_maintenance(config, prepared, run=run)
            except Exception as exc:
                rollback_errors.append(exc)
                can_restore_runtime = False
        if can_restore_runtime and stop_succeeded and (passenger_running or start_attempted):
            try:
                _run(
                    run,
                    _cloudlinux_command(config, "stop"),
                    cwd=config.live_checkout,
                    label="partial Passenger stop",
                    timeout=config.command_timeout_seconds,
                )
                passenger_running = False
            except Exception as exc:
                rollback_errors.append(exc)
                can_restore_runtime = False
        if can_restore_runtime:
            for state in reversed(switched_paths):
                try:
                    _restore_switched_path(state)
                except Exception as exc:
                    rollback_errors.append(exc)
                    can_restore_runtime = False
                    break
        if can_restore_runtime and checkout_transition_attempted:
            try:
                _restore_checkout(config, prepared, run=run)
            except Exception as exc:
                rollback_errors.append(exc)
                can_restore_runtime = False
        if can_restore_runtime and must_restore_runtime:
            try:
                _start_passenger(
                    config,
                    previous_sha,
                    run=run,
                    label="Passenger rollback start",
                )
                passenger_running = True
                _assert_live_checkout_boundary(config, previous_sha, run=run)
            except Exception as exc:
                rollback_errors.append(exc)
                can_restore_runtime = False
        if lease_id is not None and can_restore_runtime:
            released = _release_maintenance(
                config,
                prepared,
                lease_id,
                run=run,
                tolerate_failure=True,
            )
            if released:
                lease_id = None
            else:
                rollback_errors.append(ReleaseError("owned maintenance lease cleanup failed"))
                can_restore_runtime = False
        if can_restore_runtime and must_restore_runtime and passenger_running and lease_id is None:
            try:
                _run(
                    run,
                    _daemon_command(config, "--ensure"),
                    cwd=config.live_checkout,
                    env=_maintenance_environment(config),
                    label="previous daemon ensure",
                    timeout=config.command_timeout_seconds,
                )
            except Exception as exc:
                rollback_errors.append(exc)
                can_restore_runtime = False
        try:
            _write_switch_evidence(
                config,
                prepared,
                status="failed",
                rolled_back=must_restore_runtime and can_restore_runtime,
                original_error=original_error,
                rollback_errors=rollback_errors,
                failure_phase=failure_phase,
                rollback_needed=must_restore_runtime,
                maintenance_lease_retained=lease_id is not None,
            )
        except Exception as exc:
            rollback_errors.append(exc)
        if rollback_errors:
            raise ReleaseError(
                f"release failed with {type(original_error).__name__}; rollback errors: "
                + ", ".join(type(error).__name__ for error in rollback_errors)
            ) from rollback_errors[0]
        raise
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


def _default_config() -> ReleaseConfig:
    return ReleaseConfig()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="prepare and activate a verified immutable release")
    parser.add_argument("--target-sha", required=True)
    args = parser.parse_args(argv)
    config = _default_config()
    prepared = prepare(config, args.target_sha)
    result = switch(config, prepared)
    print(
        json.dumps(
            {
                "status": "activated",
                "target_sha": result.target_sha,
                "previous_sha": result.previous_sha,
                "lock_sha256": prepared.lock_sha256,
                "evidence_path": os.fspath(result.evidence_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
