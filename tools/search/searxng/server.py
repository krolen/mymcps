"""
SearXNG Search MCP Server

A FastMCP 3+ based MCP server that provides search functionality using SearXNG.
Connects to a local SearXNG instance at http://192.168.0.100:8089
"""

import httpx
from typing import Optional, List
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    name="searxng-search"
)

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
    engines: Optional[List[str]] = None,
    time_range: Optional[str] = None,
    limit: int = 30,
    lang: str = "en-CA"
) -> dict:
    """
    Perform a search using SearXNG.
    
    Args:
        query: The search query.
        engines: List of specific engines to use. If omitted, SearXNG uses defaults.
                 Check 'search/searxng/list-available-engines' to see which engine fits your needs.
        time_range: Filter results by time (day, week, month, year). 
                    Only works for: brave, duckduckgo, bing, reddit, arxiv, google news.
                    IMPORTANT: If you include engines that do NOT support time_range 
                    while providing a time_range parameter, those engines will likely 
                    return zero results. If you need both fresh results and authoritative 
                    evergreen results, perform two separate search calls.
        limit: Max number of results to return.
        lang: Language code (default: en-CA).
    """
    params = {
        "q": query,
        "format": "json",
        "language": lang,
    }
    
    if engines:
        params["engines"] = ",".join(engines)
    
    if time_range:
        params["time_range"] = time_range

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{SEARXNG_URL}/search", params=params)
            response.raise_for_status()
            data = response.json()
            
            # Reorder results by score descending
            results = data.get("results", [])
            sorted_results = sorted(
                results, 
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
