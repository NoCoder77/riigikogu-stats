"""Resolve project resource paths (SQL schema, etc.) across source, install, and frozen builds."""
from __future__ import annotations

import sys
from pathlib import Path


def get_sql_dir() -> Path:
    """Return directory containing schema_sqlite.sql / views_sqlite.sql.

    Order: PyInstaller extract dir, then package-adjacent ``sql/``, then project-root ``sql/``.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "sql"

    package_dir = Path(__file__).resolve().parent
    # Prefer sql shipped next to the package (wheel / copied into src/riigikogu_stats/sql)
    pkg_sql = package_dir / "sql"
    if (pkg_sql / "schema_sqlite.sql").is_file():
        return pkg_sql

    # Editable / source tree: <project>/src/riigikogu_stats/paths.py → <project>/sql
    root_sql = package_dir.parents[1] / "sql"
    if (root_sql / "schema_sqlite.sql").is_file():
        return root_sql

    raise FileNotFoundError(
        "Could not find sql/schema_sqlite.sql (checked package sql/ and project sql/)"
    )


def sqlite_path_from_url(database_url: str) -> str:
    """Parse sqlite:/// URL to a filesystem path or ``:memory:``.

    Supports relative paths, Unix absolute (``sqlite:////tmp/db``), and Windows
    drive paths (``sqlite:///C:/data/db``).
    """
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// URLs are supported")
    raw = database_url[len("sqlite:///") :]
    if raw == ":memory:" or raw.startswith(":memory:"):
        return ":memory:"
    return raw
