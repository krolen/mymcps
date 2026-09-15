import asyncio
import os
import pytest
from crawl4ai.docker_client import Crawl4aiDockerClient
from tools.crawler.crawl4ai.client import Crawl4AIClient
from tools.crawler.constants import CRAWL4AI_SERVER_URL

@pytest.mark.asyncio
async def test_crawl_single_url_integration():
    """
    Integration test for crawl_single_url that hits the actual Crawl4AI Docker server.
    """
    api_token = os.getenv("CRAWL4AI_API_TOKEN")
    if not api_token:
        pytest.skip("CRAWL4AI_API_TOKEN is required for Crawl4AI integration tests")

    url = "https://searx.tiekoetter.com/search?q=ai+news+%21google&category_none=1&pageno=3&language=en-US&time_range=&safesearch=0&theme=simple"

    try:
        async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL) as docker_client:
            crawler = Crawl4AIClient(docker_client, api_token=api_token)

            # Test a simple successful crawl
            result = await crawler.crawl_single_url(url)

            assert result is not None
            assert result.success is True
            # Check if we actually got content
            assert hasattr(result, 'markdown')
            assert len(str(result.markdown)) > 0
            print(result)

    except Exception as e:
        pytest.fail(f"Integration test failed with unexpected error: {e}")

@pytest.mark.asyncio
async def test_crawl_single_url_invalid_url():
    """
    Test how the system handles an invalid URL.
    """
    api_token = os.getenv("CRAWL4AI_API_TOKEN")
    if not api_token:
        pytest.skip("CRAWL4AI_API_TOKEN is required for Crawl4AI integration tests")

    url = "not-a-valid-url"

    async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL) as docker_client:
        crawler = Crawl4AIClient(docker_client, api_token=api_token)
        result = await crawler.crawl_single_url(url)

        assert result.success is False
        assert hasattr(result, 'error')
