# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

- **Run HTTP MCP Server**: `python server.py` (Starts server on port 7000)
- **Run stdio MCP Server**: `python server_stdio.py`
- **Run Search Tests**: `python tmp/full_test.py`
- **Install Dependencies**: `uv sync` (Project uses `uv` for dependency management)

## Development Guidelines

- If you need to run any tests using python files, create those under the `tests/` directory.
- Create all plans, memories, agents, skills, and other metadata under the local Claude directory.
- If you need to fetch some known url you use curl

## Architecture & Structure

This repository is a collection of MCP (Model Context Protocol) servers built using the `fastmcp` framework.

### High-Level Structure
- `server.py`: The primary entry point for the HTTP-based MCP server. It configures CORS and integrates tools like Crawl4AI.
- `server_stdio.py`: An alternative entry point for running the MCP server via standard I/O.
- `tools/`: Contains the actual logic for the MCP tools, organized by domain:
    - `tools/crawler/`: Web crawling capabilities (e.g., Crawl4AI integration).
    - `tools/search/`: Web search implementations.
        - `tools/search/searxng/`: Integration with SearXNG.
        - `tools/search/modules/ddg/`: Custom DuckDuckGo search engine implementation.
    - `tools/utils/`: General utility tools (e.g., `tools/utils/time/` for time-related functions).

### Key Architectural Patterns
- **FastMCP Framework**: The project leverages `FastMCP` for rapid development of MCP servers.
- **Modular Tooling**: Tools are decoupled from the main server logic and stored in the `tools/` directory.
- **Dynamic Discovery**: `server.py` uses a `FileSystemProvider` to provide access to the `tools/` directory.
- **Hybrid Search**: The search implementation allows for mixing results from SearXNG and custom modules like DuckDuckGo.
- **Local Crawl4AI Cleanup Fallback**: The remote Crawl4AI cleaner sometimes fails to clean up browsers. This is why the local server's browser cleanup task was introduced. Preserve this fallback requirement when optimizing browser reuse; relying exclusively on the remote cleaner does not address the observed operational failures. See `tools/crawler/crawl4ai/README.md` for current behavior.
- **Intentional Viewport Rotation**: Viewport switching is a deliberate project feature because fixed viewports have resulted in bans. Preserve rotation when optimizing Crawl4AI browser reuse. Use a bounded set of viewport profiles so matching configurations can still reuse browsers.

- **Intentional User-Agent Variation**: Preserve random selection between Windows and Linux Chrome user agents alongside viewport rotation. Keep versions current and the profile set bounded so matching configurations can reuse browsers.
