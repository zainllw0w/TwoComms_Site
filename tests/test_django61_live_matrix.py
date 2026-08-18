"""Contracts for the sanitized Django 6.1 production release matrix."""

from __future__ import annotations

import io
import json
import os
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import run_django61_live_matrix as matrix


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_django61_live_matrix.py"


class LiveMatrixEntrypointTests(unittest.TestCase):
    def test_release_matrix_script_exists(self):
        self.assertTrue(SCRIPT.is_file())

    def test_cli_exposes_separate_server_and_http_modes(self):
        parser = matrix.build_parser()

        server = parser.parse_args(["server", "--phase", "preflight"])
        http = parser.parse_args(["http", "--phase", "post-deploy"])

        self.assertEqual((server.mode, server.phase), ("server", "preflight"))
        self.assertEqual((http.mode, http.phase), ("http", "post-deploy"))


class GitSnapshotTests(unittest.TestCase):
    SHA = "a" * 40

    def _output(self, values):
        def command_output(command):
            return values[tuple(command)]

        return command_output

    def test_post_deploy_requires_head_origin_main_and_expected_sha_to_match(self):
        values = {
            ("git", "rev-parse", "HEAD"): self.SHA,
            ("git", "branch", "--show-current"): "main",
            ("git", "status", "--porcelain=v1", "--untracked-files=no"): "",
            ("git", "rev-parse", "refs/remotes/origin/main"): self.SHA,
        }

        snapshot = matrix.git_snapshot(
            phase="post-deploy",
            expected_sha=self.SHA,
            command_output=self._output(values),
        )

        self.assertEqual(snapshot["sha"], self.SHA)
        self.assertEqual(snapshot["branch"], "main")
        self.assertTrue(snapshot["tracked_clean"])

    def test_post_deploy_rejects_a_stale_origin_main(self):
        values = {
            ("git", "rev-parse", "HEAD"): self.SHA,
            ("git", "branch", "--show-current"): "main",
            ("git", "status", "--porcelain=v1", "--untracked-files=no"): "",
            ("git", "rev-parse", "refs/remotes/origin/main"): "b" * 40,
        }

        with self.assertRaisesRegex(matrix.MatrixFailure, "git_revision_mismatch"):
            matrix.git_snapshot(
                phase="post-deploy",
                expected_sha=self.SHA,
                command_output=self._output(values),
            )

    def test_tracked_changes_or_a_non_main_branch_block_server_checks(self):
        base = {
            ("git", "rev-parse", "HEAD"): self.SHA,
            ("git", "branch", "--show-current"): "main",
            ("git", "status", "--porcelain=v1", "--untracked-files=no"): "",
        }
        for command, value, failure in (
            (("git", "branch", "--show-current"), "feature", "git_branch_invalid"),
            (
                ("git", "status", "--porcelain=v1", "--untracked-files=no"),
                " M file.py",
                "git_tracked_tree_dirty",
            ),
        ):
            with self.subTest(failure=failure), self.assertRaisesRegex(
                matrix.MatrixFailure, failure
            ):
                matrix.git_snapshot(
                    phase="preflight",
                    command_output=self._output({**base, command: value}),
                )


