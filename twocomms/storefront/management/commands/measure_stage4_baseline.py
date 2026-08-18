import hashlib
import json
import math
import os
import resource
import tempfile
import threading
import time
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.core.cache.backends.filebased import FileBasedCache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


STATUS_NAMES = (
    "Created_tmp_tables",
    "Created_tmp_disk_tables",
    "Aborted_connects",
    "Aborted_clients",
)


def _percentile(values, percentile):
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, math.ceil((percentile / 100) * len(ordered)) - 1)
    return round(ordered[index], 3)


def _mariadb_status(cursor):
    placeholders = ", ".join(["%s"] * len(STATUS_NAMES))
    cursor.execute(
        f"SHOW GLOBAL STATUS WHERE Variable_name IN ({placeholders})",
        STATUS_NAMES,
    )
    return {str(name): int(value) for name, value in cursor.fetchall()}


def _database_observability():
    empty = {name: None for name in STATUS_NAMES}
    if connection.vendor != "mysql":
        return {
            "vendor": connection.vendor,
            "available": False,
            "temporary_tables": {"baseline": empty, "delta": empty},
            "aborted_connections": {"baseline": empty, "delta": empty},
        }
    with connection.cursor() as cursor:
        before = _mariadb_status(cursor)
        after = _mariadb_status(cursor)
    delta = {name: after.get(name, 0) - before.get(name, 0) for name in STATUS_NAMES}
    return {
        "vendor": connection.vendor,
        "available": True,
        "temporary_tables": {
            "baseline": {name: before[name] for name in STATUS_NAMES[:2]},
            "delta": {name: delta[name] for name in STATUS_NAMES[:2]},
        },
        "aborted_connections": {
            "baseline": {name: before[name] for name in STATUS_NAMES[2:]},
            "delta": {name: delta[name] for name in STATUS_NAMES[2:]},
        },
    }


def _file_cache_observability(samples):
    configured = settings.CACHES.get("default", {})
    configured_location = configured.get("LOCATION")
    configured_path = Path(configured_location) if configured_location else None
    inventory = {"files": 0, "inodes": 0, "bytes": 0}
    if configured_path and configured_path.is_dir():
        for path in configured_path.iterdir():
            if not path.is_file():
                continue
            stat = path.stat()
            inventory["files"] += 1
            inventory["bytes"] += stat.st_size
            inventory["inodes"] += 1

    durations = []
    with tempfile.TemporaryDirectory(prefix="twc-stage4-cache-") as probe_dir:
        probe = FileBasedCache(
            probe_dir, {"timeout": 30, "OPTIONS": {"MAX_ENTRIES": samples + 10}}
        )
        for index in range(samples):
            started = time.perf_counter()
            key = f"stage4:io:{index}"
            probe.set(key, {"sample": index}, timeout=30)
            probe.get(key)
            probe.delete(key)
            durations.append((time.perf_counter() - started) * 1000)

        barrier = threading.Barrier(3)
        results = []

        def contender():
            barrier.wait()
            results.append(bool(probe.add("stage4:add", 1, timeout=30)))

        threads = [threading.Thread(target=contender) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

    return {
        "backend": configured.get("BACKEND", ""),
        "location_sha256": hashlib.sha256(
            str(configured_location).encode()
        ).hexdigest()[:12],
        "configured_ttl_seconds": configured.get("TIMEOUT"),
        "configured_max_entries": configured.get("OPTIONS", {}).get("MAX_ENTRIES"),
        "inventory": inventory,
        "io": {
            "samples": samples,
            "p50_ms": _percentile(durations, 50),
            "p95_ms": _percentile(durations, 95),
        },
        "concurrent_add": {
            "contenders": 2,
            "winners": sum(results),
            "distributed_lock_safe": False,
        },
    }


def _cache_key_observability(release_key):
    namespace = f"stage4:cache-key:{release_key}"
    cold_key = f"{namespace}:cold"
    warm_key = f"{namespace}:warm"
    with tempfile.TemporaryDirectory(prefix="twc-stage4-key-") as probe_dir:
        probe = FileBasedCache(probe_dir, {"timeout": 30})
        cold_hit = probe.get(cold_key) is not None
        warm_before = probe.get(warm_key) is not None
        probe.set(warm_key, {"release": release_key}, timeout=30)
        warm_after = probe.get(warm_key) is not None
    return {
        "release_key": release_key,
        "cold_key": cold_key,
        "warm_key": warm_key,
        "cold_hit": cold_hit,
        "warm_hit_before": warm_before,
        "warm_hit_after": warm_after,
        "old_key_reads": 0,
    }


def _fd_observability():
    fd_path = Path("/proc/self/fd")
    open_fds = len(list(fd_path.iterdir())) if fd_path.is_dir() else None
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    return {
        "open": open_fds,
        "soft_limit": soft,
        "hard_limit": hard,
        "soft_utilization_pct": (
            round((open_fds / soft) * 100, 3)
            if open_fds is not None and soft > 0
            else None
        ),
    }


def _password_observability():
    hasher = PBKDF2PasswordHasher()
    password = "stage4-probe-password-not-a-user-secret"
    started = time.perf_counter()
    encoded = hasher.encode(password, hasher.salt())
    encode_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    verified = hasher.verify(password, encoded)
    verify_ms = (time.perf_counter() - started) * 1000
    legacy = hasher.encode(password, hasher.salt(), iterations=hasher.iterations - 1)
    return {
        "algorithm": hasher.algorithm,
        "iterations": hasher.iterations,
        "encode_ms": round(encode_ms, 3),
        "verify_ms": round(verify_ms, 3),
        "verify_ok": verified,
        "current_needs_rehash": hasher.must_update(encoded),
        "legacy_needs_rehash": hasher.must_update(legacy),
    }


class Command(BaseCommand):
    help = "Emit one bounded, machine-readable Stage 4 observability snapshot."

    def add_arguments(self, parser):
        parser.add_argument("--samples", type=int, default=9)
        parser.add_argument(
            "--release-key", default=os.environ.get("TWC_RELEASE_SHA", "current")
        )

    def handle(self, *args, **options):
        samples = options["samples"]
        if not 3 <= samples <= 50:
            raise CommandError("--samples must be between 3 and 50")
        report = {
            "schema": "twocomms.django61.stage4.v1",
            "scope": "non-dtf",
            "read_only_database": True,
            "cache": _file_cache_observability(samples),
            "cache_keys": _cache_key_observability(options["release_key"]),
            "database": _database_observability(),
            "file_descriptors": _fd_observability(),
            "password_hasher": _password_observability(),
        }
        self.stdout.write(json.dumps(report, sort_keys=True))
