from __future__ import annotations

import argparse
import logging
import threading
import time
import traceback
from datetime import date, timedelta

from .config import load_settings
from .db import (
    append_import_run_log,
    connect_db,
    create_import_run,
    execute_sql_file,
    finish_import_run,
    get_item_hash,
    merge_memberships,
    update_import_run_counts,
    upsert_item_hash,
    upsert_voting_days,
)
from .hashing import stable_hash
from .ingest.api_client import ApiClient
from .ingest.calendar import get_voting_calendar
from .ingest.sittings import iter_sitting_details, list_sittings
from .ingest.usergroups import iter_usergroup_details, list_usergroups
from .ingest.votings import iter_voting_details, list_votings
from .load.loaders import load_session, load_usergroup, load_vote
from .paths import get_sql_dir
from .policy_area import resolve_policy_area
from .transform.normalize import (
    extract_attendance,
    extract_vote_casts,
    normalize_session,
    normalize_vote,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Concurrency control -- replaces the old cancel_import_event (threading.Event)
#
# _import_lock      : ensures only one run_etl executes at a time.
# _active_run_id    : the run_id currently executing (or None).
# _cancel_run_ids   : run_ids that should stop at the next checkpoint.
#
# The old Event had a race: new run_etl called .clear() before the old one
# checked .is_set(), so the old one never saw the cancellation.  With per-id
# tracking the old run's id stays in _cancel_run_ids regardless of what the
# new run does.
# ---------------------------------------------------------------------------
_state_lock = threading.Lock()   # protects _active_run_id, _cancel_run_ids
_etl_gate = threading.Lock()     # one-at-a-time ETL execution
_active_run_id: int | None = None
_cancel_run_ids: set[int] = set()


def request_cancel(new_run_id: int) -> None:
    """Called from the API handler to signal any currently-active import to stop.

    Adds the old active run_id (if any) to _cancel_run_ids and records the
    new run_id as the active one.
    """
    global _active_run_id
    with _state_lock:
        if _active_run_id is not None and _active_run_id != new_run_id:
            _cancel_run_ids.add(_active_run_id)
        _active_run_id = new_run_id


def get_active_run_id() -> int | None:
    """Return the run_id of the currently running or queued import, or None."""
    with _state_lock:
        return _active_run_id


def clear_active_run_if_match(run_id: int) -> None:
    """If _active_run_id equals run_id, clear it so a new import can start (e.g. after crash)."""
    global _active_run_id
    with _state_lock:
        if _active_run_id == run_id:
            _active_run_id = None
        _cancel_run_ids.discard(run_id)


def _is_cancel_requested(run_id: int) -> bool:
    """True if this run has been asked to stop (already marked failed via _check_cancelled)."""
    with _state_lock:
        return run_id in _cancel_run_ids


# When import range exceeds this many days, use a higher delay to reduce rate-limiting risk
_DAYS_LONG_IMPORT = 365
_RATE_LIMIT_LONG_IMPORT_SECONDS = 1.0


def _effective_rate_limit(settings, start_date: date, end_date: date) -> float:
    """Use a higher delay for multi-year imports so the API is less likely to throttle."""
    range_days = (end_date - start_date).days
    if range_days > _DAYS_LONG_IMPORT:
        return max(settings.rate_limit_seconds, _RATE_LIMIT_LONG_IMPORT_SECONDS)
    return settings.rate_limit_seconds


def _date_range(start: date, end: date, step_days: int) -> list[tuple[date, date]]:
    ranges = []
    cursor = start
    while cursor <= end:
        chunk_end = min(end, cursor + timedelta(days=step_days - 1))
        ranges.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return ranges


def _init_db(conn) -> None:
    sql_dir = get_sql_dir()
    execute_sql_file(conn, sql_dir / "schema_sqlite.sql")
    execute_sql_file(conn, sql_dir / "views_sqlite.sql")


def _check_cancelled(conn, run_id: int) -> bool:
    """Return True if this run_id has been asked to stop; mark it failed in DB."""
    with _state_lock:
        should_cancel = run_id in _cancel_run_ids
    if not should_cancel:
        return False
    logger.info("Import run %d cancelled by new import", run_id)
    try:
        append_import_run_log(conn, run_id, "Import cancelled by new import")
        conn.commit()
        finish_import_run(conn, run_id, "failed", "Cancelled by new import")
        conn.commit()
    except Exception:
        logger.exception("Failed to record cancellation for run_id=%d", run_id)
    return True


# ---------------------------------------------------------------------------
# Lock timeout: if an old import is still running when a new one starts,
# we wait up to this many seconds for the old one to hit a cancellation
# checkpoint and release the lock.
# ---------------------------------------------------------------------------
_LOCK_WAIT_SECONDS = 60


def run_etl(
    run_id: int,
    start_date: date,
    end_date: date,
    step_days: int,
    only_votings: bool,
    only_sittings: bool,
    init_db: bool,
    sync_usergroups: bool = False,
) -> None:
    """Entry point for the background import task.

    run_id is created by the API handler so it always exists in the DB,
    even if this function crashes before doing anything.
    """
    global _active_run_id
    # Acquire the import lock so only one import runs at a time.
    acquired = _etl_gate.acquire(timeout=_LOCK_WAIT_SECONDS)
    if not acquired:
        logger.error("Could not acquire import lock after %ds (run_id=%d)", _LOCK_WAIT_SECONDS, run_id)
        try:
            settings = load_settings()
            with connect_db(settings.database_url) as conn:
                append_import_run_log(conn, run_id, "Could not start: another import is still running")
                conn.commit()
                finish_import_run(conn, run_id, "failed", "Timed out waiting for previous import")
                conn.commit()
        except Exception:
            logger.exception("Failed to record lock-timeout for run_id=%d", run_id)
        # Clear _active_run_id so the next import is not blocked by 409
        with _state_lock:
            if _active_run_id == run_id:
                _active_run_id = None
            _cancel_run_ids.discard(run_id)
        return
    try:
        _run_etl_inner(
            run_id=run_id,
            start_date=start_date,
            end_date=end_date,
            step_days=step_days,
            only_votings=only_votings,
            only_sittings=only_sittings,
            init_db=init_db,
            sync_usergroups=sync_usergroups,
        )
    except Exception:
        logger.exception("run_etl crashed (run_id=%d)", run_id)
        # Best-effort: mark the run failed in DB
        try:
            settings = load_settings()
            with connect_db(settings.database_url) as conn:
                tb = traceback.format_exc()
                append_import_run_log(conn, run_id, f"Import crashed: {tb[-500:]}")
                conn.commit()
                finish_import_run(conn, run_id, "failed", tb[-500:])
                conn.commit()
        except Exception:
            logger.exception("Failed to record crash for run_id=%d", run_id)
    finally:
        with _state_lock:
            if _active_run_id == run_id:
                _active_run_id = None
            _cancel_run_ids.discard(run_id)
        _etl_gate.release()


def _run_etl_inner(
    run_id: int,
    start_date: date,
    end_date: date,
    step_days: int,
    only_votings: bool,
    only_sittings: bool,
    init_db: bool,
    sync_usergroups: bool,
) -> None:
    """Core ETL logic. Exceptions propagate to run_etl's top-level handler."""
    settings = load_settings()
    rate_limit = _effective_rate_limit(settings, start_date, end_date)
    if rate_limit != settings.rate_limit_seconds:
        logger.info(
            "Import range > %s days: using %.1fs delay between API requests",
            _DAYS_LONG_IMPORT,
            rate_limit,
        )
    client = ApiClient(
        base_url=settings.base_url,
        language=settings.language,
        timeout_seconds=settings.request_timeout_seconds,
    )
    with connect_db(settings.database_url) as conn:
        if init_db:
            _init_db(conn)
        # Transition status from "queued" to "running"
        conn.execute(
            "UPDATE import_runs SET status = 'running' WHERE id = :id AND status = 'queued'",
            {"id": run_id},
        )
        conn.commit()
        append_import_run_log(conn, run_id, f"Import started (sync_usergroups={sync_usergroups})")
        conn.commit()

        if _check_cancelled(conn, run_id):
            return

        if sync_usergroups:
            _sync_usergroups(conn, client, settings, run_id, rate_limit)
            if _check_cancelled(conn, run_id):
                return

        items_processed = 0
        items_skipped = 0

        ranges = _date_range(start_date, end_date, step_days)
        if len(ranges) > 100:
            append_import_run_log(
                conn, run_id, f"Large import: {len(ranges)} chunks, may take hours"
            )
            conn.commit()

        for idx, (chunk_start, chunk_end) in enumerate(ranges):
            if _check_cancelled(conn, run_id):
                return
            append_import_run_log(
                conn, run_id, f"Chunk {idx + 1}/{len(ranges)}: {chunk_start}\u2013{chunk_end}"
            )
            conn.commit()

            # Load sittings first so sessions exist before votes
            if not only_votings:
                processed, skipped = _process_sittings(
                    conn, client, settings, run_id, rate_limit,
                    chunk_start, chunk_end, items_processed, items_skipped,
                )
                items_processed, items_skipped = processed, skipped
                # Sub-step may have cancelled mid-loop; do not continue or mark success
                if _is_cancel_requested(run_id):
                    return

            if not only_sittings:
                processed, skipped = _process_votings(
                    conn, client, settings, run_id, rate_limit,
                    chunk_start, chunk_end, items_processed, items_skipped,
                )
                items_processed, items_skipped = processed, skipped
                if _is_cancel_requested(run_id):
                    return

        if _is_cancel_requested(run_id):
            return

        # Voting calendar sync
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='voting_days'"
            )
            if cur.fetchone() is None:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS voting_days (vote_date TEXT PRIMARY KEY)"
                )
                conn.commit()
            calendar_dates = get_voting_calendar(
                client, settings.votings_calendar_path, start_date, end_date
            )
            if calendar_dates:
                upsert_voting_days(conn, (d.isoformat() for d in calendar_dates))
                conn.commit()
        except Exception as e:
            logger.warning("Voting calendar sync skipped: %s", e, exc_info=True)

        # Coalesce person_faction_membership into contiguous intervals to avoid overcounting in faction stats
        try:
            removed = merge_memberships(conn)
            if removed > 0:
                append_import_run_log(conn, run_id, f"Merged faction memberships: {removed} duplicate row(s) coalesced")
                conn.commit()
        except Exception as e:
            logger.warning("Merge memberships skipped: %s", e, exc_info=True)

        append_import_run_log(conn, run_id, "Import finished successfully")
        conn.commit()
        finish_import_run(conn, run_id, "success", None)
        conn.commit()


