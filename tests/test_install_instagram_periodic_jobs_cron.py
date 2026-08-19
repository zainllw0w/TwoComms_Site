import os
import shutil
import stat
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_instagram_periodic_jobs_cron.sh"
BEGIN_MARKER = "# BEGIN TWOCOMMS INSTAGRAM PERIODIC JOBS v1"
END_MARKER = "# END TWOCOMMS INSTAGRAM PERIODIC JOBS v1"
CALL_MARKER_NAME = "call_auto_analysis.enabled"
CALL_MARKER_TOKEN = b"call-auto-analysis-enabled-v1\n"
WATCHDOG_BEGIN = "# BEGIN TWOCOMMS INSTAGRAM BOT WATCHDOG"
TRACKING_BEGIN = "# BEGIN TWOCOMMS NOVA POSHTA TRACKING"
PRODUCTION_ENV_PREFIX = (
    "DJANGO_ENV=production "
    "DJANGO_SETTINGS_MODULE=twocomms.production_settings"
)


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

    def _legacy_lines(self):
        root = self.django_root
        python = self.python
        return (
            f"*/2 * * * * cd {root} && /usr/bin/flock -n {root}/tmp/order_telegram_reconcile.lock {python} manage.py reconcile_order_telegram_notifications --max-age-hours 168 --min-age-seconds 60 --limit 50 >> {root}/logs/order_telegram_reconcile.log 2>&1",
            f"*/2 * * * * cd {root} && /usr/bin/flock -n {root}/tmp/ig_checkout_reconcile.lock {python} manage.py reconcile_ig_checkout --limit 100 >> {root}/logs/ig_checkout_reconcile.log 2>&1",
            f"*/2 * * * * cd {root} && /usr/bin/flock -n {root}/tmp/ig_order_fulfillment.lock {python} manage.py reconcile_ig_order_fulfillment --limit 100 >> {root}/logs/ig_order_fulfillment.log 2>&1",
            f"*/4 * * * * cd {root} && /usr/bin/flock -n {root}/tmp/poll_ig_deal_payments.lock {python} manage.py poll_ig_deal_payments --limit 50 >> {root}/logs/poll_ig_deal_payments.log 2>&1",
            f"*/5 * * * * cd {root} && /usr/bin/flock -n {root}/tmp/run_call_ai_analyses.lock {python} manage.py run_call_ai_analyses --limit 1 >> {root}/logs/run_call_ai_analyses.log 2>&1",
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
            "run_call_ai_analyses",
            "check_ig_gemini_metadata_health",
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
        self.assertIn("# codex:call-auto-analysis", first_content)
        managed_lines = [
            line
            for line in first_content.splitlines()
            if "manage.py " in line
            and any(
                command in line
                for command in (
                    "reconcile_order_telegram_notifications",
                    "reconcile_ig_checkout",
                    "reconcile_ig_order_fulfillment",
                    "poll_ig_deal_payments",
                    "run_call_ai_analyses",
                    "check_ig_gemini_metadata_health",
                )
            )
        ]
        self.assertEqual(len(managed_lines), 6)
        for line in managed_lines:
            self.assertIn(f"&& {PRODUCTION_ENV_PREFIX} ", line)
        self.assertIn(
            f"{self.django_root}/tmp/run_call_ai_analyses.lock "
            "/bin/sh -c ",
            first_content,
        )
        gemini_lines = [line for line in first_content.splitlines() if "manage.py check_ig_gemini_metadata_health" in line]
        self.assertEqual(len(gemini_lines), 1)
        self.assertTrue(gemini_lines[0].startswith("0 * * * * "))
        self.assertIn("tmp/check_ig_gemini_metadata_health.lock", gemini_lines[0])
        self.assertIn("timeout", gemini_lines[0])
        self.assertIn(
            f"exec {self.fake_bin / 'timeout'} --signal=TERM --kill-after=15s 240s "
            f"{self.python} manage.py run_call_ai_analyses --limit 1",
            first_content,
        )

    def _install_and_get_call_command(self):
        result = self._run("--install")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self.crontab_file.read_text(encoding="utf-8").splitlines()
        return next(line for line in lines if "manage.py run_call_ai_analyses" in line)

    def _marker_path(self):
        return self.django_root / "tmp" / CALL_MARKER_NAME

    def _run_rendered_call(
        self, command, log_path, extra_env=None, flock_before_exec=None
    ):
        fake_flock = self.fake_bin / "flock"
        fake_timeout = self.fake_bin / "timeout"
        fake_python = self.root / "fake-python"
        flock_hook = flock_before_exec or ""
        fake_flock.write_text(
            "#!/usr/bin/env bash\nset -eu\nshift 4\n"
            f"{flock_hook}"
            "exec \"$@\"\n",
            encoding="utf-8",
        )
        fake_timeout.write_text(
            "#!/usr/bin/env bash\nset -eu\nshift 3\nexec \"$@\"\n",
            encoding="utf-8",
        )
        fake_python.write_text(
            f"#!/usr/bin/env bash\nprintf x >> {log_path}\n",
            encoding="utf-8",
        )
        for path in (fake_flock, fake_timeout, fake_python):
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        # Cron supplies the command after the five schedule fields to /bin/sh.
        command_body = command.split(" ", 5)[5].replace(
            str(self.python), str(fake_python)
        )
        env = self._env()
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["sh", "-c", command_body],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_call_job_gate_precedes_every_process_and_is_provider_neutral(self):
        line = self._install_and_get_call_command()
        marker = f"{self.django_root}/tmp/{CALL_MARKER_NAME}"
        gate = (
            f'if [ -f "{marker}" ] && [ ! -L "{marker}" ] && '
            f'[ "$("/usr/bin/find" "{marker}" -prune -type f -perm 600 '
            f'-print 2>/dev/null)" = "{marker}" ] && '
            '{ echo call-auto-analysis-enabled-v1 | "/usr/bin/cmp" -s - '
            f'"{marker}"; }}; then'
        )
        self.assertTrue(line.index(gate) < line.index("cd "))
        self.assertLess(line.index("cd "), line.index("flock"))
        self.assertLess(line.index("flock"), line.index("timeout"))
        self.assertLess(line.index("timeout"), line.index("manage.py"))
        self.assertLess(line.index("manage.py"), line.index(">>"))
        self.assertNotIn("binotel", line.lower())
        self.assertNotIn("%", line)

    def test_call_job_runs_only_with_exact_regular_marker(self):
        line = self._install_and_get_call_command()
        log_path = self.root / "python-started"
        marker = self._marker_path()
        invalid_markers = [None, b"", b"wrong\n", b"call-auto-analysis-enabled-v1", b"call-auto-analysis-enabled-v1\n\n"]
        for content in invalid_markers:
            with self.subTest(marker=content):
                if marker.exists() or marker.is_symlink():
                    marker.unlink()
                if content is not None:
                    marker.write_bytes(content)
                    marker.chmod(0o600)
                result = self._run_rendered_call(line, log_path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(log_path.exists(), f"python launched for {content!r}")

        marker.write_bytes(CALL_MARKER_TOKEN)
        marker.chmod(0o600)
        result = self._run_rendered_call(line, log_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log_path.read_text(encoding="utf-8"), "x")

        log_path.unlink()
        marker.chmod(0o644)
        result = self._run_rendered_call(line, log_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(log_path.exists())

        marker.unlink()
        marker.mkdir()
        result = self._run_rendered_call(line, log_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(log_path.exists())

        marker.rmdir()
        target = marker.with_name("marker-target")
        target.write_bytes(CALL_MARKER_TOKEN)
        marker.symlink_to(target)
        result = self._run_rendered_call(line, log_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(log_path.exists())

    def test_call_job_does_not_launch_when_cmp_fails(self):
        line = self._install_and_get_call_command()
        marker = self._marker_path()
        marker.write_bytes(CALL_MARKER_TOKEN)
        cmp_error = self.fake_bin / "cmp-error"
        cmp_error.write_text("#!/usr/bin/env bash\nexit 2\n", encoding="utf-8")
        cmp_error.chmod(cmp_error.stat().st_mode | stat.S_IXUSR)
        # The installed line uses the configured absolute cmp path at render time.
        self.crontab_file.write_text(
            self.crontab_file.read_text(encoding="utf-8").replace("/usr/bin/cmp", str(cmp_error)),
            encoding="utf-8",
        )
        line = next(line for line in self.crontab_file.read_text(encoding="utf-8").splitlines() if "manage.py run_call_ai_analyses" in line)
        result = self._run_rendered_call(line, self.root / "python-started")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "python-started").exists())

    def test_call_job_rechecks_marker_inside_flock_before_python(self):
        line = self._install_and_get_call_command()
        log_path = self.root / "python-started"
        marker = self._marker_path()
        marker.write_bytes(CALL_MARKER_TOKEN)
        marker.chmod(0o600)

        result = self._run_rendered_call(
            line,
            log_path,
            flock_before_exec=f'rm -f -- "{marker}"\n',
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(log_path.exists())

    def test_call_job_rejects_fifo_socket_and_unreadable_marker(self):
        short_root = Path(tempfile.mkdtemp(prefix="twc-", dir="/tmp")) / "r"
        short_root.mkdir()
        extra_env = {"TWC_DJANGO_ROOT": str(short_root)}
        marker = short_root / "tmp" / CALL_MARKER_NAME
        result = self._run("--install", extra_env)
        self.assertEqual(result.returncode, 0, result.stderr)
        line = next(
            line
            for line in self.crontab_file.read_text(encoding="utf-8").splitlines()
            if "manage.py run_call_ai_analyses" in line
        )
        log_path = self.root / "python-started"
        try:
            marker.parent.mkdir(exist_ok=True)
            os.mkfifo(marker)
            result = self._run_rendered_call(line, log_path, extra_env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(log_path.exists())
            marker.unlink()

            unix_socket = socket.socket(socket.AF_UNIX)
            try:
                unix_socket.bind(str(marker))
                result = self._run_rendered_call(line, log_path, extra_env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(log_path.exists())
            finally:
                unix_socket.close()
                marker.unlink(missing_ok=True)

            if os.geteuid() == 0:
                self.skipTest("root can read mode-000 files")
            marker.write_bytes(CALL_MARKER_TOKEN)
            marker.chmod(0)
            try:
                result = self._run_rendered_call(line, log_path, extra_env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(log_path.exists())
            finally:
                marker.chmod(0o600)
        finally:
            shutil.rmtree(short_root.parent, ignore_errors=True)

    def test_install_never_creates_call_marker(self):
        result = self._run("--install")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self._marker_path().exists())

    def test_install_migrates_ungated_managed_call_job_after_check_reports_drift(self):
        old_block = (
            f"{BEGIN_MARKER}\n# codex:binotel-call-ai\n"
            f"{self._legacy_lines()[-1]}\n{END_MARKER}\n"
        )
        self.crontab_file.write_text(
            "17 4 * * * /opt/unrelated\n" + old_block,
            encoding="utf-8",
        )

        drift = self._run("--check")
        install = self._run("--install")
        content = self.crontab_file.read_text(encoding="utf-8")

        self.assertNotEqual(drift.returncode, 0)
        self.assertIn("DRIFT", drift.stderr)
        self.assertEqual(install.returncode, 0, install.stderr)
        self.assertIn("17 4 * * * /opt/unrelated", content)
        self.assertIn("# codex:call-auto-analysis", content)
        self.assertNotIn("# codex:binotel-call-ai", content)
        self.assertIn(f"{self.django_root}/tmp/{CALL_MARKER_NAME}", content)

    def test_install_removes_loose_legacy_call_comment_with_job(self):
        self.crontab_file.write_text(
            "# codex:binotel-call-ai\n" + self._legacy_lines()[-1] + "\n",
            encoding="utf-8",
        )

        result = self._run("--install")
        content = self.crontab_file.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("# codex:binotel-call-ai", content)
        self.assertIn("# codex:call-auto-analysis", content)

    def test_cmp_path_must_be_absolute_executable_and_safe(self):
        for cmp_path in ("cmp", "relative/cmp", str(self.root / "missing-cmp")):
            with self.subTest(cmp_path=cmp_path):
                result = self._run("--install", {"TWC_CMP_BIN": cmp_path})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("cmp", result.stderr.lower())

    def test_installer_comparisons_use_configured_cmp_not_path(self):
        configured_cmp = self.fake_bin / "configured-cmp"
        configured_cmp.write_text(
            "#!/usr/bin/env bash\nexec /usr/bin/cmp \"$@\"\n",
            encoding="utf-8",
        )
        configured_cmp.chmod(configured_cmp.stat().st_mode | stat.S_IXUSR)
        path_cmp_dir = self.root / "path-cmp"
        path_cmp_dir.mkdir()
        path_cmp = path_cmp_dir / "cmp"
        path_cmp.write_text("#!/usr/bin/env bash\nexit 42\n", encoding="utf-8")
        path_cmp.chmod(path_cmp.stat().st_mode | stat.S_IXUSR)

        install = self._run(
            "--install", {"TWC_CMP_BIN": str(configured_cmp)}
        )
        self.assertEqual(install.returncode, 0, install.stderr)

        result = self._run(
            "--check",
            {
                "PATH": f"{path_cmp_dir}:{self._env()['PATH']}",
                "TWC_CMP_BIN": str(configured_cmp),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_find_path_must_be_absolute_executable_and_safe(self):
        for find_path in ("find", "relative/find", str(self.root / "missing-find")):
            with self.subTest(find_path=find_path):
                result = self._run("--install", {"TWC_FIND_BIN": find_path})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("find", result.stderr.lower())

    def test_managed_jobs_have_distinct_overlap_exit_timeout_and_bounds(self):
        self.assertEqual(self._run("--install").returncode, 0)
        content = self.crontab_file.read_text(encoding="utf-8")
        managed_lines = [
            line
            for line in content.splitlines()
            if " manage.py " in line
        ]

        self.assertEqual(len(managed_lines), 6)
        for line in managed_lines:
            self.assertIn(f"{self.fake_bin / 'flock'} -n -E 75", line)
            self.assertIn(f"{self.fake_bin / 'timeout'} --signal=TERM", line)
            self.assertIn("--kill-after=15s", line)
            if "check_ig_gemini_metadata_health" not in line:
                self.assertIn("--limit", line)
        self.assertIn("timeout --signal=TERM --kill-after=15s 90s", content)
        self.assertIn("timeout --signal=TERM --kill-after=15s 180s", content)
        self.assertIn("timeout --signal=TERM --kill-after=15s 240s", content)

    def test_install_removes_loose_gemini_metadata_owner(self):
        loose = (
            "# codex:ig-gemini-metadata-health\n"
            f"0 * * * * cd {self.django_root} && /usr/bin/flock -n -E 75 "
            f"{self.django_root}/tmp/check_ig_gemini_metadata_health.lock "
            f"/usr/bin/timeout --signal=TERM --kill-after=15s 90s {self.python} "
            "manage.py check_ig_gemini_metadata_health >> "
            f"{self.django_root}/logs/check_ig_gemini_metadata_health.log 2>&1\n"
        )
        self.crontab_file.write_text("MAILTO=ops@example.test\n" + loose, encoding="utf-8")

        result = self._run("--install")

        self.assertEqual(result.returncode, 0, result.stderr)
        content = self.crontab_file.read_text(encoding="utf-8")
        self.assertEqual(content.count("manage.py check_ig_gemini_metadata_health"), 1)
        self.assertEqual(content.count("# codex:ig-gemini-metadata-health"), 1)
        self.assertEqual(content.splitlines()[1], BEGIN_MARKER)

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

    def test_unknown_loose_owner_variant_is_rejected_without_writes(self):
        for cadence, command in (
            ("* * * * *", "reconcile_ig_checkout --limit 1"),
            ("*/5 * * * *", "run_call_ai_analyses --limit 2"),
            ("*/5 * * * *", "run_call_ai_analyses --limit 10"),
        ):
            with self.subTest(command=command):
                original = (
                    f"{cadence} cd {self.django_root} && {self.python} manage.py "
                    f"{command} >/tmp/alternate.log 2>&1\n"
                )
                self.crontab_file.write_text(original, encoding="utf-8")
                before = self.crontab_file.read_bytes()

                result = self._run("--install")

                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.crontab_file.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
