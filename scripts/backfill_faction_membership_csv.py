"""Backfill person_faction_membership from a CSV file.

Use when the voting API does not return faction for some date range and you have
external data (e.g. morph.io riigikogu-members, or manual export). After import,
run a full ETL merge (or the merge step) to coalesce intervals.

CSV format: person_id,faction_id,start_date,end_date
- person_id, faction_id: UUIDs matching persons.id and factions.id in the DB.
- start_date, end_date: YYYY-MM-DD. Leave end_date empty for open-ended.

Example:
  person_id,faction_id,start_date,end_date
  fe748f4d-3f50-4af8-8069-92a460978d2b,8772fd6f-3197-6a53-2ffc-8c4d63407d1e,2019-04-01,2023-03-31

Run from project root (riigikogu_stats):
  python -m scripts.backfill_faction_membership_csv path/to/memberships.csv
  python -m scripts.backfill_faction_membership_csv path/to/memberships.csv --merge
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Allow running as script from project root (package is in src/)
if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    src = root / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

from riigikogu_stats.config import load_settings
from riigikogu_stats.db import connect_db, merge_memberships, upsert_memberships


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill person_faction_membership from CSV")
    parser.add_argument("csv_path", type=Path, help="CSV: person_id,faction_id,start_date,end_date")
    parser.add_argument("--merge", action="store_true", help="Run merge_memberships after import")
    args = parser.parse_args()
    if not args.csv_path.is_file():
        print(f"File not found: {args.csv_path}", file=sys.stderr)
        return 1
    settings = load_settings()
    memberships: list[dict] = []
    with open(args.csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            person_id = (row.get("person_id") or "").strip()
            faction_id = (row.get("faction_id") or "").strip()
            start_date = (row.get("start_date") or "").strip() or None
            end_date = (row.get("end_date") or "").strip() or None
            if not person_id or not faction_id or not start_date:
                continue
            memberships.append({
                "person_id": person_id,
                "faction_id": faction_id,
                "start_date": start_date,
                "end_date": end_date if end_date else None,
                "raw": None,
            })
    if not memberships:
        print("No valid rows (need person_id, faction_id, start_date)", file=sys.stderr)
        return 1
    with connect_db(settings.database_url) as conn:
        upsert_memberships(conn, memberships)
        print(f"Upserted {len(memberships)} membership row(s).")
        if args.merge:
            removed = merge_memberships(conn)
            print(f"Merge: {removed} duplicate row(s) coalesced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
