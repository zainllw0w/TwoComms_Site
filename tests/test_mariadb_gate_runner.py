import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeAdmin:
    def __init__(
        self, *, host="127.0.0.1", port="3306", fail_at=None,
        fail_cleanup=False, fail_database_cleanup=False,
        identity=("11.4.12-MariaDB", "mariadb.org binary distribution"),
        residue=(False, False),
        existing=(False, False),
    ):
        self.calls = []
        self.host = host
        self.port = port
        self.fail_at = fail_at
        self.fail_cleanup = fail_cleanup
        self.fail_database_cleanup = fail_database_cleanup
        self.identity = identity
        self.residue = residue
        self.existing = existing

    def server_identity(self):
        self.calls.append(("server_identity",))
        return self.identity

    def create_database(self, name):
        self.calls.append(("create_database", name))
        if self.fail_at == "create_database":
            raise RuntimeError("create database failed")

    def create_user(self, username, password):
        self.calls.append(("create_user", username, password))
        if self.fail_at == "create_user":
            raise RuntimeError("create user failed")

    def grant_schema(self, username, database):
        self.calls.append(("grant_schema", username, database))
        if self.fail_at == "grant_schema":
            raise RuntimeError("grant schema failed")

    def ensure_namespace_absent(self, database, username):
        self.calls.append(("ensure_namespace_absent", database, username))
        if any(self.existing):
            from scripts.run_mariadb_gate import GateError

            objects = []
            if self.existing[0]:
                objects.append("database")
            if self.existing[1]:
                objects.append("user")
            raise GateError(
                "Refusing MariaDB gate: generated "
                + " and ".join(objects)
                + " already exists"
            )

    def drop_user(self, username):
        self.calls.append(("drop_user", username))
        if self.fail_cleanup:
            raise RuntimeError("drop user failed")

    def drop_database(self, database):
        self.calls.append(("drop_database", database))
        if self.fail_database_cleanup:
            raise RuntimeError("drop database failed")

    def verify_cleanup(self, database, username):
        self.calls.append(("verify_cleanup", database, username))
        return self.residue

    def close(self):
        self.calls.append(("close",))


class FakeCommandRunner:
    def __init__(self, *, returncode=0):
        self.calls = []
        self.returncode = returncode

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), kwargs))
        return subprocess.CompletedProcess(args, self.returncode, "", "migration failed")


