import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from tools.crawler.crawl4ai.client import Crawl4AIClient, TimeoutResult, ErrorResult

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
async def test_crawl_single_url_with_session_and_proxy():
    mock_docker_client = AsyncMock()
    mock_docker_client.crawl.return_value = MagicMock(success=True)

    client = Crawl4AIClient(mock_docker_client)
    url = "https://example.com"
    session_id = "test-session-123"

    await client.crawl_single_url(url, proxy=True, session_id=session_id)

    # Verify that the call happened
    mock_docker_client.crawl.assert_called_once()

    # Verify browser_config and crawler_config were passed
    kwargs = mock_docker_client.crawl.call_args.kwargs
    assert 'browser_config' in kwargs
    assert 'crawler_config' in kwargs
    assert kwargs['crawler_config'].session_id == session_id
