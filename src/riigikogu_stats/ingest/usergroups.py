from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Iterable

import requests

from .api_client import ApiClient

logger = logging.getLogger(__name__)

_FACTION_FETCH_TIMEOUT_SECONDS = 60


def _extract_uuid(item: dict[str, Any]) -> str | None:
    for key in ("uuid", "id"):
        value = item.get(key)
        if value:
            return str(value)
    return None


def list_usergroups(
    client: ApiClient,
    path: str,
    type_code: str | None = "FRAKTSIOON",
    hide_inactive: bool = False,
) -> list[dict[str, Any]]:
    """Fetch usergroups list. type_code e.g. FRAKTSIOON for factions."""
    params: dict[str, Any] = {}
    if type_code:
        params["typeCode"] = type_code
    if hide_inactive:
        params["hideInactive"] = "true"
    payload = client.get_json(path, params=params)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "data", "results", "usergroups"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _fetch_usergroup_detail(
    client: ApiClient,
    detail_template: str,
    uuid: str,
    timeout_seconds: int = _FACTION_FETCH_TIMEOUT_SECONDS,
) -> dict[str, Any] | None:
    """Fetch usergroup detail with a timeout. Returns None on timeout or error."""

    def _do_fetch() -> dict[str, Any] | None:
        try:
            return client.get_json(detail_template.format(uuid=uuid))
        except requests.RequestException:
            return None

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_fetch)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            logger.warning(
                "Usergroup %s fetch timed out after %ds, skipping",
                uuid,
                timeout_seconds,
            )
            return None


def iter_usergroup_details(
    client: ApiClient,
    detail_template: str,
    items: Iterable[dict[str, Any]],
    timeout_seconds: int = _FACTION_FETCH_TIMEOUT_SECONDS,
) -> Iterable[dict[str, Any]]:
    for item in items:
        uuid = _extract_uuid(item) if isinstance(item, dict) else None
        if not uuid:
            continue
        detail = _fetch_usergroup_detail(client, detail_template, uuid, timeout_seconds)
        if detail is None:
            # Fallback: use list item as minimal faction (id + name) so we still have
            # all 53 factions in DB; no membership data for these (API returns no detail).
            if isinstance(item, dict) and (item.get("name") or item.get("shortName")):
                minimal = {
                    "_source_uuid": uuid,
                    "id": uuid,
                    "uuid": uuid,
                    "name": item.get("name") or item.get("shortName") or item.get("title") or "",
                    "raw": item,
                }
                yield minimal
            continue
        if isinstance(detail, dict):
            detail["_source_uuid"] = uuid
        yield detail
