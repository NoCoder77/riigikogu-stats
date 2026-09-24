from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(zip(row.keys(), row))


def fetch_import_runs(conn: sqlite3.Connection, limit: int, offset: int) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id,
               started_at,
               finished_at,
               start_date,
               end_date,
               step_days,
               only_votings,
               only_sittings,
               status,
               items_processed,
               items_skipped,
               error_message
        FROM import_runs
        ORDER BY started_at DESC
        LIMIT :limit OFFSET :offset
        """,
        {"limit": limit, "offset": offset},
    )
    return [_row_to_dict(r) for r in cur.fetchall()]


def fetch_import_run_current(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Return the active import run (running or queued), or None."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id,
               started_at,
               finished_at,
               start_date,
               end_date,
               step_days,
               only_votings,
               only_sittings,
               status,
               items_processed,
               items_skipped,
               error_message
        FROM import_runs
        WHERE status IN ('running', 'queued')
        ORDER BY started_at DESC
        LIMIT 1
        """,
    )
    row = cur.fetchone()
    return _row_to_dict(row) if row else None


def fetch_import_run_logs(
    conn: sqlite3.Connection,
    run_id: int,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return recent log rows for a run, chronological (oldest first)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, run_id, logged_at, message
        FROM import_run_logs
        WHERE run_id = :run_id
        ORDER BY id DESC
        LIMIT :limit
        """,
        {"run_id": run_id, "limit": limit},
    )
    rows = [_row_to_dict(r) for r in cur.fetchall()]
    rows.reverse()
    return rows


SESSION_SORT_COLUMNS = {
    "session_date",
    "title",
    "attendance_count",
    "present_count",
    "absent_count",
}


def fetch_sessions(
    conn: sqlite3.Connection,
    start_date: date | None,
    end_date: date | None,
    status: str | None,
    limit: int,
    offset: int,
    sort_by: str = "session_date",
    order: str = "desc",
) -> dict[str, Any]:
    filters = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if start_date:
        filters.append("s.session_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        filters.append("s.session_date <= :end_date")
        params["end_date"] = end_date
    if status:
        filters.append(
            "EXISTS (SELECT 1 FROM session_attendance sa2 "
            "WHERE sa2.session_id = s.id AND sa2.status = :status)"
        )
        params["status"] = status
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    sort_col = sort_by if sort_by in SESSION_SORT_COLUMNS else "session_date"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"
    count_params = {k: v for k, v in params.items() if k in ("start_date", "end_date", "status")}
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM (
            SELECT s.id
            FROM sessions s
            LEFT JOIN session_attendance sa ON sa.session_id = s.id
            {where_clause}
            GROUP BY s.id, s.session_date, s.title
        ) sub
        """,
        count_params,
    )
    row = cur.fetchone()
    total = int(row["total"]) if row else 0
    cur.execute(
        f"""
        SELECT s.id,
               s.session_date,
               s.title,
               COUNT(sa.person_id) AS attendance_count,
               SUM(CASE WHEN sa.status IN ('present', 'kohal', 'presented') THEN 1 ELSE 0 END) AS present_count,
               SUM(CASE WHEN sa.status IN ('absent', 'puudus') THEN 1 ELSE 0 END) AS absent_count
        FROM sessions s
        LEFT JOIN session_attendance sa ON sa.session_id = s.id
        {where_clause}
        GROUP BY s.id, s.session_date, s.title
        ORDER BY {sort_col} IS NULL, {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """,
        params,
    )
    items = [_row_to_dict(r) for r in cur.fetchall()]
    return {"items": items, "total": total}


def fetch_session_by_id(conn: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    """Return session row and list of votes in that session (id, subject, title, result, vote_time)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id, s.session_date, s.title, s.term_id
        FROM sessions s
        WHERE s.id = :session_id
        """,
        {"session_id": session_id},
    )
    row = cur.fetchone()
    if not row:
        return None
    session = _row_to_dict(row)
    cur.execute(
        """
        SELECT v.id, v.subject, v.title, v.result, v.vote_time
        FROM votes v
        WHERE v.session_id = :session_id
        ORDER BY v.vote_time
        """,
        {"session_id": session_id},
    )
    session["votes"] = [_row_to_dict(r) for r in cur.fetchall()]
    return session


