import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import List

from tools.common.http_client import get_client
from .models import SearxSpaceData

logger = logging.getLogger(__name__)

QUARANTINE_DB = Path("data/quarantine.db").absolute()


class SearxSpaceManager:
    def __init__(self):
        logger.info(f"Initializing SearxSpaceManager in process {os.getpid()}")
        self.refresh_interval = 9000  # 15 minutes
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database for quarantine and cache."""
        with sqlite3.connect(QUARANTINE_DB) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS quarantine (url TEXT PRIMARY KEY, until REAL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, timestamp REAL)"
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

            # Save to DB
            with sqlite3.connect(QUARANTINE_DB) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, timestamp) VALUES (?, ?, ?)",
                    ("instances", json.dumps(data), time.time()),
                )
                conn.commit()

            logger.info("SearXNG instance list refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh SearXNG instances: {e}")

    async def get_instances(self) -> SearxSpaceData:
        now = time.time()

        # Check cache in DB
        try:
            with sqlite3.connect(QUARANTINE_DB) as conn:
                row = conn.execute(
                    "SELECT value, timestamp FROM cache WHERE key = ?", ("instances",)
                ).fetchone()

                if row:
                    value, timestamp = row
                    if now - timestamp < self.refresh_interval:
                        return SearxSpaceData(**json.loads(value))
        except Exception as e:
            logger.error(f"Error reading cache from DB: {e}")

        await self.refresh_instances()

        # Return from DB after refresh
        try:
            with sqlite3.connect(QUARANTINE_DB) as conn:
                row = conn.execute(
                    "SELECT value FROM cache WHERE key = ?", ("instances",)
                ).fetchone()
                if row:
                    return SearxSpaceData(**json.loads(row[0]))
        except Exception as e:
            logger.error(f"Error reading cache from DB after refresh: {e}")

        # Fallback if everything fails (should not happen usually)
        return SearxSpaceData(instances={})

    def quarantine_instance(self, url: str, duration_hours: float):
        """Move instance to quarantine for a specified duration"""
        until = time.time() + (duration_hours * 3600)
        self._save_quarantine(url, until)
        logger.info(f"Instance {url} quarantined until {time.ctime(until)}")

    def get_best_instances(self, engines: List[str], count: int = 3) -> List[str]:
        """Find the best instances that support the required engines"""
        # Now we must call get_instances asynchronously to get the data
        # However, get_best_instances is synchronous.
        # To maintain the signature, we'll read from DB directly.

        now = time.time()
        instances_data = None

        try:
            with sqlite3.connect(QUARANTINE_DB) as conn:
                row = conn.execute(
                    "SELECT value, timestamp FROM cache WHERE key = ?", ("instances",)
                ).fetchone()
                if row:
                    value, timestamp = row
                    # We allow a slightly stale cache here to avoid blocking,
                    # but get_instances() handles the actual refresh.
                    instances_data = SearxSpaceData(**json.loads(value))
        except Exception as e:
            logger.error(f"Failed to load instances from DB in get_best_instances: {e}")

        if not instances_data:
            return []

        # Get quarantined instances from DB
        quarantine_cache = {}
        try:
            with sqlite3.connect(QUARANTINE_DB) as conn:
                cursor = conn.execute("SELECT url, until FROM quarantine WHERE until > ?", (now,))
                for row in cursor:
                    quarantine_cache[row[0]] = row[1]
        except Exception as e:
            logger.error(f"Failed to load quarantine from DB: {e}")

        candidates = []
        for url, info in instances_data.instances.items():
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
