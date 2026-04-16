import os
import logging
import httpx
from tools.common.http_client import get_client

logger = logging.getLogger("jina_crawler")

async def crawl_via_jina(url: str) -> str:
    """
    Crawl a URL via the r.jina.ai proxy to get clean markdown content.

    Args:
        url: The target URL to crawl.

    Returns:
        The markdown content returned by Jina AI, or an error message.
    """
    jina_url = f"https://r.jina.ai/{url}"

    try:
        client = get_client()
        jina_key = os.getenv("jinaKey")
        headers = {"Authorization": f"Bearer {jina_key}"} if jina_key else {}

        response = await client.get(jina_url, headers=headers)
        response.raise_for_status()
        return response.text

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error crawling {url} via Jina: {e}")
        return f"Error: Jina AI returned status {e.response.status_code}"
    except Exception as e:
        logger.error(f"Unexpected error crawling {url} via Jina: {e}")
        return f"Error: {str(e)}"
