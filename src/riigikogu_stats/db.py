from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .paths import sqlite_path_from_url


def connect_db(database_url: str) -> sqlite3.Connection:
    path = sqlite_path_from_url(database_url)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def execute_sql_file(conn: sqlite3.Connection, sql_path: Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    cur = conn.cursor()
    for stmt in statements:
        if stmt:
            cur.execute(stmt)
    conn.commit()


def upsert_person(conn: sqlite3.Connection, person: dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO persons (id, first_name, last_name, full_name, birth_date, raw)
        VALUES (:id, :first_name, :last_name, :full_name, :birth_date, :raw)
        ON CONFLICT (id) DO UPDATE SET
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            full_name = excluded.full_name,
            birth_date = excluded.birth_date,
            raw = excluded.raw
        """,
        {**person, "raw": json.dumps(person.get("raw"))},
    )


def upsert_term(conn: sqlite3.Connection, term: dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO terms (id, name, start_date, end_date, raw)
        VALUES (:id, :name, :start_date, :end_date, :raw)
        ON CONFLICT (id) DO UPDATE SET
            name = excluded.name,
            start_date = excluded.start_date,
            end_date = excluded.end_date,
            raw = excluded.raw
        """,
        {**term, "raw": json.dumps(term.get("raw"))},
    )


def ensure_term_exists(conn: sqlite3.Connection, term_id: str) -> None:
    """Insert a stub term row if missing, so session.term_id FK is satisfied."""
    if not term_id:
        return
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO terms (id, name, start_date, end_date, raw)
        VALUES (:id, NULL, NULL, NULL, NULL)
        """,
        {"id": term_id},
    )


def ensure_person_exists(conn: sqlite3.Connection, person_id: str) -> None:
    """Insert a stub person row if missing, so person_faction_membership FK is satisfied."""
    if not person_id:
        return
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO persons (id, first_name, last_name, full_name, birth_date, raw)
        VALUES (:id, NULL, NULL, NULL, NULL, NULL)
        """,
        {"id": person_id},
    )


def upsert_faction(conn: sqlite3.Connection, faction: dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO factions (id, name, raw)
        VALUES (:id, :name, :raw)
        ON CONFLICT (id) DO UPDATE SET
            name = excluded.name,
            raw = excluded.raw
        """,
        {**faction, "raw": json.dumps(faction.get("raw"))},
    )


def ensure_session_exists(conn: sqlite3.Connection, session_id: str) -> None:
    """Insert a stub session row if missing, so vote.session_id FK is satisfied."""
    if not session_id:
        return
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO sessions (id, term_id, session_date, title, raw)
        VALUES (:id, NULL, NULL, NULL, NULL)
        """,
        {"id": session_id},
    )


def upsert_session(conn: sqlite3.Connection, session: dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO sessions (id, term_id, session_date, title, raw)
        VALUES (:id, :term_id, :session_date, :title, :raw)
        ON CONFLICT (id) DO UPDATE SET
            term_id = excluded.term_id,
            session_date = excluded.session_date,
            title = excluded.title,
            raw = excluded.raw
        """,
        {**session, "raw": json.dumps(session.get("raw"))},
    )


def upsert_session_attendance(
    conn: sqlite3.Connection, attendance: dict[str, Any]
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO session_attendance (session_id, person_id, status, raw)
        VALUES (:session_id, :person_id, :status, :raw)
        ON CONFLICT (session_id, person_id) DO UPDATE SET
            status = excluded.status,
            raw = excluded.raw
        """,
        {**attendance, "raw": json.dumps(attendance.get("raw"))},
    )


def upsert_vote(conn: sqlite3.Connection, vote: dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO votes (id, session_id, title, subject, vote_type, policy_area, result, vote_time, raw)
        VALUES (:id, :session_id, :title, :subject, :vote_type, :policy_area, :result, :vote_time, :raw)
        ON CONFLICT (id) DO UPDATE SET
            session_id = excluded.session_id,
            title = excluded.title,
            subject = excluded.subject,
            vote_type = excluded.vote_type,
            policy_area = excluded.policy_area,
            result = excluded.result,
            vote_time = excluded.vote_time,
            raw = excluded.raw
        """,
        {
            **vote,
            "subject": vote.get("subject"),
            "vote_type": vote.get("vote_type"),
            "policy_area": vote.get("policy_area"),
            "raw": json.dumps(vote.get("raw")),
        },
    )


def upsert_vote_cast(conn: sqlite3.Connection, cast: dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO vote_casts (vote_id, person_id, choice, raw)
        VALUES (:vote_id, :person_id, :choice, :raw)
        ON CONFLICT (vote_id, person_id) DO UPDATE SET
            choice = excluded.choice,
            raw = excluded.raw
        """,
        {**cast, "raw": json.dumps(cast.get("raw"))},
    )


def upsert_memberships(
    conn: sqlite3.Connection, memberships: Iterable[dict[str, Any]]
) -> None:
    cur = conn.cursor()
    for membership in memberships:
        cur.execute(
            """
            INSERT INTO person_faction_membership (person_id, faction_id, start_date, end_date, raw)
            VALUES (:person_id, :faction_id, :start_date, :end_date, :raw)
            ON CONFLICT (person_id, faction_id, start_date) DO UPDATE SET
                end_date = excluded.end_date,
                raw = excluded.raw
            """,
            {**membership, "raw": json.dumps(membership.get("raw"))},
        )


