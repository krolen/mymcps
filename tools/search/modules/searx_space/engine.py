import asyncio
import logging
from typing import List, Set

import httpx

from .browser_client import get_browser_session, get_browser_session_with_proxy
from .parser import parse_searxng_html
from tools.search.models import SearchResult
from .models import SearxSpaceData
from .shortcuts import SearchEngineShortcut
from .manager import SearxSpaceManager

logger = logging.getLogger(__name__)


class SearxSpaceEngine:
    def __init__(self, manager: SearxSpaceManager):
        self.manager = manager

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
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
        return all_results[:limit]

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
            response = await client.get(search_url, params=params)
            if response.status_code == 200:
                return response
            if response.status_code == 429:
                logger.info(f"Instance {instance_url} returned 429, trying with proxy...")
                # Fallback to proxy session
                proxy_client = await get_browser_session_with_proxy()
                response = await proxy_client.get(search_url, params=params)
                if response.status_code == 200:
                    return response
        except Exception as e:
            logger.debug(f"Request attempt failed for {instance_url}: {e}")

        return None

    async def _execute_instance_search(self, instance_url: str, query: str) -> List[SearchResult]:
        search_url = f"{instance_url.rstrip('/')}/search"

        # 1. Try JSON first (preferred)
        json_params = {"q": query, "format": "json"}
        response = await self._request_with_fallback(instance_url, search_url, json_params)
        if response:
            return self._parse_json_response(response, instance_url)

        # 2. Fallback: Try without JSON (HTML)
        html_params = {"q": query}
        response = await self._request_with_fallback(instance_url, search_url, html_params)
        if response:
            return self._parse_html_response(response, instance_url, query)

        raise RuntimeError(f"Failed to get search results from {instance_url}")

    def _parse_json_response(self, response, instance_url: str) -> List[SearchResult]:
        try:
            data = response.json()
        except Exception as e:
            logger.warning(f"Failed to parse JSON response from {instance_url}: {e}")
            raise RuntimeError("Response was not JSON")

        results = []
        for item in data.get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=item.get("score", 1.0),
                engine=f"searxng@{instance_url}"
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
                engine=f"searxng@{instance_url}"
            ) for res in parsed_response.results
        ]
