import logging
import asyncio
from typing import List, Set

import httpx

from tools.search.constants import SearchConstants
from tools.search.models import SearchResult, SearchEngine
from .browser_client import get_browser_session, get_browser_session_with_proxy
from .manager import SearxSpaceManager
from .parser import parse_searxng_html
from .shortcuts import SearchEngineShortcut, parse_shortcuts

logger = logging.getLogger(__name__)


class SearxSpaceEngine(SearchEngine):
    def __init__(self, manager: SearxSpaceManager = SearxSpaceManager()):
        self.manager = manager

    async def search(self, query: str, params: dict = None) -> List[SearchResult]:
        params = params or {}

        # 1. Resolve requested engines and clean query
        requested_engines, cleaned_query = self._resolve_engines(query, params)
        params["engines"] = ",".join(requested_engines)

        all_results: List[SearchResult] = []
        seen_urls: Set[str] = set()

        # 2. Get all candidate instances sorted by priority
        await self.manager.get_instances()
        # Request a large number of candidates to allow for fallbacks
        candidates = self.manager.get_best_instances(requested_engines, count=50)

        # Prioritize local instance and remove duplicates
        local_url = SearchConstants.SEARXNG_URL
        candidates = [local_url] + [c for c in candidates if c != local_url]

        if not candidates:
            logger.warning("No instances found that support any of the requested engines")
            return []

        logger.info(f"Candidate instances for query '{cleaned_query}': {', '.join(candidates)}")

        success_count = 0
        for instance_url in candidates:
            if success_count >= 3:
                break

            try:
                results = await self._execute_instance_search(instance_url, cleaned_query, params)
                if results:
                    for res in results:
                        if res.url not in seen_urls:
                            all_results.append(res)
                            seen_urls.add(res.url)
                    success_count += 1
            except Exception as e:
                response = getattr(e, 'response', None)
                status_code = getattr(response, 'status_code', None)
                if status_code == 429:
                    logger.warning(
                        f"Instance {instance_url} returned 429 (Too Many Requests). Quarantining for 2 hours.")
                    self.manager.quarantine_instance(instance_url, 2)
                else:
                    logger.warning(
                        f"Instance {instance_url} failed ({type(e).__name__}: {e}). Quarantining for 24 hours.")
                    self.manager.quarantine_instance(instance_url, 24)

        # 3. Join results: sort by score and apply limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        limit_ : str | int = params.get("limit")
        if limit_ is not None:
            return all_results[:int(limit_)]
        return all_results

    def _resolve_engines(self, query: str, params: dict) -> tuple[List[str], str]:
        # Parse shortcuts for instance selection
        requested_engines, cleaned_query = parse_shortcuts(query)

        # Also check for engines provided in params (as a comma-separated string)
        if "engines" in params:
            param_engines = params["engines"].split(",") if isinstance(params["engines"], str) else []
            # Append param engines to requested_engines while preserving order and removing duplicates
            for eng in param_engines:
                if eng and eng not in requested_engines:
                    requested_engines.append(eng)

        # If no engine specified, use prioritized list matching the general engines in SearchEngineShortcut
        if not requested_engines:
            requested_engines = [
                SearchEngineShortcut.get_engine_name(SearchEngineShortcut.GOOGLE.value),
                SearchEngineShortcut.get_engine_name(SearchEngineShortcut.BING.value),
                SearchEngineShortcut.get_engine_name(SearchEngineShortcut.DDG.value),
                SearchEngineShortcut.get_engine_name(SearchEngineShortcut.BRAVE.value),
            ]

        return requested_engines, cleaned_query

    async def _request_with_fallback(self, instance_url: str, search_url: str, params: dict):
        """Attempts a request with a standard session, falling back to a proxy if a 429 is encountered."""
        client = await get_browser_session()
        response = await client.get(search_url, params=params)
        # response = await client.post(search_url, data=params)

        if response.status_code == 200:
            logger.info(f"Instance {instance_url}: got 200")
            return response

        if response.status_code == 429:
            logger.info(f"Instance {instance_url} returned 429, trying with proxy...")
            # Fallback to proxy session
            proxy_client = await get_browser_session_with_proxy()
            response = await proxy_client.get(search_url, params=params, allow_redirects=False)
            # response = await proxy_client.post(search_url, data=params, allow_redirects=False)
            if response.status_code == 200:
                logger.info(f"Instance {instance_url} proxy call succeed")
                return response

        return response

    async def _execute_instance_search(self, instance_url: str, query: str, params) -> List[SearchResult]:
        search_url = f"{instance_url.rstrip('/')}/search"
        logger.info(f"Executing search on instance {instance_url} for query: {query}")

        # Create a single copy to avoid mutating the original input params
        search_params = params.copy() if params else {}
        search_params["q"] = query

        # 1. Try JSON first (preferred)
        search_params["format"] = "json"
        response = await self._request_with_fallback(instance_url, search_url, search_params)

        if response and response.status_code == 200:
            parsed = self._parse_json_response(response, instance_url)
            if parsed:
                logger.info(f"JSON search successful on {instance_url}, found {len(parsed)} results")
                return parsed

        if response:
            logger.warning(f"JSON search failed with status {response.status_code} on {instance_url}, falling back to HTML")
        else:
            logger.warning(f"JSON search returned no response on {instance_url}, falling back to HTML")

        # 2. Fallback: Try without JSON (HTML)
        # We explicitly remove the 'format' key to ensure the server returns HTML instead of attempting JSON again
        search_params.pop("format", None)
        response = await self._request_with_fallback(instance_url, search_url, search_params)

        if response and response.status_code == 200:
            results = self._parse_html_response(response, instance_url, query)
            logger.info(f"HTML search successful on {instance_url}, found {len(results)} results")
            return results

        if response:
            response.raise_for_status()
        else:
            raise RuntimeError(f"No response received from {instance_url}")

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
