"""A tool-only MCP proxy that tolerates an intermittently unavailable backend."""

import asyncio
import logging
import time
from collections.abc import Sequence

import httpx2
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.providers.base import Provider
from fastmcp.server.providers.proxy import ProxyClient, ProxyProvider
from fastmcp.tools.base import Tool
from fastmcp.utilities.versions import VersionSpec


logger = logging.getLogger(__name__)


def _http_client(**kwargs) -> httpx2.AsyncClient:
    # Browser operations may be slow; only connection establishment is short.
    kwargs["timeout"] = httpx2.Timeout(connect=2.0, read=300.0, write=10.0, pool=2.0)
    return httpx2.AsyncClient(**kwargs)


class OptionalMCPProvider(Provider):
    """Skip a down backend quickly, then retry discovery after a cooldown."""

    def __init__(
        self,
        url: str,
        token: str,
        *,
        discovery_timeout: float = 3.0,
        retry_interval: float = 15.0,
    ) -> None:
        super().__init__()
        transport = StreamableHttpTransport(
            url,
            headers={"Authorization": f"Bearer {token}"},
            httpx_client_factory=_http_client,
        )
        self._proxy = ProxyProvider(lambda: ProxyClient(transport))
        self._discovery_timeout = discovery_timeout
        self._retry_interval = retry_interval
        self._retry_at = 0.0
        self._available = False
        self._probe_lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return self._available

    @property
    def retry_after(self) -> float:
        return max(0.0, self._retry_at - time.monotonic())

    async def _run(self, operation, fallback):
        try:
            async with asyncio.timeout(self._discovery_timeout):
                result = await operation()
        except Exception as exc:
            if self._available or self._retry_at == 0.0:
                logger.warning(
                    "Optional MCP backend unavailable (%s): %s",
                    type(exc).__name__,
                    exc,
                )
            self._available = False
            self._retry_at = time.monotonic() + self._retry_interval
            return fallback
        self._available = True
        self._retry_at = 0.0
        return result

    async def _check(self, operation, fallback):
        if self.retry_after:
            return fallback
        if self._available:
            return await self._run(operation, fallback)
        if self._probe_lock.locked():
            return fallback
        async with self._probe_lock:
            if self.retry_after:
                return fallback
            return await self._run(operation, fallback)

    async def probe(self) -> bool:
        await self._list_tools()
        return self._available

    async def _list_tools(self) -> Sequence[Tool]:
        return await self._check(self._proxy.list_tools, [])

    async def _get_tool(
        self, name: str, version: VersionSpec | None = None
    ) -> Tool | None:
        return await self._check(lambda: self._proxy.get_tool(name, version), None)

    async def get_tasks(self):
        # Proxied tools cannot run as background tasks. Avoid probing at startup.
        return []