class MariaDbGateRunnerTests(unittest.TestCase):
    def setUp(self):
        from scripts import run_mariadb_gate

        self.runner = run_mariadb_gate

    def test_manages_generated_schema_and_user_and_runs_from_project_root(self):
        admin = FakeAdmin()
        command = FakeCommandRunner()
        evidence = io.StringIO()

        result = self.runner.run_gate(
            server_mode="external",
            suite="lifecycle",
            admin=admin,
            command_runner=command,
            environ={
                "MARIADB_ADMIN_PASSWORD": "root-secret",
                "DB_NAME": "production-name",
                "DB_HOST": "production.database.example",
                "DB_PASSWORD": "production-password",
                "DB_PASSWORD_DTF": "production-dtf-password",
                "MANAGER_TG_BOT_TOKEN": "provider-secret",
                "META_ACCESS_TOKEN": "meta-secret",
                "PYTHONPATH": "/untrusted/import/path",
            },
            project_root=PROJECT_ROOT,
            output=evidence,
        )

        self.assertEqual(result["status"], "passed")
        created_db = next(call[1] for call in admin.calls if call[0] == "create_database")
        created_user = next(call[1] for call in admin.calls if call[0] == "create_user")
        self.assertRegex(created_db, r"^test_twocomms_ig_[a-f0-9]{12}$")
        self.assertRegex(created_user, r"^twc_ig_[a-f0-9]{12}$")
        self.assertEqual(created_db, next(call[2] for call in admin.calls if call[0] == "grant_schema"))
        self.assertEqual(created_user, next(call[1] for call in admin.calls if call[0] == "grant_schema"))
        self.assertEqual(
            [call[0] for call in admin.calls[-4:]],
            ["drop_user", "drop_database", "verify_cleanup", "close"],
        )
        self.assertTrue(command.calls)
        self.assertEqual(
            command.calls[0][0][1],
            str(PROJECT_ROOT / "twocomms" / "manage.py"),
        )
        self.assertTrue(Path(command.calls[0][0][1]).is_file())
        self.assertEqual(command.calls[0][1]["cwd"], str(PROJECT_ROOT / "twocomms"))
        child_env = command.calls[0][1]["env"]
        self.assertEqual(child_env["TEST_MARIADB_NAME"], created_db)
        self.assertNotIn("DB_NAME", child_env)
        self.assertNotIn("DB_PASSWORD", child_env)
        self.assertNotIn("DB_PASSWORD_DTF", child_env)
        self.assertNotIn("META_ACCESS_TOKEN", child_env)
        self.assertNotIn("PYTHONPATH", child_env)
        self.assertEqual(child_env["MANAGER_TG_BOT_TOKEN"], "")
        self.assertNotIn("TEST_MARIADB_REMOTE_ALLOWED", child_env)
        self.assertNotIn("root-secret", evidence.getvalue())
        self.assertNotIn("provider-secret", evidence.getvalue())
        self.assertIn("version=11.4.12-MariaDB", evidence.getvalue())
        self.assertIn("cleanup=verified", evidence.getvalue())

    def test_failure_still_cleans_schema_and_user(self):
        admin = FakeAdmin()
        command = FakeCommandRunner(returncode=1)

        with self.assertRaises(self.runner.GateError) as raised:
            self.runner.run_gate(
                server_mode="external",
                suite="lifecycle",
                admin=admin,
                command_runner=command,
                project_root=PROJECT_ROOT,
                environ={"MARIADB_ADMIN_PASSWORD": "root-secret"},
            )

        self.assertEqual(str(raised.exception.primary_error), "lifecycle command failed (1)")
        self.assertEqual(
            [call[0] for call in admin.calls][-4:],
            ["drop_user", "drop_database", "verify_cleanup", "close"],
        )

    def test_cleanup_failure_is_red_without_hiding_primary_error(self):
        admin = FakeAdmin(fail_cleanup=True)
        command = FakeCommandRunner(returncode=1)

        with self.assertRaises(self.runner.GateError) as raised:
            self.runner.run_gate(
                server_mode="external",
                suite="lifecycle",
                admin=admin,
                command_runner=command,
                project_root=PROJECT_ROOT,
                environ={"MARIADB_ADMIN_PASSWORD": "root-secret"},
            )

        self.assertEqual(str(raised.exception.primary_error), "lifecycle command failed (1)")
        self.assertEqual(str(raised.exception.cleanup_error), "drop user failed")
        self.assertEqual(len(raised.exception.cleanup_errors), 1)
        self.assertNotIn("MariaDB gate passed", raised.exception.args[0])

    def test_schema_cleanup_is_attempted_when_user_cleanup_fails(self):
        admin = FakeAdmin(fail_cleanup=True)

        with self.assertRaises(self.runner.GateError):
            self.runner.run_gate(
                server_mode="external",
                suite="lifecycle",
                admin=admin,
                command_runner=FakeCommandRunner(),
                project_root=PROJECT_ROOT,
                environ={"MARIADB_ADMIN_PASSWORD": "root-secret"},
            )

        self.assertEqual(
            [call[0] for call in admin.calls][-4:],
            ["drop_user", "drop_database", "verify_cleanup", "close"],
        )

    def test_all_cleanup_failures_are_retained_with_the_primary_error(self):
        admin = FakeAdmin(fail_cleanup=True, fail_database_cleanup=True)

        with self.assertRaises(self.runner.GateError) as raised:
            self.runner.run_gate(
                server_mode="external",
                suite="lifecycle",
                admin=admin,
                command_runner=FakeCommandRunner(returncode=1),
                project_root=PROJECT_ROOT,
                environ={"MARIADB_ADMIN_PASSWORD": "root-secret"},
            )

        self.assertEqual(str(raised.exception.primary_error), "lifecycle command failed (1)")
        self.assertEqual(
            [str(error) for error in raised.exception.cleanup_errors],
            ["drop user failed", "drop database failed"],
        )

    def test_partial_provisioning_still_attempts_idempotent_cleanup(self):
        admin = FakeAdmin(fail_at="create_user")

        with self.assertRaises(self.runner.GateError) as raised:
            self.runner.run_gate(
                server_mode="external",
                suite="lifecycle",
                admin=admin,
                command_runner=FakeCommandRunner(),
                project_root=PROJECT_ROOT,
                environ={"MARIADB_ADMIN_PASSWORD": "root-secret"},
            )

        self.assertEqual(str(raised.exception.primary_error), "create user failed")
        self.assertEqual(
            [call[0] for call in admin.calls[-4:]],
            ["drop_user", "drop_database", "verify_cleanup", "close"],
        )

    def test_existing_generated_database_is_never_dropped(self):
        admin = FakeAdmin(existing=(True, False))

        with self.assertRaises(self.runner.GateError) as raised:
            self.runner.run_gate(
                server_mode="external",
                suite="lifecycle",
                admin=admin,
                command_runner=FakeCommandRunner(),
                project_root=PROJECT_ROOT,
                environ={"MARIADB_ADMIN_PASSWORD": "root-secret"},
            )

        self.assertIn("database already exists", str(raised.exception))
        self.assertFalse(any(call[0].startswith("create_") for call in admin.calls))
        self.assertFalse(any(call[0].startswith("drop_") for call in admin.calls))

    def test_existing_generated_user_is_never_dropped(self):
        admin = FakeAdmin(existing=(False, True))

        with self.assertRaises(self.runner.GateError) as raised:
            self.runner.run_gate(
                server_mode="external",
                suite="lifecycle",
                admin=admin,
                command_runner=FakeCommandRunner(),
                project_root=PROJECT_ROOT,
                environ={"MARIADB_ADMIN_PASSWORD": "root-secret"},
            )

        self.assertIn("user already exists", str(raised.exception))
        self.assertFalse(any(call[0].startswith("create_") for call in admin.calls))
        self.assertFalse(any(call[0].startswith("drop_") for call in admin.calls))

    def test_remote_external_host_requires_explicit_opt_in_before_provisioning(self):
        admin = FakeAdmin(host="mariadb.example.test")

        with self.assertRaises(self.runner.GateError) as raised:
            self.runner.run_gate(
                server_mode="external",
                suite="lifecycle",
                admin=admin,
                command_runner=FakeCommandRunner(),
                project_root=PROJECT_ROOT,
                environ={"MARIADB_ADMIN_PASSWORD": "root-secret"},
            )

        self.assertIn("TEST_MARIADB_REMOTE_ALLOWED=1", str(raised.exception))
        self.assertFalse(any(call[0].startswith("create_") for call in admin.calls))

    def test_explicit_remote_opt_in_is_preserved_for_the_django_child(self):
        admin = FakeAdmin(host="mariadb.example.test")
        command = FakeCommandRunner()

        self.runner.run_gate(
            server_mode="external",
            suite="lifecycle",
            admin=admin,
            command_runner=command,
            project_root=PROJECT_ROOT,
            environ={
                "MARIADB_ADMIN_PASSWORD": "root-secret",
                "TEST_MARIADB_REMOTE_ALLOWED": "1",
            },
        )

        self.assertEqual(
            command.calls[0][1]["env"]["TEST_MARIADB_REMOTE_ALLOWED"],
            "1",
        )

    def test_admin_namespace_checks_cover_every_mariadb_user_host(self):
        admin = self.runner.AdminClient(
            host="127.0.0.1", port="3306", user="root", password="secret"
        )
        queries = []

        def query(statement):
            queries.append(statement)
            return (0,)

        admin._query_one = query
        admin.ensure_namespace_absent("test_twocomms_ig_collision", "twc_ig_collision")

        self.assertIn("WHERE User = 'twc_ig_collision'", queries[1])
        self.assertNotIn("Host =", queries[1])

    def test_admin_cleanup_drops_only_the_gate_owned_wildcard_account(self):
        admin = self.runner.AdminClient(
            host="127.0.0.1", port="3306", user="root", password="secret"
        )
        statements = []
        admin._sql = statements.append

        admin.drop_user("twc_ig_owned")

        self.assertEqual(
            statements,
            ["DROP USER IF EXISTS 'twc_ig_owned'@'%'"],
        )

    def test_native_start_preserves_startup_error_when_cleanup_also_fails(self):
        native = self.runner.NativeMariaDb(
            binaries={"mariadbd": "/missing/mariadbd", "mariadb-install-db": "/missing/install"},
            command_runner=FakeCommandRunner(returncode=1),
            project_root=PROJECT_ROOT,
        )
        with mock.patch.object(native, "close", side_effect=RuntimeError("cleanup failed")):
            with self.assertRaises(self.runner.GateError) as raised:
                native.start()

        self.assertIn("native MariaDB initialization failed", str(raised.exception.primary_error))
        self.assertEqual(str(raised.exception.cleanup_error), "cleanup failed")

    def test_refuses_a_configured_production_host_even_with_remote_opt_in(self):
        admin = FakeAdmin(host="production.database.example")

        with self.assertRaises(self.runner.GateError) as raised:
            self.runner.run_gate(
                server_mode="external",
                suite="lifecycle",
                admin=admin,
                command_runner=FakeCommandRunner(),
                project_root=PROJECT_ROOT,
                environ={
                    "MARIADB_ADMIN_PASSWORD": "root-secret",
                    "TEST_MARIADB_REMOTE_ALLOWED": "1",
                    "DB_NAME": "qlknpodo_MySQL_DB",
                    "DB_HOST": "production.database.example",
                },
            )

        self.assertIn("configured production database host", str(raised.exception))
        self.assertFalse(any(call[0].startswith("create_") for call in admin.calls))

    def test_rejects_wrong_engine_or_version_before_provisioning(self):
        identities = (
            ("9.4.0", "MySQL Community Server"),
            ("11.3.2-MariaDB", "mariadb.org binary distribution"),
        )
        for identity in identities:
            with self.subTest(identity=identity):
                admin = FakeAdmin(identity=identity)
                with self.assertRaises(self.runner.GateError) as raised:
                    self.runner.run_gate(
                        server_mode="external",
                        suite="lifecycle",
                        admin=admin,
                        command_runner=FakeCommandRunner(),
                        project_root=PROJECT_ROOT,
                        environ={"MARIADB_ADMIN_PASSWORD": "root-secret"},
                    )
                self.assertIn("MariaDB 11.4", str(raised.exception))
                self.assertFalse(any(call[0].startswith("create_") for call in admin.calls))

    def test_task_6b_advertises_the_narrow_checkout_concurrency_suite(self):
        self.assertEqual(self.runner.DEFAULT_SUITE, "lifecycle")
        self.assertEqual(
            self.runner.SUITES["checkout-concurrency"],
            (
                "management.tests_ig_checkout_models."
                "IgCheckoutProposalConcurrencyTests."
                "test_concurrent_replacement_creation_serializes_on_deal",
            ),
        )
        with self.assertRaises(self.runner.GateError):
            self.runner._validate_suite("full")

    def test_missing_django_entrypoint_fails_before_database_side_effects(self):
        admin = FakeAdmin()
        with tempfile.TemporaryDirectory() as empty_root:
            with self.assertRaises(self.runner.GateError) as raised:
                self.runner.run_gate(
                    server_mode="external",
                    suite="lifecycle",
                    admin=admin,
                    command_runner=FakeCommandRunner(),
                    project_root=Path(empty_root),
                    environ={"MARIADB_ADMIN_PASSWORD": "root-secret"},
                )

        self.assertIn("twocomms/manage.py", str(raised.exception))
        self.assertEqual(admin.calls, [])

    def test_native_mode_fails_closed_when_provisioner_is_missing(self):
        with self.assertRaises(self.runner.GateError) as raised:
            self.runner.run_gate(
                server_mode="native",
                suite="lifecycle",
                project_root=PROJECT_ROOT,
                environ={},
                command_runner=FakeCommandRunner(),
                native_binaries={"mariadbd": None, "mariadb-install-db": None},
            )

        self.assertIn("native MariaDB provisioning", str(raised.exception))

    def test_native_children_receive_only_the_sanitized_environment(self):
        source = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "DB_PASSWORD": "production-secret",
            "DB_PASSWORD_DTF": "production-dtf-secret",
            "META_ACCESS_TOKEN": "provider-secret",
            "GEMINI_API_KEY": "gemini-secret",
            "PYTHONPATH": "/untrusted/import/path",
        }
        init_runner = FakeCommandRunner()
        process = mock.Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        readiness_admin = mock.Mock()
        readiness_admin._sql.return_value = None

        with (
            mock.patch.object(self.runner.subprocess, "Popen", return_value=process) as popen,
            mock.patch.object(self.runner, "AdminClient", return_value=readiness_admin),
            mock.patch.object(self.runner, "_free_port", return_value=33307),
        ):
            server = self.runner.NativeMariaDb(
                binaries={
                    "mariadbd": "/fake/mariadbd",
                    "mariadb-install-db": "/fake/mariadb-install-db",
                },
                command_runner=init_runner,
                environment=self.runner._process_environment(source),
                project_root=PROJECT_ROOT,
            ).start()
            server.close()

        init_env = init_runner.calls[0][1]["env"]
        server_env = popen.call_args.kwargs["env"]
        init_args = init_runner.calls[0][0]
        server_args = popen.call_args.args[0]
        self.assertEqual(init_args[0], "/fake/mariadb-install-db")
        self.assertEqual(init_args[1], "--no-defaults")
        self.assertEqual(server_args[0], "/fake/mariadbd")
        self.assertEqual(server_args[1], "--no-defaults")
        self.assertEqual(init_env, server_env)
        for forbidden in (
            "DB_PASSWORD", "DB_PASSWORD_DTF", "META_ACCESS_TOKEN",
            "GEMINI_API_KEY", "PYTHONPATH",
        ):
            self.assertNotIn(forbidden, init_env)
        self.assertEqual(init_env["PYTHONNOUSERSITE"], "1")
        process.terminate.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
