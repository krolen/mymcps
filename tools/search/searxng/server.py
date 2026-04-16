"""
SearXNG Search MCP Server

A FastMCP 3+ based MCP server that provides search functionality using SearXNG.
Connects to a local SearXNG instance at http://192.168.0.100:8089
"""

import logging
from typing import Optional, List

from fastmcp import FastMCP, Context

from tools.common.http_client import get_client
from tools.search.constants import SearchConstants as SC
from tools.search.models import SearchResult, SearXNGResponse
from tools.search.modules.bing import engine as bing_engine
from tools.search.modules.brave import engine as brave_engine
from tools.search.modules.ddg import engine as ddg_engine

# Engine to module mapping
ENGINE_MODULES = {
    "duckduckgo": ddg_engine,
    "brave": brave_engine,
    "bing": bing_engine,
}

# Initialize FastMCP server
mcp = FastMCP(
    name="searxng-search"
)

logger = logging.getLogger("searxng-search")

# SearXNG server configuration
SEARXNG_URL = SC.SEARXNG_URL

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


async def _fetch_module_results(
    ctx: Context,
    query: str,
    time_range: Optional[str],
    limit: int,
    engines: List[str],
    all_results: List[SearchResult],
    seen_urls: set
):
    """Helper to fetch results from search modules and add them to the results list."""
    for eng in engines:
        try:
            mod_results = await ENGINE_MODULES[eng].search(ctx=ctx, query=query, time_range=time_range, limit=limit)
            for r in mod_results:
                url = r.url
                if url and url not in seen_urls:
                    all_results.append(r)
                    seen_urls.add(url)
        except Exception as e:
            logger.error(f"Error calling module {eng} for query '{query}': {e}")


def _format_results(
    query: str,
    all_results: List[SearchResult],
    limit: int,
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
    final_results = sorted_results[:limit]

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
    name="web_searxng_search"
)
async def search(
        ctx: Context,
        query: str,
        my_search_engines: List[str],
        time_range: Optional[str] = None,
        limit: int = 30
) -> dict:
    """
    Perform a search using SearXNG.

    CRITICAL DEPENDENCY: To get accurate, time-sensitive data, you MUST FIRST call 
    'web_searxng_list_engines' to identify which my_search_engines are available and which
    ones support 'time_range'.
    
    If you provide a 'time_range' without specifying 'my_search_engines', this tool 
    will return an error because general defaults often ignore time filters.

    Args:
        ctx: The MCP context.
        query: The search query.
        my_search_engines: List of specific engines to use. (REQUIRED if time_range is used).
                           Obtain the valid list of engines and their capabilities 
                           by calling the 'web_searxng_list_engines' tool.
        time_range: Filter results by time (day, week, month, year). 
                    Only works for engines where 'supports_time_range' is True.
        limit: Max number of results to return.
    """
    # 1. Validate time_range and filter engines
    valid_engines, error_res = _validate_and_filter_engines(my_search_engines, time_range)
    if error_res:
        return error_res
    my_search_engines = valid_engines

    # Handle engines with modules
    engines_with_modules = [eng for eng in (my_search_engines if my_search_engines is not None else []) if eng in ENGINE_MODULES]

    # We'll call modules if SearXNG fails or if we want to supplement results.
    # For now, let's prepare to call them.

    params = {
        "q": query,
        "format": "json",
    }

    if my_search_engines:
        params["engines"] = ",".join(my_search_engines)

    if time_range:
        params["time_range"] = time_range

    try:
        client = ctx.lifespan_context.get("http_client") or get_client()
        response = await client.get(f"{SEARXNG_URL}/search", params=params)
        response.raise_for_status()
        data = response.json()

        # Automatically convert JSON to Pydantic model
        # We merge the query into the data because SearXNG API doesn't return it
        parsed_response = SearXNGResponse.model_validate({**data, "query": query})

        all_results = list(parsed_response.results)
        seen_urls = {r.url for r in all_results if r.url}

        # Fallback for unresponsive engines that have modules
        unresponsive_engines = parsed_response.unresponsive_engines
        engines_to_fallback = [
            eng for eng in engines_with_modules
            if any(ue and ue[0] == eng for ue in unresponsive_engines)
        ]

        if engines_to_fallback:
            await _fetch_module_results(
                ctx=ctx, query=query, time_range=time_range, limit=limit,
                engines=engines_to_fallback, all_results=all_results, seen_urls=seen_urls
            )

        return _format_results(
            query=query,
            all_results=all_results,
            limit=limit,
            search_time=data.get("search_time")
        )
    except Exception as e:
        # SearXNG server itself is unresponsive - use all available modules as fallback
        all_results = []
        seen_urls = set()
        await _fetch_module_results(
            ctx=ctx, query=query, time_range=time_range, limit=limit,
            engines=engines_with_modules, all_results=all_results, seen_urls=seen_urls
        )

        if not all_results:
            return {"error": f"SearXNG unresponsive and no module fallbacks available: {str(e)}"}

        return _format_results(
            query=query,
            all_results=all_results,
            limit=limit,
            search_time=None,
            fallback=True,
            error=str(e)
        )


@mcp.tool(
    name="web_searxng_list_engines"
)
async def list_available_engines() -> dict:
    """
    Returns a comprehensive list of search engines, their descriptions, 
    the categories they cover, and whether they support time-based filtering.
    The LLM should use this to pick the best engine for a specific query.
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
