"""
SearXNG Search MCP Server

A FastMCP 3+ based MCP server that provides search functionality using SearXNG.
Connects to a local SearXNG instance at http://192.168.0.100:8089
"""

import asyncio
import logging
from typing import Optional, List

from fastmcp import FastMCP, Context

from tools.common.health_logger import health_logger
from tools.search.constants import SearchConstants as SC
from tools.search.models import SearchResult
from tools.search.searxng.registry import ENGINE_REGISTRY

# Initialize FastMCP server
mcp = FastMCP(
    name="searxng-search"
)

logger = logging.getLogger("searxng-search")

# Engine definitions
ENGINES = SC.ENGINES
TIME_RANGES = SC.TIME_RANGES


def _validate_and_filter_engines(
        my_search_engines: List[str],
        time_range: Optional[str]
) -> tuple[Optional[List[str]], Optional[dict]]:
    """Validates time_range and filters search engines. Returns (valid_engines, error_response)."""
    if time_range and time_range not in TIME_RANGES:
        return None, {"error": f"Invalid time_range. Must be one of: {', '.join(TIME_RANGES)}"}

    if time_range and not my_search_engines:
        return None, {
            "error": "Missing search engines for time-sensitive search.",
            "instruction": "You provided a time_range but no specific engines. General searches often ignore time filters. Please call 'web_searxng_list_engines' to find engines that support time filtering (e.g., 'google news', 'bing') and provide them in the 'my_search_engines' parameter."
        }

    if my_search_engines:
        valid_engines = []
        for eng in my_search_engines:
            if eng not in ENGINES:
                return None, {"error": f"Unknown engine: {eng}. Call 'web_searxng_list_engines' for a valid list."}
            if time_range and not ENGINES[eng]["time_range_support"]:
                continue
            valid_engines.append(eng)

        if not valid_engines:
            return None, {"error": "None of the provided engines support the requested time_range."}

        return valid_engines, None

    return my_search_engines, None


def _format_results(
        query: str,
        all_results: List[SearchResult],
        limit: Optional[int] = None,
        search_time: Optional[float] = None,
        fallback: bool = False,
        error: Optional[str] = None
) -> dict:
    """Helper to sort, slice, and format search results."""
    sorted_results = sorted(
        all_results,
        key=lambda x: x.score,
        reverse=True
    )
    final_results = sorted_results[:limit] if limit is not None else sorted_results

    res = {
        "query": query,
        "result_count": len(final_results),
        "results": [r.model_dump() for r in final_results],
        "search_time": search_time,
        "engines_used": list(set([r.engine for r in final_results]))
    }
    if fallback:
        res["fallback"] = True
    if error:
        res["error"] = error
    return res


@mcp.tool(
    name="web_search"
)
async def search(
        ctx: Context,
        query: str,
        search_engines: List[str] = SC.DEFAULT_SEARCH_ENGINES,
        time_range: Optional[str] = None,
        language: Optional[str] = "en-US",
        limit: Optional[int] = 20
) -> dict:
    """
    **WORKFLOW: Execution Phase.** Perform a web search using SearXNG to find URLs and snippets.

    - **General Search (Wide-Net):** To obtain the most comprehensive results, you MUST leave the search_engines parameter empty.
      ⚠️ CRITICAL: Do NOT manually specify general-purpose engines (e.g., 'google', 'brave', 'bing') in this parameter. Doing so transforms the request into a "Restricted Search," which disables the wide-net optimization and will likely result in fewer or lower-quality results.

    - **Precise Search (Targeted Info):** Use the search_engines parameter ONLY for non-general sources (e.g., 'wikipedia', 'reddit', 'arxiv') discovered via webSearchEngines. Use this only when a general search has failed or when you require a specific domain's perspective.

    - **Time Filtering:** Use `time_range` (day, week, month, year) to filter results.
      **IMPORTANT:** Use time filtering ONLY with engines that support it. If you need to search across both engines that support and don't support time filtering while still applying the filter to the supported ones, you MUST split the operation into two separate search calls.

    Args:
        :param ctx: The MCP context.
        :param query: The search query.
        :param search_engines: Optional list of specific engines to use. Providing targeted engines
                               can improve result quality. You can discover available engines
                               via the 'web_search_engines' tool.
        :param time_range: Filter results by time (day, week, month, year). Works best with
                           engines that support time-based filtering.
        :param limit: Max number of results to return.
        :param language: Ask to return results in certain language. Use format: 'en-US', 'en-CA' and similar
    """
    # 1. Validate time_range and filter engines
    valid_engines, error_res = _validate_and_filter_engines(search_engines, time_range)
    if error_res:
        return error_res
    search_engines = valid_engines

    params = {
        "theme": "simple",
        "language": language,
    }

    if search_engines:
        params["engines"] = ",".join(search_engines)

    if time_range:
        params["time_range"] = time_range

    # 2. Perform the search using registered engines if they are specified
    all_results = []
    seen_urls = set()
    tasks = [
        ENGINE_REGISTRY[eng].search(
            query=query,
            params=params
        )
        for eng in ENGINE_REGISTRY
    ]

    if tasks:
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        for engine_name, result_list in zip(ENGINE_REGISTRY.keys(), results_lists):
            if isinstance(result_list, list):
                health_logger.log_event('search', engine_name, 'success')
                for r in result_list:
                    if r.url and r.url not in seen_urls:
                        all_results.append(r)
                        seen_urls.add(r.url)
            else:
                status = 'blocked' if 'captcha' in str(result_list).lower() or '403' in str(result_list) else 'error'
                health_logger.log_event('search', engine_name, status, str(result_list))
                logger.error(f"Error during polymorphic search for {engine_name}: {result_list}")

    return _format_results(
        query=query,
        all_results=all_results,
        limit=limit
    )


@mcp.tool(
    name="web_search_engines"
)
async def list_available_engines() -> dict:
    """
    **WORKFLOW: Discovery Phase.** Discover all available search engines and their capabilities, including descriptions,
    categories they cover, and time-range support.
    **CRITICAL: You MUST call this tool FIRST whenever a precise, specialized, or targeted search is required to ensure you are using the most appropriate engines available.**
    """
    return {
        "engines": {
            name: {
                "description": data["description"],
                "categories": data["categories"],
                "supports_time_range": data["time_range_support"]
            }
            for name, data in ENGINES.items()
        },
        "supported_time_ranges": TIME_RANGES
    }


if __name__ == "__main__":
    mcp.run()
