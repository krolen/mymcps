# Crawl4AI Crawler Constants

CRAWL4AI_SERVER_URL = "http://192.168.0.188:11235"

# Leave room for queueing and DNS within the overall deadline.
CRAWL_TIMEOUT_SECONDS = 60
CRAWL_HTTP_TIMEOUT_SECONDS = 45

# Keep warm browsers available while retaining a fallback for missed remote cleanup.
BROWSER_IDLE_TIMEOUT_SECONDS = 300
BROWSER_CLEANUP_INTERVAL_SECONDS = 30

# Bounded profiles allow viewport variation while retaining browser pool reuse.
BROWSER_VIEWPORTS = (
    (1280, 720),
    (1366, 768),
    (1440, 900),
    (1920, 1080),
)

# Chrome 157 stable verified 2026-11-03:
# https://chromereleases.googleblog.com/2026/11/stable-channel-update-for-desktop.html
# Keep the reduced UA version format; updating this does not update remote Chromium.
BROWSER_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/157.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/157.0.0.0 Safari/537.36",
)

DEFAULT_CONFIG = {
    "browser": {
        "headless": True,
        "stealth": True,
        "viewport": {
            "width": None,
            "height": None,
        },
        "user_agent": None,
        "text_mode": True,
        "avoid_ads": True,
    },
    "crawl": {
        "delay_before_return_html": 0.2,
        "wait_until": "domcontentloaded",
        "page_timeout": 20_000,
        "wait_for": None,
        "wait_for_timeout": 5_000,
        "locale": "en-US",
        "timezone_id": "America/Toronto",
    },
}

DOMAIN_CONFIGS = {
    "google.com": {
        "crawl": {
            "delay_before_return_html": 1.0,  # Allow results to render after DOMContentLoaded
        },
    },
    "medium.com": {
        "crawl": {
            "scroll": True,
            "max_scroll": 6,
        }
    },
}
