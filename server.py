import logging
import os
from contextlib import asynccontextmanager

from crawl4ai import Crawl4aiDockerClient
from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger
from fastmcp.server.providers.filesystem import FileSystemProvider
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from tools.crawler.crawl4ai.server import lifespan as crawl_lifespan

os.environ["DANGEROUSLY_OMIT_AUTH"] = "true"

to_client_logger = get_logger(name="fastmcp.server.context.to_client")
to_client_logger.setLevel(level=logging.DEBUG)

# Create the main MCP server
# mcp = FastMCP(name="Data Server", instructions="""
#   This server provides useful tools to get additional information such as time, web search
# """)
# remote_proxy = create_proxy(
#     "http://localhost:7100/mcp",
#     name="Searxng web search"
# )
#
# @mcp.tool()
# def run_tool_a(input: str) -> str:
#     result = subprocess.run(
#         ["/envs/tool_a/bin/python", "tool_a_runner.py", input],
#         capture_output=True
#     )
#     return result.stdout.decode()
# # Mount the sub-servers
# mcp.mount(time_mcp, namespace = "timeserver")
# mcp.mount(remote_proxy, namespace = "Web_Search_MCP_server")
# mcp.mount(weather_mcp)
# mcp.mount(searxng_mcp)

@asynccontextmanager
async def lifespan(app: FastMCP):
    async with crawl_lifespan(app) as crawl_state:
        yield {**crawl_state}

mcp = FastMCP(name="my-server", lifespan=lifespan)
mcp.add_provider(FileSystemProvider("./tools", reload=True))

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
    print("Starting FastMCP v3 server with CORS at /mcp")
    uvicorn.run("server:app", host="0.0.0.0", port=7000, reload=True)
