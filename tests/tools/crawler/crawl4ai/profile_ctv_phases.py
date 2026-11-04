"""Manual CTV diagnostic: separate browser/network work from HTML processing."""
import asyncio
import json
import os
from collections import Counter
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

from crawl4ai import CacheMode
from crawl4ai.docker_client import Crawl4aiDockerClient
from dotenv import load_dotenv

from tools.crawler.constants import CRAWL4AI_SERVER_URL, CRAWL_HTTP_TIMEOUT_SECONDS
from tools.crawler.crawl4ai.client import Crawl4AIClient

URL = 'https://www.ctvnews.ca/toronto/article/when-is-canada-post-ending-home-delivery-in-your-neighbourhood-heres-the-schedule-for-the-gta/'


async def main():
    load_dotenv('.env')
    async with Crawl4aiDockerClient(base_url=CRAWL4AI_SERVER_URL,
                                   timeout=CRAWL_HTTP_TIMEOUT_SECONDS, verbose=False) as docker:
        client = Crawl4AIClient(docker, api_token=os.environ['CRAWL4AI_API_TOKEN'])
        browser = client._get_browser_config(URL)
        summaries = []
        selected_cases = set(filter(None, os.getenv('CTV_PROFILE_CASES', '').split(',')))
        for label, javascript, prefetch, capture in [
            ('full_with_network_capture', True, False, True),
            ('browser_only_warm', True, True, False),
            ('no_javascript', False, False, False),
            ('no_javascript_warm', False, False, False),
            ('adblock', True, False, True),
            ('adblock_warm', True, False, False),
        ]:
            if selected_cases and label not in selected_cases:
                continue
            config = client._get_run_config(URL)
            config.cache_mode = CacheMode.BYPASS
            config.prefetch = prefetch
            config.capture_network_requests = capture
            selected_browser = browser.clone(java_script_enabled=javascript, avoid_ads=label.startswith('adblock'))
            selected_browser.headers = {}  # clone derives headers rejected by the Docker API
            started = perf_counter()
            result = await docker.crawl([URL], browser_config=selected_browser,
                                        crawler_config=config, hooks_timeout=CRAWL_HTTP_TIMEOUT_SECONDS)
            events = result.network_requests or []
            requests = [event for event in events if event.get('event_type') == 'request']
            responses = [event for event in events if event.get('event_type') == 'response']
            summary = {
                'label': label, 'seconds': round(perf_counter() - started, 3),
                'success': result.success, 'status': result.status_code,
                'html_chars': len(result.html),
                'contains_article_title': 'Canada Post is ending home delivery' in result.html,
                'fit_chars': len(result.markdown.fit_markdown) if result.markdown else 0,
                'crawl_stats': result.crawl_stats,
                'request_count': len(requests),
                'resource_types': dict(Counter(event.get('resource_type') for event in requests)),
                'request_hosts': dict(Counter(urlparse(event['url']).hostname for event in requests)),
                'document_response': [
                    {'url': event['url'], 'status': event.get('status'), 'timing': event.get('request_timing')}
                    for event in responses if event['url'].rstrip('/') == URL.rstrip('/')
                ],
            }
            summaries.append(summary)
            Path('/tmp/crawl4ai-ctv-phases.json').write_text(json.dumps(summaries, indent=2))
            print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
