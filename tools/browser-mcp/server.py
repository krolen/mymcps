"""Optional desktop Chrome bridge composition and tools."""
import os

from fastmcp import FastMCP
from tools.common.optional_mcp import OptionalMCPProvider

INSTRUCTIONS = """chrome_* tool usage:
- Get open page IDs with chrome_list_pages and select a page with chrome_select_page; other chrome_* tools target a page via its pageId.
- Before interacting with page elements, call chrome_take_snapshot and use the element uids it returns (chrome_click, chrome_fill, chrome_hover, chrome_drag, chrome_take_screenshot by element).
- The Chrome bridge is optional. If chrome_* calls fail to connect, call chrome_bridge_status to see whether the bridge is available and when it will retry."""


def create_mcp() -> FastMCP:
    """Build the optional bridge from environment configuration."""
    mcp = FastMCP("chrome-bridge", instructions=INSTRUCTIONS)
    chrome_bridge_url = os.getenv("CHROME_BRIDGE_URL")
    if chrome_bridge_url:
        chrome_bridge_token = os.getenv("CHROME_BRIDGE_TOKEN")
        if not chrome_bridge_token:
            raise RuntimeError("CHROME_BRIDGE_TOKEN is required when CHROME_BRIDGE_URL is set")
        chrome_provider = OptionalMCPProvider(chrome_bridge_url, chrome_bridge_token)
        mcp.add_provider(chrome_provider, namespace="chrome")

        @mcp.tool()
        async def chrome_bridge_status() -> dict[str, float | bool]:
            """Check whether the optional Chrome bridge is available.

            Returns its availability and how many seconds until the next
            discovery retry, while the bridge is offline.
            """
            await chrome_provider.probe()
            return {
                "available": chrome_provider.available,
                "retry_after_seconds": round(chrome_provider.retry_after, 1),
            }
    return mcp


mcp = create_mcp()
