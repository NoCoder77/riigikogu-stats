# Riigikogu statistics ETL

This project ingests Riigikogu session attendance and voting data from the official
open data API into SQLite, then exposes views for analytics and dashboards.

## Requirements
- Python 3.10+

## Setup
```bash
python -m venv .venv
.venv/bin/activate
pip install -e .
```

For tests: `pip install -e ".[dev]"` then `pytest`.

### Database (SQLite)
The app uses SQLite by default. No server or user setup is required.

- **Default**: If `DATABASE_URL` is not set, the app uses `sqlite:///riigikogu.db` (in the current working directory; when running the Windows exe, next to the exe).
- **Override**: Set `DATABASE_URL`, e.g. `sqlite:///path/to/riigikogu.db`. On Windows: `$env:DATABASE_URL="sqlite:///C:/data/riigikogu.db"`.

3. Initialize schema and views once (see below) using the UI “Init DB schema” + Import, or:
```bash
python -m riigikogu_stats.etl --init-db --start-date 2013-01-01 --end-date 2013-01-07
```

Optional API env vars:
```bash
export RIIGIKOGU_API_BASE_URL="https://api.riigikogu.ee"
export RIIGIKOGU_API_LANG="et"
# Delay between API requests in seconds (default 0.5). Use 1.0 or higher for long imports to avoid rate limiting.
export RIIGIKOGU_RATE_LIMIT_SECONDS=0.5
```

Optional overrides (if endpoints differ in Swagger):
```bash
export RIIGIKOGU_VOTINGS_LIST_PATH="/api/votings"
export RIIGIKOGU_VOTING_DETAIL_PATH_TEMPLATE="/api/votings/{uuid}"
export RIIGIKOGU_SITTINGS_LIST_PATH="/api/sittings"
export RIIGIKOGU_SITTING_DETAIL_PATH_TEMPLATE="/api/sittings/{uuid}"
```

## Initialize database schema + views
```bash
python -m riigikogu_stats.etl --init-db --start-date 2013-01-01 --end-date 2013-01-07
```

## Run ETL
```bash
python -m riigikogu_stats.etl --start-date 2013-01-01 --end-date 2013-12-31
```

**Long imports (years of data):** The ETL chunks by `--step-days` (default 7) and sleeps between each API request. If the import range is **over 365 days**, the ETL automatically uses at least 1.0 s delay to reduce rate limiting (429); otherwise it uses `RIIGIKOGU_RATE_LIMIT_SECONDS` (default 0.5). You can still set a higher env value if needed. The API client retries on 429 with 10s backoff up to 4 times.

Sync factions and membership from the usergroups API (canonical membership dates):
```bash
python -m riigikogu_stats.etl --start-date 2013-01-01 --end-date 2013-12-31 --init-db --sync-usergroups
```

You can limit to one data type:
```bash
python -m riigikogu_stats.etl --start-date 2013-01-01 --end-date 2013-12-31 --only-votings
python -m riigikogu_stats.etl --start-date 2013-01-01 --end-date 2013-12-31 --only-sittings
```

### Deduplication
Imports are deduplicated so re-running the same date range does not create duplicate rows:

- Each **vote** and **session** (with its attendance) is hashed (canonical JSON). The hash is stored in `import_item_hashes` with the entity id.
- Before loading a vote or session, the ETL compares the new hash to the stored hash. If they match, the item is **skipped** (not written again). If they differ or the item is new, it is loaded and the hash is updated.
- Tables use primary keys and `ON CONFLICT ... DO UPDATE`, so re-importing the same data is idempotent even without the hash check; the hash skip avoids unnecessary API and DB work.

## Notes
- The open data documentation notes that data before 2012 may be incomplete.
- Many API records reference UUIDs; this ETL stores source UUIDs as text primary keys.
- If the sittings/attendance endpoints differ, update the env vars above after checking
  Swagger UI. Sittings ingest is resilient: if the sittings API fails (e.g. 404), the run
  continues and only votings are imported.
