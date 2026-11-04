import asyncio
import ipaddress
import logging
import random
import socket
import time
from typing import List
from urllib.parse import urlparse

import httpx

from crawl4ai import BrowserConfig, CrawlerRunConfig, PruningContentFilter, DefaultMarkdownGenerator
from crawl4ai.docker_client import Crawl4aiDockerClient, ConnectionError as DockerConnectionError
from tools.crawler.models import RequestStatus, BrowserStatus

from tools.crawler.constants import (
    DEFAULT_CONFIG, DOMAIN_CONFIGS, CRAWL_TIMEOUT_SECONDS, CRAWL_HTTP_TIMEOUT_SECONDS,
    BROWSER_VIEWPORTS, BROWSER_USER_AGENTS,
)


logger = logging.getLogger(__name__)


class TimeoutResult:
    success = False

    def __init__(self, error: str = f"Request timed out after {CRAWL_TIMEOUT_SECONDS} seconds"):
        self.error = error


class ErrorResult:
    success = False
    error = ""  # Will be set in constructor

    def __init__(self, error_msg):
        self.error = error_msg


class Crawl4AIClient:
    def __init__(self, docker_client: Crawl4aiDockerClient, api_token: str | None = None):
        self.client = docker_client
        if api_token:
            self.client._http_client.headers["Authorization"] = f"Bearer {api_token}"
        self.semaphore = asyncio.Semaphore(10)
        self._last_viewport: tuple[int, int] | None = None

    @staticmethod
    def _deep_merge(base, override):
        if not override:
            return base
        result = dict(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = Crawl4AIClient._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def _get_domain_config(self, url: str) -> dict:
        """Extracts domain-specific configuration overrides for a given URL."""
        domain = urlparse(url).netloc.lower()
        for config_domain, config in DOMAIN_CONFIGS.items():
            if domain == config_domain or domain.endswith('.' + config_domain):
                return config
        return {}

    @staticmethod
    async def _resolve_host(hostname: str) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        """Resolve every address for a hostname so private aliases cannot bypass validation."""
        try:
            # DNS resolution also canonicalizes legacy numeric forms such as
            # 0x7f000001 and 127.1 that ipaddress.ip_address() rejects.
            hostname = hostname.encode("idna").decode("ascii")
            addresses = await asyncio.get_running_loop().getaddrinfo(
                hostname, None, type=socket.SOCK_STREAM
            )
        except (UnicodeError, socket.gaierror) as exc:
            raise ValueError("URL hostname could not be resolved") from exc

        return {ipaddress.ip_address(address[4][0]) for address in addresses}

    @classmethod
    async def _validate_crawl_url(cls, url: str) -> None:
        """Reject unsafe URLs before they can create a remote Crawl4AI request."""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("URL must be an absolute http:// or https:// URL")

        try:
            port = parsed.port
        except ValueError:
            raise ValueError("URL contains an invalid port") from None

        if port == 0:
            raise ValueError("URL port must be between 1 and 65535")

        addresses = await cls._resolve_host(parsed.hostname)
        if not addresses or any(not address.is_global for address in addresses):
            raise ValueError("URL must not target a private or reserved IP address")

    def _get_browser_config(self, url: str = "", session_id: str = None) -> BrowserConfig:
        """Helper to create a BrowserConfig from merged configs."""
        domain_config = self._get_domain_config(url)
        merged_config = self._deep_merge(DEFAULT_CONFIG, domain_config)
        browser_settings = merged_config.get("browser", {})
        viewport = browser_settings.get("viewport", {})

        # Vary viewports between requests, including repeated calls to one host.
        # A bounded set lets the remote pool reuse each matching browser profile.
        width, height = viewport.get("width"), viewport.get("height")
        if not width or not height:
            selected = random.choice([
                size for size in BROWSER_VIEWPORTS if size != self._last_viewport
            ])
            self._last_viewport = selected
            width = width or selected[0]
            height = height or selected[1]

        config = BrowserConfig(
            headless=browser_settings.get("headless", True),
            enable_stealth=browser_settings.get("stealth", True),
            viewport_width=width,
            viewport_height=height,
            user_agent=browser_settings.get("user_agent") or random.choice(BROWSER_USER_AGENTS),
            text_mode=browser_settings.get("text_mode"),
            avoid_ads=browser_settings.get("avoid_ads", True),
        )
        # BrowserConfig derives client-hint headers from the user agent. The
        # Docker API treats every request header as server-owned policy.
        config.headers = {}
        return config

    def _get_run_config(self, url: str = "", session_id: str = None) -> CrawlerRunConfig:
        """Helper to create a CrawlerRunConfig from merged configs."""
        domain_config = self._get_domain_config(url)
        merged_config = self._deep_merge(DEFAULT_CONFIG, domain_config)
        crawl_settings = merged_config.get("crawl", {})

        prune_filter = PruningContentFilter(
            threshold=0.48,
            threshold_type="dynamic",
            min_word_threshold=5
        )
        md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)

        config = CrawlerRunConfig(
            delay_before_return_html=crawl_settings.get("delay_before_return_html", 0.2),
            wait_until=crawl_settings.get("wait_until", "domcontentloaded"),
            page_timeout=crawl_settings.get("page_timeout", 20_000),
            wait_for=crawl_settings.get("wait_for"),
            wait_for_timeout=crawl_settings.get("wait_for_timeout", 5_000),
            locale=crawl_settings.get("locale"),
            timezone_id=crawl_settings.get("timezone_id"),
            markdown_generator=md_generator,
            only_text=True,
        )

        return config

    async def crawl_single_url(self, url: str, session_id: str = None):
        """Perform a single crawl operation."""
        started = time.monotonic()
        stage = "queue"
        queue_seconds = None
        outcome = "error"
        try:
            # Include admission and DNS in the deadline, not just HTTP I/O.
            async with asyncio.timeout(CRAWL_TIMEOUT_SECONDS):
                async with self.semaphore:
                    queue_seconds = time.monotonic() - started
                    stage = "validation"
                    await self._validate_crawl_url(url)
                    browser_config = self._get_browser_config(url, session_id)
                    crawler_config = self._get_run_config(url, session_id)
                    stage = "crawl"
                    result = await self.client.crawl(
                        urls=[url],
                        browser_config=browser_config,
                        crawler_config=crawler_config,
                        # SDK 0.9.5 also uses hooks_timeout for /crawl HTTP I/O,
                        # even when no hooks are supplied.
                        hooks_timeout=CRAWL_HTTP_TIMEOUT_SECONDS,
                    )
                    outcome = "success" if getattr(result, "success", False) else "error"
                    return result
        except TimeoutError:
            outcome = "timeout"
            return TimeoutResult(
                f"Request timed out during {stage} after {CRAWL_TIMEOUT_SECONDS} seconds"
            )
        except DockerConnectionError as exc:
            # SDK HTTP timeouts are wrapped; classify by type, not message text.
            cause = exc
            seen = set()
            while cause is not None and id(cause) not in seen:
                seen.add(id(cause))
                if isinstance(cause, httpx.TimeoutException):
                    outcome = "timeout"
                    return TimeoutResult(
                        f"Crawler HTTP request timed out during {stage} "
                        f"(HTTP budget {CRAWL_HTTP_TIMEOUT_SECONDS} seconds)"
                    )
                cause = cause.__cause__ or cause.__context__
            return ErrorResult(str(exc))
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception as exc:
            return ErrorResult(str(exc))
        finally:
            logger.info(
                "Crawl outcome=%s stage=%s queue_seconds=%s total_seconds=%.3f",
                outcome, stage,
                round(queue_seconds, 3) if queue_seconds is not None else None,
                time.monotonic() - started,
            )

    async def list_active_requests(self, status: str = "active") -> List[RequestStatus]:
        """List active and completed requests."""
        try:
            response = await self.client._request("GET", f"/monitor/requests?status={status}")
            data = response.json()
            # Crawl4AI 0.9.3 returns {"active": [...], "completed": [...]}.
            requests = data if isinstance(data, list) else data.get(status, data.get("data", []))
            return [RequestStatus(**r) for r in requests]
        except Exception as e:
            print(f"Error listing active requests: {e}")
            return []

    async def list_browsers(self) -> List[BrowserStatus]:
        """Get detailed browser pool information."""
        try:
            response = await self.client._request("GET", "/monitor/browsers")
            data = response.json()
            # API returns {"browsers": [...], "summary": {...}}
            browsers_data = data.get("browsers", []) if isinstance(data, dict) else data
            return [BrowserStatus(**b) for b in browsers_data]
        except Exception as e:
            print(f"Error listing browsers: {e}")
            return []

    async def kill_browser(self, sig: str) -> bool:
        """Kill a specific browser by signature."""
        try:
            response = await self.client._request("POST", "/monitor/actions/kill_browser", json={"sig": sig})
            return response.json().get("success", False)
        except Exception as e:
            print(f"Error killing browser {sig}: {e}")
            return False
