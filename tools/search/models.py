from typing import Optional, List
from pydantic import BaseModel

class SearchResult(BaseModel):
    title: str = ""
    url: str
    content: str = ""
    score: float = 1.0
    engine: str = "unknown"

class SearXNGResponse(BaseModel):
    query: str
    results: List[SearchResult]
    unresponsive_engines: List[List[str]] = []
    search_time: Optional[float] = None

