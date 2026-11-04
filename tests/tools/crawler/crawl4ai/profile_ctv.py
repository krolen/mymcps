"""Manual diagnostic: compare cold/warm CTV requests using one browser profile."""
import asyncio
import json
import os
from pathlib import Path
from time import perf_counter

from crawl4ai import CacheMode
from crawl4ai.docker_client import Crawl4aiDockerClient
from dotenv import load_dotenv

from tools.crawler.constants import CRAWL4AI_SERVER_URL, CRAWL_HTTP_TIMEOUT_SECONDS
from tools.crawler.crawl4ai.client import Crawl4AIClient

URL = "https://www.ctvnews.ca/toronto/article/when-is-canada-post-ending-home-delivery-in-your-neighbourhood-heres-the-schedule-for-the-gta/"


async def main():
    load_dotenv('.env')
    async with Crawl4aiDockerClient(
        base_url=CRAWL4AI_SERVER_URL, timeout=CRAWL_HTTP_TIMEOUT_SECONDS, verbose=False,
    ) as docker:
        crawler = Crawl4AIClient(docker, api_token=os.environ['CRAWL4AI_API_TOKEN'])
        browser = crawler._get_browser_config(URL)
        # Hold the profile fixed ONLY in this diagnostic to isolate reuse.
        crawler._get_browser_config = lambda *args: browser
        run_factory = crawler._get_run_config
        def run_config(*args):
            config = run_factory(*args)
            config.cache_mode = CacheMode.BYPASS
            return config
        crawler._get_run_config = run_config
        request = docker._request
        records = []
        async def measured_request(method, endpoint, **kwargs):
            started = perf_counter()
            response = await request(method, endpoint, **kwargs)
            if endpoint == '/crawl':
                payload = response.json()
                record = {'http_seconds': round(perf_counter() - started, 3),
                          'api_metadata': {k: v for k, v in payload.items() if k != 'results'}}
                if payload.get('results'):
                    data = payload['results'][0]
                    record['result_keys'] = list(data)
                    record['timing_fields'] = {k: v for k, v in data.items()
                                               if any(t in k for t in ['time', 'duration', 'memory'])}
                records.append(record)
            return response
        docker._request = measured_request
        for index in range(2):
            started = perf_counter()
            await crawler._validate_crawl_url(URL)
            dns_seconds = perf_counter() - started
            started = perf_counter()
            await docker._check_server()
            health_seconds = perf_counter() - started
            before = await crawler.list_browsers()
            started = perf_counter()
            result = await crawler.crawl_single_url(URL)
            elapsed = perf_counter() - started
            after = await crawler.list_browsers()
            record = records[-1] if records else {}
            record.update({'trial': index + 1, 'total_seconds': round(elapsed, 3),
                           'dns_probe_seconds': round(dns_seconds, 3),
                           'health_probe_seconds': round(health_seconds, 3),
                           'success': result.success,
                           'error': getattr(result, 'error', None) or getattr(result, 'error_message', None),
                           'browsers_before': [b.model_dump() for b in before],
                           'browsers_after': [b.model_dump() for b in after]})
            print(json.dumps(record), flush=True)
            Path('/tmp/crawl4ai-ctv-profile.json').write_text(json.dumps(records, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
