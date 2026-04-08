import logging
from fastmcp import FastMCP
from datetime import datetime

logging.basicConfig(level=logging.INFO)

mcp = FastMCP("Time Server")

@mcp.resource(uri="resource://time")  # Added uri parameter
def time() -> str:
    """
    The current local time in ISO format.
    Use this resource when the user asks for the current time or date.
    """
    logging.info("time resource accessed")
    return datetime.now().isoformat()

@mcp.tool(name="utils/time")
def time() -> str:
    """
    The current local time in ISO format.
    Use this resource when the user asks for the current time or date.
    """
    logging.info("time resource accessed")
    return datetime.now().isoformat()
