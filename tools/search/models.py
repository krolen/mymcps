from abc import ABC, abstractmethod
from typing import Optional, List

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str = ""
    url: str
    content: str = ""
    score: float = 0.01
    engine: str = "unknown"


class SearXNGResponse(BaseModel):
    query: str
    results: List[SearchResult]
    unresponsive_engines: List[List[str]] = []
    search_time: Optional[float] = None


class SearchEngine(ABC):
    @abstractmethod
    async def search(self, query: str, params: Optional[dict] = None) -> List[SearchResult]:
        """
        Perform a search and return a list of SearchResult objects.
        """
        pass
