# MCP Servers

A Python/FastMCP service providing SearXNG web search, remote Crawl4AI crawling, local time, and an optional Chrome DevTools MCP proxy.

- [Agent instructions](AGENTS.md)
- [Architecture, tool contracts, and operations](docs/architecture.md)
- [Crawler timing and browser reuse](tools/crawler/crawl4ai/README.md)

## Local setup

Requires Python 3.12+, `uv`, a reachable Crawl4AI server, and its API token for the main HTTP service.

```sh
uv sync --locked
mkdir -p data
export CRAWL4AI_API_TOKEN='<your-token>'
uv run python server.py
```

Run from the repository root. The endpoint is `http://localhost:7000/mcp` using Streamable HTTP. The development launcher binds `0.0.0.0` and enables reload. The code does not load `.env`; supply environment variables through your shell or process manager.

Crawl4AI defaults to `http://192.168.0.188:11235` in `tools/crawler/constants.py`. Local SearXNG defaults to `http://192.168.0.100:8089` in `tools/search/constants.py`. These are source constants, not environment overrides. Search also falls back to public instances discovered through searx.space. The repository does not deploy these external services.

The main service requires the crawler token at startup even for time/search usage. For the separate time-only stdio entry point:

```sh
uv run python server_stdio.py
```

This entry point is not equivalent to the HTTP service. It also prints startup/shutdown messages to stdout; clients requiring strictly protocol-only stdout may need that corrected before using it as a subprocess.

## Configuration

| Setting | Meaning |
| --- | --- |
| `CRAWL4AI_API_TOKEN` | Required by HTTP crawler lifespan; sent as a bearer token to Crawl4AI |
| `CHROME_BRIDGE_URL` | Optional remote MCP URL; enables namespaced Chrome tools |
| `CHROME_BRIDGE_TOKEN` | Required when bridge URL is set; bridge bearer token |
| `RES_PROXY` | Optional proxy used for search retry after HTTP 429 |
| `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT` | Health telemetry endpoint; defaults `192.168.0.100:9000` |
| `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` | Telemetry credentials; code defaults are `user` / `password` |
| `CLICKHOUSE_TABLE` | Existing telemetry table, default `my_data.health_logs` |
| `JINA_API_KEY` | Used by auxiliary DDG/Brave implementations, not the active search backend |
| `CRAWL4AI_LIVE_TESTS=1` | Enables opt-in CTV live crawl test |

The HTTP entry point sets `DANGEROUSLY_OMIT_AUTH=true`, configures no incoming authentication, and allows all CORS origins. Deploy behind the appropriate trusted boundary or add authentication before exposing it outside that boundary. Outgoing service tokens do not authenticate incoming MCP callers.

## Tests

Run the offline suite listed in [AGENTS.md](AGENTS.md). A live content check is available with a configured crawler token:

```sh
CRAWL4AI_LIVE_TESTS=1 .venv/bin/python -m pytest tests/tools/crawler/crawl4ai/test_ctv_live.py -s
```

The CTV test checks a listing and linked article and writes diagnostic artifacts under pytest's temporary directory. `profile_ctv.py` and `profile_ctv_phases.py` in the same directory are manual remote profiling scripts. Search tests under `tests/search/` make live requests and can update persistent quarantine/cache state.

## Containers and deployment

The Dockerfile installs dependencies into `/opt/mcp_venv` and starts `server.py` from `/app`. It does **not** copy application source into the image; `/app` must contain the source at runtime. Dependency installation uses `pyproject.toml`, not `uv.lock`.

The supplied Compose file uses `kkulagin/mcp-servers:latest`, publishes port 7000, and mounts `/mnt/MyPool/myapps/nfs/mcp` as `/app`. Adapt the host mount to your environment. Compose passes the crawler token and optional Chrome settings, but does not pass all variables listed above. A Compose `.env` supplies interpolation values; it does not automatically inject every value into the container.

`bin/push_to_hub.sh` builds and publishes timestamped and `latest` tags. `bin/sync_to_nas.sh` synchronizes source to `/mnt/truenas/nfs/mcp` with deletion enabled, excluding hidden files, runtime data, and deployment files. Review destinations before running either script. Neither script is needed for local tests.
