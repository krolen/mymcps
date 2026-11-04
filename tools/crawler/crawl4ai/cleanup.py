import asyncio
import logging

from tools.crawler.constants import (
    BROWSER_CLEANUP_INTERVAL_SECONDS,
    BROWSER_IDLE_TIMEOUT_SECONDS,
)
from tools.crawler.crawl4ai.client import Crawl4AIClient

logger = logging.getLogger("crawl4ai-cleanup")


async def run_cleanup_loop(crawler: Crawl4AIClient):
    """Clean up idle browsers when the remote janitor misses them.

    Allow warm browsers to be reused before evicting eligible idle instances.
    """
    logger.info("Crawler cleanup background task started.")
    try:
        while True:
            try:
                active_requests = await crawler.list_active_requests(status="active")
                browsers = await crawler.list_browsers()
                logger.info(
                    "Monitor: %s active requests, %s active browsers.",
                    len(active_requests), len(browsers),
                )

                for browser in browsers:
                    if not browser.killable or browser.last_used_seconds <= BROWSER_IDLE_TIMEOUT_SECONDS:
                        continue
                    logger.info(
                        "Killing idle browser: %s (last used %ss ago)",
                        browser.sig, browser.last_used_seconds,
                    )
                    if not await crawler.kill_browser(browser.sig):
                        logger.warning("Could not kill idle browser: %s", browser.sig)
            except Exception:
                logger.exception("Error during cleanup cycle")

            await asyncio.sleep(BROWSER_CLEANUP_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.info("Crawler cleanup background task shutting down...")
