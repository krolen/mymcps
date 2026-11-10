import logging
from datetime import datetime

from fastmcp import FastMCP

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


@mcp.tool(name="utils_time")
def time() -> str:
    """
    Returns the current local time in ISO format.
    Use this instead of assuming the current time from context.
    """
    logging.info("time tool accessed")
    return datetime.now().isoformat()
