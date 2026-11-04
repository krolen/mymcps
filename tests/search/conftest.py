import pytest_asyncio

from tools.common.http_client import close_client


@pytest_asyncio.fixture(autouse=True)
async def close_shared_search_sessions():
    # Each test has its own event loop. Close loop-bound clients before it ends.
    yield
    await close_client()
