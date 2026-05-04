import os
from typing import Optional

import pandas as pd
import requests

from .exceptions import APIError, AuthenticationError, NotFoundError, RateLimitError

BASE_URL = "https://api.virtus-solutions.io"


class Client:
    """Client for the vs-warehouse statistical data API.

    Args:
        api_key: Your vs_... API key. Falls back to the VS_API_KEY env var.
        base_url: Override the API base URL (useful for testing).
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = BASE_URL):
        self._key = api_key or os.getenv("VS_API_KEY") or ""
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({"X-API-Key": self._key})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list(self) -> list[dict]:
        """Return metadata for all available series."""
        data = self._get("/v1/series")
        return data.get("series", data)

    def info(self, name: str) -> dict:
        """Return metadata for a single series."""
        return self._get(f"/v1/series/{name}")

    def get(
        self,
        name: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        format: str = "json",
    ) -> pd.DataFrame:
        """Fetch time-series data as a pandas DataFrame.

        Args:
            name:   Series identifier, e.g. ``"nz_cpi"``.
            start:  ISO date lower bound, e.g. ``"2020-01-01"``.
            end:    ISO date upper bound, e.g. ``"2024-12-31"``.
            format: ``"json"`` (default) or ``"csv"``.

        Returns:
            DataFrame with columns: ``date``, ``period``, ``value``, and
            any extra dimension columns.
        """
        params: dict = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        if format == "csv":
            resp = self._raw_get(f"/v1/series/{name}/data", params={"format": "csv", **params})
            from io import StringIO
            return pd.read_csv(StringIO(resp.text))

        data = self._get(f"/v1/series/{name}/data", params=params)
        records = data.get("data", data)
        df = pd.DataFrame(records)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        resp = self._raw_get(path, params=params)
        return resp.json()

    def _raw_get(self, path: str, params: Optional[dict] = None) -> requests.Response:
        url = f"{self._base}{path}"
        resp = self._session.get(url, params=params)
        self._raise_for_status(resp)
        return resp

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if resp.status_code == 200:
            return
        if resp.status_code == 401:
            raise AuthenticationError("Invalid or missing API key.")
        if resp.status_code == 403:
            raise AuthenticationError("API key is inactive.")
        if resp.status_code == 429:
            raise RateLimitError("Daily request limit reached. Upgrade to Pro for unlimited access.")
        if resp.status_code == 404:
            try:
                detail = resp.json().get("detail", "Not found.")
            except Exception:
                detail = "Not found."
            raise NotFoundError(detail)
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise APIError(resp.status_code, detail)
