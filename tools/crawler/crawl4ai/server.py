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

# Import the proxy generator

CRAWL4AI_SERVER_URL = "http://192.168.0.188:11235"

# Semaphore to limit parallel requests to 10
CRAWL_SEMAPHORE = asyncio.Semaphore(10)


# Result utility functions
def is_success(result) -> bool:
    """Check if a crawl result indicates success."""
    return getattr(result, 'success', False)


def get_error(result, default: str = "Unknown error") -> str:
    """Extract error message from a crawl result."""
    return getattr(result, 'error', default)


def get_markdown_content(result) -> str:
    """Extract markdown content from a crawl result, preferring fit_markdown."""
    if hasattr(result, 'markdown') and hasattr(result.markdown, 'fit_markdown'):
        return result.markdown.fit_markdown
    return getattr(result, 'markdown', 'No markdown content available')


def get_html_content(result) -> str:
    """Extract HTML content from a crawl result."""
    return getattr(result, 'html', 'No HTML content available')


@asynccontextmanager
async def lifespan(app: FastMCP):
    print("LIFESPAN STARTING")
    async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL) as client:
        print("CLIENT READY:", client)
        yield {"client": client}
    print("LIFESPAN SHUTDOWN")


mcp = FastMCP(name="crawl4ai-crawler", lifespan=lifespan)


# Target server configuration
def get_domain_config(url: str) -> dict:
    """Extracts domain-specific configuration overrides for a given URL."""
    domain = urlparse(url).netloc.lower()
    for config_domain, config in DOMAIN_CONFIGS.items():
        # Check for exact match or subdomain match
        if domain == config_domain or domain.endswith('.' + config_domain):
            return config
    return {}


def get_browser_config(url: str = "", session_id: str = None) -> BrowserConfig:
    """Helper to create a BrowserConfig from merged configs."""
    domain_config = get_domain_config(url)
    merged_config = deep_merge(DEFAULT_CONFIG, domain_config)
    browser_settings = merged_config.get("browser", {})
    viewport = browser_settings.get("viewport", {})

    # Dynamic randomization per request
    local_random = random.Random(session_id)

    actual_viewport_width = viewport.get("width") or local_random.choice([1280, 1366, 1440, 1920])
    actual_viewport_height = viewport.get("height") or local_random.choice([720, 768, 900, 1080])
    actual_user_agent = browser_settings.get("user_agent") or local_random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    ])

    return BrowserConfig(
        headless=browser_settings.get("headless", True),
        enable_stealth=browser_settings.get("stealth", True),
        viewport_width=actual_viewport_width,
        viewport_height=actual_viewport_height,
        user_agent=actual_user_agent,
        extra_args=browser_settings.get("args", []),
        user_data_dir=f"/app/user_data/{session_id}" if session_id else "/app/user_data/default",
        use_persistent_context=True,
        browser_type=browser_settings.get("browser_settings", "chromium"),
        # browser_mode="builtin",
        # use_managed_browser=
        # proxy=[p["server"] for p in get_proxies()],
    )


def get_run_config(url: str = "", session_id: str = None) -> CrawlerRunConfig:
    """Helper to create a CrawlerRunConfig from merged configs."""
    domain_config = get_domain_config(url)
    merged_config = deep_merge(DEFAULT_CONFIG, domain_config)
    crawl_settings = merged_config.get("crawl", {})

    # Dynamic randomization per request
    actual_delay = crawl_settings.get("delay_before_return_html") or random.uniform(2.0, 5.0)

    # 1. Create your filter
    prune_filter = PruningContentFilter(
        threshold=0.48,
        threshold_type="dynamic",
        min_word_threshold=5
    )
    # 2. Create a Markdown generator with the filter
    md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)

    config = CrawlerRunConfig(
        delay_before_return_html=actual_delay,
        simulate_user=crawl_settings.get("simulate_user", False),
        locale=crawl_settings.get("locale"),
        timezone_id=crawl_settings.get("timezone_id"),
        markdown_generator=md_generator,
        only_text=True,
        magic=True,
    )

    if session_id:
        config.session_id = session_id

    return config