class RuntimeAndDatabaseTests(unittest.TestCase):
    def test_runtime_snapshot_delegates_to_exact_project_verifier(self):
        versions = {
            "python": "3.14.6",
            "django": "6.1",
            "djangorestframework": "3.18.0",
            "mysqlclient": "2.2.8",
        }
        verifier = mock.Mock()
        verifier.current_versions.return_value = versions
        verifier.validate_runtime.return_value = versions

        snapshot = matrix.runtime_snapshot(verifier=verifier)

        verifier.validate_runtime.assert_called_once_with(versions)
        self.assertEqual(snapshot["implementation"], "CPython")
        self.assertEqual(snapshot["django"], "6.1")
        self.assertNotIn("executable", snapshot)

    def test_database_snapshot_indexes_only_default_and_hides_connection_config(self):
        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, statement):
                self.statement = statement

            def fetchone(self):
                return ("11.4.12-MariaDB-cll-lve",)

        class Connection:
            vendor = "mysql"

            def cursor(self):
                return Cursor()

        class Registry:
            def __init__(self):
                self.requested = []

            def __getitem__(self, alias):
                self.requested.append(alias)
                return Connection()

        registry = Registry()

        snapshot = matrix.default_database_snapshot(connections_registry=registry)

        self.assertEqual(registry.requested, ["default"])
        self.assertEqual(snapshot["server"], "MariaDB")
        self.assertEqual(snapshot["version"], "11.4.12")
        for key in ("name", "host", "user", "password", "options"):
            self.assertNotIn(key, snapshot)

    def test_any_opened_alias_other_than_default_blocks_release(self):
        self.assertEqual(matrix.ensure_only_default_alias({"default"}), ["default"])
        with self.assertRaisesRegex(matrix.MatrixFailure, "database_alias_violation"):
            matrix.ensure_only_default_alias({"default", "dtf"})

    def test_django_system_check_is_scoped_to_default(self):
        invoked = []

        def call_command(*args, **kwargs):
            invoked.append((args, kwargs))

        self.assertEqual(
            matrix.django_database_check(call_command_func=call_command),
            {"alias": "default", "status": "ok"},
        )
        args, kwargs = invoked[0]
        self.assertEqual(args, ("check",))
        self.assertEqual(kwargs["databases"], ["default"])
        self.assertNotIn("dtf", repr(invoked).casefold())


