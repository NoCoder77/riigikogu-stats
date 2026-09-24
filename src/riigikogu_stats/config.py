from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(key: str, default: int) -> int:
    """Read an integer from an env var, falling back to *default* on ValueError."""
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _float_env(key: str, default: float) -> float:
    """Read a float from an env var, falling back to *default* on ValueError."""
    try:
        return float(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class Settings:
    base_url: str
    language: str
    database_url: str
    request_timeout_seconds: int
    rate_limit_seconds: float
    votings_list_path: str
    voting_detail_path_template: str
    sittings_list_path: str
    sitting_detail_path_template: str
    usergroups_list_path: str
    usergroup_detail_path_template: str
    votings_calendar_path: str


def load_settings() -> Settings:
    return Settings(
        base_url=os.getenv("RIIGIKOGU_API_BASE_URL", "https://api.riigikogu.ee"),
        language=os.getenv("RIIGIKOGU_API_LANG", "et"),
        database_url=os.environ.get("DATABASE_URL", "sqlite:///riigikogu.db"),
        request_timeout_seconds=_int_env("RIIGIKOGU_TIMEOUT_SECONDS", 30),
        rate_limit_seconds=_float_env("RIIGIKOGU_RATE_LIMIT_SECONDS", 0.5),
        votings_list_path=os.getenv("RIIGIKOGU_VOTINGS_LIST_PATH", "/api/votings"),
        voting_detail_path_template=os.getenv(
            "RIIGIKOGU_VOTING_DETAIL_PATH_TEMPLATE", "/api/votings/{uuid}"
        ),
        sittings_list_path=os.getenv("RIIGIKOGU_SITTINGS_LIST_PATH", "/api/sittings"),
        sitting_detail_path_template=os.getenv(
            "RIIGIKOGU_SITTING_DETAIL_PATH_TEMPLATE", "/api/sittings/{uuid}"
        ),
        usergroups_list_path=os.getenv("RIIGIKOGU_USERGROUPS_LIST_PATH", "/api/usergroups"),
        usergroup_detail_path_template=os.getenv(
            "RIIGIKOGU_USERGROUP_DETAIL_PATH_TEMPLATE", "/api/usergroups/{uuid}"
        ),
        votings_calendar_path=os.getenv(
            "RIIGIKOGU_VOTINGS_CALENDAR_PATH", "/api/votings/calendar"
        ),
    )
