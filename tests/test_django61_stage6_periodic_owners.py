import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/qa/django61-stage6-periodic-owners.json"
VALIDATOR = ROOT / "scripts/verify_django61_stage6_periodic_owners.py"


class Stage6PeriodicOwnerTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.jobs = self.manifest["jobs"]
        self.blocks = {}
        for job in self.jobs:
            self.blocks.setdefault(job["managed_block"], []).append(job)

    def crontab(self):
        lines = []
        for marker, jobs in self.blocks.items():
            lines.append(marker)
            for job in jobs:
                timeout = f" {job['timeout']}" if job["timeout_required"] else ""
                lines.append(
                    f"{job['cadence']} cd /srv/twocomms && {job['flock']} /srv/twocomms/{job['lock_path']}"
                    f"{timeout} /srv/twocomms/.venv/bin/python {job['command']} --limit 1"
                )
            lines.append(marker.replace("# BEGIN", "# END"))
        return "\n".join(lines) + "\n"

    def invoke_validator(self, crontab, manifest=MANIFEST, repo_root=ROOT):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(crontab)
            crontab_path = Path(handle.name)
        try:
            return subprocess.run(
                [sys.executable, str(VALIDATOR), "--manifest", str(manifest), "--crontab", str(crontab_path), "--repo-root", str(repo_root)],
                text=True, capture_output=True, check=False,
            )
        finally:
            crontab_path.unlink()

    def test_valid_non_dtf_contract(self):
        result = self.invoke_validator(self.crontab())
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["jobs"]), len(self.jobs))

    def test_duplicate_loose_owner_fails_closed(self):
        result = self.invoke_validator(self.crontab() + self.crontab().splitlines()[1] + "\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one owner", result.stderr)

    def test_duplicate_managed_block_fails_closed(self):
        result = self.invoke_validator(self.crontab() + self.crontab())
        self.assertNotEqual(result.returncode, 0)

    def test_missing_timeout_fails_closed(self):
        lines = self.crontab().splitlines()
        index = next(i for i, line in enumerate(lines) if "reconcile_ig_checkout" in line)
        lines[index] = lines[index].replace("/usr/bin/timeout --signal=TERM --kill-after=15s 90s", "")
        result = self.invoke_validator("\n".join(lines) + "\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bounded timeout", result.stderr)

    def test_dtf_is_rejected(self):
        result = self.invoke_validator(self.crontab() + "# DTF must remain excluded\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DTF", result.stderr)

    def test_rollback_path_is_required(self):
        broken = json.loads(MANIFEST.read_text(encoding="utf-8"))
        broken["rollback"]["path"] = "scripts/does-not-exist.sh"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(broken, handle)
            path = Path(handle.name)
        try:
            result = self.invoke_validator(self.crontab(), manifest=path)
        finally:
            path.unlink()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rollback path", result.stderr)


if __name__ == "__main__":
    unittest.main()
