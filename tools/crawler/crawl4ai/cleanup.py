import asyncio
import logging

from tools.crawler.constants import (
    BROWSER_CLEANUP_INTERVAL_SECONDS,
    BROWSER_IDLE_TIMEOUT_SECONDS,
    CRAWL_TIMEOUT_SECONDS,
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

                overdue_signatures = {
                    request.config_sig
                    for request in active_requests
                    if request.duration is not None
                    and request.duration > CRAWL_TIMEOUT_SECONDS
                    and request.config_sig
                }
                for browser in browsers:
                    overdue = any(
                        sig.startswith(browser.sig) or browser.sig.startswith(sig)
                        for sig in overdue_signatures
                    )
                    if overdue and not browser.killable:
                        logger.error(
                            "Overdue request uses protected browser %s; remote recovery required",
                            browser.sig,
                        )
                    if not browser.killable or (
                        not overdue and browser.last_used_seconds <= BROWSER_IDLE_TIMEOUT_SECONDS
                    ):
                        continue
                    logger.info(
                        "Killing browser: %s (overdue request=%s, last used %ss ago)",
                        browser.sig, overdue, browser.last_used_seconds,
                    )
                    if not await crawler.kill_browser(browser.sig):
                        logger.warning("Could not kill idle browser: %s", browser.sig)
            except Exception:
                logger.exception("Error during cleanup cycle")

            await asyncio.sleep(BROWSER_CLEANUP_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.info("Crawler cleanup background task shutting down...")
