from fastmcp import FastMCP
import httpx

mcp = FastMCP("Searxng Server")

@mcp.tool()
def web_search(query: str) -> str:
    """Search the web using Searxng."""
    url = "http://192.168.0.100:8089/search"
    params = {"q": query, "format": "json"}
    try:
        response = httpx.get(url, params=params)
        response.raise_for_status()
        results = response.json().get("results", [])
        return "\n".join([f"{r['title']}: {r['url']}" for r in results[:5]])
    except Exception as e:
        return f"Error searching: {e}"
