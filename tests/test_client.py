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
# Geospatial — as_geo
# ---------------------------------------------------------------------------

GEO_RECORDS = [
    {"address_id": 1, "full_address": "1 Main Rd", "geometry_wkt": "POINT (174.78 -41.28)"},
    {"address_id": 2, "full_address": "2 Main Rd", "geometry_wkt": "POINT (174.79 -41.29)"},
]


@resp_lib.activate
def test_get_auto_converts_to_geodataframe(client):
    """When geometry_wkt is present and geopandas is importable, return a GeoDataFrame."""
    pytest.importorskip("geopandas")
    import geopandas as gpd

    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_addresses/data", json={"data": GEO_RECORDS})
    df = client.get("nz_addresses")
    assert isinstance(df, gpd.GeoDataFrame)
    assert "geometry" in df.columns
    assert "geometry_wkt" not in df.columns
    assert df.crs.to_epsg() == 4326
    assert df.geometry.iloc[0].x == pytest.approx(174.78)


@resp_lib.activate
def test_get_as_geo_false_keeps_wkt(client):
    """as_geo=False returns the plain DataFrame with the WKT string column."""
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_addresses/data", json={"data": GEO_RECORDS})
    df = client.get("nz_addresses", as_geo=False)
    assert isinstance(df, VSeries)
    assert "geometry_wkt" in df.columns
    assert df["geometry_wkt"].iloc[0].startswith("POINT")


@resp_lib.activate
def test_get_no_geometry_column_returns_vseries(client):
    """Datasets without a geometry_wkt column still return a VSeries even with as_geo=None."""
    resp_lib.add(resp_lib.GET, f"{BASE}/v1/series/nz_cpi/data", json={"data": RECORDS})
    df = client.get("nz_cpi")
    assert isinstance(df, VSeries)
    # Should not be a GeoDataFrame even if geopandas is installed
    try:
        import geopandas as gpd
        assert not isinstance(df, gpd.GeoDataFrame)
    except ImportError:
        pass


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