class ConnectionGateTests(unittest.TestCase):
    def _connection(self, *, settings=None, row=None, usage_rows=None, table_rows=None):
        class Cursor:
            def __init__(self):
                self.statements = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, statement):
                self.statements.append(statement)

            def fetchone(self):
                return row or (
                    "utf8mb4",
                    "utf8mb4_unicode_ci",
                    "utf8mb4",
                    "utf8mb4",
                    "utf8mb4",
                    "utf8mb4_unicode_ci",
                    "InnoDB",
                    150,
                    20,
                    60,
                    "latin1",
                    "latin1_swedish_ci",
                )

            def fetchall(self):
                statement = self.statements[-1].upper()
                if "INFORMATION_SCHEMA.TABLES" in statement:
                    return table_rows or [
                        ("orders_order", "InnoDB", "utf8mb4_unicode_ci", "utf8mb4")
                    ]
                return usage_rows or [
                    ("Threads_connected", "3"),
                    ("Max_used_connections", "12"),
                ]

        class Connection:
            vendor = "mysql"

            def __init__(self):
                self.settings_dict = settings or {
                    "ENGINE": "django.db.backends.mysql",
                    "CONN_MAX_AGE": 0,
                    "CONN_HEALTH_CHECKS": True,
                    "OPTIONS": {
                        "charset": "utf8mb4",
                        "init_command": "SET SESSION default_storage_engine=INNODB",
                    },
                }
                self.cursor_instance = Cursor()

            def cursor(self):
                return self.cursor_instance

        return Connection()

    def test_connection_gate_proves_settings_session_schema_engine_and_budget(self):
        connection = self._connection()

        snapshot = matrix.connection_gate_snapshot(connection)

        self.assertEqual(snapshot["conn_max_age"], 0)
        self.assertTrue(snapshot["conn_health_checks"])
        self.assertEqual(snapshot["charset"], "utf8mb4")
        self.assertEqual(snapshot["schema_charset"], "utf8mb4")
        self.assertEqual(snapshot["session_charset"], "utf8mb4")
        self.assertEqual(snapshot["storage_engine"], "InnoDB")
        self.assertEqual(snapshot["max_connections"], 150)
        self.assertEqual(snapshot["max_user_connections"], 20)
        self.assertEqual(snapshot["wait_timeout"], 60)
        self.assertEqual(snapshot["character_set_server"], "latin1")
        self.assertEqual(snapshot["collation_server"], "latin1_swedish_ci")
        self.assertEqual(snapshot["threads_connected"], 3)
        self.assertEqual(snapshot["max_used_connections"], 12)
        self.assertEqual(
            snapshot["connection_usage"],
            {"threads_connected": 3, "max_used_connections": 12},
        )
        self.assertEqual(len(connection.cursor_instance.statements), 2)
        self.assertTrue(connection.cursor_instance.statements[0].lstrip().startswith("SELECT"))
        self.assertTrue(connection.cursor_instance.statements[1].lstrip().startswith("SHOW"))
        self.assertFalse(
            any(
                statement.lstrip().upper().startswith(
                    ("ALTER", "CREATE", "DELETE", "DROP", "INSERT", "SET", "UPDATE")
                )
                for statement in connection.cursor_instance.statements
            )
        )

    def test_connection_gate_fails_closed_for_unsafe_settings_and_server_values(self):
        cases = (
            ({"CONN_MAX_AGE": 60}, "database_conn_max_age_invalid"),
            ({"CONN_HEALTH_CHECKS": False}, "database_health_checks_invalid"),
            ({"OPTIONS": {"charset": "latin1"}}, "database_charset_config_invalid"),
            ({"OPTIONS": {"init_command": "SET NAMES utf8mb4"}}, "database_storage_engine_config_invalid"),
        )
        for override, failure in cases:
            safe_options = {
                "charset": "utf8mb4",
                "init_command": "SET SESSION default_storage_engine=INNODB",
            }
            settings = {
                "ENGINE": "django.db.backends.mysql",
                "CONN_MAX_AGE": 0,
                "CONN_HEALTH_CHECKS": True,
                "OPTIONS": safe_options,
            }
            settings.update(override)
            if "OPTIONS" in override:
                settings["OPTIONS"] = {**safe_options, **override["OPTIONS"]}
            with self.subTest(failure=failure), self.assertRaisesRegex(
                matrix.MatrixFailure, failure
            ):
                matrix.connection_gate_snapshot(self._connection(settings=settings))

        for row, failure in (
            (("latin1", "latin1_swedish_ci", "utf8mb4", "utf8mb4", "utf8mb4", "utf8mb4_unicode_ci", "InnoDB", 150, 20, 60, "latin1", "latin1_swedish_ci"), "database_charset_invalid"),
            (("utf8mb4", "utf8mb4_unicode_ci", "latin1", "latin1", "latin1", "latin1_swedish_ci", "InnoDB", 150, 20, 60, "latin1", "latin1_swedish_ci"), "database_charset_invalid"),
            (("utf8mb4", "latin1_swedish_ci", "utf8mb4", "utf8mb4", "utf8mb4", "utf8mb4_unicode_ci", "InnoDB", 150, 20, 60, "latin1", "latin1_swedish_ci"), "database_charset_invalid"),
            (("utf8mb4", "utf8mb4_unicode_ci", "utf8mb4", "utf8mb4", "utf8mb4", "utf8mb4_unicode_ci", "MyISAM", 150, 20, 60, "latin1", "latin1_swedish_ci"), "database_storage_engine_invalid"),
            (("utf8mb4", "utf8mb4_unicode_ci", "utf8mb4", "utf8mb4", "utf8mb4", "utf8mb4_unicode_ci", "InnoDB", 150, 40, 60, "latin1", "latin1_swedish_ci"), "database_connection_budget_invalid"),
            (("utf8mb4", "utf8mb4_unicode_ci", "utf8mb4", "utf8mb4", "utf8mb4", "utf8mb4_unicode_ci", "InnoDB", 100, 20, 60, "latin1", "latin1_swedish_ci"), "database_connection_budget_invalid"),
            (("utf8mb4", "utf8mb4_unicode_ci", "utf8mb4", "utf8mb4", "utf8mb4", "utf8mb4_unicode_ci", "InnoDB", 150, 20, 30, "latin1", "latin1_swedish_ci"), "database_wait_timeout_invalid"),
            (("utf8mb4", "utf8mb4_unicode_ci", "utf8mb4", "utf8mb4", "utf8mb4", "utf8mb4_unicode_ci", "InnoDB", 150, 20, 60, "utf8mb4", "utf8mb4_unicode_ci"), "database_host_charset_invalid"),
            (("utf8mb4", "utf8mb4_unicode_ci", "utf8mb4", "utf8mb4", "utf8mb4", "utf8mb4_unicode_ci", "InnoDB", 150, 20, 60, "latin1", "utf8mb4_unicode_ci"), "database_host_charset_invalid"),
        ):
            with self.subTest(failure=failure), self.assertRaisesRegex(
                matrix.MatrixFailure, failure
            ):
                matrix.connection_gate_snapshot(self._connection(row=row))

        for usage_rows, failure in (
            ([ ("Threads_connected", "3") ], "database_connection_usage_invalid"),
            ([ ("Threads_connected", "not-an-int"), ("Max_used_connections", "12") ], "database_connection_usage_invalid"),
            ([ ("Threads_connected", "13"), ("Max_used_connections", "12") ], "database_connection_usage_invalid"),
        ):
            with self.subTest(failure=failure), self.assertRaisesRegex(
                matrix.MatrixFailure, failure
            ):
                matrix.connection_gate_snapshot(
                    self._connection(usage_rows=usage_rows)
                )

    def test_connection_gate_fails_closed_for_incomplete_host_row(self):
        with self.assertRaisesRegex(matrix.MatrixFailure, "database_connection_gate_invalid"):
            matrix.connection_gate_snapshot(
                self._connection(row=("utf8mb4",) * 9)
            )

    def test_non_dtf_table_inventory_is_charset_complete_and_excludes_tracked_prefix(self):
        connection = self._connection(
            table_rows=[
                ("orders_order", "InnoDB", "utf8mb4_unicode_ci", "utf8mb4"),
                ("storefront_product", "MyISAM", "utf8mb4_general_ci", "utf8mb4"),
            ]
        )

        snapshot = matrix.non_dtf_table_inventory_snapshot(connection)

        self.assertEqual(snapshot["table_count"], 2)
        self.assertEqual(snapshot["excluded_table_prefix"], "dtf_")
        self.assertEqual(snapshot["tables"][0]["table_name"], "orders_order")
        statements = connection.cursor_instance.statements
        self.assertEqual(len(statements), 1)
        self.assertIn("information_schema.tables", statements[0].casefold())
        self.assertIn("not like", statements[0].casefold())

    def test_non_dtf_table_inventory_fails_closed_for_incomplete_rows(self):
        connection = self._connection(table_rows=[("orders_order", "InnoDB")])
        with self.assertRaisesRegex(
            matrix.MatrixFailure, "database_table_inventory_invalid"
        ):
            matrix.non_dtf_table_inventory_snapshot(connection)

    def test_non_dtf_table_inventory_fails_closed_for_untracked_charset_or_prefix(self):
        for row in (
            ("orders_order", "InnoDB", "latin1_swedish_ci", "latin1"),
            ("dtf_order", "InnoDB", "utf8mb4_unicode_ci", "utf8mb4"),
        ):
            with self.subTest(row=row), self.assertRaisesRegex(
                matrix.MatrixFailure, "database_table_inventory_invalid"
            ):
                matrix.non_dtf_table_inventory_snapshot(
                    self._connection(table_rows=[row])
                )