VOTE_SORT_COLUMNS = {
    "vote_time",
    "title",
    "subject",
    "result",
    "casts_count",
    "votes_for",
    "votes_against",
    "votes_abstain",
    "votes_did_not_vote",
    "votes_absent",
}


def fetch_votes(
    conn: sqlite3.Connection,
    start_date: date | None,
    end_date: date | None,
    outcome: str | None,
    choice: str | None,
    subject_contains: str | None,
    policy_area: str | None,
    limit: int,
    offset: int,
    sort_by: str = "vote_time",
    order: str = "desc",
) -> dict[str, Any]:
    filters = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if start_date:
        filters.append("date(v.vote_time) >= :start_date")
        params["start_date"] = start_date
    if end_date:
        filters.append("date(v.vote_time) <= :end_date")
        params["end_date"] = end_date
    if outcome:
        normalized_outcome = outcome.strip().lower()
        if normalized_outcome == "accepted":
            params["outcome"] = "Accepted"
        elif normalized_outcome == "rejected":
            params["outcome"] = "Rejected"
        else:
            params["outcome"] = outcome
        filters.append("v.result = :outcome")
    if choice:
        params["choice"] = choice.strip().lower() if choice else choice
        filters.append(
            "EXISTS (SELECT 1 FROM vote_casts vc2 "
            "WHERE vc2.vote_id = v.id AND vc2.choice = :choice)"
        )
    if subject_contains and subject_contains.strip():
        params["subject_contains"] = f"%{subject_contains.strip()}%"
        filters.append("(v.subject LIKE :subject_contains OR v.title LIKE :subject_contains)")
    if policy_area and policy_area.strip():
        params["policy_area"] = policy_area.strip()
        if params["policy_area"] == "Other":
            filters.append("(v.policy_area IS NULL OR v.policy_area = 'Other')")
        else:
            filters.append("v.policy_area = :policy_area")
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    sort_col = sort_by if sort_by in VOTE_SORT_COLUMNS else "vote_time"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"
    count_param_keys = ("start_date", "end_date", "outcome", "choice", "subject_contains")
    if params.get("policy_area") and params.get("policy_area") != "Other":
        count_param_keys = count_param_keys + ("policy_area",)
    count_params = {k: v for k, v in params.items() if k in count_param_keys}
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM (
            SELECT v.id
            FROM votes v
            LEFT JOIN vote_casts vc ON vc.vote_id = v.id
            {where_clause}
            GROUP BY v.id, v.title, v.vote_time, v.result
        ) sub
        """,
        count_params,
    )
    row = cur.fetchone()
    total = int(row["total"]) if row else 0
    cur.execute(
        f"""
        SELECT v.id,
               v.session_id,
               s.session_date AS session_date,
               s.title AS session_title,
               v.title,
               v.subject,
               v.vote_type,
               v.policy_area,
               v.vote_time,
               v.result,
               COUNT(vc.person_id) AS casts_count,
               SUM(CASE WHEN vc.choice = 'for' THEN 1 ELSE 0 END) AS votes_for,
               SUM(CASE WHEN vc.choice = 'against' THEN 1 ELSE 0 END) AS votes_against,
               SUM(CASE WHEN vc.choice = 'abstain' THEN 1 ELSE 0 END) AS votes_abstain,
               SUM(CASE WHEN vc.choice = 'did_not_vote' THEN 1 ELSE 0 END) AS votes_did_not_vote,
               SUM(CASE WHEN vc.choice = 'absent' THEN 1 ELSE 0 END) AS votes_absent
        FROM votes v
        LEFT JOIN sessions s ON s.id = v.session_id
        LEFT JOIN vote_casts vc ON vc.vote_id = v.id
        {where_clause}
        GROUP BY v.id, v.session_id, s.session_date, s.title, v.title, v.subject, v.vote_type, v.policy_area, v.vote_time, v.result
        ORDER BY {sort_col} IS NULL, {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """,
        params,
    )
    items = [_row_to_dict(r) for r in cur.fetchall()]
    return {"items": items, "total": total}


def fetch_votes_for_export(
    conn: sqlite3.Connection,
    start_date: date | None,
    end_date: date | None,
    outcome: str | None,
    choice: str | None,
    subject_contains: str | None,
    policy_area: str | None,
    sort_by: str = "vote_time",
    order: str = "desc",
    limit: int = 100_000,
) -> list[dict[str, Any]]:
    """Return vote rows with session_date, session_title for CSV export. Same filters as fetch_votes."""
    filters = []
    params: dict[str, Any] = {"limit": limit}
    if start_date:
        filters.append("date(v.vote_time) >= :start_date")
        params["start_date"] = start_date
    if end_date:
        filters.append("date(v.vote_time) <= :end_date")
        params["end_date"] = end_date
    if outcome:
        normalized_outcome = outcome.strip().lower()
        if normalized_outcome == "accepted":
            params["outcome"] = "Accepted"
        elif normalized_outcome == "rejected":
            params["outcome"] = "Rejected"
        else:
            params["outcome"] = outcome
        filters.append("v.result = :outcome")
    if choice:
        params["choice"] = choice.strip().lower() if choice else choice
        filters.append(
            "EXISTS (SELECT 1 FROM vote_casts vc2 "
            "WHERE vc2.vote_id = v.id AND vc2.choice = :choice)"
        )
    if subject_contains and subject_contains.strip():
        params["subject_contains"] = f"%{subject_contains.strip()}%"
        filters.append("(v.subject LIKE :subject_contains OR v.title LIKE :subject_contains)")
    if policy_area and policy_area.strip():
        params["policy_area"] = policy_area.strip()
        if params["policy_area"] == "Other":
            filters.append("(v.policy_area IS NULL OR v.policy_area = 'Other')")
        else:
            filters.append("v.policy_area = :policy_area")
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    sort_col = sort_by if sort_by in VOTE_SORT_COLUMNS else "vote_time"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"
    export_param_keys = [k for k in params if k != "policy_area" or params.get("policy_area") != "Other"]
    export_params = {k: params[k] for k in export_param_keys}
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT v.id,
               v.session_id,
               s.session_date AS session_date,
               s.title AS session_title,
               v.title,
               v.subject,
               v.vote_type,
               v.policy_area,
               v.vote_time,
               v.result,
               COUNT(vc.person_id) AS casts_count,
               SUM(CASE WHEN vc.choice = 'for' THEN 1 ELSE 0 END) AS votes_for,
               SUM(CASE WHEN vc.choice = 'against' THEN 1 ELSE 0 END) AS votes_against,
               SUM(CASE WHEN vc.choice = 'abstain' THEN 1 ELSE 0 END) AS votes_abstain,
               SUM(CASE WHEN vc.choice = 'did_not_vote' THEN 1 ELSE 0 END) AS votes_did_not_vote,
               SUM(CASE WHEN vc.choice = 'absent' THEN 1 ELSE 0 END) AS votes_absent
        FROM votes v
        LEFT JOIN sessions s ON s.id = v.session_id
        LEFT JOIN vote_casts vc ON vc.vote_id = v.id
        {where_clause}
        GROUP BY v.id, v.session_id, s.session_date, s.title, v.title, v.subject, v.vote_type, v.policy_area, v.vote_time, v.result
        ORDER BY {sort_col} IS NULL, {sort_col} {order_dir}
        LIMIT :limit
        """,
        export_params,
    )
    return [_row_to_dict(r) for r in cur.fetchall()]


