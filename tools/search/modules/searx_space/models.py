from pydantic import BaseModel, Field
from typing import Dict, List, Optional

class UptimeData(BaseModel):
    uptimeDay: float = 0.0
    uptimeWeek: float = 0.0
    uptimeMonth: float = 0.0
    uptimeYear: float = 0.0

class SearchTiming(BaseModel):
    success_percentage: float = 0.0
    error: Optional[str] = None

class TimingData(BaseModel):
    search: Optional[SearchTiming] = Field(default_factory=SearchTiming)

class EngineStatus(BaseModel):
    error_rate: Optional[float] = None
    errors: List[int] = Field(default_factory=list)

class InstanceInfo(BaseModel):
    uptime: Optional[UptimeData] = Field(default_factory=UptimeData)
    timing: Optional[TimingData] = Field(default_factory=TimingData)
    engines: Dict[str, EngineStatus] = Field(default_factory=dict)

class SearxSpaceData(BaseModel):
    instances: Dict[str, InstanceInfo]
