import asyncio
import time

import pytest
from fastmcp import Client, FastMCP
from fastmcp.tools.base import Tool

from tools.common.optional_mcp import OptionalMCPProvider


@pytest.mark.asyncio
async def test_optional_backend_recovers_without_stalling_local_tools(monkeypatch):
    provider = OptionalMCPProvider(
        "http://127.0.0.1:19876/mcp",
        "test-token",
        discovery_timeout=0.05,
        retry_interval=0.1,
    )
    attempts = 0

    async def unavailable():
        nonlocal attempts
        attempts += 1
        await asyncio.sleep(10)

    monkeypatch.setattr(provider._proxy, "list_tools", unavailable)

    server = FastMCP("optional-backend-test")

    @server.tool()
    async def local_ok() -> str:
        return "ok"

    server.add_provider(provider, namespace="chrome")

    async with Client(server) as client:
        start = time.monotonic()
        names = [tool.name for tool in await client.list_tools()]
        assert names == ["local_ok"]
        assert time.monotonic() - start < 1
        assert attempts == 1

        start = time.monotonic()
        result = await client.call_tool("local_ok", {})
        assert result.content[0].text == "ok"
        assert time.monotonic() - start < 1
        assert attempts == 1

        async def ping() -> str:
            return "pong"

        remote_tool = Tool.from_function(ping)

        async def available():
            nonlocal attempts
            attempts += 1
            return [remote_tool]

        async def get_tool(name, version=None):
            return remote_tool if name == "ping" else None

        monkeypatch.setattr(provider._proxy, "list_tools", available)
        monkeypatch.setattr(provider._proxy, "get_tool", get_tool)

        assert [tool.name for tool in await client.list_tools()] == ["local_ok"]
        assert attempts == 1

        await asyncio.sleep(0.11)
        names = [tool.name for tool in await client.list_tools()]
        assert set(names) == {"chrome_ping", "local_ok"}
        assert provider.available
        result = await client.call_tool("chrome_ping", {})
        assert result.content[0].text == "pong"
