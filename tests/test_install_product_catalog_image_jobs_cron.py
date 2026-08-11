import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_product_catalog_image_jobs_cron.sh"
BEGIN_MARKER = "# BEGIN TWOCOMMS PRODUCT CATALOG IMAGE JOBS"


class InstallProductCatalogImageJobsCronTests(unittest.TestCase):
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
  if [ -f "$FAKE_CRONTAB_FILE" ]; then cat "$FAKE_CRONTAB_FILE"; exit 0; fi
  echo 'no crontab for test' >&2
  exit 1
fi
cp "$1" "$FAKE_CRONTAB_FILE"
""",
        )

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
            "TWC_DJANGO_ROOT": str(self.django_root),
            "TWC_PYTHON": str(self.python),
        })
        return env

    def _run(self, mode):
        return subprocess.run(
            ["bash", str(INSTALL_SCRIPT), mode],
            env=self._env(),
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_install_is_idempotent_and_preserves_unrelated_cron(self):
        self.crontab_file.write_text("17 4 * * * /opt/other-job\n", encoding="utf-8")

        first = self._run("--install")
        first_content = self.crontab_file.read_text(encoding="utf-8")
        second = self._run("--install")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.crontab_file.read_text(encoding="utf-8"), first_content)
        self.assertIn("17 4 * * * /opt/other-job", first_content)
        self.assertEqual(first_content.count(BEGIN_MARKER), 1)
        self.assertIn("reconcile_image_optimization_jobs --max-jobs 4", first_content)
        self.assertIn("/usr/bin/flock -n", first_content)

    def test_check_detects_missing_or_drifted_block(self):
        self.assertNotEqual(self._run("--check").returncode, 0)
        self.assertEqual(self._run("--install").returncode, 0)
        self.assertEqual(self._run("--check").returncode, 0)
        self.crontab_file.write_text("# drift\n", encoding="utf-8")
        self.assertNotEqual(self._run("--check").returncode, 0)
