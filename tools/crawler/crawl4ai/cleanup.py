import asyncio
import logging
from tools.crawler.crawl4ai.client import Crawl4AIClient

logger = logging.getLogger("crawl4ai-cleanup")

async def run_cleanup_loop(crawler: Crawl4AIClient):
    """
    Background task to monitor and cleanup hanging browsers/requests.
    """
    logger.info("Cleanup background task started.")
    try:
        while True:
            # Periodic monitoring and cleanup logic
            try:
                active_requests = await crawler.list_active_requests(status="active")
                browsers = await crawler.list_browsers()
                
                logger.info(f"Monitor: {len(active_requests)} active requests, {len(browsers)} active browsers.")
                
                # Cleanup killable browsers that haven't been used for > 30 seconds
                killed_count = 0
                for browser in browsers:
                    if browser.killable and browser.last_used_seconds > 30:
                        logger.info(f"Killing idle browser: {browser.sig} (last used {browser.last_used_seconds}s ago)")
                        await crawler.kill_browser(browser.sig)
                        killed_count += 1
                
                if killed_count > 0:
                    logger.info(f"Successfully killed {killed_count} idle browsers.")
                
            except Exception as e:
                logger.error(f"Error during cleanup cycle: {e}")
                
            # Run every 30 seconds
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        logger.info("Cleanup background task shutting down...")