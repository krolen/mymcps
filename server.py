import logging
import os
from importlib import import_module
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger
from fastmcp.server.providers.filesystem import FileSystemProvider
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from tools.crawler.crawl4ai.server import lifespan as crawl_lifespan
from tools.common.http_client import close_client
chrome_module = import_module("tools.browser-mcp.server")

os.environ["DANGEROUSLY_OMIT_AUTH"] = "true"

to_client_logger = get_logger(name="fastmcp.server.context.to_client")
to_client_logger.setLevel(level=logging.DEBUG)

@asynccontextmanager
async def lifespan(app: FastMCP):
    async with crawl_lifespan(app) as crawl_state:
        from tools.common.http_client import get_client
        state = {**crawl_state, "http_client": get_client()}
        try:
            yield state
        finally:
            await close_client()

mcp = FastMCP(
    name="my-server",
    lifespan=lifespan,
    instructions="""\
Tools are grouped by prefix: web_* (SearXNG search and Crawl4AI crawling), utils_* (general utilities), and chrome_* (desktop Chrome DevTools browser automation, proxied through the optional Chrome bridge).

""" + chrome_module.INSTRUCTIONS,
)
mcp.add_provider(FileSystemProvider("./tools", reload=True))

mcp.mount(chrome_module.mcp)

# Configure CORS for browser-based clients
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins; use specific origins for security
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "mcp-protocol-version",
            "mcp-session-id",
            "Authorization",
            "Content-Type",
        ],
        expose_headers=["mcp-session-id"],
    )
]

app = mcp.http_app(middleware=middleware, transport="streamable-http")

# Run the server
if __name__ == "__main__":
    import uvicorn
    print("Starting FastMCP v4 server with CORS at /mcp")
    uvicorn.run("server:app", host="0.0.0.0", port=7000, reload=True)
