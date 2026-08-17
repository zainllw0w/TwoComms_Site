import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_nova_poshta_tracking_cron.sh"
BEGIN_MARKER = "# BEGIN TWOCOMMS NOVA POSHTA TRACKING"
END_MARKER = "# END TWOCOMMS NOVA POSHTA TRACKING"


class InstallNovaPoshtaTrackingCronTests(unittest.TestCase):
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
        self._write_executable("nice", "#!/usr/bin/env bash\nexit 0\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_executable(self, name, content):
        path = self.fake_bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _env(self):
        env = os.environ.copy()
        env.update({
            "PATH": f"{self.fake_bin}:/usr/bin:/bin",
            "FAKE_CRONTAB_FILE": str(self.crontab_file),
            "TWC_PROJECT_ROOT": str(self.project_root),
            "TWC_DJANGO_ROOT": str(self.django_root),
            "TWC_PYTHON": str(self.python),
            "TWC_FLOCK_BIN": str(self.fake_bin / "flock"),
            "TWC_TIMEOUT_BIN": str(self.fake_bin / "timeout"),
            "TWC_NICE_BIN": str(self.fake_bin / "nice"),
        })
        return env

    def _run(self, mode):
        return subprocess.run(
            ["bash", str(INSTALL_SCRIPT), mode],
            env=self._env(), text=True, capture_output=True, timeout=10,
        )

    def test_install_is_idempotent_and_preserves_unrelated_cron(self):
        self.crontab_file.write_text("MAILTO=ops@example.test\n17 4 * * * /opt/other-job", encoding="utf-8")
        first = self._run("--install")
        first_content = self.crontab_file.read_bytes()
        second = self._run("--install")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.crontab_file.read_bytes(), first_content)
        self.assertIn("17 4 * * * /opt/other-job", first_content.decode())
        self.assertEqual(first_content.decode().count(BEGIN_MARKER), 1)
        self.assertIn(
            f"{self.fake_bin / 'flock'} -n -E 75",
            first_content.decode(),
        )
        self.assertIn(
            f"{self.fake_bin / 'timeout'} --signal=TERM --kill-after=15s 240s",
            first_content.decode(),
        )
        self.assertIn("--kill-after=15s", first_content.decode())

    def test_malformed_or_duplicate_markers_are_rejected_without_writes(self):
        for original in (
            f"{BEGIN_MARKER}\n* * * * * /broken\n",
            f"{END_MARKER}\n",
            f"{BEGIN_MARKER}\n/one\n{END_MARKER}\n{BEGIN_MARKER}\n/two\n{END_MARKER}\n",
        ):
            with self.subTest(original=original):
                self.crontab_file.write_text(original, encoding="utf-8")
                before = self.crontab_file.read_bytes()
                result = self._run("--install")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.crontab_file.read_bytes(), before)

    def test_check_detects_missing_block(self):
        self.assertNotEqual(self._run("--check").returncode, 0)