def fetch_vote_by_id(conn: sqlite3.Connection, vote_id: str) -> dict[str, Any] | None:
    """Return vote row and list of casts (person, choice, faction_name) or None if not found."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT v.id, v.session_id, v.title, v.subject, v.vote_type, v.policy_area, v.result, v.vote_time, v.raw,
               s.session_date AS session_date, s.title AS session_title
        FROM votes v
        LEFT JOIN sessions s ON s.id = v.session_id
        WHERE v.id = :vote_id
        """,
        {"vote_id": vote_id},
    )
    row = cur.fetchone()
    if not row:
        return None
    vote = _row_to_dict(row)
    cur.execute(
        """
        SELECT
            p.id AS person_id,
            p.full_name,
            vc.choice,
            (SELECT f.name FROM person_faction_membership pf
             JOIN factions f ON f.id = pf.faction_id
             WHERE pf.person_id = vc.person_id
               AND date(v.vote_time) >= date(pf.start_date)
               AND (pf.end_date IS NULL OR date(v.vote_time) <= date(pf.end_date))
             ORDER BY pf.start_date DESC LIMIT 1) AS faction_name
        FROM vote_casts vc
        JOIN votes v ON v.id = vc.vote_id
        JOIN persons p ON p.id = vc.person_id
        WHERE vc.vote_id = :vote_id
        ORDER BY p.full_name
        """,
        {"vote_id": vote_id},
    )
    vote["casts"] = [_row_to_dict(r) for r in cur.fetchall()]
    return vote


