from importlib import import_module

import pytest
from fastmcp import Client, FastMCP
from fastmcp.server.providers.filesystem import FileSystemProvider
from fastmcp.tools.base import Tool

create_mcp = import_module("tools.browser-mcp.server").create_mcp
from tools.common.optional_mcp import OptionalMCPProvider


@pytest.mark.asyncio
async def test_disabled(monkeypatch):
    monkeypatch.delenv('CHROME_BRIDGE_URL', raising=False)
    async with Client(create_mcp()) as client:
        assert await client.list_tools() == []


def test_missing_token(monkeypatch):
    monkeypatch.setenv('CHROME_BRIDGE_URL', 'http://localhost:19876/mcp')
    monkeypatch.delenv('CHROME_BRIDGE_TOKEN', raising=False)
    with pytest.raises(RuntimeError, match='CHROME_BRIDGE_TOKEN'):
        create_mcp()


@pytest.mark.asyncio
async def test_mounted_discovery_and_recovery(monkeypatch):
    monkeypatch.setenv('CHROME_BRIDGE_URL', 'http://localhost:19876/mcp')
    monkeypatch.setenv('CHROME_BRIDGE_TOKEN', 'test-token')
    providers = []
    original_init = OptionalMCPProvider.__init__

    def init(self, url, token):
        original_init(self, url, token, discovery_timeout=0.05)
        providers.append(self)

    monkeypatch.setattr(OptionalMCPProvider, '__init__', init)
    chrome = create_mcp()
    provider = providers[0]

    async def offline():
        raise ConnectionError('offline')

    monkeypatch.setattr(provider._proxy, 'list_tools', offline)
    app = FastMCP('test')
    app.add_provider(FileSystemProvider('./tools/browser-mcp', reload=True))
    app.mount(chrome)

    @app.tool()
    def local_ok():
        return 'ok'

    async with Client(app, timeout=3) as client:
        assert {t.name for t in await client.list_tools()} == {'local_ok', 'chrome_bridge_status'}
        status = await client.call_tool('chrome_bridge_status')
        assert status.data['available'] is False
        assert (await client.call_tool('local_ok')).data == 'ok'

        def ping():
            return 'pong'

        remote = Tool.from_function(ping)

        async def online():
            return [remote]

        async def get_tool(name, version=None):
            return remote if name == 'ping' else None

        monkeypatch.setattr(provider._proxy, 'list_tools', online)
        monkeypatch.setattr(provider._proxy, 'get_tool', get_tool)
        provider._retry_at = 0
        names = [t.name for t in await client.list_tools()]
        assert sorted(names) == ['chrome_bridge_status', 'chrome_ping', 'local_ok']
        assert (await client.call_tool('chrome_ping')).data == 'pong'
        assert (await client.call_tool('chrome_bridge_status')).data['available'] is True
