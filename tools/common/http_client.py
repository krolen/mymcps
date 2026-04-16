import logging
import httpx
from typing import Optional

logger = logging.getLogger("http_client")

# Global shared HTTP client to avoid repeated TCP/TLS handshakes
_client: Optional[httpx.AsyncClient] = None

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

async def close_client():
    """
    Closes the shared HTTP client.
    Should be called during server shutdown.
    """
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
