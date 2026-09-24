"""Fetch a sample from the Riigikogu API (no DB). Run from repo: python scripts/fetch_api_sample.py"""
from __future__ import annotations

import json
from datetime import date

from riigikogu_stats.ingest.api_client import ApiClient
from riigikogu_stats.ingest.votings import list_votings

def main() -> None:
    client = ApiClient(
        base_url="https://api.riigikogu.ee",
        language="et",
        timeout_seconds=30,
    )
    start = date(2013, 1, 15)
    end = date(2013, 1, 15)
    print(f"Fetching votings from {start} to {end}...")
    try:
        sittings, votings = list_votings(client, "/api/votings", start, end)
        print(f"Got {len(sittings)} sitting(s), {len(votings)} voting(s)")
        items = votings
        if items:
            print("\nFirst item (keys):", list(items[0].keys()))
            print("First item (sample):", json.dumps(items[0], indent=2, default=str)[:800])
        else:
            raw = client.get_json("/api/votings", params={"startDate": start.isoformat(), "endDate": end.isoformat()})
            print("Raw response type:", type(raw))
            if isinstance(raw, dict):
                print("Raw keys:", list(raw.keys()))
            print("Raw (sample):", json.dumps(raw, indent=2, default=str)[:1200])
    except Exception as e:
        print("Error:", e)
        raise

if __name__ == "__main__":
    main()
