# Crawl timing and browser reuse

The client uses Crawl4AI 0.9.5. Defaults live in `tools/crawler/constants.py`:

- Overall deadline: 60 seconds per `crawl_single_url` call, including waiting
  for the client concurrency slot and DNS validation.
- HTTP timeout: 45 seconds. The SDK also uses `hooks_timeout` as its explicit
  `/crawl` HTTP timeout, so setting only the Docker client's timeout is insufficient.
- Navigation timeout: 20,000 ms; selector wait timeout: 5,000 ms.
- HTML rendering delay: 0.2 seconds, with 1 second for Google.

`DOMAIN_CONFIGS` can override `page_timeout`, `wait_until`, `wait_for`,
`wait_for_timeout`, and `delay_before_return_html`. For pages that render content
asynchronously, prefer a bounded `wait_for` such as `css:article` over increasing
fixed sleeps. Zero rendering delay is supported. Validate content completeness
when tuning a domain. Navigation and selector timeouts are not total crawl limits.
Batch calls retain their concurrency limit of five and can take multiple waves.

Viewport variation is required: the project has experienced bans when using a
fixed viewport. Each request randomly selects from four sizes (1280×720,
1366×768, 1440×900, and 1920×1080), excluding the client's previous selection.
This also varies repeated requests to the same host with the same `session_id`.
User-agent variation is also intentional: requests randomly select a Windows or
Linux Chrome 157 user agent from `BROWSER_USER_AGENTS`. Chrome 157 was verified as
the current desktop stable major version on 2026-11-03 using the
[Chrome release announcement](https://chromereleases.googleblog.com/2026/11/stable-channel-update-for-desktop.html).
The strings use the reduced `157.0.0.0` version format. This changes the advertised
user agent; it does not upgrade the remote Chromium installation.

Four viewports and two user agents produce at most eight default browser
profiles, each reusable by the remote pool. Rotation does not guarantee
protection from bans.

`BROWSER_VIEWPORTS` in `tools/crawler/constants.py` controls the available sizes.
Explicit domain viewport and user-agent overrides are respected. `session_id` is retained for
API compatibility and does not preserve a page/session or control rotation.

Ad and tracker blocking is enabled by default with `BrowserConfig.avoid_ads=True`.
This blocks known advertising/tracking domains while keeping JavaScript enabled
for site functionality. Set `browser.avoid_ads=False` in a domain override if
necessary. This curated blocklist does not block every third-party script.

The Docker API rejects client-controlled `BrowserConfig.headers`. The config
factory clears SDK-generated headers before sending requests. Diagnostic code
that calls `BrowserConfig.clone()` must clear headers again, because cloning
regenerates them from the user agent.

The remote Crawl4AI cleaner sometimes fails to clean up browsers. The local
server's cleanup task was introduced as a fallback for those observed failures.
Browser reuse optimizations must preserve that operational requirement rather
than assume the remote cleaner is always reliable.

The local cleanup task checks every 30 seconds and evicts browsers reported as
`killable` after more than 300 seconds idle. This retains the fallback while
allowing warm browser reuse beyond the former 30-second threshold. Tune
`BROWSER_IDLE_TIMEOUT_SECONDS` and `BROWSER_CLEANUP_INTERVAL_SECONDS` in
`tools/crawler/constants.py` to adjust that balance. Browsers not reported as
`killable` are left alone.

Configure retention and memory-pressure eviction on the Crawl4AI server as well. For
v0.9.5, these are useful starting points in the remote server's config.yml:

```yaml
limits:
  wall_clock_s: 40
crawler:
  pool:
    idle_ttl_sec: 300
    max_pages_before_recycle: 200
```

These server settings are deployment recommendations, not applied by this
repository. Verify the remote image version and existing configuration before
merging them. The server deadline bounds work even if an HTTP client disconnect
is not propagated as cancellation. Context recycling bounds accumulated browser
state without starting a new Chromium process on every request.

Client logs report outcome, stage, queue time, and total time. Use these alongside
remote browser creation/reuse counts, memory, and extracted content completeness
to compare cold and warm requests before changing concurrency.

Run focused tests without network access:

```sh
.venv/bin/python -m pytest tests/tools/crawler/crawl4ai/test_client.py tests/tools/crawler/crawl4ai/test_cleanup.py -k 'not integration'
```

For an opt-in live check, configure `CRAWL4AI_API_TOKEN` in the environment and run:

```sh
CRAWL4AI_LIVE_TESTS=1 .venv/bin/python -m pytest tests/tools/crawler/crawl4ai/test_ctv_live.py -s
```

The live check crawls CTV's Toronto listing and a linked article, verifies news
content and article links, and records durations, HTTP status, markdown, HTML,
and browser pool snapshots in the printed pytest temporary directory.