# ---------------------------------------------------------------------------
# Sub-steps extracted for readability
# ---------------------------------------------------------------------------


def _sync_usergroups(conn, client, settings, run_id, rate_limit) -> None:
    """Sync factions from API. List returns 53; detail endpoint returns data only for 7
    (API limitation—no date/term param documented)."""
    try:
        groups = list_usergroups(
            client,
            settings.usergroups_list_path,
            type_code="FRAKTSIOON",
            hide_inactive=False,
        )
        append_import_run_log(conn, run_id, f"Syncing {len(groups)} faction(s)\u2026")
        conn.commit()
        time.sleep(rate_limit)
        if _check_cancelled(conn, run_id):
            return
        synced_count = 0
        for i, detail in enumerate(
            iter_usergroup_details(
                client, settings.usergroup_detail_path_template, groups
            )
        ):
            if _check_cancelled(conn, run_id):
                return
            synced_count += 1
            ug_id = detail.get("_source_uuid") or detail.get("uuid") or "?"
            append_import_run_log(
                conn, run_id, f"Faction {i + 1}/{len(groups)}: {ug_id}"
            )
            conn.commit()
            try:
                load_usergroup(conn, detail)
                conn.commit()
            except Exception as ug_err:
                ug_id = detail.get("_source_uuid") or detail.get("uuid") or "?"
                append_import_run_log(conn, run_id, f"Usergroup {ug_id} skipped: {ug_err}")
                conn.commit()
                logger.warning("Usergroup %s skipped: %s", ug_id, ug_err, exc_info=False)
            time.sleep(rate_limit)
        skipped = len(groups) - synced_count
        if skipped > 0:
            append_import_run_log(
                conn, run_id,
                f"Factions sync done. {synced_count} synced, {skipped} skipped (API returned no detail for skipped)."
            )
        else:
            append_import_run_log(conn, run_id, "Factions sync done")
        conn.commit()
    except Exception as e:
        append_import_run_log(conn, run_id, f"Factions sync skipped: {e}")
        conn.commit()
        logger.warning("Usergroups sync skipped: %s", e, exc_info=True)


