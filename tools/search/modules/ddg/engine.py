import logging
import os
import re
import urllib.parse
from typing import List, Dict, Any, Optional

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ddg_search")


async def search(query: str, time_range: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Perform a search using DuckDuckGo via Jina AI proxy.

    Args:
        query: The search query.
        time_range: Filter results by time (day, week, month, year).
        limit: Max number of results to return.
    """
    # Map time_range to DDG df parameter
    df_map = {
        "day": "d",
        "week": "w",
        "month": "m",
        "year": "y"
    }
    df = df_map.get(time_range, "d") if time_range else ""

    # Construct DDG HTML URL
    encoded_query = urllib.parse.quote(query)
    ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}&b=&kl=&df={df}"

    # Wrap with Jina AI
    jina_url = f"https://r.jina.ai/{ddg_url}"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            jina_key = os.getenv("jinaKey")
            headers = {"Authorization": f"Bearer {jina_key}"} if jina_key else {}
            response = await client.get(jina_url, headers=headers)
            response.raise_for_status()
            content = response.text

            # Parse the markdown content
            # Results are typically preceded by ## [Title](URL)
            # We split by the header pattern to isolate each result block
            parts = re.split(r'\n##\s+\[', content)
            if len(parts) <= 1:
                logger.warning("No search results found in the response content")
                return []

            # The first part is usually the page header, skip it
            results = []
            for part in parts[1:]:
                if len(results) >= limit:
                    break

                try:
                    # The split removed '## ['. The part now looks like 'Title](URL)\nSnippet...'
                    # 1. Extract Title
                    title_match = re.match(r'^(.*?)\]', part)
                    if not title_match:
                        logger.debug(f"Failed to parse title for result block: {part[:50]}...")
                        continue
                    title = title_match.group(1)

                    # 2. Extract URL
                    url_match = re.search(r'\]\((.*?)\)', part)
                    if not url_match:
                        logger.debug(f"Failed to extract URL for result: {title}")
                        continue
                    url = url_match.group(1)

                    # 3. Extract Snippet (everything after the URL closing parenthesis)
                    snippet_start = url_match.end()
                    snippet = part[snippet_start:].strip()

                    # 4. Resolve DDG redirect URL
                    final_url = url
                    if "uddg=" in url:
                        parsed_url = urllib.parse.urlparse(url)
                        query_params = urllib.parse.parse_qs(parsed_url.query)
                        if "uddg" in query_params:
                            final_url = query_params["uddg"][0]
                        else:
                            logger.warning(f"DDG redirect URL missing 'uddg' parameter: {url}")
                            continue

                    # 5. Validate final URL
                    if not final_url.startswith(('http://', 'https://')):
                        logger.warning(f"Invalid final URL for result '{title}': {final_url}")
                        continue

                    # 6. Clean up snippet
                    # Remove image links: ![alt](url)
                    clean_snippet = re.sub(r'!\[.*?\]\(.*?\)', '', snippet).strip()
                    # Remove trailing timestamp (e.g., 2026-04-15T...)
                    clean_snippet = re.sub(r'\d{4}-\d{2}-\d{2}T.*$', '', clean_snippet).strip()

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
