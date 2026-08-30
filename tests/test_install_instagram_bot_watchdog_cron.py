import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_instagram_bot_watchdog_cron.sh"
SUPERVISOR_SCRIPT = REPO_ROOT / "scripts" / "instagram_bot_supervisor.py"
BEGIN_MARKER = "# BEGIN TWOCOMMS INSTAGRAM BOT WATCHDOG"
END_MARKER = "# END TWOCOMMS INSTAGRAM BOT WATCHDOG"


class InstallInstagramBotWatchdogCronTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.crontab_file = self.root / "crontab"
        self.project_root = self.root / "TwoComms_Site"
        self.django_root = self.project_root / "twocomms"
        self.django_root.mkdir(parents=True)
        self.python = self.root / "python"
        self.python.write_text("", encoding="utf-8")
        self.python.chmod(0o700)
        self._write_executable(
            "crontab",
            """#!/usr/bin/env bash
set -eu
if [ "${1:-}" = "-l" ]; then
  if [ -f "$FAKE_CRONTAB_FILE" ]; then cat "$FAKE_CRONTAB_FILE"; exit 0; fi
  echo 'no crontab for test' >&2; exit 1
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
                "TWC_PROJECT_ROOT": str(self.project_root),
                "TWC_DJANGO_ROOT": str(self.django_root),
                "TWC_PYTHON": str(self.python),
                "TWC_FLOCK_BIN": str(self.fake_bin / "flock"),
                "TWC_TIMEOUT_BIN": str(self.fake_bin / "timeout"),
                "TWC_IG_SUPERVISOR_SCRIPT": str(SUPERVISOR_SCRIPT),
            }
        )
        return env

    def _run(self, mode, extra_env=None):
        env = self._env()
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(INSTALL_SCRIPT), mode],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_install_migrates_django_watchdog_to_stdlib_and_is_idempotent(self):
        legacy = (
            f"* * * * * cd {self.django_root} && {self.python} manage.py "
            f"run_instagram_bot --ensure >> {self.django_root}/tmp/ig_bot_cron.log 2>&1"
        )
        self.crontab_file.write_text(
            f"MAILTO=ops@example.test\n{legacy}\n17 4 * * * /opt/other-job\n",
            encoding="utf-8",
        )

        first = self._run("--install")
        installed = self.crontab_file.read_bytes()
        second = self._run("--install")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.crontab_file.read_bytes(), installed)
        content = installed.decode()
        self.assertEqual(content.count(BEGIN_MARKER), 1)
        self.assertIn("instagram_bot_supervisor.py --ensure", content)
        self.assertIn("--kill-after=5s 20s", content)
        self.assertIn("DJANGO_ENV=production", content)
        self.assertNotIn("manage.py run_instagram_bot --ensure", content)
        self.assertIn("17 4 * * * /opt/other-job", content)

    def test_check_detects_drift_without_writing(self):
        self.assertEqual(self._run("--install").returncode, 0)
        original = self.crontab_file.read_text(encoding="utf-8")
        self.crontab_file.write_text(original.replace("20s", "21s"), encoding="utf-8")
        before = self.crontab_file.read_bytes()

        result = self._run("--check")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.crontab_file.read_bytes(), before)

    def test_known_previous_managed_owner_is_migrated(self):
        old_owner = (
            f"* * * * * cd {self.django_root} && "
            "DJANGO_ENV=production DJANGO_SETTINGS_MODULE=twocomms.production_settings "
            f"{self.fake_bin / 'flock'} -n -E 75 {self.django_root}/tmp/ig_bot_watchdog.lock "
            f"{self.fake_bin / 'timeout'} --signal=TERM --kill-after=15s 75s "
            f"{self.python} manage.py run_instagram_bot --ensure >> "
            f"{self.django_root}/tmp/ig_bot_cron.log 2>&1"
        )
        self.crontab_file.write_text(
            f"{BEGIN_MARKER}\n# codex:instagram-bot-watchdog\n{old_owner}\n{END_MARKER}\n",
            encoding="utf-8",
        )
        result = self._run("--install")
        self.assertEqual(result.returncode, 0, result.stderr)
        content = self.crontab_file.read_text(encoding="utf-8")
        self.assertIn("instagram_bot_supervisor.py --ensure", content)
        self.assertNotIn("manage.py run_instagram_bot --ensure", content)

    def test_duplicate_or_unknown_loose_owner_fails_closed(self):
        unknown = (
            f"*/2 * * * * cd {self.django_root} && {self.python} "
            "manage.py run_instagram_bot --ensure >/tmp/unknown 2>&1\n"
        )
        self.crontab_file.write_text(unknown, encoding="utf-8")
        before = self.crontab_file.read_bytes()

        result = self._run("--install")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.crontab_file.read_bytes(), before)

    def test_reversed_markers_fail_closed(self):
        self.crontab_file.write_text(
            f"{END_MARKER}\n/unknown\n{BEGIN_MARKER}\n",
            encoding="utf-8",
        )
        before = self.crontab_file.read_bytes()
        result = self._run("--install")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.crontab_file.read_bytes(), before)

    def test_managed_and_loose_watchdogs_cannot_coexist(self):
        self.assertEqual(self._run("--install").returncode, 0)
        loose = (
            f"* * * * * cd {self.django_root} && {self.python} manage.py "
            f"run_instagram_bot --ensure >> {self.django_root}/tmp/ig_bot_cron.log 2>&1\n"
        )
        self.crontab_file.write_text(
            self.crontab_file.read_text(encoding="utf-8") + loose,
            encoding="utf-8",
        )
        before = self.crontab_file.read_bytes()
        result = self._run("--install")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.crontab_file.read_bytes(), before)

    def test_unsafe_or_missing_paths_are_rejected_before_write(self):
        cases = (
            {"TWC_DJANGO_ROOT": "relative/root"},
            {"TWC_PYTHON": "python"},
            {"TWC_FLOCK_BIN": str(self.root / "missing")},
            {"TWC_TIMEOUT_BIN": "relative/timeout"},
            {"TWC_IG_SUPERVISOR_SCRIPT": str(self.root / "missing.py")},
        )
        for extra_env in cases:
            with self.subTest(extra_env=extra_env):
                try:
                    self.crontab_file.unlink()
                except FileNotFoundError:
                    pass
                result = self._run("--install", extra_env)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.crontab_file.exists())

    def test_crontab_read_error_fails_closed(self):
        self._write_executable(
            "crontab",
            """#!/usr/bin/env bash
if [ "${1:-}" = "-l" ]; then echo 'permission denied' >&2; exit 1; fi
exit 99
""",
        )
        result = self._run("--install")
        self.assertEqual(result.returncode, 69)
        self.assertFalse(self.crontab_file.exists())

    def test_unknown_managed_command_is_not_silently_replaced(self):
        self.crontab_file.write_text(
            f"{BEGIN_MARKER}\n# codex:instagram-bot-watchdog\n/bin/unknown\n{END_MARKER}\n",
            encoding="utf-8",
        )
        before = self.crontab_file.read_bytes()
        result = self._run("--install")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.crontab_file.read_bytes(), before)

    def test_pre_revert_rollback_restores_legacy_owner_and_is_checkable(self):
        self.crontab_file.write_text("17 4 * * * /opt/unrelated\n", encoding="utf-8")
        self.assertEqual(self._run("--install").returncode, 0)

        rollback = self._run("--rollback")
        rollback_content = self.crontab_file.read_text(encoding="utf-8")

        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(self._run("--check-rollback").returncode, 0)
        self.assertNotEqual(self._run("--check").returncode, 0)
        self.assertEqual(
            rollback_content.count("manage.py run_instagram_bot --ensure"),
            1,
        )
        self.assertNotIn("instagram_bot_supervisor.py --ensure", rollback_content)
        self.assertIn("17 4 * * * /opt/unrelated", rollback_content)

        self.assertEqual(self._run("--install").returncode, 0)
        restored = self.crontab_file.read_text(encoding="utf-8")
        self.assertIn("instagram_bot_supervisor.py --ensure", restored)


if __name__ == "__main__":
    unittest.main()
