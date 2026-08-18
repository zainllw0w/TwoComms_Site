import importlib.util
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
        if lower.startswith("select version(), @@hostname, @@port, current_user()"):
            self.rows = [("11.4.12-MariaDB", "localhost", 3306, "twc_dj61_disposable_test@localhost")]
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

    def __init__(self, admin):
        self.admin = admin
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
    @staticmethod
    def _identity(**overrides):
        identity = {
            "environment": "disposable",
            "database_role": "temporary",
            "server_vendor": "mariadb",
            "server_hostname": "localhost",
            "server_port": 3306,
            "db_user": "twc_dj61_disposable_test",
        }
        identity.update(overrides)
        return identity

    def test_full_disposable_canary_verifies_backup_conversion_timing_and_rollback(self):
        admin = _Admin()
        connections = {None: admin}

        def factory(database):
            if database is None:
                return admin
            connection = _Connection(admin)
            connections[database] = connection
            return connection

        report = MODULE.run_disposable_innodb_canary(
            factory,
            rows=4,
            allow_disposable=True,
            disposable_interlock=MODULE.DISPOSABLE_INNODB_CANARY_INTERLOCK,
            connection_identity=self._identity(),
        )
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["backup"]["verified"])
        self.assertEqual(report["conversion"]["to_engine"], "InnoDB")
        self.assertTrue(report["rollback"]["verified"])
        self.assertGreaterEqual(report["backup"]["seconds"], 0)
        self.assertGreaterEqual(report["conversion"]["seconds"], 0)
        self.assertGreaterEqual(report["rollback"]["seconds"], 0)
        self.assertTrue(report["cleanup_verified"])
        self.assertFalse(admin.created)

    def test_safety_interlocks_fail_before_connection(self):
        def forbidden(_database):
            raise AssertionError("connection factory must not be called")

        with self.assertRaisesRegex(ValueError, "allow_disposable"):
            MODULE.run_disposable_innodb_canary(forbidden)
        with self.assertRaisesRegex(RuntimeError, "interlock missing"):
            MODULE.run_disposable_innodb_canary(
                forbidden, allow_disposable=True
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
            )
        self.assertFalse(admin.created)

    def test_row_limit_and_non_mariadb_fail_closed(self):
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
            )


if __name__ == "__main__":
    unittest.main()
