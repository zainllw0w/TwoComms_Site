#!/usr/bin/env python3
"""Lightweight stdlib supervisor for the Django Instagram daemon.

Cron calls ``--ensure`` once per minute.  That path imports no Django modules
and either observes the OS supervisor lock or starts one detached supervisor.
The supervisor is the parent of ``run_instagram_bot --forever`` so child exits
can be attributed instead of inferred from a stale PID file or cache heartbeat.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path


STATE_VERSION = 1
MAX_EVENT_BYTES = 128 * 1024
MAX_EVENT_RECORDS = 200
MAX_LOG_BYTES = 2 * 1024 * 1024
MAINTENANCE_FAIL_SAFE_SECONDS = 60 * 60
RAPID_EXIT_SECONDS = 120
STABLE_UPTIME_SECONDS = 300
BACKOFF_SECONDS = (1, 5, 15, 60)
SHA_RE = re.compile(r"^[0-9a-f]{7,64}$")


def _runtime_paths(root: Path) -> dict[str, Path]:
    tmp = root / "tmp"
    return {
        "tmp": tmp,
        "supervisor_lock": tmp / "ig_bot_supervisor.lock",
        "spawn_lock": tmp / "ig_bot_supervisor_spawn.lock",
        "daemon_lock": tmp / "ig_bot_daemon.lock",
        "maintenance": tmp / "ig_bot_maintenance.json",
        "state": tmp / "ig_bot_supervisor_state.json",
        "events": tmp / "ig_bot_supervisor_events.jsonl",
        "supervisor_log": tmp / "ig_bot_supervisor.log",
        "daemon_log": tmp / "ig_bot_daemon.log",
    }


def _validate_root(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        raise ValueError("runtime root must be absolute")
    root = candidate.resolve(strict=True)
    if root == Path("/") or not (root / "manage.py").is_file():
        raise ValueError("runtime root must contain manage.py")
    return root


def _validate_python(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute() or not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise ValueError("Python executable must be an executable absolute path")
    # CloudLinux selects the virtualenv from the invoked symlink path. Resolving
    # it to python_wrapper would silently lose that binding.
    return candidate


@contextmanager
def _exclusive_lock(path: Path, *, blocking: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(handle.fileno(), flags)
        except BlockingIOError:
            yield None
            return
        try:
            yield handle
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _lock_held(path: Path) -> bool:
    with _exclusive_lock(path) as handle:
        return handle is None


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _tail_event_lines(path: Path) -> list[bytes]:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - MAX_EVENT_BYTES))
            payload = handle.read(MAX_EVENT_BYTES)
    except FileNotFoundError:
        return []
    lines = payload.splitlines()
    if size > MAX_EVENT_BYTES and lines:
        lines = lines[1:]
    return lines[-(MAX_EVENT_RECORDS - 1):]


def _append_event(path: Path, payload: dict) -> None:
    record = json.dumps(
        {"version": STATE_VERSION, **payload},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(record) > 4096:
        raise ValueError("supervisor event exceeds safe bound")
    lines = _tail_event_lines(path)
    lines.append(record)
    while lines and sum(len(line) + 1 for line in lines) > MAX_EVENT_BYTES:
        lines.pop(0)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(b"\n".join(lines) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _publish(paths: dict[str, Path], event: str, **fields) -> dict:
    payload = {
        "version": STATE_VERSION,
        "event": event,
        "observed_at": round(time.time(), 3),
        **fields,
    }
    _atomic_json(paths["state"], payload)
    _append_event(paths["events"], payload)
    return payload


def _release_sha(root: Path) -> str:
    configured = str(os.environ.get("TWC_RELEASE_SHA") or "").strip().lower()
    if SHA_RE.fullmatch(configured):
        return configured
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    observed = result.stdout.strip().lower()
    return observed if result.returncode == 0 and SHA_RE.fullmatch(observed) else "unknown"


def _pid_start_ticks(pid: int, *, proc_root: Path = Path("/proc")) -> int | None:
    try:
        payload = (proc_root / str(int(pid)) / "stat").read_text(encoding="ascii")
        _prefix, fields = payload.rsplit(") ", 1)
        # fields begins at proc field 3 (state); starttime is field 22.
        return int(fields.split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _maintenance_active(path: Path, *, now: float | None = None) -> bool:
    checked_at = time.time() if now is None else float(now)
    try:
        stat = path.stat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        started_at = float(payload["started_at"])
        expires_at = float(payload["expires_at"])
        if (
            not math.isfinite(started_at)
            or not math.isfinite(expires_at)
            or started_at > checked_at + 300
            or not 0 < expires_at - started_at <= MAINTENANCE_FAIL_SAFE_SECONDS
        ):
            raise ValueError("invalid maintenance bounds")
        return checked_at < expires_at
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return checked_at < min(stat.st_mtime, stat.st_ctime) + MAINTENANCE_FAIL_SAFE_SECONDS


def _bounded_log_handle(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.stat().st_size >= MAX_LOG_BYTES:
            rotated = path.with_suffix(path.suffix + ".1")
            try:
                rotated.unlink()
            except FileNotFoundError:
                pass
            os.replace(path, rotated)
    except FileNotFoundError:
        pass
    return path.open("a", encoding="utf-8", buffering=1)


def _exit_attribution(returncode: int) -> tuple[int | None, int | None]:
    if returncode < 0:
        return None, abs(int(returncode))
    return int(returncode), None


class Supervisor:
    def __init__(self, *, root: Path, python: Path):
        self.root = root
        self.python = python
        self.paths = _runtime_paths(root)
        self.stop_requested = False
        self.restart_requested = False
        self.received_signal: int | None = None
        self.child: subprocess.Popen | None = None
        self.restart_count = 0
        self.rapid_exit_times: list[float] = []
        self.last_restart_storm_at = 0.0
        self.last_wait_state = ""
        self._previous_handlers: dict[int, object] = {}
        self._previous_thread_hook = threading.excepthook

    def _record(self, event: str, **fields):
        return _publish(
            self.paths,
            event,
            supervisor_pid=os.getpid(),
            supervisor_start_ticks=_pid_start_ticks(os.getpid()),
            restart_count=self.restart_count,
            **fields,
        )

    def _signal_handler(self, signum, _frame):
        self.received_signal = int(signum)
        if signum == signal.SIGHUP:
            self.restart_requested = True
        else:
            self.stop_requested = True
        child = self.child
        if child is not None and child.poll() is None:
            try:
                child.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                pass

    def _thread_exception(self, args):
        self.stop_requested = True
        self._record(
            "supervisor_thread_exception",
            exception_type=getattr(args.exc_type, "__name__", "BaseException")[:80],
            thread_name=str(getattr(args.thread, "name", ""))[:80],
        )

    def _install_hooks(self):
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            self._previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, self._signal_handler)
        threading.excepthook = self._thread_exception

    def _restore_hooks(self):
        threading.excepthook = self._previous_thread_hook
        for signum, handler in self._previous_handlers.items():
            signal.signal(signum, handler)

    def _wait_interruptibly(self, seconds: float) -> bool:
        deadline = time.monotonic() + max(0.0, seconds)
        while not self.stop_requested and time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.5, remaining))
        return self.stop_requested

    def _spawn_and_wait(self) -> tuple[int, float]:
        release_sha = _release_sha(self.root)
        env = os.environ.copy()
        env["TWC_IG_RUNTIME_ROOT"] = os.fspath(self.root)
        started_at = time.time()
        started_monotonic = time.monotonic()
        with _bounded_log_handle(self.paths["daemon_log"]) as daemon_log:
            child = subprocess.Popen(
                [
                    os.fspath(self.python),
                    os.fspath(self.root / "manage.py"),
                    "run_instagram_bot",
                    "--forever",
                ],
                cwd=self.root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=daemon_log,
                stderr=daemon_log,
                start_new_session=False,
            )
            self.child = child
            child_start_ticks = _pid_start_ticks(child.pid)
            self._record(
                "child_started",
                child_pid=child.pid,
                child_start_ticks=child_start_ticks,
                child_release_sha=release_sha,
                child_started_at=round(started_at, 3),
            )
            terminate_requested_at = None
            while child.poll() is None:
                if self.stop_requested or self.restart_requested:
                    if terminate_requested_at is None:
                        terminate_requested_at = time.monotonic()
                        try:
                            child.send_signal(signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                    elif time.monotonic() - terminate_requested_at >= 20:
                        try:
                            child.kill()
                        except ProcessLookupError:
                            pass
                try:
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    continue
            returncode = int(child.returncode or 0)
            uptime = max(0.0, time.monotonic() - started_monotonic)
            exit_code, exit_signal = _exit_attribution(returncode)
            self._record(
                "child_exited",
                child_pid=child.pid,
                child_start_ticks=child_start_ticks,
                child_release_sha=release_sha,
                child_started_at=round(started_at, 3),
                child_uptime_seconds=round(uptime, 3),
                child_returncode=returncode,
                child_exit_code=exit_code,
                child_exit_signal=exit_signal,
                supervisor_signal=self.received_signal,
            )
            self.child = None
            return returncode, uptime

    def run(self) -> int:
        self.paths["tmp"].mkdir(parents=True, exist_ok=True)
        with _exclusive_lock(self.paths["supervisor_lock"]) as supervisor_lock:
            if supervisor_lock is None:
                return 0
            self._install_hooks()
            self._record("supervisor_started", child_release_sha=_release_sha(self.root))
            try:
                backoff_index = 0
                while not self.stop_requested:
                    if _maintenance_active(self.paths["maintenance"]):
                        if self.last_wait_state != "maintenance_wait":
                            self._record("maintenance_wait")
                            self.last_wait_state = "maintenance_wait"
                        if self._wait_interruptibly(5):
                            break
                        continue
                    if _lock_held(self.paths["daemon_lock"]):
                        if self.last_wait_state != "existing_daemon_wait":
                            self._record("existing_daemon_wait")
                            self.last_wait_state = "existing_daemon_wait"
                        if self._wait_interruptibly(5):
                            break
                        continue
                    self.last_wait_state = ""
                    self.restart_requested = False
                    returncode, uptime = self._spawn_and_wait()
                    if self.stop_requested:
                        break
                    self.restart_count += 1
                    now = time.time()
                    self.rapid_exit_times = [
                        observed
                        for observed in self.rapid_exit_times
                        if now - observed <= 600
                    ]
                    if uptime < RAPID_EXIT_SECONDS:
                        self.rapid_exit_times.append(now)
                    if (
                        len(self.rapid_exit_times) >= 3
                        and now - self.last_restart_storm_at >= 3600
                    ):
                        self.last_restart_storm_at = now
                        self._record(
                            "restart_storm",
                            rapid_exit_count=len(self.rapid_exit_times),
                            child_returncode=returncode,
                        )
                    if uptime >= STABLE_UPTIME_SECONDS:
                        backoff_index = 0
                    delay = BACKOFF_SECONDS[backoff_index]
                    if uptime < RAPID_EXIT_SECONDS:
                        backoff_index = min(
                            backoff_index + 1,
                            len(BACKOFF_SECONDS) - 1,
                        )
                    self._record("restart_backoff", delay_seconds=delay)
                    if self._wait_interruptibly(delay):
                        break
            finally:
                child = self.child
                if child is not None and child.poll() is None:
                    try:
                        child.terminate()
                        child.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)
                    except ProcessLookupError:
                        pass
                self._record("supervisor_stopped", supervisor_signal=self.received_signal)
                self._restore_hooks()
        return 0


def ensure_supervisor(*, root: Path, python: Path) -> int:
    paths = _runtime_paths(root)
    paths["tmp"].mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(paths["spawn_lock"]) as spawn_lock:
        if spawn_lock is None or _lock_held(paths["supervisor_lock"]):
            return 0
        release_sha = _release_sha(root)
        _publish(
            paths,
            "supervisor_spawn_requested",
            supervisor_pid=None,
            supervisor_start_ticks=None,
            child_release_sha=release_sha,
        )
        with _bounded_log_handle(paths["supervisor_log"]) as supervisor_log:
            child = subprocess.Popen(
                [
                    os.fspath(python),
                    os.path.realpath(__file__),
                    "--supervise",
                    "--root",
                    os.fspath(root),
                    "--python",
                    os.fspath(python),
                ],
                cwd=root,
                env={**os.environ, "TWC_IG_RUNTIME_ROOT": os.fspath(root)},
                stdin=subprocess.DEVNULL,
                stdout=supervisor_log,
                stderr=supervisor_log,
                start_new_session=True,
            )
        # Do not overwrite state after spawn: the new supervisor may already
        # have published child_started. Append-only evidence has no such race.
        _append_event(
            paths["events"],
            {
                "event": "supervisor_spawned",
                "observed_at": round(time.time(), 3),
                "supervisor_pid": child.pid,
                "supervisor_start_ticks": _pid_start_ticks(child.pid),
                "child_release_sha": release_sha,
            },
        )
    return 0


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--ensure", action="store_true")
    mode.add_argument("--supervise", action="store_true")
    mode.add_argument("--status", action="store_true")
    parser.add_argument("--root", required=True)
    parser.add_argument("--python", required=True)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    try:
        root = _validate_root(args.root)
        python = _validate_python(args.python)
        paths = _runtime_paths(root)
        if args.status:
            try:
                payload = json.loads(paths["state"].read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                payload = {"version": STATE_VERSION, "event": "unobserved"}
            payload["supervisor_lock_held"] = _lock_held(paths["supervisor_lock"])
            supervisor_pid = int(payload.get("supervisor_pid") or 0)
            recorded_supervisor_ticks = payload.get("supervisor_start_ticks")
            observed_supervisor_ticks = (
                _pid_start_ticks(supervisor_pid) if supervisor_pid > 0 else None
            )
            payload["supervisor_identity_matches"] = bool(
                recorded_supervisor_ticks is not None
                and observed_supervisor_ticks == recorded_supervisor_ticks
            )
            child_pid = int(payload.get("child_pid") or 0)
            recorded_child_ticks = payload.get("child_start_ticks")
            observed_child_ticks = _pid_start_ticks(child_pid) if child_pid > 0 else None
            payload["child_identity_matches"] = bool(
                payload.get("event") == "child_started"
                and recorded_child_ticks is not None
                and observed_child_ticks == recorded_child_ticks
            )
            print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
            return 0
        if args.ensure:
            return ensure_supervisor(root=root, python=python)
        return Supervisor(root=root, python=python).run()
    except Exception as exc:
        try:
            root = Path(args.root) if Path(args.root).is_absolute() else None
            if root is not None and root.exists():
                _publish(
                    _runtime_paths(root),
                    "supervisor_fatal",
                    supervisor_pid=os.getpid(),
                    exception_type=exc.__class__.__name__,
                )
        except Exception:
            pass
        print(f"instagram-bot-supervisor: {exc.__class__.__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
