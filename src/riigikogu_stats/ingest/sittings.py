from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from .api_client import ApiClient


def _extract_uuid(item: dict[str, Any]) -> str | None:
    for key in ("uuid", "id", "sittingUuid", "sittingId"):
        value = item.get(key)
        if value:
            return str(value)
    return None


def list_sittings(client: ApiClient, path: str, start: date, end: date) -> list[dict[str, Any]]:
    payload = client.get_json(
        path,
        params={"startDate": start.isoformat(), "endDate": end.isoformat()},
    )
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("sittings", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def iter_sitting_details(
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
