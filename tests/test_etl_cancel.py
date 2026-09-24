"""Regression: cancelled import must not be marked success after sub-step mid-cancel."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from riigikogu_stats import etl


def test_cancelled_during_sittings_does_not_finish_success() -> None:
    fake_conn = MagicMock()
    fake_conn.__enter__ = MagicMock(return_value=fake_conn)
    fake_conn.__exit__ = MagicMock(return_value=False)
    finish_calls: list[tuple] = []

    def track_finish(conn, run_id, status, error):
        finish_calls.append((run_id, status, error))

    def process_sittings_cancel(*args, **kwargs):
        # Simulate mid-chunk cancel: mark failed and leave cancel flag set
        run_id = args[3]
        with etl._state_lock:
            etl._cancel_run_ids.add(run_id)
        etl.finish_import_run(fake_conn, run_id, "failed", "Cancelled by new import")
        return (0, 0)

    with (
        patch("riigikogu_stats.etl.load_settings") as mock_settings,
        patch("riigikogu_stats.etl.connect_db", return_value=fake_conn),
        patch("riigikogu_stats.etl._process_sittings", side_effect=process_sittings_cancel),
        patch("riigikogu_stats.etl._process_votings") as mock_votings,
        patch("riigikogu_stats.etl.finish_import_run", side_effect=track_finish),
        patch("riigikogu_stats.etl.append_import_run_log"),
        patch("riigikogu_stats.etl.get_voting_calendar", return_value=[]),
        patch("riigikogu_stats.etl.merge_memberships", return_value=0),
    ):
        mock_settings.return_value = MagicMock(
            database_url="sqlite:///:memory:",
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
        with etl._state_lock:
            etl._cancel_run_ids.clear()
        etl._run_etl_inner(
            run_id=42,
            start_date=date(2013, 1, 1),
            end_date=date(2013, 1, 7),
            step_days=7,
            only_votings=False,
            only_sittings=False,
            init_db=False,
            sync_usergroups=False,
        )

    mock_votings.assert_not_called()
    assert any(c[0] == 42 and c[1] == "failed" for c in finish_calls)
    assert not any(c[0] == 42 and c[1] == "success" for c in finish_calls)
