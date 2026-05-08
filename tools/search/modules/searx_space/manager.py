import time
import logging
import json
import os
import sqlite3
from pathlib import Path
from typing import List, Optional
from pydantic import ValidationError
from tools.common.http_client import get_client
from .models import SearxSpaceData

logger = logging.getLogger(__name__)

QUARANTINE_DB = Path("data/quarantine.db").absolute()

class SearxSpaceManager:
    def __init__(self):
        logger.info(f"Initializing SearxSpaceManager in process {os.getpid()}")
        self.instances_data: Optional[SearxSpaceData] = None
        self.last_updated = 0.0
        self.refresh_interval = 9000  # 15 minutes
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database for quarantine."""
        with sqlite3.connect(QUARANTINE_DB) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS quarantine (url TEXT PRIMARY KEY, until REAL)"
            )
            conn.commit()

    def _save_quarantine(self, url: str, until: float):
        """Save quarantine data to SQLite."""
        try:
            with sqlite3.connect(QUARANTINE_DB) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO quarantine (url, until) VALUES (?, ?)",
                    (url, until),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save quarantine to DB: {e}")

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
        self._save_quarantine(url, until)
        logger.info(f"Instance {url} quarantined until {time.ctime(until)}")

    def get_best_instances(self, engines: List[str], count: int = 3) -> List[str]:
        """Find the best instances that support the required engines"""
        if not self.instances_data:
            return []

        # Get quarantined instances from DB
        now = time.time()
        quarantine_cache = {}
        try:
            with sqlite3.connect(QUARANTINE_DB) as conn:
                cursor = conn.execute("SELECT url, until FROM quarantine WHERE until > ?", (now,))
                for row in cursor:
                    quarantine_cache[row[0]] = row[1]
        except Exception as e:
            logger.error(f"Failed to load quarantine from DB: {e}")

        candidates = []
        for url, info in self.instances_data.instances.items():
            # Filter out quarantined instances
            if url in quarantine_cache:
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
