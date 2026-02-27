from fastmcp import FastMCP
import httpx

mcp = FastMCP("Searxng Server")

@mcp.tool()
def web_search(query: str) -> str:
    """Search the web using Searxng and return comprehensive results for LLM usage."""
    url = "http://192.168.0.100:8089/search"
    params = {"q": query, "format": "json"}
    try:
        response = httpx.get(url, params=params)
        response.raise_for_status()
        results = response.json().get("results", [])

        # Format results with more comprehensive information for LLM consumption
        formatted_results = []
        for i, r in enumerate(results[:5], 1):
            result_str = f"Result {i}:\n"
            result_str += f"Title: {r.get('title', 'N/A')}\n"
            result_str += f"URL: {r.get('url', 'N/A')}\n"
            result_str += f"Content Snippet: {r.get('content', 'No content available')}\n"
            result_str += f"Category: {r.get('category', 'N/A')}\n"
            if 'publishedDate' in r:
                result_str += f"Published Date: {r['publishedDate']}\n"
            result_str += "---\n"

        return "\n".join(formatted_results)
    except Exception as e:
        return f"Error searching: {e}"
