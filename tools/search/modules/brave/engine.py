import logging
import os
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

async def search(ctx: Context, query: str, time_range: Optional[str] = None, limit: int = 30) -> List[SearchResult]:
    """
    Perform a search using Brave via Jina AI proxy.

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
    jina_url = f"https://r.jina.ai/{brave_url}"

    try:
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

                # Filter out ads or internal Brave links if they appear in the Jina output
                if "ad" in url.lower() or snippet.startswith("Ad"):
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
                    score=0.9 - (len(results) * 0.08),
                    engine="brave"
                ))
            except Exception as e:
                logger.error(f"Unexpected error parsing individual result: {e}")
                continue

        return results

    except Exception as e:
        logger.error(f"Error searching Brave via Jina AI: {e}")
        return []
