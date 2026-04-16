import logging
import os
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from fastmcp import Context
from tools.search.constants import SearchConstants as SC
from tools.common.http_client import get_client
from tools.common.markdown_utils import (
    RESULT_SPLIT_PATTERN,
    TITLE_PATTERN,
    URL_PATTERN,
    clean_markdown_snippet
)

logger = logging.getLogger("ddg_search")

async def search(ctx: Context, query: str, time_range: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Perform a search using DuckDuckGo via Jina AI proxy.

    Args:
        ctx: The MCP context.
        query: The search query.
        time_range: Filter results by time (day, week, month, year).
        limit: Max number of results to return.
    """
    df = SC.DDG_TIME_RANGE_MAP.get(time_range, "d") if time_range else ""
    encoded_query = urllib.parse.quote(query)
    ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}&b=&kl=&df={df}"
    jina_url = f"https://r.jina.ai/{ddg_url}"

    try:
        client = ctx.lifespan_context.get("http_client") or get_client()
        jina_key = os.getenv("jinaKey")
        headers = {"Authorization": f"Bearer {jina_key}"} if jina_key else {}

        response = await client.get(jina_url, headers=headers)
        response.raise_for_status()
        content = response.text

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

                if "uddg=" not in url or "ad_domain" in url or "ad_type" in url or snippet.startswith("Ad"):
                    continue

                parsed_url = urllib.parse.urlparse(url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                final_url = query_params.get("uddg", [None])[0]

                if not final_url or not final_url.startswith(('http://', 'https://')) or "duckduckgo.com" in final_url:
                    continue

                if final_url in seen_urls:
                    continue
                seen_urls.add(final_url)

                # Clean up snippet
                clean_snippet = clean_markdown_snippet(snippet)

                results.append({
                    "title": title,
                    "url": final_url,
                    "content": clean_snippet,
                    "score": 0.9 - (len(results) * 0.08),
                    "engine": "duckduckgo"
                })
            except Exception as e:
                logger.error(f"Unexpected error parsing individual result: {e}")
                continue

        return results

    except Exception as e:
        logger.error(f"Error searching DDG via Jina AI: {e}")
        return []
