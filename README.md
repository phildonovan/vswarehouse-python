# vswarehouse

Python client for the [vs-warehouse](https://api.virtus-solutions.io) statistical data API — macro and economic time series for New Zealand, Australia, and more.

## Installation

```bash
pip install vswarehouse
```

## Quick start

```python
from vswarehouse import Client

client = Client("vs_your_api_key")

# List all available series
series = client.list()

# Get metadata for a series
meta = client.info("nz_cpi")

# Fetch data as a pandas DataFrame
df = client.get("nz_cpi", start="2020-01-01")
print(df.head())
```

## Authentication

Pass your key directly or set the `VS_API_KEY` environment variable:

```bash
export VS_API_KEY=vs_your_api_key
```

```python
client = Client()  # reads VS_API_KEY automatically
```

Get a free API key at [api.virtus-solutions.io](https://api.virtus-solutions.io).

## API reference

### `Client(api_key, base_url)`

| Method | Returns | Description |
|---|---|---|
| `list()` | `list[dict]` | All available series with metadata |
| `info(name)` | `dict` | Metadata for a single series |
| `get(name, start, end, format)` | `DataFrame` | Time-series data |

### `get()` parameters

| Param | Type | Description |
|---|---|---|
| `name` | `str` | Series identifier, e.g. `"nz_cpi"` |
| `start` | `str` | ISO date lower bound, e.g. `"2020-01-01"` |
| `end` | `str` | ISO date upper bound |
| `format` | `str` | `"json"` (default) or `"csv"` |

## Exceptions

| Exception | When |
|---|---|
| `AuthenticationError` | Invalid or inactive API key |
| `RateLimitError` | Daily free-tier limit reached |
| `NotFoundError` | Series not found |
| `APIError` | Other HTTP errors |

## License

MIT
