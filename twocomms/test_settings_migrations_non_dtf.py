"""No-network migration drift profile for the real non-DTF graph."""

from test_settings_no_network_non_dtf import *  # noqa: F401,F403


INSTALLED_APPS = [
    *INSTALLED_APPS,
    "test_support.dtf_stub.apps.DtfStubConfig",
]
MIGRATION_MODULES = {
    "dtf": "test_support.dtf_stub.migrations",
    "warehouse": "test_support.warehouse_migrations_non_dtf",
}
TEST_MIGRATION_GRAPH = "non-dtf-real-with-dtf-edge-stubbed"
