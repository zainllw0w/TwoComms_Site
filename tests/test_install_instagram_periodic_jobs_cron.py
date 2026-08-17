import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_instagram_periodic_jobs_cron.sh"
BEGIN_MARKER = "# BEGIN TWOCOMMS INSTAGRAM PERIODIC JOBS v1"
END_MARKER = "# END TWOCOMMS INSTAGRAM PERIODIC JOBS v1"
WATCHDOG_BEGIN = "# BEGIN TWOCOMMS INSTAGRAM BOT WATCHDOG"
TRACKING_BEGIN = "# BEGIN TWOCOMMS NOVA POSHTA TRACKING"


class InstallInstagramPeriodicJobsCronTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.crontab_file = self.root / "crontab"
        self.django_root = self.root / "TwoComms_Site" / "twocomms"
        self.django_root.mkdir(parents=True)
        self.python = self.root / "python"
        self.python.write_text("", encoding="utf-8")
        self.python.chmod(0o700)
        self._write_executable(
            "crontab",
            """#!/usr/bin/env bash
set -eu
if [ "${1:-}" = "-l" ]; then
  if [ -f "$FAKE_CRONTAB_FILE" ]; then
    cat "$FAKE_CRONTAB_FILE"
    exit 0
  fi
  echo 'no crontab for test' >&2
  exit 1
fi
cp "$1" "$FAKE_CRONTAB_FILE"
""",
        )
        self._write_executable("flock", "#!/usr/bin/env bash\nexit 0\n")
        self._write_executable("timeout", "#!/usr/bin/env bash\nexit 0\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_executable(self, name, content):
        path = self.fake_bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _env(self):
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{self.fake_bin}:/usr/bin:/bin",
                "FAKE_CRONTAB_FILE": str(self.crontab_file),
                "TWC_DJANGO_ROOT": str(self.django_root),
                "TWC_PYTHON": str(self.python),
                "TWC_FLOCK_BIN": str(self.fake_bin / "flock"),
                "TWC_TIMEOUT_BIN": str(self.fake_bin / "timeout"),
            }
        )
        return env

    def _run(self, mode):
        return subprocess.run(
            ["bash", str(INSTALL_SCRIPT), mode],
            env=self._env(),
            text=True,
            capture_output=True,
            timeout=10,
        )

    def _legacy_lines(self):
        root = self.django_root
        python = self.python
        return (
            f"*/2 * * * * cd {root} && /usr/bin/flock -n {root}/tmp/order_telegram_reconcile.lock {python} manage.py reconcile_order_telegram_notifications --max-age-hours 168 --min-age-seconds 60 --limit 50 >> {root}/logs/order_telegram_reconcile.log 2>&1",
            f"*/2 * * * * cd {root} && /usr/bin/flock -n {root}/tmp/ig_checkout_reconcile.lock {python} manage.py reconcile_ig_checkout --limit 100 >> {root}/logs/ig_checkout_reconcile.log 2>&1",
            f"*/2 * * * * cd {root} && /usr/bin/flock -n {root}/tmp/ig_order_fulfillment.lock {python} manage.py reconcile_ig_order_fulfillment --limit 100 >> {root}/logs/ig_order_fulfillment.log 2>&1",
            f"*/4 * * * * cd {root} && /usr/bin/flock -n {root}/tmp/poll_ig_deal_payments.lock {python} manage.py poll_ig_deal_payments --limit 50 >> {root}/logs/poll_ig_deal_payments.log 2>&1",
        )

    def test_install_migrates_loose_jobs_preserves_other_blocks_and_is_idempotent(self):
        watchdog_block = (
            f"{WATCHDOG_BEGIN}\n# codex:instagram-bot-watchdog\n"
            f"* * * * * cd {self.django_root} && /opt/watchdog\n"
            "# END TWOCOMMS INSTAGRAM BOT WATCHDOG\n"
        )
        tracking_block = (
            f"{TRACKING_BEGIN}\n# codex:nova-poshta-tracking\n"
            f"*/5 * * * * cd {self.django_root} && /opt/tracking\n"
            "# END TWOCOMMS NOVA POSHTA TRACKING\n"
        )
        original = "MAILTO=ops@example.test\n" + watchdog_block
        original += "\n".join(self._legacy_lines()) + "\n"
        original += tracking_block + "17 4 * * * /opt/unrelated\n"
        self.crontab_file.write_text(original, encoding="utf-8")

        first = self._run("--install")
        first_content = self.crontab_file.read_text(encoding="utf-8")
        second = self._run("--install")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.crontab_file.read_text(encoding="utf-8"), first_content)
        self.assertIn(watchdog_block, first_content)
        self.assertIn(tracking_block, first_content)
        self.assertIn("17 4 * * * /opt/unrelated", first_content)
        self.assertEqual(first_content.count(BEGIN_MARKER), 1)
        for command in (
            "reconcile_order_telegram_notifications",
            "reconcile_ig_checkout",
            "reconcile_ig_order_fulfillment",
            "poll_ig_deal_payments",
        ):
            self.assertEqual(
                sum(
                    f"manage.py {command}" in line
                    for line in first_content.splitlines()
                ),
                1,
            )
        self.assertNotIn("run_instagram_bot --ensure", first_content)
        self.assertNotIn("update_tracking_statuses", first_content)

    def test_managed_jobs_have_distinct_overlap_exit_timeout_and_bounds(self):
        self.assertEqual(self._run("--install").returncode, 0)
        content = self.crontab_file.read_text(encoding="utf-8")
        managed_lines = [
            line
            for line in content.splitlines()
            if " manage.py " in line
        ]

        self.assertEqual(len(managed_lines), 4)
        for line in managed_lines:
            self.assertIn(f"{self.fake_bin / 'flock'} -n -E 75", line)
            self.assertIn(f"{self.fake_bin / 'timeout'} --signal=TERM", line)
            self.assertIn("--limit", line)
        self.assertIn("timeout --signal=TERM 90s", content)
        self.assertIn("timeout --signal=TERM 180s", content)

    def test_check_detects_missing_and_drifted_block(self):
        self.assertNotEqual(self._run("--check").returncode, 0)
        self.assertEqual(self._run("--install").returncode, 0)
        self.assertEqual(self._run("--check").returncode, 0)
        original = self.crontab_file.read_text(encoding="utf-8")
        self.crontab_file.write_text(
            original.replace("--limit 100", "--limit 99", 1),
            encoding="utf-8",
        )

        drift = self._run("--check")

        self.assertNotEqual(drift.returncode, 0)
        self.assertIn("DRIFT", drift.stderr)

    def test_duplicate_or_coexisting_owner_is_rejected_without_writes(self):
        duplicate = self._legacy_lines()[1]
        for original in (
            f"{duplicate}\n{duplicate}\n",
            f"{BEGIN_MARKER}\n/managed\n{END_MARKER}\n{duplicate}\n",
            f"{BEGIN_MARKER}\n/one\n{END_MARKER}\n{BEGIN_MARKER}\n/two\n{END_MARKER}\n",
        ):
            with self.subTest(original=original):
                self.crontab_file.write_text(original, encoding="utf-8")
                before = self.crontab_file.read_bytes()

                result = self._run("--install")

                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.crontab_file.read_bytes(), before)

    def test_unknown_marker_version_is_rejected_without_writes(self):
        original = "# BEGIN TWOCOMMS INSTAGRAM PERIODIC JOBS v2\n/unknown\n"
        self.crontab_file.write_text(original, encoding="utf-8")
        before = self.crontab_file.read_bytes()

        result = self._run("--install")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.crontab_file.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
