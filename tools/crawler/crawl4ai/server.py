"""
Crawl4AI Crawler MCP Server

A FastMCP 3+ based MCP server that provides web crawling and content extraction
functionality using the crawl4ai library.
"""

import asyncio
from contextlib import asynccontextmanager

from crawl4ai.docker_client import Crawl4aiDockerClient
from fastmcp import FastMCP, Context

from tools.crawler.constants import CRAWL4AI_SERVER_URL
from tools.crawler.crawl4ai.client import Crawl4AIClient

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
        crawler = Crawl4AIClient(client)
        yield {"crawler": crawler}
    print("LIFESPAN SHUTDOWN")


mcp = FastMCP(name="crawl4ai-crawler", lifespan=lifespan)


@mcp.tool(
    name="web_crawl_url"
)
async def crawl_url(ctx: Context, url: str, extract_markdown: bool = True, session_id: str = None) -> str:
    """
    Crawl a URL and extract its content using stealth configurations. Can be used to perform a quick duckduckgo search:
    Example: search for latest news in Toronto: https://html.duckduckgo.com/html/?q=latest+Toronto+news&df={df}.
    The latest parameter can be used to constrain time: df:d mean last day, qf:w - last week, month etc

    Args:
        url: The URL to crawl.
        extract_markdown: Whether to return the content as markdown. Defaults to True.
        session_id: if you want to reuse the same browser between multiple requests
    """
    print("CTX ATTRS:", dir(ctx))
    print("LIFESPAN:", getattr(ctx, 'lifespan_context', 'NOT FOUND'))
    print("STATE:", getattr(ctx, 'state', 'NOT FOUND'))

    client = ctx.lifespan_context["crawler"]
    result = await client.crawl_single_url(url, False, session_id)

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
    crawler = ctx.lifespan_context["crawler"]

    tasks = [crawler.crawl_single_url(url, False, session_id) for url in urls]
    results = await asyncio.gather(*tasks)

    output = {}
    for url, result in zip(urls, results):
        if is_success(result):
            output[url] = get_markdown_content(result)
        else:
            output[url] = f"Error: {get_error(result)}"

    return output


# Removed redundant deep_merge as it is now part of Crawl4AIClient._deep_merge


if __name__ == "__main__":
    async def run_test():
        test_url = "https://www.google.com/search?q=toronto+news&tbs=qdr:d"
        print(f"Testing crawl_url tool: {test_url}")

        try:
            async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL) as client:
                crawler = Crawl4AIClient(client)
                result = await crawler.crawl_single_url(test_url, False, session_id="aaaa")

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
