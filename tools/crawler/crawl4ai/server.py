"""
Crawl4AI Crawler MCP Server

A FastMCP 3+ based MCP server that provides web crawling and content extraction
functionality using the crawl4ai library.
"""

import asyncio
from typing import Optional, List, Union, Dict, Any, Callable
from fastmcp import FastMCP
from crawl4ai import BrowserConfig, CrawlerRunConfig, PruningContentFilter, DefaultMarkdownGenerator
from crawl4ai.docker_client import Crawl4aiDockerClient
import random
from urllib.parse import urlparse


# Initialize FastMCP server
mcp = FastMCP(
    name="crawl4ai-crawler"
)

# Target server configuration
CRAWL4AI_SERVER_URL = "http://192.168.0.188:11235"

# Semaphore to limit parallel requests to 10
CRAWL_SEMAPHORE = asyncio.Semaphore(10)

def get_browser_config(url: str = "") -> BrowserConfig:
    """Helper to create a BrowserConfig from merged configs."""
    domain = urlparse(url).netloc
    domain_config = None
    for d in DOMAIN_CONFIGS:
        if d in domain:
            domain_config = DOMAIN_CONFIGS[d]
            break

    merged_config = deep_merge(DEFAULT_CONFIG, domain_config or {})
    browser_settings = merged_config.get("browser", {})
    viewport = browser_settings.get("viewport", {})

    return BrowserConfig(
        headless=browser_settings.get("headless", True),
        enable_stealth=browser_settings.get("stealth", True),
        viewport_width=viewport.get("width", 1080),
        viewport_height=viewport.get("height", 600),
        user_agent=browser_settings.get("user_agent"),
        extra_args=browser_settings.get("args", []),
    )

def get_run_config(url: str = "") -> CrawlerRunConfig:
    """Helper to create a CrawlerRunConfig from merged configs."""
    domain = urlparse(url).netloc
    domain_config = None
    for d in DOMAIN_CONFIGS:
        if d in domain:
            domain_config = DOMAIN_CONFIGS[d]
            break

    merged_config = deep_merge(DEFAULT_CONFIG, domain_config or {})
    crawl_settings = merged_config.get("crawl", {})

    # 1. Create your filter
    prune_filter = PruningContentFilter(
        threshold=0.48,
        threshold_type="dynamic",
        min_word_threshold=5
    )

    # 2. Create a Markdown generator with the filter
    md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)
    return CrawlerRunConfig(
        delay_before_return_html=crawl_settings.get("delay_before_return_html"),
        simulate_user=crawl_settings.get("simulate_user", False),
        locale=crawl_settings.get("locale"),
        timezone_id=crawl_settings.get("timezone_id"),
        markdown_generator=md_generator,
    )

@mcp.tool()
async def crawl_url(url: str, extract_markdown: bool = True) -> str:
    """
    Crawl a URL and extract its content using stealth configurations.

    Args:
        url: The URL to crawl.
        extract_markdown: Whether to return the content as markdown. Defaults to True.
    """
    async with CRAWL_SEMAPHORE:
        async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL) as client:
            # We skip authentication if the server doesn't require it or handles it via API key
            # If authentication is needed, it should be added here.

            result = await client.crawl(
                urls=[url],
                browser_config=get_browser_config(url),
                crawler_config=get_run_config(url)
            )

            if not result.success:
                return f"Error crawling {url}: {getattr(result, 'error', 'Unknown error')}"

            if extract_markdown:
               # return result.markdown
                # Try to return fit_markdown for a cleaner result, fallback to raw markdown
                if hasattr(result, 'markdown') and hasattr(result.markdown, 'fit_markdown'):
                    return result.markdown.fit_markdown
                return getattr(result, 'markdown', 'No markdown content available')
            else:
                # return result.html
                return getattr(result, 'html', 'No HTML content available')

@mcp.tool()
async def crawl_multiple_urls(urls: list[str]) -> dict:
    """
    Crawl multiple URLs in parallel (respecting the global concurrency limit).

    Args:
        urls: A list of URLs to crawl.
    """
    async def limited_crawl(url):
        async with CRAWL_SEMAPHORE:
            async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL) as client:
                result = await client.crawl(
                    urls=[url],
                    browser_config=get_browser_config(url),
                    crawler_config=get_run_config(url)
                )
                return url, result

    tasks = [limited_crawl(url) for url in urls]
    results = await asyncio.gather(*tasks)

    output = {}
    for url, result in results:
        if result.success:
            output[url] = result.markdown
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
            "width": random.choice([1280, 1366, 1440, 1920]),
            "height": random.choice([720, 768, 900, 1080]),
        },

        "user_agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
        ]),

        "locale": "en-US",
        "timezone": "America/Toronto",
    },

    "crawl": {
        "delay_before_return_html": random.uniform(2.0, 5.0),
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

# ----------------------------
# 4. MAIN FETCH FUNCTION
# ----------------------------

async def fetch_md(client, url, config_override=None):
    domain = urlparse(url).netloc

    domain_config = None
    for d in DOMAIN_CONFIGS:
        if d in domain:
            domain_config = DOMAIN_CONFIGS[d]
            break

    # Merge configs: DEFAULT → DOMAIN → REQUEST
    merged_config = deep_merge(DEFAULT_CONFIG, domain_config or {})
    merged_config = deep_merge(merged_config, config_override or {})

    # Map the merged dictionary to Crawl4AI config objects
    # BrowserConfig is used for browser-level settings (headless, stealth, etc.)
    # CrawlerRunConfig is used for request-level settings (locale, timezone, etc.)

    run_cfg = CrawlerRunConfig()

    # Map dictionary values to CrawlerRunConfig attributes if they exist
    crawl_settings = merged_config.get("crawl", {})
    for attr in ["delay_before_content", "simulate_user", "scroll", "max_scroll", "wait_for", "locale", "timezone_id"]:
        if hasattr(run_cfg, attr) and attr in crawl_settings:
            setattr(run_cfg, attr, crawl_settings[attr])

    # Use arun with the run_cfg
    result = await client.arun(
        url=url,
        config=run_cfg
    )

    return result


if __name__ == "__main__":
    async def run_test():
        test_url = "https://www.google.com/search?q=toronto+news&tbs=qdr:d"
        print(f"Testing crawl_url tool: {test_url}")

        try:
            # Call the tool function directly
            result = await crawl_url(url=test_url)

            if "Error crawling" not in result:
                print("SUCCESS!")
                print("\n--- Full Response ---\n")
                print(result)
                print("\n--- End of Response ---")
            else:
                print(f"FAILED: {result}")
        except Exception as e:
            print(f"Unexpected Error: {e}")

    asyncio.run(run_test())
