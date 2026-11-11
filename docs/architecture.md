# Architecture and tool reference

This describes the checked-in implementation, rather than an intended future design.

## Composition and lifecycle

```text
MCP client -> server.py: /mcp, Streamable HTTP
  -> FileSystemProvider('./tools', reload=True)
     -> search server -> registry -> SearxSpaceEngine
        -> SQLite cache/quarantine + searx.space discovery
        -> local SearXNG, then public instances
     -> crawl server -> lifespan crawler -> remote Crawl4AI
     -> time tool/resource
  -> mounted tools/browser-mcp/server.py -> optional chrome namespace -> remote authenticated MCP bridge

server_stdio.py -> mounted time server only
```

`server.py` explicitly enters the crawler lifespan, obtains the shared HTTP client, and exposes both in lifespan state. Crawler startup requires a token, opens the Docker SDK client, and starts a cleanup task. Shutdown closes shared HTTP/curl sessions, cancels cleanup, and exits the Docker client context. Crawl tools access `ctx.lifespan_context['crawler']`.

FastMCP is pinned to 4.1.4; Crawl4AI to 0.9.5. Other direct dependencies include httpx, requests, Pydantic, BeautifulSoup, curl-cffi, and clickhouse-driver. The Chrome provider uses `httpx2` supplied through the dependency graph. Preserve SDK compatibility when upgrading: code accesses the Docker client's private HTTP client and `_request` method.

## Public tools and resource

Tool names below are explicit local decorator names. Chrome tools are discovered dynamically; use MCP tool listing to inspect the bridge's actual schemas.

| Name | Inputs and defaults | Output |
| --- | --- | --- |
| `web_search` | `query`; `search_engines=['google','duckduckgo','bing','brave']`; `time_range=None`; `language='en-US'`; `limit=20` | `WebSearchResponse` |
| `web_search_engines` | None | Engine descriptions, categories, `supports_time_range`, supported ranges |
| `web_crawl_url` | `url`; `extract_markdown=True`; `session_id=None` | `CrawlResult` |
| `web_crawl_multiple_urls` | `urls`; `session_id=None` | `CrawlResponse` with ordered results |
| `utils_time` | None | Server-local ISO datetime string, without timezone offset |
| `chrome_bridge_status` | None; exists only with bridge configured | `available`, `retry_after_seconds` |
| `chrome_*` | Bridge-defined | Bridge-defined |

`resource://time` also returns server-local ISO time. `Context` parameters in Python tool functions are injected by FastMCP, not client inputs.

`SearchResult` contains `title`, `url`, `content`, `score`, and `engine`. `WebSearchResponse` contains `query`, `result_count`, `results`, `engines_used`, and optional `search_time`, `fallback`, `error`, `instruction`. The normal search path does not calculate search time or mark fallback usage. `CrawlResult` contains `url`, `content`, `success`, and optional `error`; `CrawlResponse` wraps a `results` list. Crawl failures normally return empty content with `success=false`.

Example MCP argument payloads:

```json
{"query":"Python asynchronous context managers", "search_engines":[], "limit":10}
```

```json
{"url":"https://example.com", "extract_markdown":true}
```

Discover engine capabilities before targeted or time-filtered searches. Use `day`, `week`, `month`, or `year`; explicitly supplying an empty engine list with a time filter is rejected. Unsupported time-filter engines are removed, and a request with no remaining engines fails validation. Unknown engines also fail validation. Some error messages still mention obsolete tool/argument names; the table above is authoritative.

For Chrome interactions, list/select pages first, take a snapshot, and use returned element UIDs for interactions. Check bridge status after connection failures.

## Search implementation

`ENGINE_REGISTRY` currently contains only `searx_space`. Engine names such as Google and Bing are SearXNG upstream selections, distinct from Python backend registry keys. The outer search server runs all registered backends with `asyncio.gather(return_exceptions=True)`, deduplicates exact URLs, sorts descending by score, and applies the requested limit. Backend failures are logged; empty results alone are not proof of a successful search.

The SearxSpace backend:

1. Parses bang shortcuts using `shortcuts.py`, then merges explicit engine parameters without duplicates. With neither, selects Google, Bing, DuckDuckGo, Brave in that order.
2. Refreshes instance metadata if needed and selects up to 50 public candidates.
3. Prepends the configured local instance, even if it was quarantined.
4. Visits instances sequentially until three produce nonempty results or candidates are exhausted. Engines are submitted together to each instance, not searched one at a time.
5. Tries JSON, then HTML if JSON is unsuccessful or empty. HTTP 429 triggers a proxy retry; without `RES_PROXY`, this reuses the direct session.
6. Deduplicates URLs and sorts results by score. Provenance uses `searxng@<instance>/<engine>`.

Search requests use shared curl-cffi sessions impersonating `chrome120`, with 10-second timeouts and redirects disabled. This fingerprint is separate from crawler user agents. Instance metadata uses shared httpx with a 30-second timeout and redirects enabled. There is no overall search deadline, so sequential fallbacks can take substantially longer than one request timeout.

`manager.py` creates SQLite tables `cache` and `quarantine` in `data/quarantine.db`, resolved relative to the process working directory. The parent directory must already exist. Initialization occurs when the default manager is created during import. Cache refresh is **9000 seconds (150 minutes)**, despite a misleading inline comment. Failed refreshes retain stale stored data; no cache yields an empty public list, while local search remains a candidate.

