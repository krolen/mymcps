import logging
from typing import List, Set

import httpx

from tools.search.constants import SearchConstants
from tools.search.models import SearchResult
from .browser_client import get_browser_session, get_browser_session_with_proxy
from .manager import SearxSpaceManager
from .parser import parse_searxng_html
from .shortcuts import SearchEngineShortcut

logger = logging.getLogger(__name__)


class SearxSpaceEngine:
    def __init__(self, manager: SearxSpaceManager):
        self.manager = manager

    async def search(self, query: str, limit: int = None) -> List[SearchResult]:
        # 1. Parse shortcuts for instance selection
        requested_engines, _ = self._parse_shortcuts(query)

        # If no engine specified, use prioritized list matching the general engines in SearchEngineShortcut
        if not requested_engines:
            requested_engines = [
                SearchEngineShortcut.get_engine_name(SearchEngineShortcut.GOOGLE.value),
                SearchEngineShortcut.get_engine_name(SearchEngineShortcut.BING.value),
                SearchEngineShortcut.get_engine_name(SearchEngineShortcut.DDG.value),
                SearchEngineShortcut.get_engine_name(SearchEngineShortcut.BRAVE.value),
            ]

        all_results: List[SearchResult] = []
        seen_urls: Set[str] = set()

        # 2. Get all candidate instances sorted by priority
        await self.manager.get_instances()
        # Request a large number of candidates to allow for fallbacks
        candidates = self.manager.get_best_instances(requested_engines, count=50)
        # Prioritize local instance
        candidates = [SearchConstants.SEARXNG_URL] + candidates

        if not candidates:
            logger.warning("No instances found that support any of the requested engines")
            return []

        logger.info(f"Candidate instances for query '{query}': {', '.join(candidates)}")

        success_count = 0
        for instance_url in candidates:
            if success_count >= 3:
                break

            try:
                results = await self._execute_instance_search(instance_url, query)
                if results:
                    for res in results:
                        if res.url not in seen_urls:
                            all_results.append(res)
                            seen_urls.add(res.url)
                    success_count += 1
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning(
                        f"Instance {instance_url} returned 429 (Too Many Requests). Quarantining for 2 hours.")
                    self.manager.quarantine_instance(instance_url, 2)
                else:
                    logger.warning(
                        f"Instance {instance_url} failed with status {e.response.status_code}. Quarantining for 24 hours.")
                    self.manager.quarantine_instance(instance_url, 24)
            except Exception as e:
                logger.warning(
                    f"Instance {instance_url} failed with exception {type(e).__name__}: {e}. Quarantining for 24 hours.")
                self.manager.quarantine_instance(instance_url, 24)

        # 3. Join results: sort by score and apply limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:limit] if limit else all_results

    def _parse_shortcuts(self, query: str) -> tuple[List[str], str]:
        engines = []
        # Simple parser: look for shortcuts like !g, !bi, etc.
        for shortcut in SearchEngineShortcut:
            if shortcut.value in query:
                engines.append(SearchEngineShortcut.get_engine_name(shortcut.value))

        # Remove shortcuts from query for the actual search
        cleaned_query = query
        for shortcut in SearchEngineShortcut:
            cleaned_query = cleaned_query.replace(shortcut.value, "")

        return engines, cleaned_query.strip()

    async def _request_with_fallback(self, instance_url: str, search_url: str, params: dict):
        """Attempts a request with a standard session, falling back to a proxy if a 429 is encountered."""
        # Try standard session
        try:
            client = await get_browser_session()
            response = await client.post(search_url, params=params)
            if response.status_code == 200:
                logger.info(f"Instance {instance_url}: got 200")
                return response
            if response.status_code == 429:
                logger.info(f"Instance {instance_url} returned 429, trying with proxy...")
                # Fallback to proxy session
                proxy_client = await get_browser_session_with_proxy()
                response = await proxy_client.post(search_url, params=params, allow_redirects=False)
                if response.status_code == 200:
                    logger.info(f"Instance {instance_url} proxy call succeed")
                    return response
            logger.warning(f"Instance {instance_url} failed with status {response.status_code}: {response.content}")
        except Exception as e:
            logger.warning(f"Request attempt failed for {instance_url}: {e}")

        return None

    async def _execute_instance_search(self, instance_url: str, query: str) -> List[SearchResult]:
        search_url = f"{instance_url.rstrip('/')}/search"
        logger.info(f"Executing search on instance {instance_url} for query: {query}")

        # 1. Try JSON first (preferred)
        json_params = {"q": query, "format": "json"}
        response = await self._request_with_fallback(instance_url, search_url, json_params)
        if response:
            parsed = self._parse_json_response(response, instance_url)
            if parsed:
                logger.info(f"JSON search successful on {instance_url}, found {len(parsed)} results")
                return parsed

        logger.info(f"JSON search failed or returned no results on {instance_url}, falling back to HTML")

        # 2. Fallback: Try without JSON (HTML)
        html_params = {"q": query}
        response = await self._request_with_fallback(instance_url, search_url, html_params)
        if response:
            results = self._parse_html_response(response, instance_url, query)
            logger.info(f"HTML search successful on {instance_url}, found {len(results)} results")
            return results

        logger.error(f"All search attempts failed for instance {instance_url}")
        raise RuntimeError(f"Failed to get search results from {instance_url}")

    def _parse_json_response(self, response, instance_url: str) -> List[SearchResult] | None:
        try:
            data = response.json()
        except Exception as e:
            logger.warning(f"Failed to parse JSON response from {instance_url}: {e}")
            return None

        results = []
        for item in data.get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=item.get("score", 1.0),
                engine=f"searxng@{instance_url}/{item.get('engine', '')}"
            ))
        return results

    def _parse_html_response(self, response, instance_url: str, query: str) -> List[SearchResult]:
        parsed_response = parse_searxng_html(response.text, query)
        return [
            SearchResult(
                title=res.title,
                url=res.url,
                content=res.content,
                score=res.score,
                engine=f"searxng@{instance_url}/{res.engine}"
            ) for res in parsed_response.results
        ]
