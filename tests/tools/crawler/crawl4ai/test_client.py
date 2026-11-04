import asyncio
import ipaddress
import pytest
from unittest.mock import AsyncMock, MagicMock
from tools.crawler.crawl4ai.client import Crawl4AIClient, TimeoutResult, ErrorResult


@pytest.fixture(autouse=True)
def resolve_public_hosts(monkeypatch):
    async def resolve(_hostname):
        return {ipaddress.ip_address("93.184.216.34")}

    monkeypatch.setattr(Crawl4AIClient, "_resolve_host", resolve)

@pytest.mark.asyncio
async def test_crawl_single_url_success():
    # Mock the Docker Client
    mock_docker_client = AsyncMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.markdown = "Test content"
    mock_docker_client.crawl.return_value = mock_result

    client = Crawl4AIClient(mock_docker_client)
    url = "https://example.com"

    result = await client.crawl_single_url(url)

    assert result == mock_result
    mock_docker_client.crawl.assert_called_once()
    # Verify the URL was passed correctly in the list
    args, kwargs = mock_docker_client.crawl.call_args
    assert kwargs['urls'] == [url]

@pytest.mark.asyncio
async def test_crawl_single_url_timeout():
    # Mock the Docker Client to raise a TimeoutError
    mock_docker_client = AsyncMock()
    mock_docker_client.crawl.side_effect = asyncio.TimeoutError()

    client = Crawl4AIClient(mock_docker_client)
    url = "https://example.com"

    result = await client.crawl_single_url(url)

    assert isinstance(result, TimeoutResult)
    assert result.success is False
    assert "timed out" in result.error

@pytest.mark.asyncio
async def test_crawl_single_url_exception():
    # Mock the Docker Client to raise a generic exception
    mock_docker_client = AsyncMock()
    mock_docker_client.crawl.side_effect = Exception("Connection failed")

    client = Crawl4AIClient(mock_docker_client)
    url = "https://example.com"

    result = await client.crawl_single_url(url)

    assert isinstance(result, ErrorResult)
    assert result.success is False
    assert result.error == "Connection failed"

@pytest.mark.asyncio
async def test_crawl_single_url_with_session():
    mock_docker_client = AsyncMock()
    mock_docker_client.crawl.return_value = MagicMock(success=True)

    client = Crawl4AIClient(mock_docker_client)
    url = "https://example.com"
    session_id = "test-session-123"

    await client.crawl_single_url(url, session_id=session_id)

    # Verify that the call happened
    mock_docker_client.crawl.assert_called_once()

    # Verify browser_config and crawler_config were passed
    kwargs = mock_docker_client.crawl.call_args.kwargs
    assert 'browser_config' in kwargs
    assert 'crawler_config' in kwargs
    assert kwargs['crawler_config'].session_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "not-a-valid-url",
    "https://",
    "file:///etc/hostname",
    "https://example.com:99999/",
    "http://example.com:0/",
])
async def test_crawl_single_url_rejects_invalid_or_private_targets(url):
    docker_client = AsyncMock()
    client = Crawl4AIClient(docker_client)

    result = await client.crawl_single_url(url)

    assert isinstance(result, ErrorResult)
    docker_client.crawl.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "http://192.168.0.100:12345/test",
    "http://2130706433/",
    "http://0x7f000001/",
    "http://127.1/",
    "http://localtest.me/",
    "http://127.0.0.1.nip.io/",
])
async def test_crawl_single_url_rejects_hosts_resolving_to_private_addresses(monkeypatch, url):
    async def resolve(_hostname):
        return {ipaddress.ip_address("127.0.0.1")}

    monkeypatch.setattr(Crawl4AIClient, "_resolve_host", resolve)
    docker_client = AsyncMock()

    result = await Crawl4AIClient(docker_client).crawl_single_url(url)

    assert isinstance(result, ErrorResult)
    assert "private or reserved" in result.error
    docker_client.crawl.assert_not_called()


@pytest.mark.asyncio
async def test_list_active_requests_reads_crawl4ai_093_response():
    response = MagicMock()
    response.json.return_value = {
        "active": [{"id": "req-1", "url": "https://example.com", "status": "running"}],
        "completed": [],
    }
    docker_client = AsyncMock()
    docker_client._request.return_value = response
    client = Crawl4AIClient(docker_client)

    requests = await client.list_active_requests()

    assert [request.id for request in requests] == ["req-1"]