PERSON_SORT_COLUMNS = {
    "full_name",
    "votes_recorded",
    "votes_for",
    "votes_against",
    "votes_abstain",
    "votes_did_not_vote",
    "votes_absent",
    "sessions_recorded",
    "present_count",
    "absent_count",
    "attendance_rate_pct",
}


def fetch_persons(
    conn: sqlite3.Connection,
    limit: int,
    offset: int,
    sort_by: str = "votes_recorded",
    order: str = "desc",
) -> dict[str, Any]:
    """List persons with vote participation and optional attendance from views."""
    sort_col = sort_by if sort_by in PERSON_SORT_COLUMNS else "votes_recorded"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) AS total FROM persons
        """
    )
    total = int(cur.fetchone()["total"])
    cur.execute(
        f"""
        SELECT vp.person_id AS id,
               vp.full_name,
               vp.votes_recorded,
               vp.votes_for,
               vp.votes_against,
               vp.votes_abstain,
               vp.votes_did_not_vote,
               vp.votes_absent,
               COALESCE(ar.sessions_recorded, 0) AS sessions_recorded,
               COALESCE(ar.present_count, 0) AS present_count,
               COALESCE(ar.absent_count, 0) AS absent_count,
               CASE WHEN COALESCE(ar.sessions_recorded, 0) > 0
                    THEN ROUND(100.0 * COALESCE(ar.present_count, 0) / ar.sessions_recorded, 1)
                    ELSE NULL END AS attendance_rate_pct
        FROM v_vote_participation vp
        LEFT JOIN v_person_attendance_rate ar ON ar.person_id = vp.person_id
        ORDER BY {sort_col} IS NULL, {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """,
        {"limit": limit, "offset": offset},
    )
    items = [_row_to_dict(r) for r in cur.fetchall()]
    return {"items": items, "total": total}


def fetch_person_by_id(
    conn: sqlite3.Connection,
    person_id: str,
    vote_type: str | None = None,
    policy_area: str | None = None,
) -> dict[str, Any] | None:
    """Return person with vote participation, attendance, and recent vote casts. Optional vote_type and policy_area filter recent_casts."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.id, p.full_name, p.birth_date,
               vp.votes_recorded, vp.votes_for, vp.votes_against, vp.votes_abstain,
               vp.votes_did_not_vote, vp.votes_absent,
               ar.sessions_recorded, ar.present_count, ar.absent_count
        FROM persons p
        LEFT JOIN v_vote_participation vp ON vp.person_id = p.id
        LEFT JOIN v_person_attendance_rate ar ON ar.person_id = p.id
        WHERE p.id = :person_id
        """,
        {"person_id": person_id},
    )
    row = cur.fetchone()
    if not row:
        return None
    person = _row_to_dict(row)
    sr = person.get("sessions_recorded")
    pc = person.get("present_count")
    if sr is not None and sr > 0 and pc is not None:
        person["attendance_rate_pct"] = round(100.0 * pc / sr, 1)
    else:
        person["attendance_rate_pct"] = None
    cast_params: dict[str, Any] = {"person_id": person_id}
    extra_filters: list[str] = []
    if vote_type and vote_type.strip():
        extra_filters.append("v.vote_type = :vote_type")
        cast_params["vote_type"] = vote_type.strip()
    if policy_area and policy_area.strip():
        if policy_area.strip() == "Other":
            extra_filters.append("(v.policy_area IS NULL OR v.policy_area = 'Other')")
        else:
            extra_filters.append("v.policy_area = :policy_area")
            cast_params["policy_area"] = policy_area.strip()
    and_extra = " AND " + " AND ".join(extra_filters) if extra_filters else ""
    cur.execute(
        f"""
        SELECT vc.vote_id, v.subject, v.title, v.vote_type, v.policy_area, vc.choice, v.vote_time
        FROM vote_casts vc
        JOIN votes v ON v.id = vc.vote_id
        WHERE vc.person_id = :person_id{and_extra}
        ORDER BY v.vote_time DESC
        LIMIT 50
        """,
        cast_params,
    )
    person["recent_casts"] = [_row_to_dict(r) for r in cur.fetchall()]
    # Distinct vote_type values for this person (for filter dropdown), most frequent first
    cur.execute(
        """
        SELECT v.vote_type
        FROM vote_casts vc
        JOIN votes v ON v.id = vc.vote_id
        WHERE vc.person_id = :person_id AND v.vote_type IS NOT NULL AND v.vote_type != ''
        GROUP BY v.vote_type
        ORDER BY COUNT(*) DESC, v.vote_type
        """,
        {"person_id": person_id},
    )
    person["vote_types"] = [r["vote_type"] for r in cur.fetchall()]
    return person


def fetch_factions(
    conn: sqlite3.Connection,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    """List factions with aggregate vote counts from v_faction_vote_counts."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM factions")
    total = int(cur.fetchone()["total"])
    cur.execute(
        """
        SELECT f.id, f.name,
               SUM(fvc.vote_count) AS total_votes,
               SUM(CASE WHEN fvc.choice = 'for' THEN fvc.vote_count ELSE 0 END) AS votes_for,
               SUM(CASE WHEN fvc.choice = 'against' THEN fvc.vote_count ELSE 0 END) AS votes_against,
               SUM(CASE WHEN fvc.choice = 'abstain' THEN fvc.vote_count ELSE 0 END) AS votes_abstain,
               SUM(CASE WHEN fvc.choice = 'did_not_vote' THEN fvc.vote_count ELSE 0 END) AS votes_did_not_vote,
               SUM(CASE WHEN fvc.choice = 'absent' THEN fvc.vote_count ELSE 0 END) AS votes_absent,
               fa.total_slots AS attendance_slots,
               fa.present_slots AS attendance_present,
               fa.absent_slots AS attendance_absent,
               CASE WHEN fa.total_slots > 0 THEN ROUND(100.0 * fa.present_slots / fa.total_slots, 1) ELSE NULL END AS attendance_rate_pct
        FROM factions f
        LEFT JOIN v_faction_vote_counts fvc ON fvc.faction_id = f.id
        LEFT JOIN v_faction_attendance fa ON fa.faction_id = f.id
        GROUP BY f.id, f.name, fa.total_slots, fa.present_slots, fa.absent_slots
        ORDER BY f.name
        LIMIT :limit OFFSET :offset
        """,
        {"limit": limit, "offset": offset},
    )
    items = [_row_to_dict(r) for r in cur.fetchall()]
    return {"items": items, "total": total}


