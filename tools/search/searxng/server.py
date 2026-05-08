"""
SearXNG Search MCP Server

A FastMCP 3+ based MCP server that provides search functionality using SearXNG.
Connects to a local SearXNG instance at http://192.168.0.100:8089
"""

import asyncio
import logging
from typing import Optional, List

from fastmcp import FastMCP, Context

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
        limit: Optional[int] = None
) -> dict:
    """
    Perform a comprehensive web search using SearXNG to find relevant URLs and snippets.
    Use this tool when you need to find information, discover new URLs, or perform a broad search across multiple engines.

    While providing specific search engines is optional, specifying engines (e.g., 'reddit', 'google', 'bing')
    can significantly improve result quality for specific needs.

    The time_range feature (day, week, month, year) is available to filter results, and it typically
    works best when combined with specific engines that support time-based filtering.

    Args:
        :param ctx: The MCP context.
        :param query: The search query.
        :param search_engines: Optional list of specific engines to use. Providing targeted engines
                               can improve result quality. You can discover available engines
                               via the 'web_search_engines' tool.
        :param time_range: Filter results by time (day, week, month, year). Works best with
                           engines that support time-based filtering.
        :param limit: Max number of results to return.
        :param language: Ask to return results in certain language
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
        for result_list in results_lists:
            if isinstance(result_list, list):
                for r in result_list:
                    if r.url and r.url not in seen_urls:
                        all_results.append(r)
                        seen_urls.add(r.url)
            else:
                logger.error(f"Error during polymorphic search: {result_list}")


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
    Discover available search engines and their capabilities, including descriptions,
    categories they cover, and whether they support time-range filtering.

    Use this tool to identify the best search engines for your specific needs and
    optimize the 'search_engines' parameter when calling the 'web_search' tool.
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
