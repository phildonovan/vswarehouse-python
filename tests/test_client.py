import pandas as pd
import pytest
import responses as resp_lib

from vswarehouse import Client
from vswarehouse.exceptions import AuthenticationError, NotFoundError, RateLimitError

BASE = "https://api.virtus-solutions.io"


@pytest.fixture()
def client():
    return Client("vs_testkey123", base_url=BASE)


# ---------------------------------------------------------------------------
# list()
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_list_returns_series(client):
    resp_lib.add(
        resp_lib.GET,
        f"{BASE}/v1/series",
        json={"series": [{"name": "nz_cpi", "title": "NZ CPI"}]},
    )
    result = client.list()
    assert len(result) == 1
    assert result[0]["name"] == "nz_cpi"


# ---------------------------------------------------------------------------
# info()
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_info_returns_meta(client):
    resp_lib.add(
        resp_lib.GET,
        f"{BASE}/v1/series/nz_cpi",
        json={"name": "nz_cpi", "title": "NZ Consumer Price Index"},
    )
    meta = client.info("nz_cpi")
    assert meta["name"] == "nz_cpi"


@resp_lib.activate
def test_info_not_found_raises(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/bad_series", json={"detail": "Not found."}, status=404)
    with pytest.raises(NotFoundError):
        client.info("bad_series")


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

RECORDS = [
    {"date": "2023-01-01", "period": "2023Q1", "value": 100.0, "dimensions": ""},
    {"date": "2023-04-01", "period": "2023Q2", "value": 101.5, "dimensions": ""},
]


@resp_lib.activate
def test_get_returns_dataframe(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data", json={"data": RECORDS})
    df = client.get("nz_cpi")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ["date", "period", "value", "dimensions"]
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


@resp_lib.activate
def test_get_passes_date_params(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data", json={"data": RECORDS})
    client.get("nz_cpi", start="2023-01-01", end="2023-06-30")
    req = resp_lib.calls[0].request
    assert "start=2023-01-01" in req.url
    assert "end=2023-06-30" in req.url


@resp_lib.activate
def test_get_csv_returns_dataframe(client):
    csv_body = "date,period,value\n2023-01-01,2023Q1,100.0\n"
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data", body=csv_body, content_type="text/csv")
    df = client.get("nz_cpi", format="csv")
    assert isinstance(df, pd.DataFrame)
    assert "value" in df.columns


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_unauthorised_raises_auth_error(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data", json={"detail": "Unauthorised"}, status=401)
    with pytest.raises(AuthenticationError):
        client.get("nz_cpi")


@resp_lib.activate
def test_rate_limit_raises(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data", json={"detail": "Daily limit"}, status=429)
    with pytest.raises(RateLimitError):
        client.get("nz_cpi")


# ---------------------------------------------------------------------------
# Env var fallback
# ---------------------------------------------------------------------------

def test_key_from_env(monkeypatch):
    monkeypatch.setenv("VS_API_KEY", "vs_from_env")
    c = Client()
    assert c._key == "vs_from_env"
