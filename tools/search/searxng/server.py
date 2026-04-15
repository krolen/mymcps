"""
SearXNG Search MCP Server

A FastMCP 3+ based MCP server that provides search functionality using SearXNG.
Connects to a local SearXNG instance at http://192.168.0.100:8089
"""

from typing import Optional, List

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel

from tools.search.modules.ddg import engine as ddg_engine

# Initialize FastMCP server
mcp = FastMCP(
    name="searxng-search"
)


class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float = 1.0
    engine: str


# SearXNG server configuration
SEARXNG_URL = "http://192.168.0.100:8089"

# Engine definitions
ENGINES = {
    "brave": {
        "description": "Brave Search - General web search, privacy-focused",
        "categories": ["general"],
        "time_range_support": True
    },
    "duckduckgo": {
        "description": "DuckDuckGo - General web and programming search",
        "categories": ["general", "programming"],
        "time_range_support": True
    },
    "bing": {
        "description": "Microsoft Bing - Comprehensive general web search",
        "categories": ["general", "programming"],
        "time_range_support": True
    },
    "wikipedia": {
        "description": "Wikipedia - Factual encyclopedia knowledge",
        "categories": ["facts"],
        "time_range_support": False
    },
    "wikidata": {
        "description": "Wikidata - Structured factual data",
        "categories": ["facts"],
        "time_range_support": False
    },
    "wolframalpha": {
        "description": "Wolfram Alpha - Computational and mathematical queries",
        "categories": ["compute"],
        "time_range_support": False
    },
    "github": {
        "description": "GitHub - Source code and repository search",
        "categories": ["programming"],
        "time_range_support": False
    },
    "stackexchange": {
        "description": "Stack Exchange - Programming Q&A (Stack Overflow)",
        "categories": ["programming"],
        "time_range_support": False
    },
    "reddit": {
        "description": "Reddit - Community discussions and opinions",
        "categories": ["discussion", "programming"],
        "time_range_support": True
    },
    "hackernews": {
        "description": "Hacker News - Tech, startups, and programming news",
        "categories": ["discussion", "news"],
        "time_range_support": False
    },
    "pypi": {
        "description": "PyPI - Python package search",
        "categories": ["packages"],
        "time_range_support": False
    },
    "npm": {
        "description": "npm - JavaScript/Node package search",
        "categories": ["packages"],
        "time_range_support": False
    },
    "crates": {
        "description": "Crates.io - Rust package search",
        "categories": ["packages"],
        "time_range_support": False
    },
    "dockerhub": {
        "description": "Docker Hub - Container image search",
        "categories": ["packages"],
        "time_range_support": False
    },
    "huggingface": {
        "description": "Hugging Face - AI models and datasets",
        "categories": ["packages", "ai", "programming"],
        "time_range_support": False
    },
    "arxiv": {
        "description": "arXiv - Scientific preprints and research papers",
        "categories": ["science"],
        "time_range_support": True
    },
    "semanticscholar": {
        "description": "Semantic Scholar - AI-powered scientific research",
        "categories": ["science"],
        "time_range_support": False
    },
    "reuters": {
        "description": "Reuters - Global news",
        "categories": ["news"],
        "time_range_support": False
    },
    "google news": {
        "description": "Google News - News aggregation",
        "categories": ["news"],
        "time_range_support": True
    },
    "wikinews": {
        "description": "Wikinews - Collaborative news wiki",
        "categories": ["news", "wikimedia"],
        "time_range_support": False
    },
}

TIME_RANGES = ["day", "week", "month", "year"]


@mcp.tool(
    name="web_searxng_search"
)
async def search(
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
        query: The search query.
        my_search_engines: List of specific engines to use. (REQUIRED if time_range is used).
                           Obtain the valid list of engines and their capabilities 
                           by calling the 'web_searxng_list_engines' tool.
        time_range: Filter results by time (day, week, month, year). 
                    Only works for engines where 'supports_time_range' is True.
        limit: Max number of results to return.
    """
    # 1. Validate time_range value
    if time_range and time_range not in TIME_RANGES:
        return {"error": f"Invalid time_range. Must be one of: {', '.join(TIME_RANGES)}"}

    # 2. Enforce engine specification when using time_range
    if time_range and not my_search_engines:
        return {
            "error": "Missing search engines for time-sensitive search.",
            "instruction": "You provided a time_range but no specific engines. General searches often ignore time filters. Please call 'web_searxng_list_engines' to find engines that support time filtering (e.g., 'google news', 'bing') and provide them in the 'my_search_engines' parameter."
        }

    # 3. Validate and filter engines
    if my_search_engines:
        valid_engines = []
        for eng in my_search_engines:
            if eng not in ENGINES:
                return {"error": f"Unknown engine: {eng}. Call 'web_searxng_list_engines' for a valid list."}

            # If time_range is set, filter out engines that don't support it
            if time_range and not ENGINES[eng]["time_range_support"]:
                continue  # Skip engines that don't support time_range

            valid_engines.append(eng)

        if not valid_engines:
            return {"error": "None of the provided engines support the requested time_range."}

        my_search_engines = valid_engines

    # Handle DuckDuckGo separately if it's requested
    ddg_results = []
    if my_search_engines and "duckduckgo" in my_search_engines:
        # Use our custom DDG module
        ddg_results = await ddg_engine.search(query=query, time_range=time_range, limit=limit)
        # Remove duckduckgo from the list to avoid duplicate search via SearXNG
        my_search_engines = [eng for eng in my_search_engines if eng != "duckduckgo"]

    params = {
        "q": query,
        "format": "json",
    }

    if my_search_engines:
        params["engines"] = ",".join(my_search_engines)

    if time_range:
        params["time_range"] = time_range

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{SEARXNG_URL}/search", params=params)
            response.raise_for_status()
            data = response.json()

            searxng_results = data.get("results", [])

            # Merge with DDG results
            all_results = []
            seen_urls = set()
            for r in searxng_results:
                url = r.get("url")
                if url:
                    all_results.append({
                        "title": r.get("title"),
                        "url": url,
                        "content": r.get("content"),
                        "score": r.get("score", 0),
                        "engine": r.get("engine")
                    })
                    seen_urls.add(url)
                else:
                    continue

            for r in ddg_results:
                url = r.get("url")
                if url and url not in seen_urls:
                    all_results.append({
                        "title": r.get("title"),
                        "url": url,
                        "content": r.get("content"),
                        "score": r.get("score", 0),
                        "engine": r.get("engine")
                    })
                    seen_urls.add(url)
                else:
                    continue

            sorted_results = sorted(
                all_results,
                key=lambda x: x.get("score", 0),
                reverse=True
            )

            final_results = sorted_results[:limit]

            return {
                "query": query,
                "result_count": len(final_results),
                "results": final_results,
                "search_time": data.get("search_time"),
                "engines_used": list(set([r.get("engine") for r in final_results]))
            }
    except Exception as e:
        return {"error": str(e)}


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
