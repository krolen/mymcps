# Crawl4AI Crawler Constants

CRAWL4AI_SERVER_URL = "http://192.168.0.188:11235"

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
    },
    "crawl": {
        "delay_before_return_html": 3.0,  # Give JS time to render after load
        "locale": "en-US",
        "timezone_id": "America/Toronto",
    },
}

DOMAIN_CONFIGS = {
    "google.com": {
        "crawl": {
            "delay_before_return_html": 6,
        },
    },
    "medium.com": {
        "crawl": {
            "scroll": True,
            "max_scroll": 6,
        }
    },
}
