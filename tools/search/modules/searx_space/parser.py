from bs4 import BeautifulSoup

from tools.search.models import SearchResult, SearXNGResponse


def parse_searxng_html(html: str, query: str) -> SearXNGResponse:
    """
    Parses SearXNG HTML search results into a SearXNGResponse model.
    """
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Find all result articles
    articles = soup.find_all('article', class_='result')

    for article in articles:
        try:
            # Title and URL
            # The structure is <h3><a href="...">Title</a></h3>
            header_link = article.find('h3').find('a') if article.find('h3') else None
            if not header_link:
                continue

            title = header_link.get_text(strip=True)
            url = header_link.get('href', '')

            # Content/Snippet
            # The structure is <p class="content">Snippet</p>
            content_tag = article.find('p', class_='content')
            content = content_tag.get_text(strip=True) if content_tag else ""

            # Engine
            # The structure is <div class="engines"><span>engine_name</span></div>
            engines_div = article.find('div', class_='engines')
            engine = "unknown"
            if engines_div:
                engine_span = engines_div.find('span')
                if engine_span:
                    engine = engine_span.get_text(strip=True)

            results.append(SearchResult(
                title=title,
                url=url,
                content=content,
                engine=engine
            ))
        except Exception as e:
            # Log the error but continue parsing other results
            continue

    return SearXNGResponse(
        query=query,
        results=results,
        search_time=None  # HTML doesn't explicitly provide search time in a way that's easy to parse
    )
