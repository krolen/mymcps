import logging
import os
import re
import urllib.parse
from typing import List, Optional
from fastmcp import Context
from tools.search.models import SearchResult
from tools.search.constants import SearchConstants as SC
from tools.common.http_client import get_client
from tools.common.markdown_utils import (
    RESULT_SPLIT_PATTERN,
    TITLE_PATTERN,
    URL_PATTERN,
    clean_markdown_snippet
)

logger = logging.getLogger("brave_search")

async def _parse_search_results_jina(content: str, limit: int) -> List[SearchResult]:
    """Parse search results from content using the existing parsing logic."""
    # Parse the markdown/content
    parts = RESULT_SPLIT_PATTERN.split(content)
    if len(parts) <= 1:
        logger.warning("No search results found in the response content")
        return []

    results = []
    seen_urls = set()
    for part in parts[1:]:
        if len(results) >= limit:
            break

        try:
            title_match = TITLE_PATTERN.match(part)
            if not title_match:
                continue
            title = title_match.group(1)

            url_match = URL_PATTERN.search(part)
            if not url_match:
                continue
            url = url_match.group(1)

            snippet = part[url_match.end():].strip()

            # Filter out ads or internal Brave links
            if "ad" in url.lower() or "brave.com" in url.lower() or snippet.startswith("Ad"):
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Clean up snippet
            clean_snippet = clean_markdown_snippet(snippet)

            results.append(SearchResult(
                title=title,
                url=url,
                content=clean_snippet,
                score=0.9 * (0.8 ** len(results)),
                engine="brave"
            ))
        except Exception as e:
            logger.error(f"Unexpected error parsing individual result: {e}")
            continue

    return results


async def _parse_search_results_crawl(content: str, limit: int) -> List[SearchResult]:
    """Parse search results from crawl4ai content."""
    # Find all markdown link patterns [title](url)
    link_pattern = re.compile(r'\[(.*?)\]\((https?://[^\s\)]+)\)')
    matches = list(link_pattern.finditer(content))

    if not matches:
        logger.warning("No search results found in the crawl4ai response content")
        return []

    results = []
    seen_urls = set()

    for i, match in enumerate(matches):
        if len(results) >= limit:
            break

        try:
            title = match.group(1).strip()
            url = match.group(2).strip()

            # Extract snippet - get content between this match and the next match
            snippet_start = match.end()
            snippet_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            snippet = content[snippet_start:snippet_end].strip()

            # Filter out ads or internal Brave links
            if "ad" in url.lower() or "brave.com" in url.lower() or snippet.startswith("Ad"):
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Clean up snippet
            clean_snippet = clean_markdown_snippet(snippet)

            results.append(SearchResult(
                title=title,
                url=url,
                content=clean_snippet,
                score=0.9 * (0.8 ** len(results)),
                engine="brave"
            ))
        except Exception as e:
            logger.error(f"Unexpected error parsing individual result: {e}")
            continue

    return results


async def search(ctx: Context, query: str, time_range: Optional[str] = None, limit: int = 30) -> List[SearchResult]:
    """
    Perform a search using Brave with crawl4ai as primary and Jina AI as fallback.

    Args:
        ctx: The MCP context.
        query: The search query.
        time_range: Filter results by time (day, week, month, year).
        limit: Max number of results to return.
    """
    tf = SC.BRAVE_TIME_RANGE_MAP.get(time_range, "d") if time_range else ""
    encoded_query = urllib.parse.quote(query)
    # Brave search string: https://search.brave.com/search?q=hello+world&source=desktop&country=ca&lang=en&safesearch=moderate&tf=pw
    brave_url = f"https://search.brave.com/search?q={encoded_query}&source=desktop&country=ca&lang=en&safesearch=moderate&tf={tf}"

    # Try crawl4ai first
    try:
        logger.info(f"Attempting Brave search via crawl4ai for query: {query}")

        # Import crawl4ai functions if available
        from tools.crawler.crawl4ai.server import crawl_url, is_success, get_markdown_content

        result = await crawl_url(ctx, brave_url, session_id=f"brave")

        if is_success(result):
            content = get_markdown_content(result)
            logger.info(f"Successfully crawled Brave via crawl4ai, content length: {len(content)}")
            results = await _parse_search_results_crawl(content, limit)
            if results:
                logger.info(f"Found {len(results)} results via crawl4ai")
                return results
            else:
                logger.warning("No results found via crawl4ai, falling back to Jina AI")
        else:
            error = getattr(result, 'error', 'Unknown error')
            logger.warning(f"Crawl4ai failed: {error}, falling back to Jina AI")
    except Exception as e:
        logger.warning(f"Error using crawl4ai for Brave search: {e}, falling back to Jina AI")

    # Fallback to Jina AI proxy method
    try:
        logger.info(f"Falling back to Brave search via Jina AI for query: {query}")
        jina_url = f"https://r.jina.ai/{brave_url}"
        client = ctx.lifespan_context.get("http_client") or get_client()
        jina_key = os.getenv("jinaKey")
        headers = {"Authorization": f"Bearer {jina_key}"} if jina_key else {}

        response = await client.get(jina_url, headers=headers)
        response.raise_for_status()
        content = response.text

        if "Warning: This page maybe requiring CAPTCHA" in content or "Warning: Target URL returned error" in content:
            logger.warning("CAPTCHA detected in Jina AI response for Brave")
            return []

        # Parse the markdown content
        results = await _parse_search_results_jina(content, limit)
        logger.info(f"Found {len(results)} results via Jina AI fallback")
        return results

    except Exception as e:
        logger.error(f"Error searching Brave via Jina AI: {e}")
        return []
