# Agent guide

This repository provides Python MCP tools for web search, remote Crawl4AI content extraction, local time, and an optional desktop Chrome bridge. Read [README.md](README.md) for setup and [docs/architecture.md](docs/architecture.md) for implementation details and tool contracts.

## Working in this repository

- Run commands from the repository root. Tool discovery and SQLite storage depend on the working directory.
- Use Python 3.12+ and the dependencies in `pyproject.toml` / `uv.lock`. Install with `uv sync --locked`.
- Put tests in `tests/`. Keep task notes and other agent metadata in `.claude/` as requested by the existing project guidance. This file and `docs/` are maintained project documentation.
- Never copy `.env` values or tokens into documentation, logs, tests, or commits. The Python entry points do not load `.env` automatically.
- Preserve unrelated working-tree changes and local runtime data. `data/quarantine.db` contains persistent search state, not source code.
- Do not run deployment scripts as validation: `bin/push_to_hub.sh` publishes images, and `bin/sync_to_nas.sh` uses `rsync --delete` against a NAS.
- Source code takes precedence over historical descriptions in `logic.md` or old comments. Update the maintained documentation when behavior changes.

## Architecture landmarks

| Area | Main files |
| --- | --- |
| HTTP composition, CORS, optional Chrome | `server.py` |
| Time-only stdio composition | `server_stdio.py` |
| Search API, validation, result aggregation | `tools/search/searxng/server.py` |
| Active backend registry | `tools/search/searxng/registry.py` |
| Instance selection, HTTP fallback, parsing, cache | `tools/search/modules/searx_space/` |
| Crawl API and lifespan | `tools/crawler/crawl4ai/server.py` |
| Crawl validation, configuration, deadlines | `tools/crawler/crawl4ai/client.py` |
| Remote browser cleanup fallback | `tools/crawler/crawl4ai/cleanup.py` |
| Shared HTTP clients, telemetry, optional proxy | `tools/common/` |
| Engine metadata and crawl defaults | `tools/search/constants.py`, `tools/crawler/constants.py` |

## Invariants to preserve

- Keep viewport rotation and Windows/Linux user-agent variation. Fixed viewports caused operational bans. Keep profiles bounded so matching configurations can reuse remote browsers.
- Retain local browser cleanup: the remote janitor has missed browsers in production. Only kill browsers reported as `killable`.
- Keep the overall crawl deadline around queue admission, DNS validation, and remote I/O. Preserve cancellation propagation and semaphore release.
- Validate crawl targets before sending remote requests. Preserve the exact-origin exception for the configured local SearXNG service; do not broaden it to arbitrary private networks.
- Remote Crawl4AI rejects client-controlled browser headers. Clear SDK-generated headers; do not introduce unsupported serialized configuration fields.
- `session_id` is compatibility-only, not browser session persistence.
- Optional Chrome discovery failures must not block local tool discovery. Preserve cooldown and bounded discovery timeout.
- Close shared HTTP and browser-impersonating sessions during shutdown.

## Validation

Focused offline suite:

```sh
.venv/bin/python -m pytest tests/test_fastmcp_smoke.py tests/tools/common/test_optional_mcp.py tests/tools/crawler/crawl4ai/test_client.py tests/tools/crawler/crawl4ai/test_cleanup.py -k 'not integration'
```

Search tests contact real services. Crawler integration tests require the remote service and token; the cleanup integration test can kill remote browsers. Do not treat the whole suite as an isolated unit suite. See README for opt-in live checks.

When extending tools, register them on a module-level `mcp`, verify actual tool discovery, and update the tool table. A new search backend also needs a `SearchEngine` implementation and a registry entry; an engine metadata entry alone does not register a backend. Keep transport configuration in the entry point and domain behavior in the relevant module.
