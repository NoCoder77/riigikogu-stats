from __future__ import annotations

from datetime import date, datetime
from typing import Any

from dateutil.parser import isoparse


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return isoparse(str(value)).date()
    except (ValueError, TypeError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return isoparse(str(value))
    except (ValueError, TypeError):
        return None


def normalize_person(person: dict[str, Any]) -> dict[str, Any] | None:
    person_id = person.get("uuid") or person.get("id") or person.get("personId")
    if not person_id:
        return None
    first_name = person.get("firstName") or person.get("first_name")
    last_name = person.get("lastName") or person.get("last_name")
    full_name = person.get("fullName") or person.get("name")
    if not full_name and first_name and last_name:
        full_name = f"{first_name} {last_name}"
    birth_date = _parse_date(person.get("birthDate") or person.get("birth_date"))
    return {
        "id": str(person_id),
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "birth_date": birth_date.isoformat() if birth_date else None,
        "raw": person,
    }


def normalize_term(term: dict[str, Any]) -> dict[str, Any] | None:
    term_id = term.get("uuid") or term.get("id") or term.get("termId")
    if not term_id:
        return None
    start = _parse_date(term.get("startDate") or term.get("start_date"))
    end = _parse_date(term.get("endDate") or term.get("end_date"))
    return {
        "id": str(term_id),
        "name": term.get("name") or term.get("title"),
        "start_date": start.isoformat() if start else None,
        "end_date": end.isoformat() if end else None,
        "raw": term,
    }


def normalize_faction(faction: dict[str, Any]) -> dict[str, Any] | None:
    faction_id = faction.get("uuid") or faction.get("id") or faction.get("factionId")
    if not faction_id:
        return None
    return {
        "id": str(faction_id),
        "name": faction.get("name") or faction.get("title"),
        "raw": faction,
    }


def normalize_usergroup_as_faction(detail: dict[str, Any]) -> dict[str, Any] | None:
    """From usergroup detail (e.g. GET /api/usergroups/{uuid}) build faction row."""
    faction_id = (
        detail.get("_source_uuid")
        or detail.get("uuid")
        or detail.get("id")
    )
    if not faction_id:
        return None
    return {
        "id": str(faction_id),
        "name": detail.get("name") or detail.get("title") or detail.get("shortName"),
        "raw": detail,
    }


def extract_usergroup_memberships(detail: dict[str, Any]) -> list[dict[str, Any]]:
    """From usergroup detail extract list of {person, start_date, end_date, raw} for memberships."""
    memberships_list = None
    for key in ("memberships", "members", "membershipList", "participants"):
        val = detail.get(key)
        if isinstance(val, list):
            memberships_list = val
            break
    if not memberships_list:
        return []
    out: list[dict[str, Any]] = []
    faction_id = str(
        detail.get("_source_uuid") or detail.get("uuid") or detail.get("id") or ""
    )
    for entry in memberships_list:
        if not isinstance(entry, dict):
            continue
        person = entry.get("person") or entry.get("member") or entry
        if isinstance(person, dict):
            person_id = person.get("uuid") or person.get("id") or entry.get("personId") or entry.get("memberId")
        else:
            person_id = entry.get("personId") or entry.get("memberId")
        if not person_id:
            continue
        person_id = str(person_id)
        start_date = _parse_date(
            entry.get("startDate")
            or entry.get("start_date")
            or entry.get("membershipStart")
            or entry.get("beginDate")
        )
        end_date = _parse_date(
            entry.get("endDate")
            or entry.get("end_date")
            or entry.get("membershipEnd")
            or entry.get("expiryDate")
        )
        normalized_person = normalize_person(person) if isinstance(person, dict) else None
        out.append(
            {
                "person_id": person_id,
                "faction_id": faction_id,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "person": normalized_person,
                "raw": entry,
            }
        )
    return out


def normalize_session(session: dict[str, Any]) -> dict[str, Any] | None:
    session_id = session.get("_source_uuid") or session.get("uuid") or session.get("id")
    if not session_id:
        return None
    term = session.get("term") or session.get("riigikoguTerm")
    term_id = None
    if isinstance(term, dict):
        term_id = term.get("uuid") or term.get("id") or term.get("termId")
    session_date = _parse_date(
        session.get("date") or session.get("sessionDate") or session.get("sittingDateTime")
    )
    return {
        "id": str(session_id),
        "term_id": str(term_id) if term_id else None,
        "session_date": session_date.isoformat() if session_date else None,
        "title": session.get("title") or session.get("name"),
        "raw": session,
    }


def extract_attendance(session: dict[str, Any]) -> list[dict[str, Any]]:
    attendance_list = None
    for key in ("attendance", "participants", "attendees", "members"):
        if isinstance(session.get(key), list):
            attendance_list = session[key]
            break
    if attendance_list is None:
        return []
    normalized: list[dict[str, Any]] = []
    for entry in attendance_list:
        person = entry.get("person") if isinstance(entry, dict) else None
        if not isinstance(person, dict):
            person = entry if isinstance(entry, dict) else None
        normalized_person = normalize_person(person or {})
        if not normalized_person:
            continue
        status = (
            entry.get("status")
            or entry.get("attendanceStatus")
            or entry.get("presence")
            or entry.get("state")
        )
        normalized.append(
            {
                "person": normalized_person,
                "status": str(status).lower() if status is not None else None,
                "raw": entry,
            }
        )
    return normalized


def normalize_vote(vote: dict[str, Any]) -> dict[str, Any] | None:
    vote_id = vote.get("_source_uuid") or vote.get("uuid") or vote.get("id")
    if not vote_id:
        return None
    session = vote.get("session") or vote.get("sitting") or vote.get("plenary")
    session_id = None
    if isinstance(session, dict):
        session_id = session.get("uuid") or session.get("id")
    related = vote.get("relatedDraft")
    subject = (related.get("title") if isinstance(related, dict) and related.get("title") else None)
    vote_type = vote.get("description")
    fallback_title = (
        vote.get("title")
        or vote.get("subject")
        or vote.get("description")
        or (related.get("title") if isinstance(related, dict) else None)
    )
    title = subject if subject else fallback_title
    result = vote.get("result") or vote.get("outcome")
    if result is None and (vote.get("inFavor") is not None or vote.get("against") is not None):
        result = "Accepted" if (vote.get("inFavor") or 0) > (vote.get("against") or 0) else "Rejected"
    vote_time = _parse_datetime(
        vote.get("dateTime") or vote.get("time") or vote.get("startDateTime")
    )
    return {
        "id": str(vote_id),
        "session_id": str(session_id) if session_id else None,
        "title": title,
        "subject": subject,
        "vote_type": vote_type,
        "result": result,
        "vote_time": vote_time.isoformat() if vote_time else None,
        "raw": vote,
    }


def normalize_vote_choice(choice: Any) -> str | None:
    if choice is None:
        return None
    if isinstance(choice, dict):
        choice = choice.get("code") or choice.get("value") or choice.get("decision")
    value = str(choice).strip().lower()
    mapping = {
        "poolt": "for",
        "for": "for",
        "yes": "for",
        "vastu": "against",
        "against": "against",
        "no": "against",
        "erapooletu": "abstain",
        "abstain": "abstain",
        "ei hääletanud": "did_not_vote",
        "ei_haaletanud": "did_not_vote",
        "did_not_vote": "did_not_vote",
        "absent": "absent",
        "puudus": "absent",
    }
    return mapping.get(value, value)


def extract_vote_casts(vote: dict[str, Any]) -> list[dict[str, Any]]:
    vote_list = None
    for key in ("voters", "votes", "members", "participants", "castVotes"):
        if isinstance(vote.get(key), list):
            vote_list = vote[key]
            break
    if vote_list is None:
        return []
    vote_time = _parse_datetime(
        vote.get("dateTime") or vote.get("time") or vote.get("startDateTime")
    )
    vote_date = vote_time.date().isoformat() if vote_time else None
    normalized: list[dict[str, Any]] = []
    for entry in vote_list:
        if not isinstance(entry, dict):
            continue
        person = entry.get("person") or entry  # API uses "voters" with person fields on entry
        normalized_person = normalize_person(person)
        if not normalized_person:
            continue
        choice_value = (
            entry.get("decision")
            or entry.get("choice")
            or entry.get("vote")
            or entry.get("result")
            or entry.get("option")
        )
        faction = None
        membership = None
        faction_data = entry.get("faction")
        if isinstance(faction_data, dict):
            faction = normalize_faction(faction_data)
            if faction and vote_date:
                membership = {
                    "person_id": normalized_person["id"],
                    "faction_id": faction["id"],
                    "start_date": vote_date,
                    "end_date": None,
                    "raw": faction_data,
                }
        normalized.append(
            {
                "person": normalized_person,
                "choice": normalize_vote_choice(choice_value),
                "raw": entry,
                "faction": faction,
                "membership": membership,
            }
        )
    return normalized