def test_config_factories_only_send_docker_api_supported_fields(monkeypatch):
    """The 0.9 Docker API rejects client-controlled browser/stealth policy."""
    browser_factory = MagicMock(return_value=MagicMock())
    run_factory = MagicMock(return_value=MagicMock())
    monkeypatch.setattr("tools.crawler.crawl4ai.client.BrowserConfig", browser_factory)
    monkeypatch.setattr("tools.crawler.crawl4ai.client.CrawlerRunConfig", run_factory)

    client = Crawl4AIClient(AsyncMock())
    browser_config = client._get_browser_config("https://www.google.com/search?q=crawl4ai")
    run_config = client._get_run_config("https://www.google.com/search?q=crawl4ai")

    assert browser_config is browser_factory.return_value
    assert run_config is run_factory.return_value

    browser_kwargs = browser_factory.call_args.kwargs
    supported_browser_fields = {
        "headless",
        "enable_stealth",
        "viewport_width",
        "viewport_height",
        "user_agent",
        "text_mode",
    }
    assert supported_browser_fields <= browser_kwargs.keys()
    assert browser_kwargs["enable_stealth"] is True
    assert browser_kwargs["avoid_ads"] is True
    assert "extra_args" not in browser_kwargs
    assert "proxy_config" not in browser_kwargs

    run_kwargs = run_factory.call_args.kwargs
    supported_run_fields = {
        "delay_before_return_html",
        "locale",
        "timezone_id",
        "markdown_generator",
        "only_text",
    }
    assert supported_run_fields <= run_kwargs.keys()
    assert run_kwargs["delay_before_return_html"] == 1.0
    assert run_kwargs["locale"] == "en-US"
    assert run_kwargs["timezone_id"] == "America/Toronto"
    assert run_kwargs["only_text"] is True
    assert "simulate_user" not in run_kwargs
    assert "magic" not in run_kwargs


def test_serialized_configs_exclude_all_forbidden_fields():
    client = Crawl4AIClient(AsyncMock())

    browser_params = client._get_browser_config("https://example.com").dump()["params"]
    run_params = client._get_run_config("https://example.com", session_id="session-1").dump()["params"]

    assert not {"extra_args", "proxy_config", "headers"} & browser_params.keys()
    assert not {"simulate_user", "magic", "session_id"} & run_params.keys()


def test_configures_static_api_token_on_docker_client():
    docker_client = MagicMock()
    docker_client._http_client.headers = {}

    Crawl4AIClient(docker_client, api_token="lan-only-token")

    assert docker_client._http_client.headers == {
        "Authorization": "Bearer lan-only-token"
    }


def test_viewports_switch_for_repeated_requests_without_unbounded_profiles():
    from tools.crawler.constants import BROWSER_VIEWPORTS

    client = Crawl4AIClient(AsyncMock())
    configs = [
        client._get_browser_config("https://example.com", "same-session").to_dict()
        for _ in range(20)
    ]
    sizes = [(config["viewport_width"], config["viewport_height"]) for config in configs]
    assert all(size in BROWSER_VIEWPORTS for size in sizes)
    assert all(previous != current for previous, current in zip(sizes, sizes[1:]))
    # Only viewport and user-agent selection should vary the browser profile.
    normalized = [
        {key: value for key, value in config.items()
         if key not in {"viewport_width", "viewport_height", "user_agent"}}
        for config in configs
    ]
    assert all(config == normalized[0] for config in normalized)


def test_matching_viewports_reuse_same_profile_across_hosts(monkeypatch):
    from tools.crawler.constants import BROWSER_VIEWPORTS, BROWSER_USER_AGENTS

    picks = iter([BROWSER_VIEWPORTS[0], BROWSER_VIEWPORTS[1], BROWSER_VIEWPORTS[0]])
    monkeypatch.setattr(
        "tools.crawler.crawl4ai.client.random.choice",
        lambda choices: BROWSER_USER_AGENTS[0] if choices is BROWSER_USER_AGENTS else next(picks),
    )
    client = Crawl4AIClient(AsyncMock())
    first = client._get_browser_config("https://example.com", "first").to_dict()
    other = client._get_browser_config("https://example.com", "first").to_dict()
    reused = client._get_browser_config("https://other.example", "second").to_dict()
    assert first != other
    assert first == reused


def test_domain_viewport_override_is_preserved(monkeypatch):
    from tools.crawler.constants import DOMAIN_CONFIGS

    monkeypatch.setitem(DOMAIN_CONFIGS, "example.com", {"browser": {
        "viewport": {"width": 1600, "height": 1000},
        "user_agent": "domain-specific-agent",
    }})
    client = Crawl4AIClient(AsyncMock())
    for _ in range(3):
        config = client._get_browser_config("https://example.com")
        assert (config.viewport_width, config.viewport_height) == (1600, 1000)
        assert config.user_agent == "domain-specific-agent"



