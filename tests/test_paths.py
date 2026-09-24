"""Tests for sqlite URL and SQL path helpers."""
from __future__ import annotations

import pytest

from riigikogu_stats.paths import get_sql_dir, sqlite_path_from_url


def test_sqlite_path_relative() -> None:
    assert sqlite_path_from_url("sqlite:///riigikogu.db") == "riigikogu.db"


def test_sqlite_path_memory() -> None:
    assert sqlite_path_from_url("sqlite:///:memory:") == ":memory:"


def test_sqlite_path_windows_drive() -> None:
    assert sqlite_path_from_url("sqlite:///C:/data/riigikogu.db") == "C:/data/riigikogu.db"


def test_sqlite_path_unix_absolute() -> None:
    assert sqlite_path_from_url("sqlite:////tmp/riigikogu.db") == "/tmp/riigikogu.db"


def test_sqlite_path_rejects_non_sqlite() -> None:
    with pytest.raises(ValueError):
        sqlite_path_from_url("postgresql://localhost/db")


def test_get_sql_dir_finds_schema() -> None:
    sql_dir = get_sql_dir()
    assert (sql_dir / "schema_sqlite.sql").is_file()
    assert (sql_dir / "views_sqlite.sql").is_file()
