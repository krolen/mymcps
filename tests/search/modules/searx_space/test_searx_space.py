import asyncio
import logging

import pytest

from tools.search.modules.searx_space.manager import SearxSpaceManager
from tools.search.modules.searx_space.engine import SearxSpaceEngine
from tools.search.modules.searx_space.shortcuts import SearchEngineShortcut

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_searx_space_general_search():
    """Test general search using Google and DuckDuckGo via shortcuts"""
    manager = SearxSpaceManager()
    engine = SearxSpaceEngine(manager)

    # We use a query with both !g and !ddg shortcuts to test multiple engines
    query = "!g !ddg Claude AI search test"
    limit = 5

    logger.info(f"Performing search with query: {query}")
    results = await engine.search(query, limit=limit)

    logger.info(f"Received {len(results)} results")
    for i, res in enumerate(results):
        logger.info(f"Result {i+1}: {res.title} - {res.url} (score: {res.score})")
    for i, res in enumerate(results):
        logger.info(f"Result {i+1}: {res.title} - {res.url} (score: {res.score})")
    for i, res in enumerate(results):
        logger.info(f"Result {i+1}: {res.title} - {res.url} (score: {res.score})")

    # Verify we got some results
    assert len(results) > 0, "Should return at least one result"

    # Verify that results are SearchResult objects
    for res in results:
        assert hasattr(res, 'url'), "Result should have a url"
        assert hasattr(res, 'title'), "Result should have a title"

    # Verify that the results are sorted by score
    for i in range(len(results) - 1):
        assert results[i].score >= results[i+1].score, "Results should be sorted by score descending"

@pytest.mark.asyncio
async def test_searx_space_default_search():
    """Test search without any shortcuts (should use default priority list)"""
    manager = SearxSpaceManager()
    engine = SearxSpaceEngine(manager)

    query = "Claude AI search test"
    limit = 5

    logger.info(f"Performing search with query: {query}")
    results = await engine.search(query, limit=limit)

    logger.info(f"Received {len(results)} results")
    for i, res in enumerate(results):
        logger.info(f"Result {i+1}: {res.title} - {res.url} (score: {res.score})")
    for i, res in enumerate(results):
        logger.info(f"Result {i+1}: {res.title} - {res.url} (score: {res.score})")
    for i, res in enumerate(results):
        logger.info(f"Result {i+1}: {res.title} - {res.url} (score: {res.score})")

    assert len(results) > 0, "Should return results for a general query"

if __name__ == "__main__":
    # Run the tests using asyncio
    async def run_tests():
        try:
            await test_searx_space_general_search()
            logger.info("test_searx_space_general_search: PASSED")
        except Exception as e:
            logger.error(f"test_searx_space_general_search: FAILED - {e}")
            import traceback
            traceback.print_exc()

        try:
            await test_searx_space_default_search()
            logger.info("test_searx_space_default_search: PASSED")
        except Exception as e:
            logger.error(f"test_searx_space_default_search: FAILED - {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(run_tests())
