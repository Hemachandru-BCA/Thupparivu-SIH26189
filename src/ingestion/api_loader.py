"""
api_loader.py
--------------
Ingestion module for pulling CriminalAnalysis AI datasets from a remote
REST API instead of local CSVs (e.g. a live case-management system).

Uses `requests` if available; otherwise falls back to the standard-library
`urllib` so the module has zero hard dependencies.
"""

import json
import time
from typing import Dict, List, Optional
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover
    _HAS_REQUESTS = False


class ApiLoaderError(Exception):
    pass


class ApiLoader:
    """
    Generic paginated REST API loader.

    Example:
        loader = ApiLoader(base_url="https://intel.example.com/api/v1",
                            api_key="secret-token")
        persons = loader.fetch_all("persons")
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 15,
        max_retries: int = 3,
        page_size: int = 500,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.page_size = page_size

    def fetch_page(self, endpoint: str, page: int = 1) -> Dict:
        url = f"{self.base_url}/{endpoint}?page={page}&page_size={self.page_size}"
        headers = self._headers()

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if _HAS_REQUESTS:
                    resp = requests.get(url, headers=headers, timeout=self.timeout)
                    resp.raise_for_status()
                    return resp.json()
                else:
                    req = urllib_request.Request(url, headers=headers)
                    with urllib_request.urlopen(req, timeout=self.timeout) as response:
                        return json.loads(response.read().decode("utf-8"))
            except (URLError, HTTPError) as exc:
                last_error = exc
            except Exception as exc:  # requests exceptions, JSON errors, etc.
                last_error = exc

            time.sleep(min(2 ** attempt, 10))  # exponential backoff

        raise ApiLoaderError(
            f"Failed to fetch {url} after {self.max_retries} attempts: {last_error}"
        )

    def fetch_all(self, endpoint: str) -> List[Dict]:
        """
        Fetches every page for an endpoint and concatenates the `results`
        (or `data`) arrays. Assumes a JSON envelope like:
            {"results": [...], "next_page": 2}  # or "next_page": null
        """
        records: List[Dict] = []
        page = 1
        while True:
            payload = self.fetch_page(endpoint, page=page)
            batch = payload.get("results") or payload.get("data") or []
            records.extend(batch)

            next_page = payload.get("next_page")
            if not next_page or not batch:
                break
            page = next_page

        return records

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
