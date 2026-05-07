import os
import logging
from typing import Optional
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

_session: Optional[AsyncSession] = None
_proxy_session: Optional[AsyncSession] = None

async def get_browser_session() -> AsyncSession:
    """
    Returns a shared curl_cffi AsyncSession configured to impersonate a browser.
    """
    global _session
    if _session is None:
        # Impersonating Chrome allows bypassing many bot detection systems
        _session = AsyncSession(impersonate="chrome120", timeout=10.0, allow_redirects=False)
    return _session

async def get_browser_session_with_proxy() -> AsyncSession:
    """
    Returns a shared curl_cffi AsyncSession configured with a proxy if available.
    """
    global _proxy_session
    proxy = os.getenv("RES_PROXY")
    if not proxy:
        return await get_browser_session()

    if _proxy_session is None:
        # curl_cffi doesn't support shared sessions with different proxy settings
        # so we create a separate session for the proxy
        _proxy_session = AsyncSession(impersonate="chrome120", proxy=proxy, timeout=10.0, allow_redirects=False)

    return _proxy_session

async def close_browser_session():
    """
    Closes the browser session.
    """
    global _session, _proxy_session
    if _session is not None:
        await _session.close()
        _session = None
    if _proxy_session is not None:
        await _proxy_session.close()
        _proxy_session = None