def fetch_faction_by_id(
    conn: sqlite3.Connection,
    faction_id: str,
    policy_area: str | None = None,
) -> dict[str, Any] | None:
    """Return faction with aggregate vote counts. Optional policy_area filters votes_by_type and votes_by_policy_area."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT f.id, f.name,
               SUM(fvc.vote_count) AS total_votes,
               SUM(CASE WHEN fvc.choice = 'for' THEN fvc.vote_count ELSE 0 END) AS votes_for,
               SUM(CASE WHEN fvc.choice = 'against' THEN fvc.vote_count ELSE 0 END) AS votes_against,
               SUM(CASE WHEN fvc.choice = 'abstain' THEN fvc.vote_count ELSE 0 END) AS votes_abstain,
               SUM(CASE WHEN fvc.choice = 'did_not_vote' THEN fvc.vote_count ELSE 0 END) AS votes_did_not_vote,
               SUM(CASE WHEN fvc.choice = 'absent' THEN fvc.vote_count ELSE 0 END) AS votes_absent,
               fa.total_slots AS attendance_slots,
               fa.present_slots AS attendance_present,
               fa.absent_slots AS attendance_absent,
               CASE WHEN fa.total_slots > 0 THEN ROUND(100.0 * fa.present_slots / fa.total_slots, 1) ELSE NULL END AS attendance_rate_pct
        FROM factions f
        LEFT JOIN v_faction_vote_counts fvc ON fvc.faction_id = f.id
        LEFT JOIN v_faction_attendance fa ON fa.faction_id = f.id
        WHERE f.id = :faction_id
        GROUP BY f.id, f.name, fa.total_slots, fa.present_slots, fa.absent_slots
        """,
        {"faction_id": faction_id},
    )
    row = cur.fetchone()
    if not row:
        return None
    faction = _row_to_dict(row)
    pa_filter = ""
    pa_params: dict[str, Any] = {"faction_id": faction_id}
    if policy_area and policy_area.strip():
        if policy_area.strip() == "Other":
            pa_filter = " AND (v.policy_area IS NULL OR v.policy_area = 'Other')"
        else:
            pa_filter = " AND v.policy_area = :policy_area"
            pa_params["policy_area"] = policy_area.strip()
    cur.execute(
        f"""
        SELECT v.vote_type,
               SUM(CASE WHEN vc.choice = 'for' THEN 1 ELSE 0 END) AS votes_for,
               SUM(CASE WHEN vc.choice = 'against' THEN 1 ELSE 0 END) AS votes_against,
               SUM(CASE WHEN vc.choice = 'abstain' THEN 1 ELSE 0 END) AS votes_abstain,
               SUM(CASE WHEN vc.choice = 'did_not_vote' THEN 1 ELSE 0 END) AS votes_did_not_vote,
               SUM(CASE WHEN vc.choice = 'absent' THEN 1 ELSE 0 END) AS votes_absent
        FROM vote_casts vc
        JOIN votes v ON v.id = vc.vote_id
        JOIN person_faction_membership pf ON pf.person_id = vc.person_id
            AND date(v.vote_time) >= date(pf.start_date)
            AND (pf.end_date IS NULL OR date(v.vote_time) <= date(pf.end_date))
        WHERE pf.faction_id = :faction_id
        {pa_filter}
        GROUP BY v.vote_type
        ORDER BY SUM(1) DESC, v.vote_type
        """,
        pa_params,
    )
    faction["votes_by_type"] = [_row_to_dict(r) for r in cur.fetchall()]
    cur.execute(
        f"""
        SELECT COALESCE(v.policy_area, 'Other') AS policy_area,
               SUM(CASE WHEN vc.choice = 'for' THEN 1 ELSE 0 END) AS votes_for,
               SUM(CASE WHEN vc.choice = 'against' THEN 1 ELSE 0 END) AS votes_against,
               SUM(CASE WHEN vc.choice = 'abstain' THEN 1 ELSE 0 END) AS votes_abstain,
               SUM(CASE WHEN vc.choice = 'did_not_vote' THEN 1 ELSE 0 END) AS votes_did_not_vote,
               SUM(CASE WHEN vc.choice = 'absent' THEN 1 ELSE 0 END) AS votes_absent
        FROM vote_casts vc
        JOIN votes v ON v.id = vc.vote_id
        JOIN person_faction_membership pf ON pf.person_id = vc.person_id
            AND date(v.vote_time) >= date(pf.start_date)
            AND (pf.end_date IS NULL OR date(v.vote_time) <= date(pf.end_date))
        WHERE pf.faction_id = :faction_id
        {pa_filter}
        GROUP BY COALESCE(v.policy_area, 'Other')
        ORDER BY SUM(1) DESC, COALESCE(v.policy_area, 'Other')
        """,
        pa_params,
    )
    faction["votes_by_policy_area"] = [_row_to_dict(r) for r in cur.fetchall()]
    return faction


