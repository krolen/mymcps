import asyncio
import ipaddress
import random
import socket
from typing import List
from urllib.parse import urlparse

from crawl4ai import BrowserConfig, CrawlerRunConfig, PruningContentFilter, DefaultMarkdownGenerator
from crawl4ai.docker_client import Crawl4aiDockerClient
from tools.crawler.models import RequestStatus, BrowserStatus

from tools.crawler.constants import DEFAULT_CONFIG, DOMAIN_CONFIGS


class TimeoutResult:
    success = False
    error = "Request timed out after 60 seconds"


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

        seed = session_id or urlparse(url).netloc.lower()
        local_random = random.Random(seed)
        res_w, res_h = local_random.choice([
            (1280, 720),
            (1366, 768),
            (1440, 900),
            (1920, 1080),
        ])
        actual_viewport_width = viewport.get("width") or res_w
        actual_viewport_height = viewport.get("height") or res_h
        actual_user_agent = browser_settings.get("user_agent") or local_random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
        ])

        config = BrowserConfig(
            headless=browser_settings.get("headless", True),
            enable_stealth=browser_settings.get("stealth", True),
            viewport_width=actual_viewport_width,
            viewport_height=actual_viewport_height,
            user_agent=actual_user_agent,
            text_mode=browser_settings.get("text_mode"),
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

        actual_delay = crawl_settings.get("delay_before_return_html") or random.uniform(2.0, 5.0)
        prune_filter = PruningContentFilter(
            threshold=0.48,
            threshold_type="dynamic",
            min_word_threshold=5
        )
        md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)

        config = CrawlerRunConfig(
            delay_before_return_html=actual_delay,
            locale=crawl_settings.get("locale"),
            timezone_id=crawl_settings.get("timezone_id"),
            markdown_generator=md_generator,
            only_text=True,
        )

        return config

    async def crawl_single_url(self, url: str, session_id: str = None):
        """Perform a single crawl operation."""
        async with self.semaphore:
            try:
                # Crawl4AI 0.9.3 records monitor activity before rejecting an
                # unsafe URL. Validate here so bad input never creates a stale
                # remote request record.
                await self._validate_crawl_url(url)
                browser_config = self._get_browser_config(url, session_id)
                crawler_config = self._get_run_config(url, session_id)

                return await asyncio.wait_for(
                    self.client.crawl(
                        urls=[url],
                        browser_config=browser_config,
                        crawler_config=crawler_config
                    ),
                    timeout=60
                )
            except asyncio.TimeoutError:
                return TimeoutResult()
            except Exception as e:
                return ErrorResult(str(e))

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
