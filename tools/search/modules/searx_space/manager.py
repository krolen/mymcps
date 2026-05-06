import time
import logging
from typing import List, Optional
from pydantic import ValidationError
from tools.common.http_client import get_client
from .models import SearxSpaceData

logger = logging.getLogger(__name__)

class SearxSpaceManager:
    def __init__(self):
        self.instances_data: Optional[SearxSpaceData] = None
        self.last_updated = 0.0
        self.refresh_interval = 300  # 5 minutes
        self.quarantine: dict[str, float] = {}  # instance_url -> quarantine_until_timestamp

    async def refresh_instances(self):
        """Fetch and cache SearXNG instances from searx.space"""
        try:
            client = get_client()
            response = await client.get("https://searx.space/data/instances.json")
            response.raise_for_status()
            data = response.json()
            self.instances_data = SearxSpaceData(**data)
            self.last_updated = time.time()
            logger.info("SearXNG instance list refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh SearXNG instances: {e}")
            # We do not fail if retrieval fails, as per user request

    async def get_instances(self) -> SearxSpaceData:
        if self.instances_data is None or (time.time() - self.last_updated > self.refresh_interval):
            await self.refresh_instances()
        return self.instances_data

    def quarantine_instance(self, url: str, duration_hours: float):
        """Move instance to quarantine for a specified duration"""
        until = time.time() + (duration_hours * 3600)
        self.quarantine[url] = until
        logger.info(f"Instance {url} quarantined until {time.ctime(until)}")

    def get_best_instances(self, engines: List[str], count: int = 3) -> List[str]:
        """Find the best instances that support the required engines"""
        if not self.instances_data:
            return []

        now = time.time()
        candidates = []
        for url, info in self.instances_data.instances.items():
            # Filter out quarantined instances
            if url in self.quarantine and now < self.quarantine[url]:
                continue

            # Only consider instances with 100% uptime for the last day
            uptime_data = info.uptime
            if not uptime_data or uptime_data.uptimeDay < 100:
                continue

            # Build a priority tuple based on the error rate of requested engines in order
            # We use a high value (100.0) for engines that are not supported or have high error rates
            error_rates = []
            for engine in engines:
                engine_status = info.engines.get(engine)
                if engine_status and engine_status.error_rate is not None and engine_status.error_rate < 15:
                    error_rates.append(engine_status.error_rate)
                else:
                    error_rates.append(100.0)

            # Only consider instances that support at least one of the required engines within acceptable limits
            if all(rate == 100.0 for rate in error_rates):
                continue

            candidates.append((url, tuple(error_rates)))

        # Sort by the error rate tuple lexicographically (first engine, then second, etc.)
        candidates.sort(key=lambda x: x[1])
        return [url for url, _ in candidates[:count]]
