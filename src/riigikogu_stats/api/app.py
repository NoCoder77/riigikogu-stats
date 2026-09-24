from __future__ import annotations

import csv
import io
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from ..config import load_settings
from ..db import (
    connect_db,
    create_import_run,
    execute_sql_file,
    mark_stale_running_imports_failed,
)
from ..etl import clear_active_run_if_match, get_active_run_id, request_cancel, run_etl
from ..paths import get_sql_dir, sqlite_path_from_url
from .queries import (
    fetch_faction_by_id,
    fetch_factions,
    fetch_import_run_current,
    fetch_import_run_logs,
    fetch_import_runs,
    fetch_person_by_id,
    fetch_persons,
    fetch_session_by_id,
    fetch_sessions,
    fetch_stats,
    fetch_vote_by_id,
    fetch_vote_faction_breakdown,
    fetch_votes,
    fetch_votes_for_export,
    fetch_voting_days,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Validate env on startup; ensure DB schema exists so API endpoints do not 500."""
    settings = load_settings()
    # Ensure schema exists so /imports, /sessions, /votes do not 500 on first run
    try:
        with connect_db(settings.database_url) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='import_runs'"
            )
            if cur.fetchone() is None:
                sql_dir = get_sql_dir()
                execute_sql_file(conn, sql_dir / "schema_sqlite.sql")
                execute_sql_file(conn, sql_dir / "views_sqlite.sql")
            else:
                # Mark orphaned "running"/"queued" imports as failed
                n = mark_stale_running_imports_failed(conn)
                if n > 0:
                    conn.commit()
            # Migration: add subject, vote_type to votes if missing (existing DBs)
            cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='votes'")
            if cur.fetchone() is not None:
                cur.execute("SELECT 1 FROM pragma_table_info('votes') WHERE name='subject'")
                if cur.fetchone() is None:
                    cur.execute("ALTER TABLE votes ADD COLUMN subject TEXT")
                    cur.execute("ALTER TABLE votes ADD COLUMN vote_type TEXT")
                    conn.commit()
                cur.execute("SELECT 1 FROM pragma_table_info('votes') WHERE name='policy_area'")
                if cur.fetchone() is None:
                    cur.execute("ALTER TABLE votes ADD COLUMN policy_area TEXT")
                    conn.commit()
            # Migration: add voting_days table if missing (existing DBs)
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='voting_days'"
            )
            if cur.fetchone() is None:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS voting_days (vote_date TEXT PRIMARY KEY)"
                )
                conn.commit()
            # Migration: add import_run_logs table if missing (existing DBs)
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='import_run_logs'"
            )
            if cur.fetchone() is None:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS import_run_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id INTEGER NOT NULL REFERENCES import_runs(id),
                        logged_at TEXT NOT NULL,
                        message TEXT NOT NULL
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_import_run_logs_run_id "
                    "ON import_run_logs (run_id)"
                )
                conn.commit()
            # Migration: add v_faction_attendance view if missing (existing DBs)
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_faction_attendance'"
            )
            if cur.fetchone() is None:
                cur.execute("DROP VIEW IF EXISTS v_faction_attendance")
                cur.execute("""
                    CREATE VIEW v_faction_attendance AS
                    SELECT pf.faction_id,
                        COUNT(*) AS total_slots,
                        SUM(CASE WHEN sa.status IN ('present','kohal','presented')
                            THEN 1 ELSE 0 END) AS present_slots,
                        SUM(CASE WHEN sa.status IN ('absent','puudus')
                            THEN 1 ELSE 0 END) AS absent_slots
                    FROM sessions s
                    JOIN person_faction_membership pf
                        ON date(s.session_date) >= date(pf.start_date)
                        AND (pf.end_date IS NULL
                             OR date(s.session_date) <= date(pf.end_date))
                    LEFT JOIN session_attendance sa
                        ON sa.session_id = s.id AND sa.person_id = pf.person_id
                    GROUP BY pf.faction_id
                """)
                conn.commit()
    except Exception:
        logger.exception("Lifespan DB setup failed; endpoints may 500 until Init DB")
    # Mount UI at startup so routes are registered after app is fully set up (fixes 404 on GET / in frozen exe)
    try:
        _static_dir = _get_ui_static_dir()
        if _static_dir and (_static_dir / "index.html").is_file():
            mount_ui(app, _static_dir)
        else:
            @app.get("/")
            def _serve_root_fallback() -> HTMLResponse:
                return _root_fallback_html()
    except Exception:
        logger.warning("UI mount failed, using fallback", exc_info=True)
        @app.get("/")
        def _serve_root_fallback() -> HTMLResponse:
            return _root_fallback_html()
    yield


app = FastAPI(title="Riigikogu Stats API", lifespan=_lifespan)

cors_origins = os.getenv("RIIGIKOGU_CORS_ORIGINS", "http://localhost:5173")
allowed_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ImportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_date: date = Field(..., alias="startDate")
    end_date: date = Field(..., alias="endDate")
    step_days: int = Field(7, alias="stepDays")
    only_votings: bool = Field(False, alias="onlyVotings")
    only_sittings: bool = Field(False, alias="onlySittings")
    init_db: bool = Field(False, alias="initDb")
    sync_usergroups: bool = Field(False, alias="syncUsergroups")


@app.get("/health")
def health() -> dict:
    """Check API and DB connectivity. When frozen, also return database_path and frozen."""
    try:
        settings = load_settings()
        with connect_db(settings.database_url) as conn:
            conn.execute("SELECT 1")
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
    out: dict = {"status": "ok"}
    if getattr(sys, "frozen", False):
        out["frozen"] = True
        if settings.database_url.startswith("sqlite:///"):
            out["database_path"] = sqlite_path_from_url(settings.database_url)
    return out


@app.get("/api/debug-ui")
def debug_ui() -> dict:
    """Return UI path resolution for diagnosis (frozen, candidates tried, resolved path, index_exists)."""
    return {
        "frozen": getattr(sys, "frozen", False),
        "candidates_tried": list(_ui_candidates_tried),
        "ui_static_dir": str(_ui_static_dir_resolved) if _ui_static_dir_resolved else None,
        "index_exists": (_ui_static_dir_resolved / "index.html").is_file()
        if _ui_static_dir_resolved else False,
    }


@app.post("/api/shutdown")
def shutdown() -> dict[str, str]:
    """Trigger graceful process exit (e.g. for Quit app from UI)."""
    os.kill(os.getpid(), signal.SIGINT)
    return {"status": "shutting down"}


@app.post("/imports")
def create_import(
    request: ImportRequest, background_tasks: BackgroundTasks
) -> dict:
    """Create an import run record and dispatch the ETL background task.

    The run record is created here (status='queued') so it is always visible
    in the import history even if the background task crashes on startup.
    """
    if request.start_date > request.end_date:
        raise HTTPException(
            status_code=422, detail="start_date must be <= end_date"
        )
    if request.step_days < 1:
        raise HTTPException(
            status_code=422, detail="step_days must be >= 1"
        )
    if request.only_votings and request.only_sittings:
        raise HTTPException(
            status_code=422,
            detail="only_votings and only_sittings cannot both be true",
        )
    settings = load_settings()
    active_id = get_active_run_id()
    if active_id is not None:
        with connect_db(settings.database_url) as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM import_runs WHERE id = ?", (active_id,))
            row = cur.fetchone()
            status = row["status"] if row else None
        if status in ("running", "queued"):
            raise HTTPException(
                status_code=409,
                detail="An import is already in progress. Wait for it to finish before starting another.",
            )
        clear_active_run_if_match(active_id)
    run_id = None
    for attempt in range(2):
        try:
            with connect_db(settings.database_url) as conn:
                mark_stale_running_imports_failed(conn)
                run_id = create_import_run(
                    conn,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    step_days=request.step_days,
                    only_votings=request.only_votings,
                    only_sittings=request.only_sittings,
                    status="queued",
                )
                conn.commit()
            break
        except Exception as e:
            logger.exception("Failed to create import run")
            is_lock_busy = "locked" in str(e).lower() or "busy" in str(e).lower()
            if is_lock_busy and attempt == 0:
                time.sleep(1)
                continue
            detail = (
                "Another import may be in progress. Please wait a moment and try again."
                if "locked" in str(e).lower()
                else f"Database busy, please try again in a moment: {e}"
            )
            raise HTTPException(status_code=503, detail=detail)

    # Signal any currently-running import to stop and register the new run
    request_cancel(run_id)

    background_tasks.add_task(
        run_etl,
        run_id=run_id,
        start_date=request.start_date,
        end_date=request.end_date,
        step_days=request.step_days,
        only_votings=request.only_votings,
        only_sittings=request.only_sittings,
        init_db=request.init_db,
        sync_usergroups=request.sync_usergroups,
    )
    return {"status": "queued", "run_id": run_id}


@app.get("/imports")
def list_imports(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        return fetch_import_runs(conn, limit=limit, offset=offset)


@app.get("/imports/current")
def get_import_current() -> dict | None:
    """Return the currently running (or queued) import run, if any."""
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        return fetch_import_run_current(conn)


@app.get("/imports/{run_id:int}/logs")
def get_import_logs(
    run_id: int,
    limit: int = Query(200, ge=1, le=500),
) -> list[dict]:
    """Return recent log lines for an import run (chronological)."""
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        return fetch_import_run_logs(conn, run_id=run_id, limit=limit)


@app.get("/sessions")
def list_sessions(
    start_date: Optional[date] = Query(None, alias="startDate"),
    end_date: Optional[date] = Query(None, alias="endDate"),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("session_date", alias="sortBy"),
    order: str = Query("desc"),
) -> dict:
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        return fetch_sessions(
            conn,
            start_date=start_date,
            end_date=end_date,
            status=status,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            order=order,
        )


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        session = fetch_session_by_id(conn, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session


@app.get("/stats")
def get_stats() -> dict:
    """Return data scope: date range, total sessions, votes, persons, factions."""
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        return fetch_stats(conn)


@app.get("/voting-days")
def list_voting_days(
    start_date: Optional[date] = Query(None, alias="startDate"),
    end_date: Optional[date] = Query(None, alias="endDate"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """Return dates when at least one plenary vote occurred."""
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        return fetch_voting_days(
            conn,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )


@app.get("/votes")
def list_votes(
    start_date: Optional[date] = Query(None, alias="startDate"),
    end_date: Optional[date] = Query(None, alias="endDate"),
    outcome: Optional[str] = Query(None),
    choice: Optional[str] = Query(None),
    subject_contains: Optional[str] = Query(None, alias="subjectContains"),
    policy_area: Optional[str] = Query(None, alias="policyArea"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("vote_time", alias="sortBy"),
    order: str = Query("desc"),
) -> dict:
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        return fetch_votes(
            conn,
            start_date=start_date,
            end_date=end_date,
            outcome=outcome,
            choice=choice,
            subject_contains=subject_contains,
            policy_area=policy_area,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            order=order,
        )


@app.get("/votes/{vote_id}/faction-breakdown")
def get_vote_faction_breakdown(vote_id: str) -> list:
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        return fetch_vote_faction_breakdown(conn, vote_id)


@app.get("/votes/{vote_id}")
def get_vote(vote_id: str) -> dict:
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        vote = fetch_vote_by_id(conn, vote_id)
        if vote is None:
            raise HTTPException(status_code=404, detail="Vote not found")
        return vote


EXPORT_VOTE_COLUMNS = [
    "id", "session_id", "session_date", "session_title", "title", "subject",
    "vote_type", "policy_area", "vote_time", "result", "casts_count",
    "votes_for", "votes_against", "votes_abstain", "votes_did_not_vote", "votes_absent",
]


@app.get("/persons")
def list_persons(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("votes_recorded", alias="sortBy"),
    order: str = Query("desc"),
) -> dict:
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        return fetch_persons(
            conn, limit=limit, offset=offset, sort_by=sort_by, order=order
        )


@app.get("/persons/{person_id}")
def get_person(
    person_id: str,
    vote_type: Optional[str] = Query(None, alias="voteType"),
    policy_area: Optional[str] = Query(None, alias="policyArea"),
) -> dict:
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        person = fetch_person_by_id(
            conn, person_id, vote_type=vote_type, policy_area=policy_area
        )
        if person is None:
            raise HTTPException(status_code=404, detail="Person not found")
        return person


@app.get("/factions")
def list_factions(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        return fetch_factions(conn, limit=limit, offset=offset)


@app.get("/factions/{faction_id}")
def get_faction(
    faction_id: str,
    policy_area: Optional[str] = Query(None, alias="policyArea"),
) -> dict:
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        faction = fetch_faction_by_id(conn, faction_id, policy_area=policy_area)
        if faction is None:
            raise HTTPException(status_code=404, detail="Faction not found")
        return faction


@app.get("/export/votes")
def export_votes(
    start_date: Optional[date] = Query(None, alias="startDate"),
    end_date: Optional[date] = Query(None, alias="endDate"),
    outcome: Optional[str] = Query(None),
    choice: Optional[str] = Query(None),
    subject_contains: Optional[str] = Query(None, alias="subjectContains"),
    policy_area: Optional[str] = Query(None, alias="policyArea"),
    sort_by: str = Query("vote_time", alias="sortBy"),
    order: str = Query("desc"),
) -> Response:
    """Return filtered votes as CSV. Same query params as GET /votes."""
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        rows = fetch_votes_for_export(
            conn,
            start_date=start_date,
            end_date=end_date,
            outcome=outcome,
            choice=choice,
            subject_contains=subject_contains,
            policy_area=policy_area,
            sort_by=sort_by,
            order=order,
        )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPORT_VOTE_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(
            {k: ("" if r.get(k) is None else r[k]) for k in EXPORT_VOTE_COLUMNS}
        )
    content = "\ufeff" + buf.getvalue()
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=votes.csv"},
    )


# Populated by _get_ui_static_dir() for GET /api/debug-ui
_ui_candidates_tried: list[str] = []
_ui_static_dir_resolved: Path | None = None


def _get_ui_static_dir() -> Path | None:
    """Return UI static directory (Vite build output) when running frozen or from source. Never raises."""
    global _ui_candidates_tried, _ui_static_dir_resolved
    _ui_candidates_tried = []
    _ui_static_dir_resolved = None
    try:
        if getattr(sys, "frozen", False):
            exe_parent = Path(sys.executable).parent
            meipass = getattr(sys, "_MEIPASS", None)
            # PyInstaller 6 onedir: datas end up in _internal/, so try _internal/ui_dist first
            bases: list[Path] = [
                exe_parent / "_internal" / "ui_dist",
                exe_parent / "ui_dist",
            ]
            if meipass is not None:
                bases.append(Path(meipass) / "ui_dist")
                bases.append(Path(meipass).parent / "ui_dist")
            for base in bases:
                path = base.resolve() if base.is_absolute() else base
                _ui_candidates_tried.append(str(path))
                is_dir = path.is_dir()
                index_ok = (path / "index.html").is_file() if is_dir else False
                if is_dir and index_ok:
                    _ui_static_dir_resolved = path
                    return path
            return None
        # __file__ = .../riigikogu_stats/src/riigikogu_stats/api/app.py -> parents[3] = project root
        path = Path(__file__).resolve().parents[3] / "ui" / "dist"
        _ui_candidates_tried.append(str(path))
        if path.is_dir():
            _ui_static_dir_resolved = path
            return path
        return None
    except Exception:
        return None


def _root_fallback_html() -> HTMLResponse:
    """Fallback when UI is not built or path resolution fails."""
    return HTMLResponse(
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Riigikogu Stats</title></head>"
        "<body><p>UI not built.</p><p>Run: <code>cd ui && npm run build</code></p>"
        "<p><a href='/docs'>API docs</a></p></body></html>",
        status_code=200,
    )


def mount_ui(app: FastAPI, static_dir: str | Path) -> None:
    """Serve built React UI from static_dir (Vite build output)."""
    root = Path(static_dir)
    assets_dir = root / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="ui_assets")
    index_path = root / "index.html"
    if not index_path.is_file():
        return

    @app.get("/")
    def serve_root() -> FileResponse:
        return FileResponse(str(index_path))

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        return FileResponse(str(index_path))


# UI is mounted in lifespan so GET / is registered after app startup (fixes frozen exe 404)
