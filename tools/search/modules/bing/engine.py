import logging
from typing import List, Optional
from fastmcp import Context
from tools.search.models import SearchResult

logger = logging.getLogger("bing_search")

async def search(ctx: Context, query: str, time_range: Optional[str] = None, limit: int = 30) -> List[SearchResult]:
    """
    Perform a search using Bing. Currently returns nothing.
    """
    logger.info(f"Bing search for query: {query}")
    return []
