import os

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from timeserver.server import mcp as time_mcp
from weather.server import mcp as weather_mcp
from searxng.server import mcp as searxng_mcp
import logging
from fastmcp.utilities.logging import get_logger


os.environ["DANGEROUSLY_OMIT_AUTH"] = "true"

to_client_logger = get_logger(name="fastmcp.server.context.to_client")
to_client_logger.setLevel(level=logging.DEBUG)

# Create the main MCP server
mcp = FastMCP(name="Data Server", instructions="""
  This server provides useful tools to get additional information
""")

# # Mount the sub-servers
mcp.mount(time_mcp)
mcp.mount(weather_mcp)
mcp.mount(searxng_mcp)

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