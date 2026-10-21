from datetime import datetime

import pytest
from fastmcp import Client

from server_stdio import mcp


@pytest.mark.asyncio
async def test_stdio_time_tool_is_callable():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert "utils_time" in {tool.name for tool in tools}

        result = await client.call_tool("utils_time")
        assert not result.is_error
        datetime.fromisoformat(result.content[0].text)
