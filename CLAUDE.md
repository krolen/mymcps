# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

- **Run HTTP MCP Server**: `python server.py` (Starts server on port 7000)
- **Run stdio MCP Server**: `python server_stdio.py`
- **Run Search Tests**: `python tmp/full_test.py`
- **Install Dependencies**: `uv sync` (Project uses `uv` for dependency management)

## Development Guidelines

- If you need to run any tests using python files, create those under the `./tmp` directory instead of the root.

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

