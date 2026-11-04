"""Opt-in live content check; uses the configured remote Crawl4AI server."""
import json
import os
import re
import time

import pytest
from crawl4ai.docker_client import Crawl4aiDockerClient

from tools.crawler.constants import CRAWL4AI_SERVER_URL, CRAWL_HTTP_TIMEOUT_SECONDS
from tools.crawler.crawl4ai.client import Crawl4AIClient


@pytest.mark.asyncio
async def test_ctv_toronto_listing_and_article(tmp_path):
    if os.getenv("CRAWL4AI_LIVE_TESTS") != "1":
        pytest.skip("Set CRAWL4AI_LIVE_TESTS=1 to enable live CTV crawls")
    token = os.getenv("CRAWL4AI_API_TOKEN")
    if not token:
        pytest.skip("CRAWL4AI_API_TOKEN is required")

    async with Crawl4aiDockerClient(
        base_url=CRAWL4AI_SERVER_URL, timeout=CRAWL_HTTP_TIMEOUT_SECONDS, verbose=False,
    ) as docker:
        crawler = Crawl4AIClient(docker, api_token=token)
        before = await crawler.list_browsers()
        summary = []

        async def crawl(url, name):
            started = time.monotonic()
            result = await crawler.crawl_single_url(url)
            record = {
                "url": url, "elapsed_seconds": round(time.monotonic() - started, 2),
                "success": result.success,
                "error": getattr(result, "error", None) or getattr(result, "error_message", None),
                "status_code": getattr(result, "status_code", None),
            }
            summary.append(record)
            (tmp_path / "summary.json").write_text(json.dumps(summary, indent=2))
            print(json.dumps(record))
            assert result.success, record
            assert result.status_code is not None and 200 <= result.status_code < 300, record
            markdown = result.markdown.raw_markdown
            fitted = result.markdown.fit_markdown
            (tmp_path / f"{name}.md").write_text(markdown)
            (tmp_path / f"{name}.fit.md").write_text(fitted)
            record["raw_markdown_chars"] = len(markdown)
            record["fit_markdown_chars"] = len(fitted)
            (tmp_path / "summary.json").write_text(json.dumps(summary, indent=2))
            assert len(fitted) > 300, "Expected usable filtered markdown returned by the MCP tool"
            (tmp_path / f"{name}.html").write_text(result.html)
            assert len(markdown) > 500, "Expected substantial news content"
            assert "toronto" in markdown.lower(), "Expected Toronto content"
            return result, markdown

        print(f"CTV crawl artifacts: {tmp_path}")
        listing, markdown = await crawl("https://www.ctvnews.ca/toronto/", "listing")
        # Extract real news links, so a successful challenge/empty shell isn't a pass.
        articles = {}
        for link in listing.links.get("internal", []) + listing.links.get("external", []):
            href = link.get("href", "")
            if re.match(r"https://(?:www\.)?ctvnews\.ca/toronto/article/", href):
                articles.setdefault(href, link.get("text", ""))
        assert len(articles) >= 3, "Expected at least three Toronto article links"
        print("Toronto article links:", json.dumps(list(articles.items())[:5]))
        await crawl(next(iter(articles)), "article")
        after = await crawler.list_browsers()
        (tmp_path / "browsers.json").write_text(json.dumps({
            "before": [browser.model_dump() for browser in before],
            "after": [browser.model_dump() for browser in after],
        }, indent=2))
        print(f"Browser pool: {len(before)} before, {len(after)} after")
