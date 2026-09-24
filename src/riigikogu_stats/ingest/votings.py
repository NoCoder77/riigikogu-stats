from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from .api_client import ApiClient


def _extract_uuid(item: dict[str, Any]) -> str | None:
    for key in ("uuid", "id", "votingUuid", "votingId"):
        value = item.get(key)
        if value:
            return str(value)
    return None


def list_votings(
    client: ApiClient, path: str, start: date, end: date
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch votings list. API returns sittings with nested votings. Returns (sittings, flat_voting_refs)."""
    payload = client.get_json(
        path,
        params={"startDate": start.isoformat(), "endDate": end.isoformat()},
    )
    items: list[dict[str, Any]] = []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for key in ("votings", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                items = value
                break
    # API returns sittings each with nested "votings" array; flatten to one ref per voting
    sittings: list[dict[str, Any]] = []
    flat: list[dict[str, Any]] = []
    for sitting in items:
        nested = sitting.get("votings") if isinstance(sitting, dict) else None
        if isinstance(nested, list):
            sittings.append(sitting)
            for v in nested:
                uid = (v.get("uuid") or v.get("id")) if isinstance(v, dict) else None
                if uid:
                    flat.append({"uuid": str(uid)})
        else:
            # single voting or legacy flat list
            uid = _extract_uuid(sitting) if isinstance(sitting, dict) else None
            if uid:
                flat.append({"uuid": uid})
    voting_refs = flat if flat else items
    return (sittings, voting_refs)


def iter_voting_details(
    client: ApiClient, detail_template: str, items: Iterable[dict[str, Any]]
) -> Iterable[dict[str, Any]]:
    for item in items:
        uuid = _extract_uuid(item)
        if not uuid:
            continue
        detail = client.get_json(detail_template.format(uuid=uuid))
        if isinstance(detail, dict):
            detail["_source_uuid"] = uuid
        yield detail
