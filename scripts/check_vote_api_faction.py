"""Check if GET /api/votings/{uuid} returns faction per voter for sample years.
Run: python -m scripts.check_vote_api_faction (from project root) or python scripts/check_vote_api_faction.py
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date

BASE = "https://api.riigikogu.ee"
SAMPLES = [
    ("2013", date(2013, 6, 1), date(2013, 6, 5)),
    ("2016", date(2016, 9, 1), date(2016, 9, 5)),
    ("2019", date(2019, 4, 1), date(2019, 4, 5)),
    ("2024", date(2024, 1, 15), date(2024, 1, 16)),
]


def main() -> None:
    for label, start, end in SAMPLES:
        url = f"{BASE}/api/votings?startDate={start}&endDate={end}&lang=et"
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.loads(r.read().decode())
        except Exception as e:
            print(f"{label}: list failed: {e}")
            continue
        if not isinstance(data, list) or not data:
            print(f"{label}: no sittings")
            continue
        sitting = data[0]
        votings = sitting.get("votings") or []
        if not votings:
            print(f"{label}: no votings in first sitting")
            continue
        uuid = votings[0].get("uuid")
        if not uuid:
            print(f"{label}: no voting uuid")
            continue
        detail_url = f"{BASE}/api/votings/{uuid}"
        try:
            with urllib.request.urlopen(detail_url, timeout=15) as r2:
                detail = json.loads(r2.read().decode())
        except Exception as e:
            print(f"{label}: detail failed: {e}")
            continue
        voters = detail.get("voters") or []
        with_faction = sum(1 for v in voters if isinstance(v, dict) and v.get("faction"))
        print(f"{label} ({start}): {len(voters)} voters, {with_faction} with faction")


if __name__ == "__main__":
    main()
