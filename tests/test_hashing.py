from datetime import date, datetime, timezone

from riigikogu_stats.hashing import stable_hash


def test_stable_hash_respects_key_order() -> None:
    payload_a = {"b": 2, "a": 1}
    payload_b = {"a": 1, "b": 2}
    assert stable_hash(payload_a) == stable_hash(payload_b)


def test_stable_hash_handles_dates() -> None:
    payload = {
        "session_date": date(2020, 1, 2),
        "vote_time": datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    }
    digest = stable_hash(payload)
    assert isinstance(digest, str)
    assert len(digest) == 64