class MigrationAndPassengerTests(unittest.TestCase):
    def test_pending_plan_excludes_dtf_targets_and_migrations(self):
        captured_targets = []

        class Executor:
            def __init__(self, connection):
                self.connection = connection
                self.loader = types.SimpleNamespace(
                    graph=types.SimpleNamespace(
                        leaf_nodes=lambda: [("storefront", "0096"), ("dtf", "0004")]
                    )
                )

            def migration_plan(self, targets):
                captured_targets.extend(targets)
                return [
                    (types.SimpleNamespace(app_label="dtf", name="0004"), False),
                    (
                        types.SimpleNamespace(app_label="storefront", name="0096"),
                        False,
                    ),
                ]

        pending = matrix.pending_non_dtf_migrations(
            object(), executor_factory=Executor
        )

        self.assertEqual(captured_targets, [("storefront", "0096")])
        self.assertEqual(pending, ["storefront.0096"])
        with self.assertRaisesRegex(matrix.MatrixFailure, "pending_non_dtf_migrations"):
            matrix.migration_snapshot(object(), executor_factory=Executor)

    def test_passenger_reads_comm_only_and_requires_lswsgi(self):
        commands = []

        def command_output(command):
            commands.append(tuple(command))
            return "bash\nlswsgi\nlswsgi\n"

        snapshot = matrix.passenger_snapshot(command_output=command_output)

        self.assertEqual(snapshot, {"lswsgi_processes": 2, "status": "ok"})
        self.assertEqual(
            commands,
            [("ps", "-u", str(os.getuid()), "-o", "comm=")],
        )
        self.assertFalse(any("args" in item for item in commands[0]))