def fetch_vote_faction_breakdown(conn: sqlite3.Connection, vote_id: str) -> list[dict[str, Any]]:
    """Per-faction counts (for/against/abstain/did_not_vote/absent) for one vote."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT f.id AS faction_id, f.name AS faction_name,
               SUM(CASE WHEN vc.choice = 'for' THEN 1 ELSE 0 END) AS votes_for,
               SUM(CASE WHEN vc.choice = 'against' THEN 1 ELSE 0 END) AS votes_against,
               SUM(CASE WHEN vc.choice = 'abstain' THEN 1 ELSE 0 END) AS votes_abstain,
               SUM(CASE WHEN vc.choice = 'did_not_vote' THEN 1 ELSE 0 END) AS votes_did_not_vote,
               SUM(CASE WHEN vc.choice = 'absent' THEN 1 ELSE 0 END) AS votes_absent
        FROM vote_casts vc
        JOIN persons p ON p.id = vc.person_id
        JOIN person_faction_membership pf ON pf.person_id = vc.person_id
            AND date((SELECT vote_time FROM votes WHERE id = :vote_id)) >= date(pf.start_date)
            AND (pf.end_date IS NULL OR date((SELECT vote_time FROM votes WHERE id = :vote_id)) <= date(pf.end_date))
        JOIN factions f ON f.id = pf.faction_id
        WHERE vc.vote_id = :vote_id
        GROUP BY f.id, f.name
        ORDER BY f.name
        """,
        {"vote_id": vote_id},
    )
    return [_row_to_dict(r) for r in cur.fetchall()]