- Factions and `person_faction_membership` are populated from the voting-detail API
  (each voter’s faction at time of vote). For canonical faction membership with start/end
  dates, run with `--sync-usergroups` (or enable “Sync factions and membership” in the UI);
  this calls `/api/usergroups` (type FRAKTSIOON) and upserts factions and memberships.
  The API list returns all terms’ factions (e.g. 53), but the detail endpoint often returns
  data only for the current term’s factions (~7). When detail is missing, we fall back to
  the list item (id + name) so all factions appear in the DB; only those with detail get
  membership dates. For full historical membership, consider external sources (e.g.
  morph.io “riigikogu-members”, or Riigikogu web pages). After each import, faction memberships are merged into contiguous intervals so vote-based stats are correct (see [docs/faction_membership.md](docs/faction_membership.md)).
- Terms are populated from session data or created as stubs when referenced.
- Voting calendar: after each run, the ETL fetches `/api/votings/calendar` for the date
  range and stores dates in `voting_days`; `GET /stats` includes `last_voting_date`, and
  `GET /voting-days` lists those dates.

## Run API
```bash
uvicorn riigikogu_stats.api.app:app --reload --port 8000
```

Endpoints:
- `GET /health` — API and DB connectivity (returns `{ "status": "ok" }` or `"unhealthy"` with error).
- `GET /stats` — data scope: min/max session_date, min/max vote_time, total_sessions, total_votes, total_persons, total_factions, last_voting_date (from voting_days if present).
- `GET /voting-days` — dates when at least one plenary vote occurred. Optional: startDate, endDate, limit, offset.
- `POST /imports` with `{startDate,endDate,stepDays,onlyVotings,onlySittings,initDb,syncUsergroups}`
- `GET /imports` — list of import runs.
- `GET /sessions` — `{ "items": [...], "total": N }`. Optional: `sortBy`, `order`, date filters.
- `GET /sessions/{session_id}` — session row + list of votes in that session.
- `GET /votes` — `{ "items": [...], "total": N }`. Optional: `sortBy`, `order`, `startDate`, `endDate`, `outcome`, `choice`, `subjectContains` (search in subject/title).
- `GET /votes/{vote_id}` — vote detail + casts (person, choice, faction).
- `GET /votes/{vote_id}/faction-breakdown` — per-faction counts for that vote.
- `GET /export/votes` — same filters as list votes; returns CSV.
- `GET /persons` — `{ "items": [...], "total": N }`. Optional: `sortBy`, `order`.
- `GET /persons/{person_id}` — person + vote participation, attendance, recent casts.
- `GET /factions` — `{ "items": [...], "total": N }`.
- `GET /factions/{faction_id}` — faction + aggregate vote counts.

CORS is enabled for the UI origin; set `RIIGIKOGU_CORS_ORIGINS` (e.g. `http://localhost:5173`) if needed.

## Run UI
```bash
cd ui
npm install
npm run dev
```

If the API runs on a different host/port, set:
```bash
export VITE_API_BASE_URL="http://localhost:8000"
```

## Windows executable (one-folder build)
You can build a Windows executable that runs both the API and the built UI. By default it uses a SQLite database in a persistent location so updating the exe does not remove your data; no `.env` is required.

**Build** (from project root):
```powershell
.\build\build_windows.ps1
```
This installs PyInstaller if needed, builds the UI with relative API URLs (`VITE_API_BASE_URL=`), runs PyInstaller, and copies `.env.example` into the output folder. Result: `dist\riigikogu_stats\` with `riigikogu_stats.exe` and dependencies.

**Run the exe:**
1. (Optional) Place a `.env` next to the exe to set `DATABASE_URL=sqlite:///path/to/riigikogu.db`. If unset: if `riigikogu.db` exists in the same folder as the exe, it is used; otherwise the exe uses `%LOCALAPPDATA%\RiigikoguStats\riigikogu.db` (created automatically), so the database survives when you replace the exe folder.
2. Double-click `riigikogu_stats.exe` or run it from a terminal. The API serves at `http://127.0.0.1:8000` and the built UI is served from the same origin; the default browser opens after startup.

To run without opening the browser, use the normal API/UI dev workflow (uvicorn + `npm run dev`).

## Views for analytics
Views are defined in `sql/views_sqlite.sql`, e.g.:
- `v_votes_summary`
- `v_person_attendance_rate`
- `v_vote_participation`
- `v_faction_vote_counts`

## License

MIT — see [LICENSE](LICENSE). Free to use, modify, and redistribute.
