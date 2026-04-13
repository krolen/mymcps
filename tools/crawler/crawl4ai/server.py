"""
Crawl4AI Crawler MCP Server

A FastMCP 3+ based MCP server that provides web crawling and content extraction
functionality using the crawl4ai library.
"""

import asyncio
import random
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from crawl4ai import BrowserConfig, CrawlerRunConfig, PruningContentFilter, DefaultMarkdownGenerator
from crawl4ai.docker_client import Crawl4aiDockerClient
from fastmcp import FastMCP, Context

CRAWL4AI_SERVER_URL = "http://192.168.0.188:11235"

# Semaphore to limit parallel requests to 10
CRAWL_SEMAPHORE = asyncio.Semaphore(10)

@asynccontextmanager
async def lifespan(app):
    async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL) as client:
        yield {"client": client}


mcp = FastMCP(name="crawl4ai-crawler", lifespan=lifespan)

# Target server configuration
def get_domain_config(url: str) -> dict:
    """Extracts domain-specific configuration overrides for a given URL."""
    domain = urlparse(url).netloc
    for d in DOMAIN_CONFIGS:
        if d in domain:
            return DOMAIN_CONFIGS[d]
    return {}


def get_browser_config(url: str = "") -> BrowserConfig:
    """Helper to create a BrowserConfig from merged configs."""
    domain_config = get_domain_config(url)
    merged_config = deep_merge(DEFAULT_CONFIG, domain_config)
    browser_settings = merged_config.get("browser", {})
    viewport = browser_settings.get("viewport", {})

    # Dynamic randomization per request
    actual_viewport_width = random.choice([1280, 1366, 1440, 1920]) if not viewport.get("width") else viewport.get(
        "width")
    actual_viewport_height = random.choice([720, 768, 900, 1080]) if not viewport.get("height") else viewport.get(
        "height")
    actual_user_agent = random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    ]) if not browser_settings.get("user_agent") else browser_settings.get("user_agent")

    return BrowserConfig(
        headless=browser_settings.get("headless", True),
        enable_stealth=browser_settings.get("stealth", True),
        viewport_width=actual_viewport_width,
        viewport_height=actual_viewport_height,
        user_agent=actual_user_agent,
        extra_args=browser_settings.get("args", []),
    )


def get_run_config(url: str = "") -> CrawlerRunConfig:
    """Helper to create a CrawlerRunConfig from merged configs."""
    domain_config = get_domain_config(url)
    merged_config = deep_merge(DEFAULT_CONFIG, domain_config)
    crawl_settings = merged_config.get("crawl", {})

    # Dynamic randomization per request
    actual_delay = random.uniform(2.0, 5.0) if crawl_settings.get(
        "delay_before_return_html") is None else crawl_settings.get("delay_before_return_html")

    # 1. Create your filter
    prune_filter = PruningContentFilter(
        threshold=0.48,
        threshold_type="dynamic",
        min_word_threshold=5
    )

    # 2. Create a Markdown generator with the filter
    md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)
    return CrawlerRunConfig(
        delay_before_return_html=actual_delay,
        simulate_user=crawl_settings.get("simulate_user", False),
        locale=crawl_settings.get("locale"),
        timezone_id=crawl_settings.get("timezone_id"),
        markdown_generator=md_generator,
    )


async def _crawl_single_url(client: Crawl4aiDockerClient, url: str):
    """
    Private helper to perform a single crawl operation.
    Returns the result object on success, or a mock result with success=False on failure.
    """
    async with CRAWL_SEMAPHORE:
        async with client:
            try:
                result = await asyncio.wait_for(
                    client.crawl(
                        urls=[url],
                        browser_config=get_browser_config(url),
                        crawler_config=get_run_config(url)
                    ),
                    timeout=60
                )
                return result
            except asyncio.TimeoutError:
                class TimeoutResult:
                    success = False
                    error = "Request timed out after 60 seconds"

                return TimeoutResult()
            except Exception as e:
                class ErrorResult:
                    success = False
                    error = str(e)

                return ErrorResult()


