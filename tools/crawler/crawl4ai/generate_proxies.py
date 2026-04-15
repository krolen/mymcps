import os
import random
import threading
import time

import requests

# Configuration
REFRESH_INTERVAL = 7 * 24 * 60 * 60  # 1 week in seconds

# Global state
_PROXY_CACHE = []
_LAST_REFRESH_TIME = 0
_IS_REFRESHING = False


def fetch_nordvpn_proxies():
    """
    Fetches the latest NordVPN proxy list from GitHub.
    """
    api_url = "https://api.github.com/repos/ip-address-list/nordvpn/contents/foxyproxy"

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        files = response.json()
    except Exception as e:
        print(f"Error fetching file list: {e}")
        return None

    username = os.getenv("nordVpnUser")
    password = os.getenv("nordVpnPass")

    if not username or not password:
        print("Warning: nordVpnUser or nordVpnPass environment variables are not set.")

    proxy_list = []
    for file in files:
        if file['name'].endswith('.txt') or file['name'].endswith('.conf'):
            try:
                content_res = requests.get(file['download_url'], timeout=10)
                content_res.raise_for_status()
                for line in content_res.text.splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    clean_line = line.replace('ssl://', '').replace('http://', '').replace('https://', '').strip()
                    if '@' in clean_line:
                        clean_line = clean_line.split('@')[-1]

                    server_addr = clean_line if ':' in clean_line else f"{clean_line}:89"
                    proxy_list.append({
                        "server": f"http://{server_addr}",
                        "username": username,
                        "password": password
                    })
            except Exception as e:
                print(f"Error processing file {file['name']}: {e}")

    return proxy_list


def _background_refresh():
    """
    Worker function to refresh the cache in the background.
    """
    global _PROXY_CACHE, _LAST_REFRESH_TIME, _IS_REFRESHING
    try:
        new_proxies = fetch_nordvpn_proxies()
        if new_proxies:
            _PROXY_CACHE = new_proxies
            _LAST_REFRESH_TIME = time.time()
            print("Proxy cache successfully refreshed in background.")
        else:
            print("Background refresh failed: No proxies fetched.")
    except Exception as e:
        print(f"Background refresh encountered an error: {e}")
    finally:
        _IS_REFRESHING = False


def get_proxies(shuffle=True):
    """
    Returns the proxy list from memory. 
    If stale, triggers a background refresh and returns current data.
    """
    global _PROXY_CACHE, _LAST_REFRESH_TIME, _IS_REFRESHING

    current_time = time.time()

    # Check if data is stale
    if (current_time - _LAST_REFRESH_TIME) > REFRESH_INTERVAL:
        if not _IS_REFRESHING:
            _IS_REFRESHING = True
            # Start background refresh
            thread = threading.Thread(target=_background_refresh, daemon=True)
            thread.start()

    # Return current data (even if stale)
    result = list(_PROXY_CACHE)
    if shuffle and result:
        random.shuffle(result)
    return result


if __name__ == "__main__":
    # Initial load to populate cache for the first time
    print("Performing initial load...")
    _PROXY_CACHE = fetch_nordvpn_proxies() or []
    _LAST_REFRESH_TIME = time.time()

    print(f"Loaded {len(_PROXY_CACHE)} proxies.")
    print(f"First few: {get_proxies()[:3]}")
    print(f"First few: {get_proxies()[:3]}")
    print(f"First few: {get_proxies()[:3]}")
