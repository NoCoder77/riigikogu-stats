# Faction membership and historical data

## Primary source: voting detail API

Faction-at-time-of-vote is taken from **GET /api/votings/{uuid}**: each item in `voters[]` can include a `faction` object (`uuid`, `name`). When present, we persist it as `person_faction_membership` with `start_date` = vote date and `end_date` = NULL. This gives correct faction attribution for every vote we import, as long as the API returns `faction` for that vote.

**Verified:** For votes in 2024, the API returns `faction` for every voter in the detail response.

**Older votes:** Sample checks for 2013, 2016, 2019 were not completed (API returned 429 Too Many Requests during verification). To verify yourself, run (with appropriate rate limiting):

```bash
python scripts/check_vote_api_faction.py
```

If the API returns `voters[].faction` for all dates you care about, re-importing votes for that range will backfill historical membership. If older votes do not include `faction`, consider an external backfill (see below).

## Merge step (no overcounting)

Vote import creates one `person_faction_membership` row per (person, faction, vote_date). That can produce many rows for the same person and faction (e.g. one per day). The views `v_faction_vote_counts` and `v_faction_attendance` join on `vote_time` within `[start_date, end_date]`; without merging, a single vote could match multiple membership rows and be counted multiple times per faction.

After each import run, we call **`merge_memberships(conn)`** (in `db.py`). It coalesces rows with the same `(person_id, faction_id)` into contiguous intervals (overlapping/adjacent `[start_date, end_date]` merged). After merge, each vote date matches at most one membership row per (person, faction), so faction totals and percentages are correct.

## Alternative sources if the API omits faction for older votes

- **CSV backfill**: The script `scripts/backfill_faction_membership_csv.py` reads a CSV with columns `person_id,faction_id,start_date,end_date` (UUIDs matching the DB; end_date optional) and upserts into `person_faction_membership`. Run from project root with `PYTHONPATH=src python scripts/backfill_faction_membership_csv.py path/to/memberships.csv`; add `--merge` to coalesce intervals after. Use this with data from morph.io or any export that includes person and faction identifiers.
- **morph.io “riigikogu-members”**: CSV with person UUID and faction name; single snapshot (e.g. 2015). Map faction name to our `factions.id` (e.g. by matching names in the DB), then produce a CSV in the format above with term-based start/end dates and run the backfill script.
- **Riigikogu web / other scrapers**: Term composition pages may list member–faction by term; would require a separate importer that outputs the same CSV format or calls the DB.
