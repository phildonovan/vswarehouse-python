import pandas as pd
import pytest
import responses as resp_lib

from vswarehouse import Client, VSeries
from vswarehouse.exceptions import AuthenticationError, NotFoundError, RateLimitError

BASE = "https://api.virtus-solutions.io"

RECORDS = [
    {"date": "2023-01-01", "period": "2023Q1", "value": 100.0},
    {"date": "2023-04-01", "period": "2023Q2", "value": 101.5},
]

SERIES_LIST = [
    {"name": "nz_cpi",  "title": "NZ CPI",  "source": "Stats NZ", "namespace": "statsnz"},
    {"name": "nz_gdp",  "title": "NZ GDP",  "source": "OECD",     "namespace": "oecd"},
    {"name": "nz_rbnz", "title": "NZ RBNZ", "source": "RBNZ",     "namespace": "rbnz"},
]


@pytest.fixture()
def client():
    return Client("vs_testkey123", base_url=BASE)


@pytest.fixture()
def cached_client():
    return Client("vs_testkey123", base_url=BASE, cache=True)


# ---------------------------------------------------------------------------
# Client repr
# ---------------------------------------------------------------------------

def test_client_repr(client):
    assert "vs_testk" in repr(client)
    assert "..." in repr(client)


def test_cached_client_repr(cached_client):
    assert "cache=on" in repr(cached_client)


# ---------------------------------------------------------------------------
# list()
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_list_returns_all_series(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series", json={"series": SERIES_LIST})
    result = client.list()
    assert len(result) == 3


@resp_lib.activate
def test_list_filters_by_source(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series", json={"series": SERIES_LIST})
    result = client.list("Stats NZ")
    assert len(result) == 1
    assert result[0]["name"] == "nz_cpi"


@resp_lib.activate
def test_list_unknown_source_returns_empty(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series", json={"series": SERIES_LIST})
    result = client.list("Unknown")
    assert result == []


# ---------------------------------------------------------------------------
# info()
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_info_returns_meta(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi",
                 json={"name": "nz_cpi", "title": "NZ Consumer Price Index"})
    meta = client.info("nz_cpi")
    assert meta["name"] == "nz_cpi"


@resp_lib.activate
def test_info_not_found_raises(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/bad", json={"detail": "Not found."}, status=404)
    with pytest.raises(NotFoundError):
        client.info("bad")


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_get_returns_vs_series(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data", json={"data": RECORDS})
    df = client.get("nz_cpi")
    assert isinstance(df, VSeries)
    assert len(df) == 2
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert df.vs_name == "nz_cpi"


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
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data",
                 body=csv_body, content_type="text/csv")
    df = client.get("nz_cpi", format="csv")
    assert isinstance(df, pd.DataFrame)
    assert "value" in df.columns


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_cache_avoids_second_request(cached_client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data", json={"data": RECORDS})
    cached_client.get("nz_cpi")
    cached_client.get("nz_cpi")
    assert len(resp_lib.calls) == 1


# ---------------------------------------------------------------------------
# Source-specific methods
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_statsnz_sets_source(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data", json={"data": RECORDS})
    df = client.statsnz("nz_cpi")
    assert isinstance(df, VSeries)
    assert df.vs_source == "Stats NZ"


@resp_lib.activate
def test_oecd_sets_source(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_gdp/data", json={"data": RECORDS})
    df = client.oecd("nz_gdp")
    assert df.vs_source == "OECD"


@resp_lib.activate
def test_rbnz_sets_source(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_rbnz/data", json={"data": RECORDS})
    df = client.rbnz("nz_rbnz")
    assert df.vs_source == "RBNZ"


@resp_lib.activate
def test_treasury_sets_source(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/fiscal/data", json={"data": RECORDS})
    df = client.treasury("fiscal")
    assert df.vs_source == "NZ Treasury"


# ---------------------------------------------------------------------------
# VSeries repr
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_vs_series_repr_includes_name_and_source(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data", json={"data": RECORDS})
    df = client.statsnz("nz_cpi")
    r = repr(df)
    assert "nz_cpi" in r
    assert "Stats NZ" in r
    assert "2 rows" in r


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_unauthorised_raises_auth_error(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data",
                 json={"detail": "Unauthorised"}, status=401)
    with pytest.raises(AuthenticationError):
        client.get("nz_cpi")


@resp_lib.activate
def test_rate_limit_raises(client):
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data",
                 json={"detail": "Daily limit"}, status=429)
    with pytest.raises(RateLimitError):
        client.get("nz_cpi")


# ---------------------------------------------------------------------------
# Env var fallback
# ---------------------------------------------------------------------------

def test_key_from_env(monkeypatch):
    monkeypatch.setenv("VS_API_KEY", "vs_from_env")
    c = Client()
    assert c._key == "vs_from_env"
