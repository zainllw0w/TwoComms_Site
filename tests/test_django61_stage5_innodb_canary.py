import copy
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_stage5_innodb_canary.py"
SPEC = importlib.util.spec_from_file_location("stage5_innodb_canary", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        normalized = " ".join(sql.strip().split())
        lower = normalized.casefold()
        if lower.startswith("select version(), @@hostname, @@port, current_user(), database()"):
            self.rows = [(
                "11.4.12-MariaDB",
                "localhost",
                3307,
                "twc_dj61_disposable_test@localhost",
                self.connection.selected_database,
            )]
        elif lower == "select version()":
            self.rows = [("11.4.12-MariaDB",)]
        elif lower == "show engines":
            self.rows = [("InnoDB", "DEFAULT"), ("MyISAM", "YES")]
        elif lower.startswith("create database"):
            self.connection.admin.created = True
            self.rows = []
        elif lower.startswith("drop database"):
            self.connection.admin.created = False
            self.rows = []
        elif "information_schema.schemata" in lower:
            self.rows = [("leftover",)] if self.connection.admin.created else []
        elif lower.startswith("use "):
            self.rows = []
        elif lower.startswith("create table") and " like " not in lower:
            name = normalized.split("CREATE TABLE", 1)[1].split("(", 1)[0].strip().strip("`")
            engine = "InnoDB" if "engine=innodb" in lower else "MyISAM"
            self.connection.tables[name] = {"engine": engine, "rows": []}
            self.rows = []
        elif lower.startswith("create table") and " like " in lower:
            name = normalized.split("CREATE TABLE", 1)[1].split("LIKE", 1)[0].strip().strip("`")
            source = normalized.split("LIKE", 1)[1].strip().strip("`")
            original = self.connection.tables[source]
            self.connection.tables[name] = {"engine": original["engine"], "rows": list(original["rows"])}
            self.rows = []
        elif lower.startswith("insert into") and "select *" in lower:
            target = normalized.split("INSERT INTO", 1)[1].split("SELECT", 1)[0].strip().strip("`")
            source = normalized.rsplit("FROM", 1)[1].strip().strip("`")
            self.connection.tables[target]["rows"] = list(self.connection.tables[source]["rows"])
            self.rows = []
        elif lower.startswith("select engine from information_schema.tables"):
            table = str(params[1])
            item = self.connection.tables.get(table)
            self.rows = [(item["engine"],)] if item else []
        elif lower.startswith("select count(*) from"):
            table = normalized.rsplit("FROM", 1)[1].strip().strip("`")
            self.rows = [(len(self.connection.tables[table]["rows"]),)]
        elif lower.startswith("select id, payload from"):
            table = normalized.split("FROM", 1)[1].split("ORDER", 1)[0].strip().strip("`")
            self.rows = sorted(self.connection.tables[table]["rows"])
        elif lower.startswith("alter table") and "engine=innodb" in lower:
            table = normalized.split("ALTER TABLE", 1)[1].split("ENGINE", 1)[0].strip().strip("`")
            self.connection.tables[table]["engine"] = "InnoDB"
            self.rows = []
        elif lower.startswith("drop table"):
            table = normalized.split("DROP TABLE", 1)[1].strip().strip("`")
            self.connection.tables.pop(table, None)
            self.rows = []
        elif lower.startswith("rename table"):
            parts = normalized.split()
            source, target = parts[2].strip("`"), parts[4].strip("`")
            self.connection.tables[target] = self.connection.tables.pop(source)
            self.rows = []
        else:
            raise AssertionError(f"unhandled SQL: {normalized}")

    def executemany(self, sql, values):
        normalized = " ".join(sql.strip().split())
        table = normalized.split("INSERT INTO", 1)[1].split("(", 1)[0].strip().strip("`")
        self.connection.tables[table]["rows"].extend(tuple(value) for value in values)
        self.rows = []

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class _Connection:
    vendor = "mysql"

    def __init__(self, admin, selected_database=None):
        self.admin = admin
        self.selected_database = selected_database
        self.tables = {}
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        return None

    def close(self):
        self.closed = True


class _Admin(_Connection):
    def __init__(self):
        super().__init__(self)
        self.created = False


class Stage5InnodbCanaryTests(unittest.TestCase):
    def setUp(self):
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix="twc-dj61-stage5-canary-proof-"
        )
        self.backup_artifact = (
            Path(self._temporary_directory.name) / "candidate-backup.sql"
        )
        self.backup_artifact.write_bytes(b"verified disposable backup artifact\n")

    def tearDown(self):
        self._temporary_directory.cleanup()

    @staticmethod
    def _identity(**overrides):
        identity = {
            "environment": "disposable",
            "database_role": "temporary",
            "server_vendor": "mariadb",
            "server_hostname": "localhost",
            "server_port": 3307,
            "db_user": "twc_dj61_disposable_test",
        }
        identity.update(overrides)
        return identity

    def _preflight(self, *, rows=4):
        backup_sha256 = hashlib.sha256(self.backup_artifact.read_bytes()).hexdigest()
        index_sha256 = hashlib.sha256(
            b"PRIMARY(id);payload_lookup(payload)"
        ).hexdigest()
        return {
            "schema": 1,
            "scope": "disposable_non-DTF_canary_only",
            "candidate": {
                "table": "stage5_synthetic_legacy",
                "source_engine": "MyISAM",
                "target_engine": "InnoDB",
                "exact_rows": rows,
                "index_inventory_complete": True,
                "index_count": 2,
                "index_sha256": index_sha256,
                "fulltext_inventory_complete": True,
                "fulltext_indexes": 0,
            },
            "writer_audit": {
                "complete": True,
                "active_writers": 0,
            },
            "orphan_scan": {
                "complete": True,
                "orphan_count": 0,
            },
            "backup": {
                "artifact_path": str(self.backup_artifact),
                "verified": True,
                "size_bytes": self.backup_artifact.stat().st_size,
                "sha256": backup_sha256,
                "rows": rows,
                "index_sha256": index_sha256,
            },
            "rehearsal": {
                "measured": True,
                "conversion_seconds": 0.05,
                "rollback_seconds": 0.04,
                "approved_max_seconds": 1.0,
            },
            "rollback": {
                "rehearsed": True,
                "verified": True,
                "write_loss_safe": True,
                "strategy": "maintenance_window",
                "write_freeze_verified": True,
                "restored_rows": rows,
                "restored_index_sha256": index_sha256,
                "backup_sha256": backup_sha256,
            },
        }

    def _run(self, factory, *, rows=4, preflight=None, **overrides):
        kwargs = {
            "rows": rows,
            "allow_disposable": True,
            "disposable_interlock": MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
            "connection_identity": self._identity(),
            "preflight": self._preflight(rows=rows) if preflight is None else preflight,
        }
        kwargs.update(overrides)
        return MODULE.run_disposable_innodb_canary(factory, **kwargs)

    def test_full_disposable_canary_verifies_backup_conversion_timing_and_rollback(self):
        admin = _Admin()
        connections = {None: admin}

        def factory(database):
            if database is None:
                return admin
            connection = _Connection(admin)
            connections[database] = connection
            return connection

        report = self._run(factory)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["preflight"]["status"], "verified")
        self.assertEqual(
            report["preflight"]["candidate"], "stage5_synthetic_legacy"
        )
        self.assertNotIn(str(self.backup_artifact), repr(report))
        self.assertTrue(report["backup"]["verified"])
        self.assertEqual(report["conversion"]["to_engine"], "InnoDB")
        self.assertTrue(report["rollback"]["verified"])
        self.assertGreaterEqual(report["backup"]["seconds"], 0)
        self.assertGreaterEqual(report["conversion"]["seconds"], 0)
        self.assertGreaterEqual(report["rollback"]["seconds"], 0)
        self.assertTrue(report["cleanup_verified"])
        self.assertFalse(admin.created)

        selected = _Admin()
        selected.selected_database = "production_db"
        with self.assertRaisesRegex(RuntimeError, "selects a database"):
            self._run(lambda _database: selected)
        self.assertFalse(selected.created)

    def test_preflight_evidence_fails_before_connection_or_ddl(self):
        def forbidden(_database):
            raise AssertionError("connection factory must not be called")

        with self.assertRaisesRegex(RuntimeError, "preflight evidence missing"):
            MODULE.run_disposable_innodb_canary(
                forbidden,
                rows=4,
                allow_disposable=True,
                disposable_interlock=MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
                connection_identity=self._identity(),
                preflight=None,
            )

        invalid_proofs = []

        def invalid(label, path, value, message):
            proof = copy.deepcopy(self._preflight())
            target = proof
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = value
            invalid_proofs.append((label, proof, message))

        invalid("boolean schema", ("schema",), True, "preflight scope")
        invalid("DTF candidate", ("candidate", "table"), "dtf_order", "non-DTF")
        invalid(
            "missing backup artifact",
            ("backup", "artifact_path"),
            str(self.backup_artifact.with_name("missing.sql")),
            "backup artifact",
        )
        invalid(
            "unverified backup",
            ("backup", "verified"),
            False,
            "backup verification",
        )
        invalid(
            "backup size mismatch", ("backup", "size_bytes"), 1, "backup size"
        )
        invalid(
            "backup digest mismatch",
            ("backup", "sha256"),
            "0" * 64,
            "backup SHA-256",
        )
        invalid(
            "backup rows mismatch", ("backup", "rows"), 3, "backup row contract"
        )
        invalid(
            "row contract mismatch",
            ("candidate", "exact_rows"),
            3,
            "row contract",
        )
        invalid(
            "index inventory incomplete",
            ("candidate", "index_inventory_complete"),
            False,
            "index inventory",
        )
        invalid(
            "empty index contract",
            ("candidate", "index_count"),
            0,
            "index contract",
        )
        invalid(
            "index contract mismatch",
            ("backup", "index_sha256"),
            "1" * 64,
            "index contract",
        )
        invalid(
            "fulltext inventory incomplete",
            ("candidate", "fulltext_inventory_complete"),
            False,
            "FULLTEXT inventory",
        )
        invalid(
            "fulltext index present",
            ("candidate", "fulltext_indexes"),
            1,
            "FULLTEXT indexes",
        )
        invalid(
            "orphan scan incomplete",
            ("orphan_scan", "complete"),
            False,
            "orphan scan",
        )
        invalid(
            "orphan found", ("orphan_scan", "orphan_count"), 1, "orphans"
        )
        invalid(
            "writer audit incomplete",
            ("writer_audit", "complete"),
            False,
            "writer audit",
        )
        invalid(
            "active writer found",
            ("writer_audit", "active_writers"),
            1,
            "active writers",
        )
        invalid(
            "timing absent",
            ("rehearsal", "measured"),
            False,
            "rehearsal timing",
        )
        invalid(
            "conversion outside limit",
            ("rehearsal", "conversion_seconds"),
            2.0,
            "approved timing limit",
        )
        invalid(
            "rollback outside limit",
            ("rehearsal", "rollback_seconds"),
            2.0,
            "approved timing limit",
        )
        invalid(
            "rollback not rehearsed",
            ("rollback", "rehearsed"),
            False,
            "rollback rehearsal",
        )
        invalid(
            "rollback not verified",
            ("rollback", "verified"),
            False,
            "rollback rehearsal",
        )
        invalid(
            "rollback not write-loss-safe",
            ("rollback", "write_loss_safe"),
            False,
            "write-loss-safe",
        )
        invalid(
            "unsafe rollback strategy",
            ("rollback", "strategy"),
            "backup_restore",
            "rollback strategy",
        )
        invalid(
            "write freeze unverified",
            ("rollback", "write_freeze_verified"),
            False,
            "write freeze",
        )
        invalid(
            "online rollback without reverse sync",
            ("rollback", "strategy"),
            "dual_write",
            "reverse sync",
        )
        invalid(
            "restored rows mismatch",
            ("rollback", "restored_rows"),
            3,
            "rollback row contract",
        )
        invalid(
            "restored indexes mismatch",
            ("rollback", "restored_index_sha256"),
            "2" * 64,
            "rollback index contract",
        )
        invalid(
            "rollback artifact mismatch",
            ("rollback", "backup_sha256"),
            "3" * 64,
            "rollback backup contract",
        )

        for label, proof, message in invalid_proofs:
            with self.subTest(label=label):
                with self.assertRaisesRegex(RuntimeError, message):
                    self._run(forbidden, preflight=proof)

    def test_safety_interlocks_fail_before_connection(self):
        def forbidden(_database):
            raise AssertionError("connection factory must not be called")

        with self.assertRaisesRegex(ValueError, "allow_disposable"):
            MODULE.run_disposable_innodb_canary(forbidden)
        with self.assertRaisesRegex(RuntimeError, "interlock missing"):
            MODULE.run_disposable_innodb_canary(
                forbidden, allow_disposable=True
            )
        with self.assertRaisesRegex(RuntimeError, "dedicated disposable port"):
            MODULE.run_disposable_innodb_canary(
                forbidden,
                allow_disposable=True,
                disposable_interlock=MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
                connection_identity=self._identity(server_port=3306),
            )
        with self.assertRaisesRegex(ValueError, "local MariaDB"):
            MODULE.run_disposable_innodb_canary(
                forbidden,
                host="195.191.25.63",
                allow_disposable=True,
                disposable_interlock=MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
                connection_identity=self._identity(),
            )
        with self.assertRaisesRegex(ValueError, "default disposable alias"):
            MODULE.run_disposable_innodb_canary(
                forbidden,
                database_alias="dtf",
                allow_disposable=True,
                disposable_interlock=MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
                connection_identity=self._identity(),
            )

        with self.assertRaisesRegex(ValueError, "temporary socket"):
            MODULE.run_disposable_innodb_canary(
                forbidden,
                unix_socket="/var/lib/mysql/mysql.sock",
                allow_disposable=True,
                disposable_interlock=MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
                connection_identity=self._identity(),
            )

        admin = _Admin()
        with self.assertRaisesRegex(RuntimeError, "hostname mismatch"):
            MODULE.run_disposable_innodb_canary(
                lambda _database: admin,
                allow_disposable=True,
                disposable_interlock=MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
                connection_identity=self._identity(server_hostname="wrong-host"),
                preflight=self._preflight(rows=250),
            )
        self.assertFalse(admin.created)

    def test_row_limit_and_non_mariadb_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "between"):
            MODULE.run_disposable_innodb_canary(
                lambda _database: _Admin(),
                rows=4.0,
                allow_disposable=True,
                disposable_interlock=MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
                connection_identity=self._identity(),
                preflight=self._preflight(rows=4),
            )

        with self.assertRaisesRegex(ValueError, "between"):
            MODULE.run_disposable_innodb_canary(
                lambda _database: _Admin(),
                rows=MODULE.MAX_ROWS + 1,
                allow_disposable=True,
                disposable_interlock=MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
                connection_identity=self._identity(),
            )

        class SQLiteConnection(_Admin):
            vendor = "sqlite"

        with self.assertRaisesRegex(RuntimeError, "MariaDB/MySQL"):
            MODULE.run_disposable_innodb_canary(
                lambda _database: SQLiteConnection(),
                allow_disposable=True,
                disposable_interlock=MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
                connection_identity=self._identity(),
                preflight=self._preflight(rows=250),
            )


if __name__ == "__main__":
    unittest.main()