def test_run_config_honors_zero_delay_and_bounded_selector_wait(monkeypatch):
    from tools.crawler.constants import DOMAIN_CONFIGS

    monkeypatch.setitem(DOMAIN_CONFIGS, "example.com", {"crawl": {
        "delay_before_return_html": 0,
        "page_timeout": 12_000,
        "wait_for": "css:article",
        "wait_for_timeout": 2_000,
    }})
    config = Crawl4AIClient(AsyncMock())._get_run_config("https://example.com")
    assert config.delay_before_return_html == 0
    assert config.page_timeout == 12_000
    assert config.wait_for == "css:article"
    assert config.wait_for_timeout == 2_000
    assert config.wait_until == "domcontentloaded"


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["queue", "validation", "crawl"])
async def test_overall_deadline_bounds_each_stage(monkeypatch, stage):
    monkeypatch.setattr("tools.crawler.crawl4ai.client.CRAWL_TIMEOUT_SECONDS", 0.02)
    client = Crawl4AIClient(AsyncMock())
    blocked = asyncio.Event()
    if stage == "queue":
        client.semaphore = asyncio.Semaphore(0)
    elif stage == "validation":
        async def validate(_):
            await blocked.wait()
        client._validate_crawl_url = validate
    else:
        async def crawl(**_):
            await blocked.wait()
        client.client.crawl.side_effect = crawl

    result = await asyncio.wait_for(client.crawl_single_url("https://example.com"), 1)
    assert isinstance(result, TimeoutResult)
    assert stage in result.error
    if stage != "crawl":
        client.client.crawl.assert_not_called()
    if stage != "queue":
        assert client.semaphore._value == 10


@pytest.mark.asyncio
async def test_external_cancellation_propagates_and_releases_slot():
    client = Crawl4AIClient(AsyncMock())
    started = asyncio.Event()
    async def crawl(**_):
        started.set()
        await asyncio.Event().wait()
    client.client.crawl.side_effect = crawl
    task = asyncio.create_task(client.crawl_single_url("https://example.com"))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert client.semaphore._value == 10


@pytest.mark.asyncio
@pytest.mark.parametrize("http_timeout", [False, True])
async def test_sdk_http_budget_and_wrapped_timeout_classification(http_timeout):
    import httpx
    from crawl4ai.docker_client import Crawl4aiDockerClient
    from tools.crawler.constants import CRAWL_HTTP_TIMEOUT_SECONDS

    requests = []
    async def handle(request):
        requests.append(request)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if http_timeout:
            raise httpx.ReadTimeout("slow response", request=request)
        return httpx.Response(200, json={"success": True, "results": [{
            "url": "https://example.com", "html": "<p>ok</p>", "success": True,
        }]})

    async with Crawl4aiDockerClient(base_url="http://crawler.test", verbose=False) as docker:
        await docker._http_client.aclose()
        docker._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        result = await Crawl4AIClient(docker).crawl_single_url("https://example.com")

    assert [request.url.path for request in requests] == ["/health", "/crawl"]
    assert requests[-1].extensions["timeout"]["read"] == CRAWL_HTTP_TIMEOUT_SECONDS
    if http_timeout:
        assert isinstance(result, TimeoutResult)
        assert "HTTP" in result.error
    else:
        assert result.success


def test_user_agents_vary_for_same_host_with_bounded_reusable_profiles(monkeypatch):
    import json
    from itertools import product
    from tools.crawler.constants import BROWSER_VIEWPORTS, BROWSER_USER_AGENTS

    # Exercise all eight profiles, then repeat them across a different host.
    pairs = list(product(BROWSER_USER_AGENTS, BROWSER_VIEWPORTS))
    selections = iter(value for agent, size in pairs * 2 for value in (size, agent))
    monkeypatch.setattr("tools.crawler.crawl4ai.client.random.choice", lambda _: next(selections))
    client = Crawl4AIClient(AsyncMock())
    configs = [
        client._get_browser_config(url, "same-session").to_dict()
        for url in ["https://example.com"] * 8 + ["https://other.example"] * 8
    ]
    assert {config["user_agent"] for config in configs} == set(BROWSER_USER_AGENTS)
    assert all("Chrome/157.0.0.0" in agent for agent in BROWSER_USER_AGENTS)
    assert len({json.dumps(config, sort_keys=True) for config in configs}) == 8
    assert configs[:8] == configs[8:]


@pytest.mark.parametrize("block_ads", [True, False])
def test_domain_can_override_ad_blocking(monkeypatch, block_ads):
    from tools.crawler.constants import DOMAIN_CONFIGS

    monkeypatch.setitem(DOMAIN_CONFIGS, "example.com", {"browser": {"avoid_ads": block_ads}})
    config = Crawl4AIClient(AsyncMock())._get_browser_config("https://example.com")
    assert config.avoid_ads is block_ads
    assert config.java_script_enabled is True
    assert "headers" not in config.dump()["params"]
