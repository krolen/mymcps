from pydantic import BaseModel
from typing import Optional, List


class CrawlResult(BaseModel):
    url: str
    content: str
    success: bool
    error: Optional[str] = None


class CrawlResponse(BaseModel):
    results: List[CrawlResult]
