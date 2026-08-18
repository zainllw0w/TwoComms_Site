#!/usr/bin/env python3
"""Fail-closed validator for the non-DTF periodic ownership contract.

This is an evidence validator, not a cron installer. It never edits a crontab,
starts a process, or infers production state from a local checkout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_JOB_KEYS = {
    "id", "cadence", "command", "managed_block", "owner_path", "lock_path",
    "flock", "timeout", "timeout_required",
}
DTF_RE = re.compile(r"(?<!non-)\bdtf\b", re.IGNORECASE)
CRON_FIELD_RE = re.compile(r"^(?:\*|\*/\d+|\d+)(?:[-/,](?:\*|\d+))*$")


class ContractError(ValueError):
    """Raised when evidence cannot prove the ownership contract."""


def _fail(message: str) -> None:
    raise ContractError(message)


def _walk_strings(value: Any, path: str = "manifest"):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"cannot load manifest: {exc}")
    if not isinstance(data, dict):
        _fail("manifest root must be an object")
    for location, value in _walk_strings(data):
        if DTF_RE.search(value):
            _fail(f"DTF scope is forbidden ({location})")
    if data.get("schema_version") != 1 or data.get("scope") != "non-dtf":
        _fail("manifest must declare schema_version=1 and scope=non-dtf")
    rollback = data.get("rollback")
    if not isinstance(rollback, dict) or not all(isinstance(rollback.get(k), str) and rollback[k].strip() for k in ("owner", "path", "action")):
        _fail("rollback must include non-empty owner, path, and action")
    rollback_path = Path(rollback["path"])
    if rollback_path.is_absolute() or ".." in rollback_path.parts:
        _fail("rollback.path must be a repository-relative path")
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        _fail("jobs must be a non-empty list")
    seen: set[str] = set()
    for index, job in enumerate(jobs):
        if not isinstance(job, dict):
            _fail(f"jobs[{index}] must be an object")
        missing = REQUIRED_JOB_KEYS - job.keys()
        if missing:
            _fail(f"jobs[{index}] missing keys: {sorted(missing)}")
        job_id = job["id"]
        if not isinstance(job_id, str) or not re.fullmatch(r"[a-z0-9_]+", job_id) or job_id in seen:
            _fail(f"jobs[{index}].id must be unique lowercase identifier")
        seen.add(job_id)
        cadence = job["cadence"]
        if not isinstance(cadence, str) or len(cadence.split()) != 5 or not all(CRON_FIELD_RE.fullmatch(field) for field in cadence.split()):
            _fail(f"jobs[{index}] has invalid five-field cadence")
        for key in ("command", "managed_block", "owner_path", "lock_path", "flock", "timeout"):
            if not isinstance(job[key], str) or not job[key].strip():
                if key == "timeout" and job.get("timeout_required") is False:
                    continue
                _fail(f"jobs[{index}].{key} must be a non-empty string")
        if "manage.py " not in job["command"] or "/" in job["id"]:
            _fail(f"jobs[{index}] must identify a Django management command")
        owner = Path(job["owner_path"])
        if owner.is_absolute() or ".." in owner.parts or not job["owner_path"].startswith("scripts/"):
            _fail(f"jobs[{index}].owner_path must be a scripts-relative path")
        if not job["managed_block"].startswith("# BEGIN TWOCOMMS "):
            _fail(f"jobs[{index}].managed_block must be a TWOCOMMS marker")
        if not job["lock_path"].startswith("tmp/"):
            _fail(f"jobs[{index}].lock_path must be under tmp/")
        if not isinstance(job["timeout_required"], bool):
            _fail(f"jobs[{index}].timeout_required must be boolean")
        if job["timeout_required"] and not job["timeout"].strip():
            _fail(f"jobs[{index}] requires a bounded timeout")
        if "environment" in job and (
            not isinstance(job["environment"], list)
            or not job["environment"]
            or any(not isinstance(item, str) or not item.strip() for item in job["environment"])
        ):
            _fail(f"jobs[{index}].environment must be a non-empty list of assignments")
    return data


def _extract_managed_blocks(lines: list[str]) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    active: str | None = None
    for line in lines:
        if line.startswith("# BEGIN TWOCOMMS "):
            if active is not None:
                _fail("nested managed cron blocks")
            active = line
            blocks.setdefault(line, []).append(line)
            continue
        if line.startswith("# END TWOCOMMS "):
            if active is None:
                _fail("managed END marker without BEGIN")
            blocks[active].append(line)
            active = None
            continue
        if active is not None:
            blocks[active].append(line)
    if active is not None:
        _fail(f"unterminated managed block: {active}")
    return blocks


def validate_crontab(manifest: dict[str, Any], crontab: str, *, repo_root: Path) -> dict[str, Any]:
    if DTF_RE.search(crontab):
        _fail("DTF scope is forbidden in crontab evidence")
    lines = crontab.splitlines()
    blocks = _extract_managed_blocks(lines)
    for marker, block in blocks.items():
        if len([line for line in lines if line == marker]) != 1:
            _fail(f"duplicate managed block marker: {marker}")
        if len([line for line in block if line.startswith("# END TWOCOMMS ")]) != 1:
            _fail(f"managed block has invalid END marker: {marker}")
    rollback = manifest["rollback"]
    rollback_target = repo_root / rollback["path"]
    if not rollback_target.is_file():
        _fail(f"rollback path is absent from repository: {rollback_target}")
    known_markers = {job["managed_block"] for job in manifest["jobs"]}
    unknown_markers = sorted(set(blocks) - known_markers)
    if unknown_markers:
        _fail(f"unknown TWOCOMMS managed block: {unknown_markers}")
    results: list[dict[str, Any]] = []
    for job in manifest["jobs"]:
        owner_target = repo_root / job["owner_path"]
        if not owner_target.is_file():
            _fail(f"owner script is absent from repository for {job['id']}: {owner_target}")
        marker = job["managed_block"]
        if marker not in blocks:
            _fail(f"managed block missing for {job['id']}: {marker}")
        matching = [line for line in lines if job["command"] in line and not line.lstrip().startswith("#")]
        if len(matching) != 1:
            _fail(f"{job['id']} requires exactly one owner line, found {len(matching)}")
        owner_line = matching[0]
        block = blocks[marker]
        if owner_line not in block:
            _fail(f"{job['id']} has a loose owner outside managed block")
        if not owner_line.startswith(job["cadence"] + " "):
            _fail(f"{job['id']} cadence does not match manifest")
        if job["flock"] not in owner_line:
            _fail(f"{job['id']} lacks required flock contract")
        if job["timeout_required"] and job["timeout"] not in owner_line:
            _fail(f"{job['id']} lacks required bounded timeout")
        if job["lock_path"] not in owner_line:
            _fail(f"{job['id']} lock path is missing")
        for assignment in job.get("environment", []):
            if assignment not in owner_line:
                _fail(f"{job['id']} production environment contract is missing")
        owner_count = sum(job["command"] in line for line in block if not line.lstrip().startswith("#"))
        if owner_count != 1:
            _fail(f"{job['id']} has duplicate managed owners")
        results.append({"id": job["id"], "owner_line": owner_line, "managed_block": marker})
    return {"status": "ok", "scope": manifest["scope"], "jobs": results, "rollback": rollback}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--crontab", type=Path)
    source.add_argument("--stdin", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        crontab = sys.stdin.read() if args.stdin else args.crontab.read_text(encoding="utf-8")
        result = validate_crontab(manifest, crontab, repo_root=args.repo_root)
    except (ContractError, OSError) as exc:
        print(f"stage6-periodic-owners: FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
