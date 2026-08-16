"""Real warehouse migrations with one DTF-coupled leaf shadowed for tests."""

from pathlib import Path


_PACKAGE_DIR = Path(__file__).resolve().parent
_REAL_MIGRATIONS = _PACKAGE_DIR.parents[1] / "warehouse" / "migrations"
__path__ = [str(_PACKAGE_DIR), str(_REAL_MIGRATIONS)]