class FakeResponse:
    def __init__(self, status, body=b"", headers=None):
        self.status = status
        self._body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit=-1):
        return self._body


class HttpMatrixTests(unittest.TestCase):
    def test_allowlist_contains_only_approved_non_dtf_hosts(self):
        hosts = {matrix.urlsplit(probe.url).hostname for probe in matrix.HTTP_PROBES}

        self.assertEqual(
            hosts,
            {
                "twocomms.shop",
                "management.twocomms.shop",
                "fin.twocomms.shop",
                "storage.twocomms.shop",
            },
        )
        self.assertFalse(any("dtf" in (host or "").casefold() for host in hosts))
        matrix.validate_http_probes(matrix.HTTP_PROBES)

    def test_any_dtf_hostname_is_rejected_before_network_access(self):
        probe = matrix.HttpProbe("forbidden", "https://dtf.twocomms.shop/", 200)

        with self.assertRaisesRegex(matrix.MatrixFailure, "http_host_forbidden"):
            matrix.validate_http_probes((probe,))

    def test_redirect_handler_never_follows_redirects(self):
        request = matrix.Request("https://twocomms.shop/")
        handler = matrix.NoRedirectHandler()

        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {"Location": "/login/"},
            "https://twocomms.shop/login/",
        )

        self.assertIsNone(redirected)

    def test_probe_uses_release_bot_user_agent_and_checks_health_json(self):
        seen = []

        def open_http(request, timeout):
            seen.append((request, timeout))
            return FakeResponse(200, b'{"status":"ok"}')

        result = matrix.probe_http_route(
            matrix.HttpProbe(
                "management-bot-health",
                "https://management.twocomms.shop/bot/health/",
                200,
                json_status="ok",
            ),
            open_http=open_http,
        )

        request, timeout = seen[0]
        self.assertEqual(request.get_header("User-agent"), "TwoCommsReleaseBot/1.0")
        self.assertEqual(timeout, 15)
        self.assertEqual(
            result,
            {"name": "management-bot-health", "status": "ok", "status_code": 200},
        )
        self.assertNotIn("body", result)
        self.assertNotIn("headers", result)

    def test_bot_health_requires_strict_ok_payload(self):
        def open_http(_request, _timeout):
            return FakeResponse(200, b'{"status":"degraded"}')

        with self.assertRaisesRegex(matrix.MatrixFailure, "http_health_invalid"):
            matrix.probe_http_route(
                matrix.HttpProbe(
                    "management-bot-health",
                    "https://management.twocomms.shop/bot/health/",
                    200,
                    json_status="ok",
                ),
                open_http=open_http,
            )

    def test_redirect_contract_checks_location_without_following(self):
        def open_http(_request, _timeout):
            return FakeResponse(302, headers={"Location": "/login/?next=/health/"})

        result = matrix.probe_http_route(
            matrix.HttpProbe(
                "finance-health",
                "https://fin.twocomms.shop/health/",
                302,
                location_path="/login/",
            ),
            open_http=open_http,
        )

        self.assertEqual(result["status_code"], 302)
        self.assertNotIn("location", result)

    def test_redirect_contract_rejects_a_path_that_only_contains_login(self):
        def open_http(_request, _timeout):
            return FakeResponse(302, headers={"Location": "/unexpected/login/"})

        with self.assertRaisesRegex(matrix.MatrixFailure, "http_redirect_invalid"):
            matrix.probe_http_route(
                matrix.HttpProbe(
                    "finance-health",
                    "https://fin.twocomms.shop/health/",
                    302,
                    location_path="/login/",
                ),
                open_http=open_http,
            )

    def test_redirect_contract_rejects_an_external_login_location(self):
        def open_http(_request, _timeout):
            return FakeResponse(
                302,
                headers={"Location": "https://example.invalid/login/"},
            )

        with self.assertRaisesRegex(matrix.MatrixFailure, "http_redirect_invalid"):
            matrix.probe_http_route(
                matrix.HttpProbe(
                    "finance-health",
                    "https://fin.twocomms.shop/health/",
                    302,
                    location_path="/login/",
                ),
                open_http=open_http,
            )

    def test_http_matrix_uses_four_workers_and_preserves_contract_order(self):
        workers = []

        class ImmediateFuture:
            def __init__(self, value):
                self.value = value

            def result(self):
                return self.value

        class Executor:
            def __init__(self, max_workers):
                workers.append(max_workers)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def submit(self, function, probe):
                return ImmediateFuture(function(probe))

        probes = matrix.HTTP_PROBES[:2]
        with mock.patch.object(matrix, "ThreadPoolExecutor", Executor):
            results = matrix.probe_non_dtf_routes(
                probes=probes,
                worker=lambda probe: {
                    "name": probe.name,
                    "status": "ok",
                    "status_code": probe.expected_status,
                },
            )

        self.assertEqual(workers, [4])
        self.assertEqual([item["name"] for item in results], [p.name for p in probes])