def _merge_intervals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge overlapping/adjacent (start_date, end_date) intervals. None end_date = open."""
    if not rows:
        return []
    sorted_rows = sorted(rows, key=lambda r: (r.get("start_date") or "", r.get("end_date") or "9999-12-31"))
    merged: list[dict[str, Any]] = []
    current = dict(sorted_rows[0])
    for r in sorted_rows[1:]:
        n_start = r.get("start_date") or ""
        n_end = r.get("end_date")
        c_end = current.get("end_date")
        # Overlap/adjacent if: current is open (c_end is None) or n_start <= c_end
        if c_end is None or (n_start and str(n_start)[:10] <= str(c_end)[:10]):
            if n_end is None:
                current["end_date"] = None
            elif current.get("end_date") is None or (str(n_end)[:10] > str(current.get("end_date") or "")[:10]):
                current["end_date"] = n_end
        else:
            merged.append(current)
            current = dict(r)
    merged.append(current)
    return merged


def merge_memberships(conn: sqlite3.Connection) -> int:
    """Coalesce person_faction_membership by (person_id, faction_id) into contiguous intervals.
    Fixes overcounting when vote import created one row per vote_date. Returns number of rows removed."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT person_id, faction_id FROM person_faction_membership
        GROUP BY person_id, faction_id
        HAVING COUNT(*) > 1
        """
    )
    pairs = [{"person_id": r[0], "faction_id": r[1]} for r in cur.fetchall()]
    total_removed = 0
    for p in pairs:
        cur.execute(
            """
            SELECT person_id, faction_id, start_date, end_date, raw
            FROM person_faction_membership
            WHERE person_id = :person_id AND faction_id = :faction_id
            ORDER BY start_date, end_date
            """,
            p,
        )
        rows = [
            {
                "person_id": r["person_id"],
                "faction_id": r["faction_id"],
                "start_date": r["start_date"],
                "end_date": r["end_date"],
                "raw": r["raw"],
            }
            for r in cur.fetchall()
        ]
        merged = _merge_intervals(rows)
        if len(merged) >= len(rows):
            continue
        cur.execute(
            """
            DELETE FROM person_faction_membership
            WHERE person_id = :person_id AND faction_id = :faction_id
            """,
            p,
        )
        total_removed += cur.rowcount
        for m in merged:
            cur.execute(
                """
                INSERT INTO person_faction_membership (person_id, faction_id, start_date, end_date, raw)
                VALUES (:person_id, :faction_id, :start_date, :end_date, :raw)
                """,
                {**m, "raw": m.get("raw") or "null"},
            )
    conn.commit()
    return total_removed


def get_item_hash(conn: sqlite3.Connection, entity_type: str, entity_id: str) -> str | None:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT content_hash
        FROM import_item_hashes
        WHERE entity_type = :entity_type AND entity_id = :entity_id
        """,
        {"entity_type": entity_type, "entity_id": entity_id},
    )
    row = cur.fetchone()
    return row["content_hash"] if row else None


def upsert_item_hash(
    conn: sqlite3.Connection, entity_type: str, entity_id: str, content_hash: str
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO import_item_hashes (entity_type, entity_id, content_hash, last_seen_at)
        VALUES (:entity_type, :entity_id, :content_hash, datetime('now'))
        ON CONFLICT (entity_type, entity_id) DO UPDATE SET
            content_hash = excluded.content_hash,
            last_seen_at = datetime('now')
        """,
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "content_hash": content_hash,
        },
    )


def create_import_run(
    conn: sqlite3.Connection,
    start_date: Any,
    end_date: Any,
    step_days: int,
    only_votings: bool,
    only_sittings: bool,
    status: str = "running",
) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO import_runs (
            start_date,
            end_date,
            step_days,
            only_votings,
            only_sittings,
            status
        )
        VALUES (:start_date, :end_date, :step_days, :only_votings, :only_sittings, :status)
        """,
        {
            "start_date": start_date,
            "end_date": end_date,
            "step_days": step_days,
            "only_votings": only_votings,
            "only_sittings": only_sittings,
            "status": status,
        },
    )
    row = cur.execute("SELECT last_insert_rowid() AS id").fetchone()
    return int(row["id"])


def append_import_run_log(conn: sqlite3.Connection, run_id: int, message: str) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO import_run_logs (run_id, logged_at, message)
        VALUES (:run_id, datetime('now'), :message)
        """,
        {"run_id": run_id, "message": message},
    )


def update_import_run_counts(
    conn: sqlite3.Connection,
    run_id: int,
    items_processed: int,
    items_skipped: int,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE import_runs
        SET items_processed = :items_processed,
            items_skipped = :items_skipped
        WHERE id = :run_id
        """,
        {
            "run_id": run_id,
            "items_processed": items_processed,
            "items_skipped": items_skipped,
        },
    )


def finish_import_run(conn: sqlite3.Connection, run_id: int, status: str, error: str | None) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE import_runs
        SET finished_at = datetime('now'),
            status = :status,
            error_message = :error_message
        WHERE id = :run_id
        """,
        {"run_id": run_id, "status": status, "error_message": error},
    )


def mark_stale_running_imports_failed(conn: sqlite3.Connection) -> int:
    """Mark any orphaned 'running'/'queued' imports as failed (e.g. app was closed). Returns count."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE import_runs
        SET finished_at = datetime('now'),
            status = 'failed',
            error_message = 'App was closed before import finished'
        WHERE status IN ('running', 'queued')
        """
    )
    return cur.rowcount


def upsert_voting_days(conn: sqlite3.Connection, dates: Iterable[str]) -> None:
    """Insert or ignore voting day dates (YYYY-MM-DD). Creates voting_days table if missing."""
    cur = conn.cursor()
    for d in dates:
        if not d or len(str(d)) < 10:
            continue
        day = str(d)[:10]
        cur.execute(
            """
            INSERT OR IGNORE INTO voting_days (vote_date)
            VALUES (:vote_date)
            """,
            {"vote_date": day},
        )
