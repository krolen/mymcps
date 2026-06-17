import asyncio
import pytest
from tools.crawler.crawl4ai.client import Crawl4AIClient
from crawl4ai.docker_client import Crawl4aiDockerClient
from tools.crawler.constants import CRAWL4AI_SERVER_URL

@pytest.mark.asyncio
async def test_kill_browser_integration():
    """
    Integration test to verify browser killing functionality on the real server.
    """
    print(f"Connecting to crawl server at {CRAWL4AI_SERVER_URL}...")
    
    async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL) as docker_client:
        crawler = Crawl4AIClient(docker_client)
        
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