import logging
import httpx
import os
from typing import Optional

logger = logging.getLogger("http_client")

# Global shared HTTP client to avoid repeated TCP/TLS handshakes
_client: Optional[httpx.AsyncClient] = None
_proxy_client: Optional[httpx.AsyncClient] = None

def get_client() -> httpx.AsyncClient:
    """
    Returns a shared httpx.AsyncClient instance.
    Initializes it if it doesn't exist or is closed.
    """
    global _client
    if _client is None or _client.is_closed:
        # Default timeout of 30s and follow_redirects=True for general web usage
        _client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    return _client

def get_proxy_client() -> httpx.AsyncClient:
    """
    Returns a shared httpx.AsyncClient instance configured with the RES_PROXY.
    """
    global _proxy_client
    proxy = os.getenv("RES_PROXY")
    if not proxy:
        # Fallback to default client if no proxy is configured
        return get_client()

    if _proxy_client is None or _proxy_client.is_closed:
        _proxy_client = httpx.AsyncClient(proxy=proxy, timeout=30.0, follow_redirects=True)
    return _proxy_client

async def close_client():
    """
    Closes the shared HTTP clients.
    Should be called during server shutdown.
    """
    global _client, _proxy_client
    if _client is not None:
        await _client.aclose()
        _client = None
    if _proxy_client is not None:
        await _proxy_client.aclose()
        _proxy_client = None
