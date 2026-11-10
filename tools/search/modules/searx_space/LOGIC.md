# SearX-Space search

The maintained implementation description is in [Architecture and tool reference](../../../../docs/architecture.md#search-implementation).

The public entry point is `web_search`, implemented in `tools/search/searxng/server.py`. It delegates through the backend registry to this module. Instance metadata and quarantine state persist in `data/quarantine.db`; local SearXNG is tried first, followed by public candidates until three instances return results.

See `engine.py` for request fallback and aggregation, `manager.py` for cache and candidate selection, `parser.py` for HTML parsing, and `shortcuts.py` for bang mappings.