def fetch_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return data scope: min/max session_date, min/max vote_time, total counts, last_voting_date from voting_days."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            (SELECT MIN(session_date) FROM sessions) AS min_session_date,
            (SELECT MAX(session_date) FROM sessions) AS max_session_date,
            (SELECT MIN(vote_time) FROM votes) AS min_vote_time,
            (SELECT MAX(vote_time) FROM votes) AS max_vote_time,
            (SELECT COUNT(*) FROM sessions) AS total_sessions,
            (SELECT COUNT(*) FROM votes) AS total_votes,
            (SELECT COUNT(*) FROM persons) AS total_persons,
            (SELECT COUNT(*) FROM factions) AS total_factions
        """
    )
    row = cur.fetchone()
    out = _row_to_dict(row) if row else {}
    try:
        cur.execute(
            "SELECT MAX(vote_date) AS last_voting_date FROM voting_days"
        )
        vd = cur.fetchone()
        if vd and vd["last_voting_date"]:
            out["last_voting_date"] = vd["last_voting_date"]
    except sqlite3.OperationalError:
        pass
    return out


def fetch_voting_days(
    conn: sqlite3.Connection,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    """Return list of dates when at least one plenary vote occurred (from voting_days)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='voting_days'"
        )
        if cur.fetchone() is None:
            return {"items": [], "total": 0}
    except sqlite3.OperationalError:
        return {"items": [], "total": 0}
    filters = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if start_date:
        filters.append("vote_date >= :start_date")
        params["start_date"] = start_date.isoformat()
    if end_date:
        filters.append("vote_date <= :end_date")
        params["end_date"] = end_date.isoformat()
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    cur.execute(
        f"""
        SELECT COUNT(*) AS total FROM voting_days {where}
        """,
        {k: v for k, v in params.items() if k in ("start_date", "end_date")},
    )
    total = int(cur.fetchone()["total"])
    cur.execute(
        f"""
        SELECT vote_date FROM voting_days {where}
        ORDER BY vote_date DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )
    items = [{"vote_date": r["vote_date"]} for r in cur.fetchall()]
    return {"items": items, "total": total}
