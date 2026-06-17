from pydantic import BaseModel
from typing import Optional, List, Any


class CrawlResult(BaseModel):
    url: str
    content: str
    success: bool
    error: Optional[str] = None


class CrawlResponse(BaseModel):
    results: List[CrawlResult]


class RequestStatus(BaseModel):
    id: str
    url: str
    status: str
    start_time: Optional[str] = None
    duration: Optional[float] = None


class BrowserStatus(BaseModel):
    sig: str
    type: str
    age_seconds: int
    last_used_seconds: int
    memory_mb: int
    hits: int
    killable: bool

class BrowserSummary(BaseModel):
    total_count: int
    total_memory_mb: int
    reuse_rate_percent: float

class MonitorResponse(BaseModel):
    browsers: List[BrowserStatus]
    summary: BrowserSummary
