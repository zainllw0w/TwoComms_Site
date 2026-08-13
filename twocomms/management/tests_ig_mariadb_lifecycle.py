"""Small live-DB lifecycle smoke suite invoked by the disposable gate."""

from django.db import connection
from django.test import SimpleTestCase


class InstagramMariaDbLifecycleTests(SimpleTestCase):
    databases = {"default"}

    def test_database_is_mariadb_and_schema_is_disposable(self):
        self.assertEqual(connection.vendor, "mysql")
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_twocomms_ig_"))
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION(), @@version_comment")
            version, version_comment = cursor.fetchone()
        self.assertIn("mariadb", f"{version} {version_comment}".lower())
        self.assertRegex(version, r"^11\.4(?:\.|-)")

    def test_database_connection_uses_utf8mb4(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@character_set_connection, @@collation_connection")
            charset, collation = cursor.fetchone()
        self.assertEqual(charset.lower(), "utf8mb4")
        self.assertIn("utf8mb4", collation.lower())
