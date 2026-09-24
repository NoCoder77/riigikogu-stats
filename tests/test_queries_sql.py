from datetime import date

from riigikogu_stats.api import queries


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query: str, params: dict):
        self.conn.last_query = query
        self.conn.last_params = params

    def fetchone(self):
        return {"total": 0}

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConn:
    def __init__(self):
        self.last_query = ""
        self.last_params = {}

    def cursor(self):
        return FakeCursor(self)


def test_fetch_sessions_uses_exists_for_status_filter() -> None:
    conn = FakeConn()
    queries.fetch_sessions(
        conn,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 31),
        status="present",
        limit=10,
        offset=0,
    )
    assert "EXISTS (SELECT 1 FROM session_attendance" in conn.last_query
    assert "sa.status =" not in conn.last_query


def test_fetch_votes_uses_exists_for_choice_filter() -> None:
    conn = FakeConn()
    queries.fetch_votes(
        conn,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 31),
        outcome="accepted",
        choice="for",
        subject_contains=None,
        policy_area=None,
        limit=10,
        offset=0,
    )
    assert "EXISTS (SELECT 1 FROM vote_casts" in conn.last_query
    assert "WHERE vc.choice = %(choice)s" not in conn.last_query
