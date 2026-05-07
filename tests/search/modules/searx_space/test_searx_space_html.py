#!/usr/bin/env python3
"""
Test script to test the HTML request and parsing flow for SearxSpace engine.
Tests: response = await self._request_with_fallback(instance_url, search_url, html_params)
       if response:
           return self._parse_html_response(response, instance_url, query)
"""

import asyncio
import logging

import pytest

from tools.search.modules.searx_space.browser_client import get_browser_session
from tools.search.modules.searx_space.parser import parse_searxng_html
from tools.search.models import SearchResult, SearXNGResponse

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_searx_space_html_request():
    """Test making an HTML request to searx.oloke.xyz and parsing the results."""

    instance_url = "https://searx.oloke.xyz"
    query = "ai news !g"
    search_url = f"{instance_url.rstrip('/')}/search"
    html_params = {"q": query}

    logger.info(f"Making HTML request to {search_url} with params: {html_params}")

    try:
        # Get browser session
        client = await get_browser_session()

        # Make the request
        response = await client.get(search_url, params=html_params)

        if response.status_code == 200:
            logger.info(f"Successfully received response with status {response.status_code}")
            logger.info(f"Response length: {len(response.text)} characters")

            # Parse the HTML response
            parsed_response = parse_searxng_html(response.text, query)

            logger.info(f"Parsed {len(parsed_response.results)} results")

            # Convert to SearchResult objects (similar to what _parse_html_response does)
            results = []
            for res in parsed_response.results:
                search_result = SearchResult(
                    title=res.title,
                    url=res.url,
                    content=res.content,
                    score=res.score,
                    engine=f"searxng@{instance_url}"
                )
                results.append(search_result)

            # Output results
            print("\n" + "="*80)
            print(f"SEARCH RESULTS FOR: '{query}'")
            print("="*80)

            for i, result in enumerate(results[:5], 1):  # Show first 5 results
                print(f"\n{i}. {result.title}")
                print(f"   URL: {result.url}")
                print(f"   Engine: {result.engine}")
                if result.content:
                    print(f"   Content: {result.content[:100]}...")

            print(f"\nTotal results found: {len(results)}")
            print("="*80)

            return results

        else:
            logger.error(f"Request failed with status {response.status_code}")
            logger.error(f"Response text: {response.text[:500]}...")
            return []

    except Exception as e:
        logger.error(f"Request failed with exception: {e}")
        return []
    finally:
        # Close the browser session
        try:
            from tools.search.modules.searx_space.browser_client import close_browser_session
            await close_browser_session()
        except:
            pass

if __name__ == "__main__":
    # Run the test
    results = asyncio.run(test_searx_space_html_request())

    # Exit with appropriate code
    if results:
        print(f"\n✅ Test PASSED: Found {len(results)} results")
        exit(0)
    else:
        print(f"\n❌ Test FAILED: No results found")
        exit(1)