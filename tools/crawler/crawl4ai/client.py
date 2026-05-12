import asyncio
import os
import random
from urllib.parse import urlparse

from crawl4ai import BrowserConfig, CrawlerRunConfig, PruningContentFilter, DefaultMarkdownGenerator, ProxyConfig
from crawl4ai.docker_client import Crawl4aiDockerClient

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
    def __init__(self, docker_client: Crawl4aiDockerClient):
        self.client = docker_client
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

    def _get_browser_config(self, url: str = "", session_id: str = None, use_proxy: bool = False) -> BrowserConfig:
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

        proxy_config = None
        if use_proxy:
            proxy_url = os.getenv("RES_PROXY")
            if proxy_url:
                proxy_config = ProxyConfig.from_string(proxy_url)

        user_data_dir_val = f"/app/user_data/{session_id}" if session_id else None
        use_persistent_context_val = True if session_id else False

        return BrowserConfig(
            headless=browser_settings.get("headless", True),
            enable_stealth=browser_settings.get("stealth", True),
            viewport_width=actual_viewport_width,
            viewport_height=actual_viewport_height,
            # user_data_dir=user_data_dir_val,
            # use_persistent_context=use_persistent_context_val,
            user_agent=actual_user_agent,
            extra_args=browser_settings.get("args", []),
            browser_type=browser_settings.get("browser_settings", "chromium"),
            text_mode=True,
            proxy_config=proxy_config,
        )

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
            simulate_user=crawl_settings.get("simulate_user", False),
            locale=crawl_settings.get("locale"),
            timezone_id=crawl_settings.get("timezone_id"),
            markdown_generator=md_generator,
            only_text=True,
            magic=True,
        )

        if session_id:
            config.session_id = session_id
        return config

    async def crawl_single_url(self, url: str, proxy: bool = False, session_id: str = None):
        """Perform a single crawl operation."""
        async with self.semaphore:
            try:
                browser_config = self._get_browser_config(url, session_id, proxy)
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
