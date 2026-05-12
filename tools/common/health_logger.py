import logging
import os
from datetime import datetime, timezone
from typing import Literal
from threading import Lock
from clickhouse_driver import Client

logger = logging.getLogger("health_logger")

class HealthLogger:
    def __init__(self):
        # Use environment variables or defaults for NAS ClickHouse
        self.host = os.getenv("CLICKHOUSE_HOST", "192.168.0.100")
        try:
            self.port = int(os.getenv("CLICKHOUSE_PORT", "9000"))
        except ValueError:
            logger.error("Invalid CLICKHOUSE_PORT environment variable. Falling back to 9000.")
            self.port = 9000
            
        self.user = os.getenv("CLICKHOUSE_USER", "user")
        self.password = os.getenv("CLICKHOUSE_PASSWORD", "password")
        self.table = os.getenv("CLICKHOUSE_TABLE", "my_data.health_logs")
        
        self._client = None
        self._lock = Lock()

    def _get_client(self):
        with self._lock:
            if self._client is None:
                try:
                    self._client = Client(
                        host=self.host,
                        port=self.port,
                        user=self.user,
                        password=self.password,
                        settings={'async_insert': 1} # Server-side async insert to protect NAS
                    )
                except Exception as e:
                    logger.error(f"Failed to connect to ClickHouse: {e}")
                    return None
            return self._client

    def log_event(self, component: Literal['search', 'crawl'], engine_or_domain: str, status: Literal['success', 'blocked', 'error'], detail: str = ""):
        """
        Logs a health event to ClickHouse.
        component: 'search' or 'crawl'
        status: 'success', 'blocked', 'error'
        """
        client = self._get_client()
        if not client:
            logger.warning(f"Health event dropped: No ClickHouse connection available. Event: {component}, {status}")
            return

        try:
            # We use a simple execute. Since async_insert=1 is set in settings, 
            # ClickHouse will buffer this on the server side.
            client.execute(
                f'INSERT INTO {self.table} (timestamp, component, engine_or_domain, status, detail) VALUES',
                [(datetime.now(timezone.utc), component, engine_or_domain, status, detail)]
            )
        except Exception as e:
            logger.error(f"Failed to log health event to ClickHouse: {e}")
            # Reset client on connection error to trigger reconnect next time
            with self._lock:
                self._client = None

# Global instance for easy import
health_logger = HealthLogger()