@mcp.tool()
async def crawl_url(ctx: Context, url: str, extract_markdown: bool = True) -> str:
    """
    Crawl a URL and extract its content using stealth configurations.

    Args:
        url: The URL to crawl.
        extract_markdown: Whether to return the content as markdown. Defaults to True.
    """
    client = ctx.request_context.lifespan_context["client"]
    result = await _crawl_single_url(client, url)

    if not result.success:
        return f"Error crawling {url}: {getattr(result, 'error', 'Unknown error')}"

    if extract_markdown:
        # Try to return fit_markdown for a cleaner result, fallback to raw markdown
        if hasattr(result, 'markdown') and hasattr(result.markdown, 'fit_markdown'):
            return result.markdown.fit_markdown
        return getattr(result, 'markdown', 'No markdown content available')
    else:
        return getattr(result, 'html', 'No HTML content available')


@mcp.tool()
async def crawl_multiple_urls(ctx: Context, urls: list[str]) -> dict[str, str]:
    """
    Crawl multiple URLs in parallel (respecting the global concurrency limit).

    Args:
        urls: A list of URLs to crawl.
    """
    client = ctx.request_context.lifespan_context["client"]

    tasks = [_crawl_single_url(client, url) for url in urls]
    results = await asyncio.gather(*tasks)

    output = {}
    for url, result in zip(urls, results):
        if result.success:
            # Try to return fit_markdown for a cleaner result, fallback to raw markdown
            if hasattr(result, 'markdown') and hasattr(result.markdown, 'fit_markdown'):
                output[url] = result.markdown.fit_markdown
            else:
                output[url] = getattr(result, 'markdown', 'No markdown content available')
        else:
            output[url] = f"Error: {getattr(result, 'error', 'Unknown error')}"

    return output


# ----------------------------
# 1. DEFAULT STEALTH CONFIG
# ----------------------------

DEFAULT_CONFIG = {
    "browser": {
        "headless": True,
        "stealth": True,

        "args": [
            "--headless=new",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],

        "viewport": {
            "width": None,
            "height": None,
        },

        "user_agent": None,
    },

    "crawl": {
        "delay_before_return_html": None,
        "simulate_user": True,
        "scroll": True,
        "max_scroll": random.randint(2, 5),
        "wait_for": "networkidle",
        "locale": "en-US",
        "timezone_id": "America/Toronto",
    },

    # proxy placeholder (VERY IMPORTANT in real usage)
    "proxy": None,
}

# ----------------------------
# 2. DOMAIN-SPECIFIC OVERRIDES
# ----------------------------

DOMAIN_CONFIGS = {
    "google.com": {
        "crawl": {
            "delay_before_content": 6,
            "simulate_user": True,
        }
    },
    "medium.com": {
        "crawl": {
            "scroll": True,
            "max_scroll": 6,
        }
    },
}


# ----------------------------
# 3. DEEP MERGE HELPER
# ----------------------------

def deep_merge(base, override):
    if not override:
        return base

    result = dict(base)

    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v

    return result

if __name__ == "__main__":
    async def run_test():
        test_url = "https://www.google.com/search?q=toronto+news&tbs=qdr:d"
        print(f"Testing crawl_url tool: {test_url}")

        try:
            async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL) as client:
                result = await _crawl_single_url(client, test_url)

                if result.success:
                    print("SUCCESS!")
                    print("\n--- Full Response ---\n")
                    if hasattr(result, 'markdown') and hasattr(result.markdown, 'fit_markdown'):
                        print(result.markdown.fit_markdown)
                    else:
                        print(getattr(result, 'markdown', 'No markdown content available'))
                    print("\n--- End of Response ---")
                else:
                    print(f"FAILED: {getattr(result, 'error', 'Unknown error')}")
        except Exception as e:
            print(f"Unexpected Error: {e}")

    asyncio.run(run_test())