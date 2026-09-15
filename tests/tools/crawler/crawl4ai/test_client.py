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
    assert run_kwargs["delay_before_return_html"] == 6
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
