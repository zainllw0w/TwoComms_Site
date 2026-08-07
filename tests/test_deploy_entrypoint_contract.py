"""Source contracts for the canonical release entry point and retired wrappers."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL = REPO_ROOT / "deploy.sh"
BLOCKER_DOC = REPO_ROOT / "docs/instagram_bot_audit/10_OPEN_QUESTIONS_AND_BLOCKERS.md"

EXPECTED_RETIRED = {
    "clear_cache.exp",
    "debug_sitemap.exp",
    "deploy.exp",
    "deploy2.exp",
    "deploy_finance.sh",
    "deploy_fixes.sh",
    "deploy_optimizations.sh",
    "deploy_pull.exp",
    "deploy_promo_system.sh",
    "deploy_redis.sh",
    "deploy_seo.exp",
    "deploy_with_expect.exp",
    "deploy_with_expect2.exp",
    "infra/deploy_management_stats_placeholder.sh",
    "ls_remote.exp",
    "restart.exp",
    "run_clear.exp",
    "run_deploy.exp",
    "run_restart.exp",
    "scripts/deploy_finance.sh",
}

NON_RELEASE_OPERATOR_ALLOWLIST = {
    "additional_optimization.sh",
    "check_all_cron_jobs.sh",
    "check_merchant_cron.sh",
    "check_telegram_bot.sh",
    "server_audit_script.sh",
    "setup_cron_2x_daily.sh",
    "setup_nova_poshta_cron.sh",
    "setup_session_cleaner.sh",
    "setup_utm_email_reports.sh",
    "update_feed_now.sh",
    "update_google_merchant_feed.sh",
    "verify_google_feed.sh",
}

OPERATOR_DISCOVERY_RE = re.compile(
    r"(?i)(?:deploy|restart|run_|setup_|update_|clear_|debug_|ls_remote|check_|"
    r"server_audit|verify_.*feed|additional_optimization)"
)

FORBIDDEN = (
    "195.191.24.169",
    "195.191.25.63",
    "3.13",
    "git reset --hard",
    "makemigrations",
    "sshpass",
    "scp ",
    "cloudlinux-selector",
    "touch passenger_wsgi.py",
    "touch twocomms/wsgi.py",
    "pkill ",
    "pip install",
)

FORBIDDEN_DEPLOY_OPERATIONS = (
    re.compile(r"\b(?:git\s+)?pull\b"),
    re.compile(r"\b(?:git\s+)?checkout\b"),
    re.compile(r"\b(?:git\s+)?reset\s+--hard\b"),
    re.compile(r"\bmakemigrations\b"),
    re.compile(r"\b(?:sshpass|scp|rsync)\b"),
    re.compile(r"\bpip(?:3)?\s+(?:install|upgrade)\b"),
    re.compile(r"(?:passenger_wsgi|(?:TwoComms_Site/)?wsgi\.py|tmp/restart\.txt)"),
    re.compile(r"\b(?:pkill|killall|kill)\b"),
)


def _entrypoints() -> tuple[Path, ...]:
    candidates = set(REPO_ROOT.glob("deploy*.sh"))
    candidates.update(REPO_ROOT.glob("*.exp"))
    candidates.update((REPO_ROOT / "scripts").glob("deploy*.sh"))
    candidates.update((REPO_ROOT / "infra").glob("deploy*.sh"))
    return tuple(sorted(path for path in candidates if path.is_file()))


def _tracked_operator_candidates() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        path
        for path in result.stdout.splitlines()
        if Path(path).suffix in {".sh", ".exp"} and OPERATOR_DISCOVERY_RE.search(Path(path).name)
    }


class DeployEntrypointContractTests(unittest.TestCase):
    def test_canonical_entrypoint_is_the_only_live_deployer(self):
        self.assertTrue(CANONICAL.is_file())
        self.assertTrue(os.access(CANONICAL, os.X_OK))
        source = CANONICAL.read_text(encoding="utf-8")
        self.assertEqual(
            len(re.findall(r"^\s*exec\s+.*scripts/deploy_release\.py.*\"\$@\"\s*$", source, re.MULTILINE)),
            1,
        )
        self.assertNotRegex(source, r"^\s*(?:ssh|scp|sshpass|git|pip|python)\b", source)
        self.assertIn("TWC_DEPLOY_SYSTEM_PYTHON", source)
        self.assertNotIn("195.191.", source)

    def test_discovered_wrappers_have_a_complete_retirement_ledger(self):
        discovered = {path.relative_to(REPO_ROOT).as_posix() for path in _entrypoints() if path != CANONICAL}
        self.assertTrue(
            discovered <= EXPECTED_RETIRED,
            f"unclassified deploy/operator wrappers: {sorted(discovered - EXPECTED_RETIRED)}",
        )

    def test_tracked_operator_scripts_are_classified(self):
        classified = EXPECTED_RETIRED | NON_RELEASE_OPERATOR_ALLOWLIST | {"deploy.sh"}
        unknown = _tracked_operator_candidates() - classified
        self.assertEqual(unknown, set(), f"unclassified tracked operator scripts: {sorted(unknown)}")

    def test_canonical_source_has_no_legacy_destructive_operations(self):
        source = CANONICAL.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_DEPLOY_OPERATIONS:
            self.assertIsNone(pattern.search(source), f"{pattern.pattern!r} in {CANONICAL}")

    def test_every_discovered_noncanonical_entrypoint_is_explicitly_retired(self):
        entrypoints = _entrypoints()
        self.assertIn(CANONICAL, entrypoints)
        for path in entrypoints:
            if path == CANONICAL:
                continue
            source = path.read_text(encoding="utf-8")
            self.assertIn("RETIRED", source, path.as_posix())
            self.assertIn("deploy.sh", source, path.as_posix())
            for forbidden in FORBIDDEN:
                self.assertNotIn(forbidden, source, f"{forbidden!r} in {path}")

    def test_retired_wrappers_fail_closed_without_remote_side_effects(self):
        for path in _entrypoints():
            if path == CANONICAL:
                continue
            result = subprocess.run(
                ["bash", str(path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0, path.as_posix())
            self.assertIn("RETIRED", result.stdout + result.stderr)

    def test_canonical_requires_explicit_target_sha(self):
        result = subprocess.run(
            ["bash", str(CANONICAL)],
            cwd=REPO_ROOT,
            env={"PATH": "/usr/bin:/bin", "TWC_DEPLOY_SYSTEM_PYTHON": "/bin/false"},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target-sha", result.stderr)

    def test_canonical_forwards_target_sha_unchanged_to_orchestrator(self):
        target_sha = "0123456789abcdef0123456789abcdef01234567"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            received = temp / "received"
            fake_python = temp / "fake-python"
            fake_python.write_text(
                "#!/usr/bin/env python3\n"
                "import os\n"
                "from pathlib import Path\n"
                "Path(os.environ['TWC_TEST_RECEIVED']).write_text('\\n'.join(__import__('sys').argv[1:]))\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            result = subprocess.run(
                ["bash", str(CANONICAL), "--target-sha", target_sha],
                cwd=REPO_ROOT,
                env={
                    "PATH": "/usr/bin:/bin",
                    "TWC_DEPLOY_SYSTEM_PYTHON": str(fake_python),
                    "TWC_TEST_RECEIVED": str(received),
                },
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                received.read_text(encoding="utf-8").splitlines(),
                [str(REPO_ROOT / "scripts/deploy_release.py"), "--target-sha", target_sha],
            )

    def test_blocker_document_records_usage_boundary_and_contract_evidence(self):
        self.assertTrue(BLOCKER_DOC.is_file())
        source = BLOCKER_DOC.read_text(encoding="utf-8")
        for marker in (
            "Task 4C",
            "crontab -l",
            "operator-use",
            "deploy.sh --target-sha",
            "F-DEPLOY-004",
            "production usage evidence is complete",
            "remains open until the reviewed retired stubs reach `main`",
        ):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
