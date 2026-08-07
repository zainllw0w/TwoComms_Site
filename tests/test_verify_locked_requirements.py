import hashlib
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class _Distribution:
    def __init__(self, name, version):
        self.metadata = {"Name": name}
        self.version = version


class VerifyLockedRequirementsTests(unittest.TestCase):
    def test_parses_multiline_hashed_lock_and_canonicalizes_names(self):
        from scripts.verify_locked_requirements import parse_lock

        lock = """
        # generated lock\n
        Django==5.2.11 \\
            --hash=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \\
            --hash=sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
        django-rest_framework==3.15.2; python_version >= '3.14' \\
            --hash=sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
        django_rest_framework==3.15.2
        """

        self.assertEqual(
            parse_lock(lock),
            {"django": "5.2.11", "django-rest-framework": "3.15.2"},
        )

    def test_rejects_unpinned_recursive_vcs_and_conflicting_entries(self):
        from scripts.verify_locked_requirements import LockParseError, parse_lock

        bad_locks = (
            "\n# comments only\n  # still empty\n",
            "requests>=2.0\n",
            "-r other-requirements.txt\n",
            "example @ git+https://github.com/example/example.git@abc123\n",
            "-e ./local-package\n",
            "Django==5.2.11\ndjango==5.2.10\n",
            "Django==5.2.11; python_version >= '3.14' --no-index\n",
            "Django==5.2.11; python_version >= '3.14' -e ./local\n",
            "Django==5.2.11; python_version >= '3.14' -r extras.txt\n",
            "Django==5.2.11; python_version >= '3.14' -c constraints.txt\n",
            "Django==5.2.11; python_version >= '3.14' foo\n",
        )
        for lock in bad_locks:
            with self.subTest(lock=lock):
                with self.assertRaises(LockParseError):
                    parse_lock(lock)

    def test_accepts_full_pep508_marker_forms_and_hash_continuations(self):
        from scripts.verify_locked_requirements import parse_lock

        lock = """
        Django==5.2.11;python_version>='3.14' \\
            --hash=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        backports.zoneinfo==0.2.1;'3.14'<=python_version
        marker-tilde==1.0;python_version~='3.14'
        marker-strict==1.0;'3.14'===python_version
        marker-nested==1.0;(python_version>='3.14' and (sys_platform=='linux' or os_name!='nt'))
        marker-membership==1.0;python_version not in '3.10 3.11'
        """

        self.assertEqual(
            parse_lock(lock),
            {
                "django": "5.2.11",
                "backports-zoneinfo": "0.2.1",
                "marker-tilde": "1.0",
                "marker-strict": "1.0",
                "marker-nested": "1.0",
                "marker-membership": "1.0",
            },
        )

    def test_rejects_unquoted_marker_values_and_trailing_marker_tokens(self):
        from scripts.verify_locked_requirements import LockParseError, parse_lock

        bad_markers = (
            "Django==5.2.11;python_version>=3.14\n",
            "Django==5.2.11; python_version >= 3.14\n",
            "Django==5.2.11;python_version>='3.14' plain\n",
            "Django==5.2.11;python_version>='3.14' -e ./local\n",
            "Django==5.2.11;python_version>='3.14' -r extras.txt\n",
            "Django==5.2.11;python_version>='3.14' -c constraints.txt\n",
            "Django==5.2.11;(python_version>='3.14'\n",
        )
        for lock in bad_markers:
            with self.subTest(lock=lock):
                with self.assertRaises(LockParseError):
                    parse_lock(lock)

    @patch("scripts.verify_locked_requirements.metadata.version")
    @patch("scripts.verify_locked_requirements.metadata.distributions")
    def test_reports_missing_and_mismatched_distributions(self, distributions, version):
        from scripts.verify_locked_requirements import verify_environment

        distributions.return_value = [
            _Distribution("Django", "5.2.10"),
            _Distribution("requests", "2.31.0"),
            _Distribution("pip", "24.0"),
        ]
        version.side_effect = {"django": "5.2.10", "requests": KeyError()}.get

        result = verify_environment({"django": "5.2.11", "urllib3": "2.2.1"})

        self.assertEqual(result["missing"], ["urllib3"])
        self.assertEqual(result["mismatched"], ["django"])

    @patch("scripts.verify_locked_requirements.metadata.version")
    @patch("scripts.verify_locked_requirements.metadata.distributions")
    def test_rejects_unexpected_distributions_outside_bootstrap_allowlist(
        self, distributions, version
    ):
        from scripts.verify_locked_requirements import verify_environment

        distributions.return_value = [
            _Distribution("Django", "5.2.11"),
            _Distribution("pip", "24.0"),
            _Distribution("setuptools", "70.0"),
            _Distribution("wheel", "0.44.0"),
            _Distribution("unexpected-package", "1.0"),
        ]
        version.return_value = "5.2.11"

        result = verify_environment({"django": "5.2.11"})

        self.assertEqual(result["unexpected"], ["unexpected-package"])
        self.assertEqual(result["status"], "failed")

    @patch("scripts.verify_locked_requirements.metadata.version", return_value="5.2.11")
    @patch("scripts.verify_locked_requirements.metadata.distributions")
    def test_accepts_exact_versions_with_only_bootstrap_packaging_tools(
        self, distributions, _version
    ):
        from scripts.verify_locked_requirements import verify_environment

        distributions.return_value = [
            _Distribution("Django", "5.2.11"),
            _Distribution("pip", "24.0"),
            _Distribution("setuptools", "70.0"),
            _Distribution("wheel", "0.44.0"),
        ]

        result = verify_environment({"django": "5.2.11"})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["mismatched"], [])
        self.assertEqual(result["unexpected"], [])

    @patch("scripts.verify_locked_requirements.metadata.version", return_value="5.2.11")
    @patch("scripts.verify_locked_requirements.metadata.distributions")
    def test_metadata_contains_python_version_lock_sha_and_requirement_count(
        self, distributions, _version
    ):
        from scripts.verify_locked_requirements import main

        distributions.return_value = [_Distribution("Django", "5.2.11")]
        with TemporaryDirectory() as directory:
            lock_path = Path(directory) / "requirements.lock"
            lock_path.write_text("Django==5.2.11\n", encoding="utf-8")
            output = io.StringIO()
            with patch("scripts.verify_locked_requirements.platform.python_version", return_value="3.14.1"), redirect_stdout(output):
                self.assertEqual(main(["--lock", str(lock_path)]), 0)

        result = json.loads(output.getvalue())
        self.assertEqual(
            set(result),
            {"status", "python", "lock_sha256", "requirement_count", "missing", "mismatched", "unexpected"},
        )
        self.assertEqual(result["python"], "3.14.1")
        self.assertEqual(result["lock_sha256"], hashlib.sha256(b"Django==5.2.11\n").hexdigest())
        self.assertEqual(result["requirement_count"], 1)

    @patch("scripts.verify_locked_requirements.metadata.version", return_value="5.2.11")
    @patch("scripts.verify_locked_requirements.metadata.distributions")
    def test_json_output_never_contains_environment_values(self, distributions, _version):
        from scripts.verify_locked_requirements import main

        distributions.return_value = [_Distribution("Django", "5.2.11")]
        with TemporaryDirectory() as directory:
            lock_path = Path(directory) / "requirements.lock"
            lock_path.write_text("Django==5.2.11\n", encoding="utf-8")
            output = io.StringIO()
            with patch.dict("os.environ", {"SECRET_KEY": "do-not-leak", "DATABASE_URL": "postgres://user:secret@example"}, clear=False), redirect_stdout(output):
                self.assertEqual(main(["--lock", str(lock_path)]), 0)

        self.assertNotIn("do-not-leak", output.getvalue())
        self.assertNotIn("postgres://", output.getvalue())
        self.assertNotIn(str(lock_path), output.getvalue())

    def test_invalid_lock_still_emits_sanitized_failure_schema(self):
        from scripts.verify_locked_requirements import main

        with TemporaryDirectory() as directory:
            lock_path = Path(directory) / "requirements.lock"
            lock_path.write_text("\n# comments only\n", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--lock", str(lock_path)]), 2)

        result = json.loads(output.getvalue())
        self.assertEqual(
            set(result),
            {"status", "python", "lock_sha256", "requirement_count", "missing", "mismatched", "unexpected"},
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["requirement_count"], 0)
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["mismatched"], [])
        self.assertEqual(result["unexpected"], [])


if __name__ == "__main__":
    unittest.main()
