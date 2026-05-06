from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import requests

from .exceptions import APIError, AuthenticationError, NotFoundError, RateLimitError
from .series import VSeries

BASE_URL = "https://api.virtus-solutions.io"


class Client:
    """Client for the vs-warehouse statistical data API.

    Args:
        api_key:  Your ``vs_...`` API key. Falls back to the ``VS_API_KEY``
                  environment variable.
        base_url: Override the API base URL (useful for testing).
        cache:    Cache responses in memory for the lifetime of the client.
                  Useful in notebooks to avoid re-fetching on re-runs.

    Examples::

        from vswarehouse import Client
        client = Client("vs_your_key")

        # Source-specific helpers
        df = client.statsnz("nz_cpi", start="2020-01-01")
        df = client.oecd("nz_gdp")

        # Generic
        df = client.get("nz_cpi")

        # Discovery
        all_series  = client.list()
        nz_series   = client.list("Stats NZ")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = BASE_URL,
        cache: bool = False,
    ):
        self._key   = api_key or os.getenv("VS_API_KEY") or ""
        self._base  = base_url.rstrip("/")
        self._cache: dict | None = {} if cache else None
        self._session = requests.Session()
        self._session.headers.update({"X-API-Key": self._key})

    def __repr__(self) -> str:
        masked = self._key[:8] + "..." if len(self._key) > 8 else self._key
        cache  = " cache=on" if self._cache is not None else ""
        return f"<vswarehouse.Client key={masked!r}{cache}>"

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def list(self, source: Optional[str] = None) -> list[dict]:
        """Return metadata for all available series.

        Args:
            source: Optional filter, e.g. ``"Stats NZ"``, ``"OECD"``.
        """
        data   = self._get("/v1/series")
        series = data.get("series", data) if isinstance(data, dict) else data
        if source:
            series = [s for s in series if s.get("source") == source]
        return series

    def info(self, name: str) -> dict:
        """Return metadata for a single series."""
        return self._get(f"/v1/series/{name}")

    # ------------------------------------------------------------------
    # Source-specific helpers
    # ------------------------------------------------------------------

    def statsnz(self, name: str, **kwargs) -> VSeries:
        """Fetch a Stats NZ series."""
        return self._get_source(name, "Stats NZ", **kwargs)

    def oecd(self, name: str, **kwargs) -> VSeries:
        """Fetch an OECD series."""
        return self._get_source(name, "OECD", **kwargs)

    def rbnz(self, name: str, **kwargs) -> VSeries:
        """Fetch an RBNZ series."""
        return self._get_source(name, "RBNZ", **kwargs)

    def treasury(self, name: str, **kwargs) -> VSeries:
        """Fetch a NZ Treasury series."""
        return self._get_source(name, "NZ Treasury", **kwargs)

    def linz(self, name: str, **kwargs) -> VSeries:
        """Fetch a LINZ series."""
        return self._get_source(name, "LINZ", **kwargs)

    def _get_source(self, name: str, source: str, **kwargs) -> VSeries:
        df = self.get(name, **kwargs)
        df.vs_source = source
        return df

    # ------------------------------------------------------------------
    # Core data fetch
    # ------------------------------------------------------------------

    def get(
        self,
        name: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        format: str = "json",
        engine: str = "pandas",
    ) -> VSeries:
        """Fetch time-series data.

        Args:
            name:   Series identifier, e.g. ``"nz_cpi"``.
            start:  ISO date lower bound, e.g. ``"2020-01-01"``.
            end:    ISO date upper bound, e.g. ``"2024-12-31"``.
            format: ``"json"`` (default) or ``"csv"``.
            engine: ``"pandas"`` (default) or ``"polars"``.

        Returns:
            A :class:`VSeries` (pandas DataFrame subclass), or a polars
            DataFrame when ``engine="polars"``.
        """
        params: dict = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        cache_key = f"{name}:{start}:{end}:{format}"
        if self._cache is not None and cache_key in self._cache:
            return self._cache[cache_key]

        if format == "csv":
            from io import StringIO
            resp = self._raw_get(f"/v1/series/{name}/data", params={"format": "csv", **params})
            df   = pd.read_csv(StringIO(resp.text))
        else:
            data    = self._get(f"/v1/series/{name}/data", params=params)
            records = data.get("data", data) if isinstance(data, dict) else data
            df      = pd.DataFrame(records)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])

        result = VSeries(df)
        result.vs_name   = name
        result.vs_source = ""

        if engine == "polars":
            try:
                import polars as pl
                return pl.from_pandas(result)
            except ImportError:
                raise ImportError(
                    "polars is required for engine='polars'. "
                    "Install with: pip install polars"
                )

        if self._cache is not None:
            self._cache[cache_key] = result

        return result

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        return self._raw_get(path, params=params).json()

    def _raw_get(self, path: str, params: Optional[dict] = None) -> requests.Response:
        url  = f"{self._base}{path}"
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
            raise RateLimitError(
                "Daily request limit reached. Upgrade to Pro for unlimited access."
            )
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