# Define result classes outside the function to avoid recreation
class TimeoutResult:
    success = False
    error = "Request timed out after 60 seconds"


class ErrorResult:
    success = False
    error = ""  # Will be set in constructor

    def __init__(self, error_msg):
        self.error = error_msg


async def _crawl_single_url(client: Crawl4aiDockerClient, url: str, session_id: str = None):
    """
    Private helper to perform a single crawl operation.
    Returns the result object on success, or a mock result with success=False on failure.
    :param session_id:
    """
    async with CRAWL_SEMAPHORE:
        try:
            browser_config = get_browser_config(url, session_id)
            crawler_config = get_run_config(url, session_id)

            result = await asyncio.wait_for(
                client.crawl(
                    urls=[url],
                    browser_config=browser_config,
                    crawler_config=crawler_config
                ),
                timeout=60
            )
            return result
        except asyncio.TimeoutError:
            return TimeoutResult()
        except Exception as e:
            return ErrorResult(str(e))


@mcp.tool(
    name="web_crawl_url"
)
async def crawl_url(ctx: Context, url: str, extract_markdown: bool = True, session_id: str = None) -> str:
    """
    Crawl a URL and extract its content using stealth configurations. Can be used to perform a quick duckduckgo search:
    Example: search for latest news in Toronto: https://html.duckduckgo.com/html/?q=latest+Toronto+news&df={df}.
    The latest parameter can be used to constrain time: df:d mean last day, qf:w - last week, month etc

    Args:
        ctx: The MCP context.
        url: The URL to crawl.
        extract_markdown: Whether to return the content as markdown. Defaults to True.
        session_id: if you want to reuse the same browser between multiple requests
    """
    print("CTX ATTRS:", dir(ctx))
    print("LIFESPAN:", getattr(ctx, 'lifespan_context', 'NOT FOUND'))
    print("STATE:", getattr(ctx, 'state', 'NOT FOUND'))

    client = ctx.lifespan_context["client"]
    result = await _crawl_single_url(client, url, session_id)

    if not is_success(result):
        return f"Error crawling {url}: {get_error(result)}"

    if extract_markdown:
        return get_markdown_content(result)
    else:
        return get_html_content(result)


@mcp.tool(
    name="web_crawl_multiple_urls"
)
async def crawl_multiple_urls(ctx: Context, urls: list[str], session_id: str = None) -> dict[str, str]:
    """
    Crawl multiple URLs in parallel (respecting the global concurrency limit).

    Args:
        ctx: The MCP context.
        urls: A list of URLs to crawl.
        session_id: if you want to reuse the same browser between multiple requests
    """
    client = ctx.lifespan_context["client"]

    tasks = [_crawl_single_url(client, url, session_id) for url in urls]
    results = await asyncio.gather(*tasks)

    output = {}
    for url, result in zip(urls, results):
        if is_success(result):
            output[url] = get_markdown_content(result)
        else:
            output[url] = f"Error: {get_error(result)}"

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
        },
        "browser": {
            "browser_type": "undetected"
        }
    },
    "duckduckgo.com": {
        "browser": {
            "browser_type": "undetected"
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
                result = await _crawl_single_url(client, test_url, session_id="aaaa")

                if is_success(result):
                    print("SUCCESS!")
                    print("\n--- Full Response ---\n")
                    if hasattr(result, 'markdown') and hasattr(result.markdown, 'fit_markdown'):
                        print(result.markdown.fit_markdown)
                    else:
                        print(get_markdown_content(result))
                    print("\n--- End of Response ---")
                else:
                    print(f"FAILED: {get_error(result)}")
        except Exception as e:
            print(f"Unexpected Error: {e}")


    asyncio.run(run_test())
