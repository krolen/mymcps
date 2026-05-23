from abc import ABC, abstractmethod
from typing import Optional, List

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str = ""
    url: str
    content: str = ""
    score: float = 0.01
    engine: str = "unknown"


class WebSearchResponse(BaseModel):
    query: str = ""
    result_count: int = 0
    results: List[SearchResult] = []
    search_time: Optional[float] = None
    engines_used: List[str] = []
    fallback: Optional[bool] = None
    error: Optional[str] = None
    instruction: Optional[str] = None


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
