"""Thin client for the NLB OpenWeb Catalogue API v2.

Responsibilities
----------------
- Hold credentials and build auth headers.
- Wrap every GET request with rate-limit-aware retry logic.
- Expose two clean methods: search_titles() and get_availability().

Rate-limit notes (from experimentation)
----------------------------------------
- The API returns HTTP 429 when you exceed the allowed call rate.
- A REQUEST_DELAY of ~1 s between calls is usually safe.
- On a 429 the client waits RETRY_WAIT seconds and retries up to MAX_RETRIES times.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://openweb.nlb.gov.sg/api/v2/Catalogue"


class NLBClient:
    """Reusable HTTP client for the NLB Catalogue API.

    Parameters
    ----------
    api_key:        Value for the X-Api-Key header.
    app_code:       Value for the X-App-Code header.
    request_delay:  Seconds to sleep between *successful* requests (default 1.0).
    retry_wait:     Seconds to wait after a 429 before retrying (default 5.0).
    max_retries:    Maximum number of retry attempts on 429 (default 3).
    timeout:        HTTP timeout in seconds (default 15).
    """

    def __init__(
        self,
        api_key: str,
        app_code: str,
        request_delay: float = 1.0,
        retry_wait: float = 20.0,
        max_retries: int = 3,
        timeout: int = 15,
    ) -> None:
        self._headers = {
            "X-Api-Key": api_key,
            "X-App-Code": app_code,
        }
        self.request_delay = request_delay
        self.retry_wait = retry_wait
        self.max_retries = max_retries
        self.timeout = timeout

    # ------------------------------------------------------------------ private

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET *endpoint* with retry-on-429 logic.  Returns parsed JSON."""
        url = f"{BASE_URL}/{endpoint}"
        for attempt in range(1, self.max_retries + 1):
            resp = requests.get(url, headers=self._headers, params=params, timeout=self.timeout)
            if resp.status_code == 429:
                logger.warning(
                    "Rate-limited (429) on %s attempt %d/%d — waiting %.0fs",
                    endpoint,
                    attempt,
                    self.max_retries,
                    self.retry_wait,
                )
                time.sleep(self.retry_wait)
                continue
            resp.raise_for_status()
            time.sleep(self.request_delay)   # polite delay after every successful call
            return resp.json()

        raise RuntimeError(
            f"Endpoint {endpoint} returned HTTP 429 after {self.max_retries} retries. "
            "Try increasing retry_wait or request_delay."
        )

    # ------------------------------------------------------------------ public

    def search_titles(
        self,
        title: str,
        author: Optional[str] = None,
        limit: int = 20,
        material_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Call /GetTitles and return the 'titles' list.

        Parameters
        ----------
        title:         Title to search for.
        author:        Optional author filter.
        limit:         Max number of records to return (max 100).
        material_type: NLB material-type code, e.g. 'bks', 'dvd'.
        """
        params: dict[str, Any] = {"Title": title, "Limit": limit}
        if author:
            params["Author"] = author
        if material_type:
            params["MaterialTypes"] = material_type

        data = self._get("GetTitles", params)
        return data.get("titles", [])

    def get_availability(self, brn: int, limit: int = 100) -> list[dict[str, Any]]:
        """Call /GetAvailabilityInfo for *brn* and return the 'items' list."""
        params: dict[str, Any] = {"BRN": brn, "Limit": limit}
        data = self._get("GetAvailabilityInfo", params)
        return data.get("items", [])
