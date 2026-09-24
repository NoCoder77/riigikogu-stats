from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Retry 429 (Too Many Requests) with backoff so Riigikogu API rate limits don't fail imports
_MAX_RETRIES = 4
_429_BACKOFF_SECONDS = 10
_NETWORK_BACKOFF_SECONDS = 3


@dataclass
class ApiClient:
    base_url: str
    language: str
    timeout_seconds: int

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url.rstrip('/')}{path}"
        query = {"lang": self.language}
        if params:
            query.update(params)
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = requests.get(url, params=query, timeout=self.timeout_seconds)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    logger.warning(
                        "Network error on %s (attempt %d/%d): %s",
                        path, attempt + 1, _MAX_RETRIES, exc,
                    )
                    time.sleep(_NETWORK_BACKOFF_SECONDS)
                    continue
                raise
            if response.status_code == 429 and attempt < _MAX_RETRIES - 1:
                logger.warning(
                    "Rate limited on %s (attempt %d/%d), waiting %ds",
                    path, attempt + 1, _MAX_RETRIES, _429_BACKOFF_SECONDS,
                )
                time.sleep(_429_BACKOFF_SECONDS)
                continue
            response.raise_for_status()
            return response.json()
        # All retries exhausted
        if last_exc is not None:
            raise last_exc
        response.raise_for_status()
        return response.json()
