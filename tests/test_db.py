"""Tests for db module (hash helpers and dedupe support)."""
from __future__ import annotations

from riigikogu_stats import db


class FakeCursor:
    def __init__(self, conn: "FakeConn"):
        self.conn = conn

    def execute(self, query: str, params: dict):
        self.conn.last_query = query
        self.conn.last_params = params

    def fetchone(self):
        if self.conn.fetchone_returns:
            return self.conn.fetchone_returns.pop(0)
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConn:
    def __init__(self):
        self.last_query = ""
        self.last_params: dict = {}
        self.fetchone_returns: list = []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass


def test_get_item_hash_returns_none_when_missing() -> None:
    conn = FakeConn()
    conn.fetchone_returns = [None]
    result = db.get_item_hash(conn, "vote", "vote-uuid-123")
    assert result is None
    assert "import_item_hashes" in conn.last_query
    assert conn.last_params["entity_type"] == "vote"
    assert conn.last_params["entity_id"] == "vote-uuid-123"


def test_get_item_hash_returns_hash_when_present() -> None:
    conn = FakeConn()
    conn.fetchone_returns = [{"content_hash": "abc123def"}]
    result = db.get_item_hash(conn, "session", "session-uuid-456")
    assert result == "abc123def"
    assert conn.last_params["entity_type"] == "session"
    assert conn.last_params["entity_id"] == "session-uuid-456"


def test_upsert_item_hash_executes_insert_update() -> None:
    conn = FakeConn()
    db.upsert_item_hash(conn, "vote", "vote-id", "hashvalue")
    assert "import_item_hashes" in conn.last_query
    assert "INSERT INTO" in conn.last_query
    assert "ON CONFLICT" in conn.last_query
    assert conn.last_params["entity_type"] == "vote"
    assert conn.last_params["entity_id"] == "vote-id"
    assert conn.last_params["content_hash"] == "hashvalue"
