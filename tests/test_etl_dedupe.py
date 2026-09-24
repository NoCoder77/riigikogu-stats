"""Tests for ETL deduplication: skip load when content hash unchanged."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from riigikogu_stats.etl import _run_etl_inner
from riigikogu_stats.hashing import stable_hash
from riigikogu_stats.transform.normalize import extract_vote_casts, normalize_vote


def test_etl_skips_vote_when_hash_unchanged() -> None:
    """When get_item_hash returns the same hash we compute, load_vote is not called."""
    # Minimal vote detail that normalizes to a vote with id "v1"
    detail = {
        "uuid": "vote-uuid-dedupe-test",
        "session": {"uuid": "session-1"},
        "relatedDraft": {"title": "Draft title"},
        "voters": [],
    }
    vote = normalize_vote(detail)
    assert vote is not None
    vote["policy_area"] = "Other"
    casts = extract_vote_casts(detail)
    casts_sorted = sorted(casts, key=lambda e: (e.get("person") or {}).get("id", ""))
    content_hash = stable_hash({"vote": vote, "casts": casts_sorted})

    fake_conn = MagicMock()
    load_vote_calls: list = []

    def track_load_vote(conn, v, c):
        load_vote_calls.append((v["id"],))

    def get_item_hash_side_effect(conn, entity_type, entity_id):
        if entity_type == "vote" and entity_id == vote["id"]:
            return content_hash
        return None

    with (
        patch("riigikogu_stats.etl.load_settings") as mock_settings,
        patch("riigikogu_stats.etl.connect_db", return_value=fake_conn),
        patch("riigikogu_stats.etl.list_votings", return_value=([], [{"uuid": detail["uuid"]}])),
        patch(
            "riigikogu_stats.etl.iter_voting_details",
            return_value=iter([detail]),
        ),
        patch("riigikogu_stats.etl.get_item_hash", side_effect=get_item_hash_side_effect),
        patch("riigikogu_stats.etl.load_vote", side_effect=track_load_vote),
        patch("riigikogu_stats.etl.upsert_item_hash"),
        patch("riigikogu_stats.etl.update_import_run_counts"),
        patch("riigikogu_stats.etl.finish_import_run"),
        patch("riigikogu_stats.etl.append_import_run_log"),
        patch("riigikogu_stats.etl.get_voting_calendar", return_value=[]),
    ):
        mock_settings.return_value = MagicMock(
            database_url="postgresql://localhost/test",
            base_url="https://api.example.com",
            language="et",
            request_timeout_seconds=30,
            rate_limit_seconds=0,
            votings_list_path="/api/votings",
            voting_detail_path_template="/api/votings/{uuid}",
            sittings_list_path="/api/sittings",
            sitting_detail_path_template="/api/sittings/{uuid}",
            usergroups_list_path="/api/usergroups",
            usergroup_detail_path_template="/api/usergroups/{uuid}",
            votings_calendar_path="/api/votings/calendar",
        )
        _run_etl_inner(
            run_id=1,
            start_date=date(2013, 1, 1),
            end_date=date(2013, 1, 7),
            step_days=7,
            only_votings=True,
            only_sittings=False,
            init_db=False,
            sync_usergroups=False,
        )

    assert len(load_vote_calls) == 0, "load_vote should not be called when hash matches"
