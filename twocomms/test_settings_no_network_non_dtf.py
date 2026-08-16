"""No-network SQLite profile with the production DTF app fully excluded."""

from test_settings_no_network import *  # noqa: F401,F403


INSTALLED_APPS = [
    app
    for app in INSTALLED_APPS
    if app not in {"dtf", "dtf.apps.DtfConfig"}
]
DATABASES = {"default": DATABASES["default"]}
DATABASE_ROUTERS = []
ALLOWED_HOSTS = [host for host in ALLOWED_HOSTS if "dtf" not in host.casefold()]
TEST_DTF_SCOPE = "excluded"
