import asyncio
import logging
from typing import List, Set

import httpx

from tools.common.http_client import get_client, get_proxy_client
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

    async def _execute_instance_search(self, instance_url: str, query: str) -> List[SearchResult]:
        client = get_client()
        # SearXNG search URL format: /search
        search_url = f"{instance_url.rstrip('/')}/search"
        params = {"q": query}

        response = None
        try:
            # try:
            # Try POST first as it often avoids some restrictions
            response = await client.get(search_url, params=params)
            response.raise_for_status()
        # except Exception as e:
        #     logger.debug(f"GET failed for {instance_url}, trying POST: {e}")
        #     response = await client.post(search_url, data=params)
        #     response.raise_for_status()
        except Exception as e:
            logger.info(f"Instance {instance_url} failed with default client, retrying with proxy client: {e}")
            proxy_client = get_proxy_client()
            try:
                # try:
                # Try Proxy POST
                response = await proxy_client.get(search_url, params=params)
                response.raise_for_status()
            # except Exception as e_p:
            #     logger.debug(f"Proxy GET failed for {instance_url}, trying Proxy POST: {e_p}")
            #     response = await proxy_client.post(search_url, data=params)
            #     response.raise_for_status()
            except Exception as proxy_e:
                logger.error(f"Proxy search failed for {instance_url}: {proxy_e}")
                raise proxy_e

        if response is None:
            raise RuntimeError("Failed to get a response from SearXNG instance")

        data = response.json()

        results = []
        # SearXNG JSON response usually has a 'results' key
        for item in data.get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=item.get("score", 1.0),
                engine=f"searxng@{instance_url}"
            ))
        return results
