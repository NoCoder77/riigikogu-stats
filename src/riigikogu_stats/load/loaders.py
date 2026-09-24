from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from .. import db
from ..transform.normalize import (
    extract_usergroup_memberships,
    normalize_term,
    normalize_usergroup_as_faction,
)


def load_session(
    conn: sqlite3.Connection,
    session: dict[str, Any],
    attendance: Iterable[dict[str, Any]],
) -> None:
    # sessions.term_id -> terms(id); ensure term exists before inserting session
    if session.get("term_id") and isinstance(session.get("raw"), dict):
        term_data = session["raw"].get("term") or session["raw"].get("riigikoguTerm")
        if isinstance(term_data, dict):
            term = normalize_term(term_data)
            if term:
                db.upsert_term(conn, term)
    if session.get("term_id"):
        db.ensure_term_exists(conn, session["term_id"])
    db.upsert_session(conn, session)
    for entry in attendance:
        person = entry.get("person")
        if not person:
            continue
        db.upsert_person(conn, person)
        if entry.get("status"):
            db.upsert_session_attendance(
                conn,
                {
                    "session_id": session["id"],
                    "person_id": person["id"],
                    "status": entry.get("status"),
                    "raw": entry.get("raw"),
                },
            )


def load_vote(
    conn: sqlite3.Connection,
    vote: dict[str, Any],
    casts: Iterable[dict[str, Any]],
) -> None:
    if vote.get("session_id"):
        db.ensure_session_exists(conn, vote["session_id"])
    db.upsert_vote(conn, vote)
    for entry in casts:
        person = entry.get("person")
        if not person:
            continue
        db.upsert_person(conn, person)
        if entry.get("faction"):
            db.upsert_faction(conn, entry["faction"])
        if entry.get("membership"):
            db.upsert_memberships(conn, [entry["membership"]])
        db.upsert_vote_cast(
            conn,
            {
                "vote_id": vote["id"],
                "person_id": person["id"],
                "choice": entry.get("choice"),
                "raw": entry.get("raw"),
            },
        )


def load_usergroup(
    conn: sqlite3.Connection,
    detail: dict[str, Any],
) -> None:
    """Upsert faction and person_faction_membership from usergroup detail (e.g. FRAKTSIOON)."""
    faction = normalize_usergroup_as_faction(detail)
    if not faction:
        return
    db.upsert_faction(conn, faction)
    memberships_raw = extract_usergroup_memberships(detail)
    for m in memberships_raw:
        person = m.get("person")
        if person:
            db.upsert_person(conn, person)
        else:
            db.ensure_person_exists(conn, m["person_id"])
        start_date = m.get("start_date") or "1970-01-01"
        db.upsert_memberships(
            conn,
            [
                {
                    "person_id": m["person_id"],
                    "faction_id": m["faction_id"],
                    "start_date": start_date,
                    "end_date": m.get("end_date"),
                    "raw": m.get("raw"),
                }
            ],
        )
