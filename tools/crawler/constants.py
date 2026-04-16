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
    },
    "crawl": {
        "delay_before_return_html": None,
        "simulate_user": True,
        "scroll": True,
        "max_scroll": 5, # Using a fixed value here, randomization handled in server
        "wait_for": "networkidle",
        "locale": "en-US",
        "timezone_id": "America/Toronto",
    },
    "proxy": None,
}

DOMAIN_CONFIGS = {
    "google.com": {
        "crawl": {
            "delay_before_content": 6,
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