Public selection excludes active quarantines, requires daily uptime of at least 100%, and requires at least one requested engine with error rate below 15%. Candidates sort lexicographically by per-engine error rates in requested order, using 100 for unsupported/unhealthy engines. Exceptions quarantine instances for two hours on HTTP 429 and 24 hours otherwise. A successful empty response does not itself trigger quarantine.

`parser.py` parses SearXNG HTML into response models. `shortcuts.py` owns the bang mapping. `tools/search/constants.py` owns the full advertised engine catalog and time-range mappings; use `web_search_engines` for the current catalog rather than maintaining a duplicate list here.

The DDG, Brave, and Bing modules are auxiliary implementations, absent from the active registry. DDG/Brave include crawler and Jina parsing paths and use `tools/common/markdown_utils.py`. Their presence does not mean the public `web_search` tool invokes them.

## Crawler implementation

Each `Crawl4AIClient` has a semaphore of ten. Batch calls add a five-request fan-out limit; results retain input order. The 60-second per-call deadline includes client semaphore admission, DNS, and remote I/O, but not waiting for the batch fan-out semaphore. Large batches therefore run in waves.

Validation accepts absolute HTTP(S) URLs and valid nonzero ports. All locally resolved addresses must be global, except for the exact configured SearXNG scheme/host/effective-port origin with no embedded credentials. This checks the initial URL locally; it does not enforce redirect destinations or the remote browser's DNS resolution. Remote network policy remains relevant.

Configuration deep-merges defaults with matching domain overrides. Four rotating viewports and two randomly selected user agents bound default browser profiles to eight. Consecutive default viewport choices differ. Explicit domain settings override defaults. `BrowserConfig.headers` is cleared because the remote API rejects it. `session_id` is not passed through as remote session state.

The SDK crawl HTTP budget is 45 seconds, including the explicit `hooks_timeout` argument. Default navigation timeout is 20 seconds, selector wait timeout five seconds, and post-render delay 0.2 seconds (one second for Google). Markdown uses a dynamic pruning filter at threshold 0.48 with minimum word threshold five. Markdown extraction prefers `fit_markdown`; HTML is returned when requested for a single URL. Batch extraction always uses Markdown.

Timeouts become failure results; wrapped SDK HTTP timeouts are identified through their exception chain. External cancellation propagates. Logs include outcome, stage, queue duration, and total duration. The Medium override contains scroll settings that the current run-config factory does not consume; declaring a configuration key does not automatically forward it to the SDK.

Cleanup polls `/monitor/requests?status=active` and `/monitor/browsers` every 30 seconds. It kills eligible browsers through `/monitor/actions/kill_browser` when idle more than 300 seconds, or when their signature matches an active request exceeding 60 seconds. Signature matching accepts either prefix direction. Protected (`killable=false`) browsers are never killed. Monitor failures return empty lists and log errors. The server also needs its own resource limits: client cancellation does not guarantee remote work stops. See the crawler README for deployment tuning.

## Optional Chrome bridge

`tools/browser-mcp/server.py` owns configuration, namespacing, instructions, and the status tool. The entry point explicitly mounts its module-level `mcp`: filesystem discovery extracts decorated functions but does not compose nested providers. The status function is scoped inside a factory so it is registered only through the mount. An unset URL yields an empty server; a configured URL without a token raises at startup.

`OptionalMCPProvider` exposes tools only. Discovery has a three-second timeout, a 15-second failure cooldown, and a lock preventing duplicate probes during recovery. Failed discovery returns an empty list or missing tool instead of stopping local discovery. Tool operations use transport timeouts of two seconds connect/pool, ten seconds write, and 300 seconds read. These are distinct from the discovery timeout. `chrome_bridge_status` probes subject to cooldown; it is not an unconditional reconnect. Remote background tasks are disabled.

## Telemetry and troubleshooting

`HealthLogger` lazily opens ClickHouse and inserts UTC timestamps plus `component`, `engine_or_domain`, `status`, and `detail`. It does not create the database/table. Failures are logged and reset the client for reconnection. Inserts are synchronous Python calls even though ClickHouse is configured with `async_insert=1`; logging can still delay async tool execution.

| Symptom | Check |
| --- | --- |
| HTTP startup fails | Export crawler token; when bridge URL is configured, export bridge token too |
| SQLite cannot open database | Run from root and create writable `data/` before importing search |
| Missing web tools over stdio | Stdio mounts only time; use the HTTP service |
| Empty/slow search | Local SearXNG reachability, public candidate cache/quarantines, upstream failures and telemetry latency |
| Crawl rejects private URL | Intentional initial-target validation; only configured SearXNG origin is exempt |
| Crawl times out | Stage/queue logs, remote availability, HTTP and navigation budgets |
| Chrome tools disappear | Bridge connectivity, bearer token, status and cooldown |
| Browser pool grows | Remote monitor responses, killable flags, local cleanup task and remote janitor |

Current diagnostic prints in crawler handlers include context/lifespan state. Review logging before deploying with sensitive runtime state. No application change is implied by this documentation.
