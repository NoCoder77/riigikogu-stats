"""Resolve policy area from vote subject/title/vote_type using keyword rules.

Raw vote payload inspection: no standard policy/committee field was identified
in the Riigikogu API response; this module uses a configurable keyword-based
mapping. If the API later provides an official taxonomy, it can replace or
complement this logic.
"""
from __future__ import annotations

import json
from pathlib import Path


def _default_rules_path() -> Path:
    return Path(__file__).resolve().parent / "config" / "policy_area_rules.json"


_rules_cache: dict | None = None


def load_rules(path: Path | None = None) -> dict:
    """Load policy area rules from JSON. Cached for repeated calls."""
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache
    p = path or _default_rules_path()
    if not p.is_file():
        _rules_cache = {"areas": {}}
        return _rules_cache
    with open(p, encoding="utf-8") as f:
        _rules_cache = json.load(f)
    return _rules_cache


def resolve_policy_area(
    subject: str | None,
    title: str | None,
    vote_type: str | None,
    rules_path: Path | None = None,
) -> str:
    """Return policy area name for a vote based on keyword matching.

    Concatenates subject, title, and vote_type (case-insensitive). First area
    whose keyword appears in that text wins. If none match, returns "Other".
    """
    text = " ".join(
        (s or "") for s in (subject, title, vote_type)
    ).lower()
    rules = load_rules(rules_path)
    areas = rules.get("areas") or {}
    for area_name, config in areas.items():
        keywords = config.get("keywords") if isinstance(config, dict) else []
        for kw in keywords:
            if kw and kw.lower() in text:
                return area_name
    return "Other"
