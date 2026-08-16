#!/usr/bin/env python3
"""Build a sanitized, DTF-free Django-version test comparison artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


OUTCOME_RE = re.compile(r"^(FAIL|ERROR):\s+(.+?)\s*$")
VERBOSE_TEST_RE = re.compile(
    r"^(?P<identifier>.+?\s+\([A-Za-z_][A-Za-z0-9_.]*\))\s+\.\.\.\s+"
    r"(?:ok|FAIL|ERROR|skipped(?:\s+.+)?|expected failure|unexpected success)$"
)
RAN_RE = re.compile(r"^Ran\s+(\d+)\s+tests?\s+in\s+([0-9.]+)s$")
SUMMARY_RE = re.compile(
    r"^FAILED\s*\((?P<body>[^)]*)\)$|^OK(?:\s*\((?P<ok_body>[^)]*)\))?$"
)
COUNT_RE = re.compile(r"(?P<name>failures|errors|skipped|expected failures|unexpected successes)=(?P<count>\d+)")
DTF_IDENTIFIER_RE = re.compile(r"(?<![A-Za-z0-9_-])dtf\.", re.IGNORECASE)
REPO_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
TEST_PATH_RE = re.compile(
    r"\((?P<path>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\)"
)

SUMMARY_COUNT_KEYS = (
    "failures",
    "errors",
    "skipped",
    "expected_failures",
    "unexpected_successes",
)


def _assert_non_dtf(identifier: str) -> None:
    if DTF_IDENTIFIER_RE.search(identifier):
        raise ValueError(f"DTF test identifier is outside this artifact scope: {identifier}")


def _parse_summary(text: str, outcome_counts: dict[str, int]) -> dict[str, int]:
    # Django's MariaDB migration output can emit an indented `` OK`` line.
    # Only a zero-column unittest footer is an A/B result summary.
    ran_matches = [RAN_RE.match(line.rstrip()) for line in text.splitlines()]
    ran_matches = [match for match in ran_matches if match]
    summary_matches = [SUMMARY_RE.match(line.rstrip()) for line in text.splitlines()]
    summary_matches = [match for match in summary_matches if match]
    if len(ran_matches) != 1 or len(summary_matches) != 1:
        raise ValueError(
            "Expected exactly one complete unittest footer "
            f"(Ran={len(ran_matches)}, summary={len(summary_matches)})"
        )

    tests = int(ran_matches[0].group(1))
    summary_match = summary_matches[0]
    body = summary_match.group("body")
    if body is None:
        body = summary_match.group("ok_body") or ""
    counts = {key: 0 for key in SUMMARY_COUNT_KEYS}
    seen_keys: set[str] = set()
    summary_tokens = [] if not body else [token.strip() for token in body.split(",")]
    for token in summary_tokens:
        count_match = COUNT_RE.fullmatch(token)
        if not count_match:
            raise ValueError(f"Unrecognized unittest summary content: {token!r}")
        key = count_match.group("name").replace(" ", "_")
        if key in seen_keys:
            raise ValueError(f"Duplicate summary count: {key}")
        seen_keys.add(key)
        counts[key] = int(count_match.group("count"))

    expected_failures = outcome_counts["FAIL"]
    expected_errors = outcome_counts["ERROR"]
    if counts["failures"] != expected_failures:
        raise ValueError(
            "Summary failures count does not match parsed FAIL ids: "
            f"summary failures={counts['failures']} vs FAIL ids={expected_failures}"
        )
    if counts["errors"] != expected_errors:
        raise ValueError(
            "Summary errors count does not match parsed ERROR ids: "
            f"summary errors={counts['errors']} vs ERROR ids={expected_errors}"
        )

    is_failed = summary_match.group("body") is not None
    if is_failed and not (
        counts["failures"]
        or counts["errors"]
        or counts["unexpected_successes"]
    ):
        raise ValueError("FAILED summary has no failure, error, or unexpected-success count")
    if not is_failed and (
        counts["failures"]
        or counts["errors"]
        or counts["unexpected_successes"]
    ):
        raise ValueError("OK summary contains a failing outcome count")

    return {
        "tests": tests,
        **counts,
    }


def parse_test_log(text: str) -> dict[str, object]:
    ids: dict[str, list[str]] = {"FAIL": [], "ERROR": []}
    for line in text.splitlines():
        stripped = line.strip()
        verbose_match = VERBOSE_TEST_RE.match(stripped)
        if verbose_match:
            _assert_non_dtf(verbose_match.group("identifier"))
        match = OUTCOME_RE.match(stripped)
        if not match:
            continue
        outcome, identifier = match.groups()
        _assert_non_dtf(identifier)
        ids[outcome].append(identifier)
    return {
        "summary": _parse_summary(
            text,
            {outcome: len(values) for outcome, values in ids.items()},
        ),
        "failure_ids": sorted(ids["FAIL"]),
        "error_ids": sorted(ids["ERROR"]),
    }


def _outcome_keys(parsed: dict[str, object]) -> list[str]:
    return [
        *(f"FAIL: {identifier}" for identifier in parsed["failure_ids"]),
        *(f"ERROR: {identifier}" for identifier in parsed["error_ids"]),
    ]


def _test_module_prefix(identifier: str) -> str:
    match = TEST_PATH_RE.search(identifier)
    if not match:
        return "unparsed"
    parts = match.group("path").split(".")
    if len(parts) <= 2:
        return parts[0]
    return ".".join(parts[:-2])


def _build_root_cause_clusters(
    baseline: dict[str, object], candidate: dict[str, object]
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, list[str]]] = {}
    for runtime_name, parsed in (("baseline", baseline), ("candidate", candidate)):
        outcomes = grouped.setdefault(runtime_name, {})
        for outcome, key in (("FAIL", "failure_ids"), ("ERROR", "error_ids")):
            for identifier in parsed[key]:
                module_prefix = _test_module_prefix(identifier)
                outcomes.setdefault(module_prefix, []).append(f"{outcome}: {identifier}")

    modules = sorted(
        set(grouped.get("baseline", {})) | set(grouped.get("candidate", {}))
    )
    return [
        {
            "baseline_outcomes": sorted(
                grouped.get("baseline", {}).get(module, [])
            ),
            "basis": "test_module_prefix",
            "candidate_outcomes": sorted(
                grouped.get("candidate", {}).get(module, [])
            ),
            "cluster_id": f"module:{module}",
            # A module prefix is a deterministic triage grouping, not a diagnosis.
            "diagnosis": None,
        }
        for module in modules
    ]


def _normalise_metadata(
    *,
    command: str,
    scope: str,
    source_base_sha: str,
    evidence_scope: str,
    source_tree_state: str,
    stable_shards: tuple[str, ...] | list[str],
    dtf_scope: str = "excluded",
    dtf_migration_setup: str = "not-loaded",
) -> dict[str, object]:
    if not isinstance(command, str) or not command.strip():
        raise ValueError("Artifact command metadata must be non-empty")
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("Artifact scope metadata must be non-empty")
    if not isinstance(source_base_sha, str) or not REPO_SHA_RE.fullmatch(source_base_sha):
        raise ValueError(
            "Artifact source_base_sha must be a 40-character hexadecimal SHA"
        )
    if not isinstance(evidence_scope, str) or not evidence_scope.strip():
        raise ValueError("Artifact evidence_scope metadata must be non-empty")
    if not isinstance(source_tree_state, str) or not source_tree_state.strip():
        raise ValueError("Artifact source_tree_state metadata must be non-empty")
    if not isinstance(dtf_scope, str) or "excluded" not in dtf_scope.casefold():
        raise ValueError("Artifact dtf_scope must explicitly state DTF exclusion")
    if not isinstance(dtf_migration_setup, str) or not dtf_migration_setup.strip():
        raise ValueError("Artifact dtf_migration_setup metadata must be non-empty")
    normalised_shards = sorted(
        {
            shard.strip()
            for shard in stable_shards
            if isinstance(shard, str) and shard.strip()
        }
    )
    if not normalised_shards:
        raise ValueError("Artifact must list at least one stable shard")
    if any(DTF_IDENTIFIER_RE.search(shard) for shard in normalised_shards):
        raise ValueError("DTF stable shard is outside this artifact scope")
    return {
        "command": command.strip(),
        "dtf_scope": dtf_scope.strip(),
        "dtf_migration_setup": dtf_migration_setup.strip(),
        "provenance": {
            "base_sha": source_base_sha.lower(),
            # Base SHA identifies the tracked ancestor. It deliberately does
            # not assert that the evidence was captured from a clean tree.
            "clean_tree_assertion": "not-made",
            "evidence_scope": evidence_scope.strip(),
            "source_tree_state": source_tree_state.strip(),
        },
        "scope": scope.strip(),
        "stable_shards": normalised_shards,
    }


def build_comparison(
    *,
    baseline_text: str,
    candidate_text: str,
    baseline_runtime: str,
    candidate_runtime: str,
    command: str,
    scope: str,
    source_base_sha: str,
    evidence_scope: str,
    source_tree_state: str,
    stable_shards: tuple[str, ...] | list[str],
    dtf_scope: str = "excluded",
    dtf_migration_setup: str = "not-loaded",
) -> dict[str, object]:
    baseline = parse_test_log(baseline_text)
    candidate = parse_test_log(candidate_text)
    baseline_keys = Counter(_outcome_keys(baseline))
    candidate_keys = Counter(_outcome_keys(candidate))
    delta = {
        "candidate_only": sorted((candidate_keys - baseline_keys).elements()),
        "baseline_only": sorted((baseline_keys - candidate_keys).elements()),
    }
    summary_matches = baseline["summary"] == candidate["summary"]
    if not summary_matches:
        delta["summary"] = {
            "baseline": baseline["summary"],
            "candidate": candidate["summary"],
        }
    return {
        "schema_version": 2,
        "status": "matched" if not any(delta.values()) else "different",
        "summary_matches": summary_matches,
        "metadata": _normalise_metadata(
            command=command,
            scope=scope,
            source_base_sha=source_base_sha,
            evidence_scope=evidence_scope,
            source_tree_state=source_tree_state,
            stable_shards=stable_shards,
            dtf_scope=dtf_scope,
            dtf_migration_setup=dtf_migration_setup,
        ),
        "baseline": {
            "runtime": baseline_runtime,
            "status": _test_status(baseline),
            **baseline,
        },
        "candidate": {
            "runtime": candidate_runtime,
            "status": _test_status(candidate),
            **candidate,
        },
        "delta": delta,
        "root_cause_clusters": _build_root_cause_clusters(baseline, candidate),
    }


def _test_status(parsed: dict[str, object]) -> str:
    summary = parsed["summary"]
    if not isinstance(summary, dict):
        raise ValueError("Artifact test summary must be an object")
    if any(
        int(summary[name])
        for name in ("failures", "errors", "unexpected_successes")
    ):
        return "failed"
    return "passed"


def _validate_summary(summary: object, *, side: str) -> dict[str, int]:
    if not isinstance(summary, dict):
        raise ValueError(f"Artifact {side}.summary must be an object")
    expected_keys = {"tests", *SUMMARY_COUNT_KEYS}
    if set(summary) != expected_keys:
        raise ValueError(f"Artifact {side}.summary has unexpected keys")
    normalised: dict[str, int] = {}
    for name in expected_keys:
        value = summary[name]
        if type(value) is not int or value < 0:
            raise ValueError(f"Artifact {side}.summary.{name} must be a non-negative integer")
        normalised[name] = value
    if normalised["tests"] < sum(
        normalised[name]
        for name in ("failures", "errors", "skipped", "expected_failures")
    ):
        raise ValueError(f"Artifact {side}.summary counts exceed tests")
    return normalised


def _validate_side(payload: object, *, side: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError(f"Artifact {side} must be an object")
    required_keys = {
        "runtime",
        "status",
        "summary",
        "failure_ids",
        "error_ids",
        "log_sha256",
    }
    missing_keys = required_keys - set(payload)
    if missing_keys:
        raise ValueError(
            f"Artifact {side} is missing: {', '.join(sorted(missing_keys))}"
        )
    if set(payload) != required_keys:
        raise ValueError(f"Artifact {side} has unexpected keys")
    runtime = payload["runtime"]
    if not isinstance(runtime, str) or not runtime.strip():
        raise ValueError(f"Artifact {side}.runtime must be non-empty")
    summary = _validate_summary(payload["summary"], side=side)
    status = payload["status"]
    expected_status = "failed" if any(
        summary[name] for name in ("failures", "errors", "unexpected_successes")
    ) else "passed"
    if status != expected_status:
        raise ValueError(f"Artifact {side}.status does not match its summary")
    log_sha256 = payload["log_sha256"]
    if not isinstance(log_sha256, str) or not SHA256_RE.fullmatch(log_sha256):
        raise ValueError(f"Artifact {side}.log_sha256 must be a SHA-256 digest")

    parsed: dict[str, object] = {"summary": summary}
    for source_key, target_key, count_name in (
        ("failure_ids", "failure_ids", "failures"),
        ("error_ids", "error_ids", "errors"),
    ):
        identifiers = payload[source_key]
        if not isinstance(identifiers, list) or not all(
            isinstance(identifier, str) and identifier for identifier in identifiers
        ):
            raise ValueError(f"Artifact {side}.{source_key} must be a string list")
        if identifiers != sorted(identifiers):
            raise ValueError(f"Artifact {side}.{source_key} must be sorted")
        if len(identifiers) != summary[count_name]:
            raise ValueError(
                f"Artifact {side}.{source_key} count does not match its summary"
            )
        for identifier in identifiers:
            _assert_non_dtf(identifier)
        parsed[target_key] = identifiers
    return parsed


def validate_comparison_artifact(artifact: object) -> None:
    """Fail closed when a tracked Stage 0 A/B artifact is malformed."""

    if not isinstance(artifact, dict):
        raise ValueError("Artifact must be a JSON object")
    required_keys = {
        "schema_version",
        "status",
        "summary_matches",
        "metadata",
        "baseline",
        "candidate",
        "delta",
        "root_cause_clusters",
    }
    if set(artifact) != required_keys or artifact["schema_version"] != 2:
        raise ValueError("Artifact must use the complete schema v2 contract")

    metadata = artifact["metadata"]
    if not isinstance(metadata, dict):
        raise ValueError("Artifact metadata must be an object")
    provenance = metadata.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Artifact metadata.provenance must be an object")
    expected_metadata = _normalise_metadata(
        command=metadata.get("command"),
        scope=metadata.get("scope"),
        source_base_sha=provenance.get("base_sha"),
        evidence_scope=provenance.get("evidence_scope"),
        source_tree_state=provenance.get("source_tree_state"),
        stable_shards=metadata.get("stable_shards", []),
        dtf_scope=metadata.get("dtf_scope"),
        dtf_migration_setup=metadata.get("dtf_migration_setup"),
    )
    if metadata != expected_metadata:
        raise ValueError("Artifact metadata is not normalized")

    baseline = _validate_side(artifact["baseline"], side="baseline")
    candidate = _validate_side(artifact["candidate"], side="candidate")
    if type(artifact["summary_matches"]) is not bool:
        raise ValueError("Artifact summary_matches must be a boolean")
    summary_matches = baseline["summary"] == candidate["summary"]
    if artifact["summary_matches"] != summary_matches:
        raise ValueError("Artifact summary_matches does not match the summaries")

    baseline_keys = Counter(_outcome_keys(baseline))
    candidate_keys = Counter(_outcome_keys(candidate))
    expected_delta: dict[str, object] = {
        "candidate_only": sorted((candidate_keys - baseline_keys).elements()),
        "baseline_only": sorted((baseline_keys - candidate_keys).elements()),
    }
    if not summary_matches:
        expected_delta["summary"] = {
            "baseline": baseline["summary"],
            "candidate": candidate["summary"],
        }
    if artifact["delta"] != expected_delta:
        raise ValueError("Artifact delta does not match the normalized outcomes")
    expected_status = "matched" if not any(expected_delta.values()) else "different"
    if artifact["status"] != expected_status:
        raise ValueError("Artifact status does not match the normalized delta")
    expected_clusters = _build_root_cause_clusters(baseline, candidate)
    if artifact["root_cause_clusters"] != expected_clusters:
        raise ValueError("Artifact root_cause_clusters do not match the outcomes")


def compare_candidate_log(
    *,
    artifact: object,
    candidate_text: str,
) -> dict[str, object]:
    """Compare a fresh Django 6.1 smoke log to the tracked candidate side."""

    validate_comparison_artifact(artifact)
    fresh = parse_test_log(candidate_text)
    tracked = _validate_side(artifact["candidate"], side="candidate")
    fresh_keys = Counter(_outcome_keys(fresh))
    tracked_keys = Counter(_outcome_keys(tracked))
    delta: dict[str, object] = {
        "fresh_only": sorted((fresh_keys - tracked_keys).elements()),
        "tracked_candidate_only": sorted((tracked_keys - fresh_keys).elements()),
    }
    if fresh["summary"] != tracked["summary"]:
        delta["summary"] = {
            "fresh": fresh["summary"],
            "tracked_candidate": tracked["summary"],
        }
    return {
        "status": "matched" if not any(delta.values()) else "different",
        "summary": fresh["summary"],
        "log_sha256": hashlib.sha256(candidate_text.encode()).hexdigest(),
        "delta": delta,
    }


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", type=Path)
    parser.add_argument("--tracked-artifact", type=Path)
    parser.add_argument("--compare-candidate-log", type=Path)
    parser.add_argument("--comparison-output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--baseline-runtime")
    parser.add_argument("--candidate-runtime")
    parser.add_argument("--command")
    parser.add_argument("--scope")
    parser.add_argument("--source-base-sha")
    parser.add_argument("--evidence-scope")
    parser.add_argument("--source-tree-state")
    parser.add_argument("--dtf-scope", default="excluded")
    parser.add_argument("--dtf-migration-setup", default="not-loaded")
    parser.add_argument("--stable-shard", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if args.validate:
        if (
            args.output
            or args.baseline
            or args.candidate
            or args.tracked_artifact
            or args.compare_candidate_log
            or args.comparison_output
        ):
            parser.error("--validate cannot be combined with build arguments")
        try:
            artifact = json.loads(_read(args.validate))
            validate_comparison_artifact(artifact)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(json.dumps({"status": "invalid", "error": type(exc).__name__}))
            return 1
        print(json.dumps({"status": "valid", "artifact": str(args.validate)}))
        return 0

    if args.tracked_artifact or args.compare_candidate_log or args.comparison_output:
        if not (
            args.tracked_artifact
            and args.compare_candidate_log
            and args.comparison_output
        ):
            parser.error(
                "--tracked-artifact, --compare-candidate-log, and "
                "--comparison-output must be supplied together"
            )
        if args.output or args.baseline or args.candidate:
            parser.error("candidate comparison cannot be combined with build arguments")
        try:
            comparison = compare_candidate_log(
                artifact=json.loads(_read(args.tracked_artifact)),
                candidate_text=_read(args.compare_candidate_log),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(json.dumps({"status": "invalid", "error": type(exc).__name__}))
            return 1
        args.comparison_output.parent.mkdir(parents=True, exist_ok=True)
        args.comparison_output.write_text(
            json.dumps(comparison, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": comparison["status"], "output": str(args.comparison_output)}))
        return 0 if comparison["status"] == "matched" else 2

    required = {
        "--baseline": args.baseline,
        "--candidate": args.candidate,
        "--baseline-runtime": args.baseline_runtime,
        "--candidate-runtime": args.candidate_runtime,
        "--command": args.command,
        "--scope": args.scope,
        "--source-base-sha": args.source_base_sha,
        "--evidence-scope": args.evidence_scope,
        "--source-tree-state": args.source_tree_state,
        "--output": args.output,
    }
    missing = [name for name, value in required.items() if not value]
    if missing or not args.stable_shard:
        parser.error("missing required build arguments: " + ", ".join(missing))

    baseline_text = _read(args.baseline)
    candidate_text = _read(args.candidate)
    artifact = build_comparison(
        baseline_text=baseline_text,
        candidate_text=candidate_text,
        baseline_runtime=args.baseline_runtime,
        candidate_runtime=args.candidate_runtime,
        command=args.command,
        scope=args.scope,
        source_base_sha=args.source_base_sha,
        evidence_scope=args.evidence_scope,
        source_tree_state=args.source_tree_state,
        stable_shards=args.stable_shard,
        dtf_scope=args.dtf_scope,
        dtf_migration_setup=args.dtf_migration_setup,
    )
    artifact["baseline"]["log_sha256"] = hashlib.sha256(baseline_text.encode()).hexdigest()
    artifact["candidate"]["log_sha256"] = hashlib.sha256(candidate_text.encode()).hexdigest()
    validate_comparison_artifact(artifact)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": artifact["status"], "output": str(args.output)}))
    return 0 if artifact["status"] == "matched" else 2


if __name__ == "__main__":
    raise SystemExit(main())
