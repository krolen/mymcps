# Crawl4AI Crawler Constants

CRAWL4AI_SERVER_URL = "http://192.168.0.188:11235"

DEFAULT_CONFIG = {
    "browser": {
        "headless": True,
        "stealth": True,
        "args": [
            "--headless=new",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],
        "viewport": {
            "width": None,
            "height": None,
        },
        "user_agent": None,
        "headers": {                           # ← Add realistic headers
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-CA,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.google.ca/",  # ← Appear to come from Google
        },
    },
    "crawl": {
        "delay_before_return_html": 3.0,      # Give JS time to render after load
        "simulate_user": True,
        "magic": True,                         # ← Add this: enables stealth mode in crawl4ai
        "scroll": True,
        "max_scroll": 3,
        "wait_for": "domcontentloaded",        # ← Change from "networkidle" — news sites never idle
        "page_timeout": 30000,                 # ← Explicit timeout in ms (30s)
        "locale": "en-US",
        "timezone_id": "America/Toronto",
        "ignore_https_errors": True,           # ← Prevents abort on cert issues
    },
    "proxy": None,
}

DOMAIN_CONFIGS = {
    "google.com": {
        "crawl": {
            "delay_before_return_html": 6,
        },
        "browser": {
            "browser_type": "undetected"
        }
    },
    "duckduckgo.com": {
        "browser": {
            "browser_type": "undetected"
        }
    },
    "bing.com": {
        "browser": {
            "browser_type": "undetected"
        }
    },
    "medium.com": {
        "crawl": {
            "scroll": True,
            "max_scroll": 6,
        }
    },
}