class SanitizationTests(unittest.TestCase):
    def test_payload_removes_credentials_bodies_headers_env_and_exceptions(self):
        payload = matrix.sanitized_payload(
            {
                "status": "failed",
                "database": {
                    "alias": "default",
                    "server": "MariaDB",
                    "version": "11.4.12",
                    "name": "private_database",
                    "host": "private_host",
                    "user": "private_user",
                    "password": "private_password",
                },
                "body": "private_body",
                "headers": {"Set-Cookie": "private_cookie"},
                "cookies": "private_cookie",
                "env": {"SECRET": "private_secret"},
                "executable": "/private/python",
                "exception": RuntimeError("private_exception"),
                "access_token": "private_access_token",
                "database_password": "private_database_password",
                "api_key": "private_api_key",
                "private_key": "private_private_key",
                "probes": [{"name": "homepage", "status": "ok"}],
            }
        )
        rendered = json.dumps(payload, sort_keys=True)

        self.assertEqual(payload["database"]["alias"], "default")
        self.assertEqual(payload["probes"][0]["name"], "homepage")
        for private_value in (
            "private_database",
            "private_host",
            "private_user",
            "private_password",
            "private_body",
            "private_cookie",
            "private_secret",
            "/private/python",
            "private_exception",
                "private_access_token",
                "private_database_password",
                "private_api_key",
                "private_private_key",
            ):
            self.assertNotIn(private_value, rendered)

    def test_cli_never_prints_raw_unexpected_exception(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(
            matrix,
            "run_http_matrix",
            side_effect=RuntimeError("password=private_value"),
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            returncode = matrix.main(["http", "--phase", "preflight"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(returncode, 1)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["failed_check"], "internal_error")
        self.assertNotIn("private_value", stdout.getvalue() + stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