def _process_sittings(
    conn, client, settings, run_id, rate_limit,
    chunk_start, chunk_end, items_processed, items_skipped,
) -> tuple[int, int]:
    """Process sittings for one date chunk. Returns (items_processed, items_skipped)."""
    try:
        append_import_run_log(
            conn, run_id, f"Processing sittings {chunk_start}\u2013{chunk_end}",
        )
        conn.commit()
        sittings = list_sittings(
            client, settings.sittings_list_path, chunk_start, chunk_end
        )
        time.sleep(rate_limit)
        for detail in iter_sitting_details(
            client, settings.sitting_detail_path_template, sittings
        ):
            if _check_cancelled(conn, run_id):
                return items_processed, items_skipped
            session = normalize_session(detail)
            if not session:
                continue
            attendance = extract_attendance(detail)
            attendance_sorted = sorted(
                attendance,
                key=lambda entry: (entry.get("person") or {}).get("id", ""),
            )
            content_hash = stable_hash(
                {"session": session, "attendance": attendance_sorted}
            )
            existing_hash = get_item_hash(conn, "session", session["id"])
            if existing_hash == content_hash:
                items_skipped += 1
                update_import_run_counts(conn, run_id, items_processed, items_skipped)
                conn.commit()
                continue
            load_session(conn, session, attendance_sorted)
            upsert_item_hash(conn, "session", session["id"], content_hash)
            items_processed += 1
            update_import_run_counts(conn, run_id, items_processed, items_skipped)
            conn.commit()
            time.sleep(rate_limit)
    except Exception as e:
        logger.warning(
            "Sittings ingest skipped for %s\u2013%s: %s",
            chunk_start, chunk_end, e, exc_info=True,
        )
    return items_processed, items_skipped


