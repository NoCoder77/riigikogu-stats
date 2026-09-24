from __future__ import annotations

from datetime import date

from .api_client import ApiClient


def get_voting_calendar(
    client: ApiClient,
    path: str,
    start: date,
    end: date,
) -> list[date]:
    """Fetch dates when at least one plenary vote occurred. Returns list of date objects."""
    payload = client.get_json(
        path,
        params={
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        },
    )
    out: list[date] = []
    if not isinstance(payload, list):
        return out
    for item in payload:
        if isinstance(item, dict):
            d = item.get("date") or item.get("voteDate") or item.get("sessionDate")
            if d:
                try:
                    out.append(date.fromisoformat(str(d)[:10]))
                except (ValueError, TypeError):
                    pass
        elif isinstance(item, str) and len(item) >= 10:
            try:
                out.append(date.fromisoformat(item[:10]))
            except (ValueError, TypeError):
                pass
    return sorted(set(out))
