import os

from fastmcp import FastMCP
from tools.common.http_client import close_client

from tools.utils.time import mcp as time_mcp
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

# Run the server
if __name__ == "__main__":
    print("Starting FastMCP server in stdio mode...")
    try:
        mcp.run()
    finally:
        import asyncio
        asyncio.run(close_client())
    print("FastMCP server stopped.")