def _process_votings(
    conn, client, settings, run_id, rate_limit,
    chunk_start, chunk_end, items_processed, items_skipped,
) -> tuple[int, int]:
    """Process votings for one date chunk. Returns (items_processed, items_skipped)."""
    try:
        append_import_run_log(
            conn, run_id, f"Processing votings {chunk_start}\u2013{chunk_end}",
        )
        conn.commit()
        sittings, votings = list_votings(
            client, settings.votings_list_path, chunk_start, chunk_end
        )
        # Load sessions from sittings embedded in votings API response
        for sitting in sittings:
            if _check_cancelled(conn, run_id):
                return items_processed, items_skipped
            session = normalize_session(sitting)
            if not session:
                continue
            load_session(conn, session, [])
            conn.commit()
            time.sleep(rate_limit)
        time.sleep(rate_limit)
        for detail in iter_voting_details(
            client, settings.voting_detail_path_template, votings
        ):
            if _check_cancelled(conn, run_id):
                return items_processed, items_skipped
            vote = normalize_vote(detail)
            if not vote:
                continue
            vote["policy_area"] = resolve_policy_area(
                vote.get("subject"), vote.get("title"), vote.get("vote_type")
            )
            casts = extract_vote_casts(detail)
            casts_sorted = sorted(
                casts, key=lambda entry: (entry.get("person") or {}).get("id", "")
            )
            content_hash = stable_hash({"vote": vote, "casts": casts_sorted})
            existing_hash = get_item_hash(conn, "vote", vote["id"])
            if existing_hash == content_hash:
                items_skipped += 1
                update_import_run_counts(conn, run_id, items_processed, items_skipped)
                conn.commit()
                continue
            load_vote(conn, vote, casts_sorted)
            upsert_item_hash(conn, "vote", vote["id"], content_hash)
            items_processed += 1
            update_import_run_counts(conn, run_id, items_processed, items_skipped)
            conn.commit()
            time.sleep(rate_limit)
    except Exception as e:
        logger.warning(
            "Votings ingest skipped for %s\u2013%s: %s",
            chunk_start, chunk_end, e, exc_info=True,
        )
    return items_processed, items_skipped


# ---------------------------------------------------------------------------
# CLI entry point (unchanged)
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Riigikogu ETL")
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument("--step-days", type=int, default=7)
    parser.add_argument("--only-votings", action="store_true")
    parser.add_argument("--only-sittings", action="store_true")
    parser.add_argument("--init-db", action="store_true")
    parser.add_argument(
        "--sync-usergroups", action="store_true",
        help="Sync factions and membership from /api/usergroups (FRAKTSIOON)",
    )
    args = parser.parse_args()

    # CLI path: create the run record ourselves (no API handler)
    settings = load_settings()
    with connect_db(settings.database_url) as conn:
        run_id = create_import_run(
            conn,
            start_date=args.start_date,
            end_date=args.end_date,
            step_days=args.step_days,
            only_votings=args.only_votings,
            only_sittings=args.only_sittings,
            status="queued",
        )
        conn.commit()
    request_cancel(run_id)
    run_etl(
        run_id=run_id,
        start_date=args.start_date,
        end_date=args.end_date,
        step_days=args.step_days,
        only_votings=args.only_votings,
        only_sittings=args.only_sittings,
        init_db=args.init_db,
        sync_usergroups=args.sync_usergroups,
    )


if __name__ == "__main__":
    main()
