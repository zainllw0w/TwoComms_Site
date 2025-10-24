#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def _ensure_env_file():
    """
    Автоматически подставляет DJANGO_ENV_FILE, чтобы manage-команды
    на сервере не требовали ручного `export`.
    """
    if os.environ.get("DJANGO_ENV_FILE"):
        env_candidate = Path(os.environ["DJANGO_ENV_FILE"])
        if env_candidate.exists():
            try:
                from dotenv import load_dotenv
            except Exception:
                load_dotenv = None
            if load_dotenv:
                load_dotenv(env_candidate)
        return

    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / ".env.production",
        base_dir.parent / ".env.production",
        base_dir / ".env",
        base_dir.parent / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            os.environ["DJANGO_ENV_FILE"] = str(candidate)
            try:
                from dotenv import load_dotenv
            except Exception:
                load_dotenv = None
            if load_dotenv:
                load_dotenv(candidate)
            break


def main():
    """Run administrative tasks."""
    _ensure_env_file()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
