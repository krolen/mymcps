import logging
import os
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from tools.search.constants import SearchConstants as SC

import httpx

# Configure logging
logger = logging.getLogger("ddg_search")

# Pre-compiled regex patterns for efficiency
RESULT_SPLIT_PATTERN = re.compile(r'\n##\s+\[')
TITLE_PATTERN = re.compile(r'^(.*?)\]')
URL_PATTERN = re.compile(r'\]\((.*?)\)')
IMAGE_CLEAN_PATTERN = re.compile(r'\[\!\[Image.*?\]\(.*?\)\].*?(\n|$)', re.MULTILINE)
PREFIX_URL_PATTERN = re.compile(r'^\[[a-zA-Z0-9./-_\s]+\]\(.*?\)')
CONTENT_LINK_PATTERN = re.compile(r'\[(.*?)\]\(https?://.*?\)', re.DOTALL)
MD_LINK_PATTERN = re.compile(r'\[.*?\]\(.*?\)')
MD_IMAGE_PATTERN = re.compile(r'!\[.*?\]\(.*?\)')
TIMESTAMP_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}T.*$')

# Shared HTTP client to avoid repeated TCP/TLS handshakes
_client: Optional[httpx.AsyncClient] = None

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    return _client

async def search(query: str, time_range: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Perform a search using DuckDuckGo via Jina AI proxy.

    Args:
        query: The search query.
        time_range: Filter results by time (day, week, month, year).
        limit: Max number of results to return.
    """
    df = SC.DDG_TIME_RANGE_MAP.get(time_range, "d") if time_range else ""
    encoded_query = urllib.parse.quote(query)
    ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}&b=&kl=&df={df}"
    jina_url = f"https://r.jina.ai/{ddg_url}"

    try:
        client = get_client()
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
                snippet = IMAGE_CLEAN_PATTERN.sub('', snippet).strip()
                snippet = PREFIX_URL_PATTERN.sub('', snippet).strip()

                content_match = CONTENT_LINK_PATTERN.search(snippet)
                if content_match:
                    clean_snippet = content_match.group(1)
                else:
                    clean_snippet = MD_LINK_PATTERN.sub('', snippet).strip()

                clean_snippet = MD_IMAGE_PATTERN.sub('', clean_snippet).strip()
                clean_snippet = TIMESTAMP_PATTERN.sub('', clean_snippet).strip()

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
