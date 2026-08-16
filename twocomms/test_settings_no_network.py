"""Deterministic SQLite test settings with external network denied."""

from __future__ import annotations

import os

from test_network_guard import install_external_network_guard


install_external_network_guard()

from test_settings import *  # noqa: E402,F401,F403


os.environ["SECRET_KEY"] = "test-secret-key-for-no-network-profile"
for _name in (
    "DATABASE_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_ADMIN_ID",
    "MANAGER_TG_BOT_TOKEN",
    "MANAGEMENT_TG_BOT_TOKEN",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "BINOTEL_SECRET",
    "META_ACCESS_TOKEN",
):
    os.environ[_name] = ""


TEST_NETWORK_POLICY = "deny-external"
TESTING = True
