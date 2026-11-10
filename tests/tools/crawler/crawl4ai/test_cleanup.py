import asyncio
import os
import pytest
from tools.crawler.crawl4ai.client import Crawl4AIClient
from crawl4ai.docker_client import Crawl4aiDockerClient
from tools.crawler.constants import CRAWL4AI_SERVER_URL

@pytest.mark.asyncio
async def test_kill_browser_integration():
    """
    Integration test to verify browser killing functionality on the real server.
    """
    api_token = os.getenv("CRAWL4AI_API_TOKEN")
    if not api_token:
        pytest.skip("CRAWL4AI_API_TOKEN is required for Crawl4AI integration tests")

    print(f"Connecting to crawl server at {CRAWL4AI_SERVER_URL}...")
    
    async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL) as docker_client:
        crawler = Crawl4AIClient(docker_client, api_token=api_token)
        
        # 1. Trigger a crawl to ensure a browser is created
        print("Triggering crawl to create a browser session...")
        await crawler.crawl_single_url("https://www.google.com", session_id="test_cleanup_session")
        
        # 2. List browsers and find our session
        print("Listing browsers...")
        browsers = await crawler.list_browsers()
        
        # We look for any killable browser or specifically the one we might have created
        # Since we used a session_id, it should be in the list.
        target_browser = None
        for b in browsers:
            # In a real scenario, we'd map session_id to sig if the API provided it, 
            # but here we just need ANY killable browser to test the 'kill' functionality.
            if b.killable:
                target_browser = b
                break
        
        if not target_browser:
            pytest.fail("No killable browsers found to test cleanup")
            
        sig = target_browser.sig
        print(f"Found killable browser with sig: {sig}")
        
        # 3. Kill the browser
        print(f"Killing browser {sig}...")
        success = await crawler.kill_browser(sig)
        assert success is True, "Failed to send kill command to server"
        
        # 4. Verify it's gone
        print("Verifying browser is removed...")
        updated_browsers = await crawler.list_browsers()
        sigs = [b.sig for b in updated_browsers]
        
        assert sig not in sigs, f"Browser {sig} was not removed from the pool"
        print("Successfully verified browser removal.")

if __name__ == "__main__":
    # Allow running the test directly via python
    asyncio.run(test_kill_browser_integration())


@pytest.mark.asyncio
@pytest.mark.parametrize("kill_succeeds", [True, False])
async def test_local_cleanup_preserves_warm_browsers_and_evicts_stale_ones(monkeypatch, kill_succeeds):
    from unittest.mock import AsyncMock, MagicMock, call
    from tools.crawler.constants import BROWSER_CLEANUP_INTERVAL_SECONDS, BROWSER_IDLE_TIMEOUT_SECONDS
    from tools.crawler.crawl4ai.cleanup import run_cleanup_loop

    crawler = AsyncMock()
    crawler.list_active_requests.return_value = []
    crawler.list_browsers.return_value = [
        MagicMock(killable=True, last_used_seconds=31, sig="warm"),
        MagicMock(killable=True, last_used_seconds=BROWSER_IDLE_TIMEOUT_SECONDS, sig="at-threshold"),
        MagicMock(killable=False, last_used_seconds=3600, sig="protected"),
        MagicMock(killable=True, last_used_seconds=BROWSER_IDLE_TIMEOUT_SECONDS + 1, sig="stale"),
        MagicMock(killable=True, last_used_seconds=3600, sig="also-stale"),
    ]
    crawler.kill_browser.return_value = kill_succeeds
    # Stop after one cycle, including when a kill reports failure.
    sleep = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr("tools.crawler.crawl4ai.cleanup.asyncio.sleep", sleep)
    await run_cleanup_loop(crawler)
    crawler.list_active_requests.assert_awaited_once()
    crawler.list_browsers.assert_awaited_once()
    assert crawler.kill_browser.await_args_list == [call("stale"), call("also-stale")]
    sleep.assert_awaited_once_with(BROWSER_CLEANUP_INTERVAL_SECONDS)


@pytest.mark.asyncio
async def test_overdue_request_kills_matching_warm_browser(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from tools.crawler.models import RequestStatus
    from tools.crawler.crawl4ai.cleanup import run_cleanup_loop

    crawler = AsyncMock()
    # Actual monitor shape: epoch timestamp, elapsed, no status.
    crawler.list_active_requests.return_value = [
        RequestStatus(id="hung", url="https://example.com",
                      start_time=1700000000.0, elapsed=70000,
                      config_sig="abcdef012345"),
        RequestStatus(id="fresh", url="https://example.org",
                      elapsed=10, config_sig="fresh"),
    ]
    crawler.list_browsers.return_value = [
        MagicMock(sig="abcdef01", killable=True, last_used_seconds=0),
        MagicMock(sig="fresh", killable=True, last_used_seconds=0),
    ]
    monkeypatch.setattr("tools.crawler.crawl4ai.cleanup.asyncio.sleep",
                        AsyncMock(side_effect=asyncio.CancelledError))
    await run_cleanup_loop(crawler)
    crawler.kill_browser.assert_awaited_once_with("abcdef01")
