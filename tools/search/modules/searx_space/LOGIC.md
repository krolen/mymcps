# SearX-Space Search Module Logic

The `searx-space` module provides a distributed search capability by leveraging public SearXNG instances listed on
`searx.space`. Instead of relying on a single SearXNG instance, it spreads requests across multiple high-quality public
instances to increase reliability and success rates.

## 1. Instance Management (`manager.py`)

The `SearxSpaceManager` is responsible for discovering and maintaining a list of healthy SearXNG instances.

### Data Acquisition

- **Source**: Fetches `https://searx.space/data/instances.json`.
- **Caching**: Stores the instance list in memory.
- **Lazy Refresh**: Updates the cache every 5 minutes. If the fetch fails, the module continues to use the last cached
  version to avoid service interruption.
- **Data Validation**: Uses Pydantic models (`models.py`) to ensure the JSON structure is correct and to extract
  specific metrics:
    - `uptimeDay`: Daily availability percentage.
    - `timing.search.success_percentage`: Percentage of successful search queries.
    - `engines`: Map of search engines supported by the instance and their associated `error_rate`.

### Instance Selection

For a given search engine (e.g., "google"), the manager finds the best instances based on:

1. **Filtering**: Only considers instances where the engine is explicitly supported and the `error_rate` is below 50%.
2. **Ranking**: Scores instances using the average of their daily uptime and search success percentage:
   $$\text{Score} = \frac{\text{uptimeDay} + \text{success\_percentage}}{2}$$
3. **Selection**: Returns the top 3 highest-scoring instances.

## 2. Search Logic (`engine.py`)

The `SearxSpaceEngine` orchestrates the search process across the selected instances.

### Query Parsing

- **Bang Shortcuts**: The engine scans the query for shortcuts defined in `shortcuts.py` (e.g., `!g` for Google, `!ddg`
  for DuckDuckGo).
- **Engine Prioritization**:
    - If specific shortcuts are found, those engines are targeted.
    - If no shortcuts are provided, the engine defaults to a priority list: **Google $\rightarrow$
      DuckDuckGo $\rightarrow$ Brave $\rightarrow$ Bing**.

### Execution Flow

For each target engine:

1. **Instance Retrieval**: Get the top 3 best instances from the manager.
2. **Sequential Requests**: Execute searches against these instances **sequentially**. This approach is chosen to:
    - Prevent overwhelming public instances.
    - Maintain stability and avoid triggering rate limits/CAPTCHAs.
3. **Collection**: Aggregate results from every instance that responds successfully.

### Result Aggregation

1. **Deduplication**: Uses a set of URLs to ensure that the same page is not listed multiple times, even if returned by
   different instances.
2. **Ranking**: All collected results are sorted globally by their relevance `score` provided by SearXNG.
3. **Limiting**: Returns the top $N$ results as requested by the user.

## 3. MCP Interface (`server.py`)

The module is exposed as a FastMCP server with the following tool:

**`web_searx_space_search(query: str, limit: int = 10)`**

- Parses the query for bang shortcuts.
- Performs the distributed search.
- Returns a list of `SearchResult` objects (title, url, content, score, engine).
