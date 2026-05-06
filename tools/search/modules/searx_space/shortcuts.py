from enum import Enum

class SearchEngineShortcut(Enum):
    GOOGLE = "!g"
    BING = "!bi"
    DDG = "!ddg"
    BRAVE = "!b"
    WIKIPEDIA = "!w"
    WIKIDATA = "!wd"
    WOLFRAMALPHA = "!wa"
    GITHUB = "!gh"
    STACKOVERFLOW = "!so"
    REDDIT = "!reddit"
    HACKERNEWS = "!hn"
    PYPI = "!pypi"
    NPM = "!npm"
    CRATES = "!crates"
    DOCKERHUB = "!docker"
    HUGGINGFACE = "!hf"
    ARXIV = "!arxiv"
    SEMANTICSCHOLAR = "!ss"
    REUTERS = "!reuters"
    GOOGLE_NEWS = "!gn"
    WIKINEWS = "!wn"
    YOUTUBE = "!yt"

    @classmethod
    def get_engine_name(cls, shortcut: str) -> str:
        mapping = {
            cls.GOOGLE.value: "google",
            cls.BING.value: "bing",
            cls.DDG.value: "duckduckgo",
            cls.BRAVE.value: "brave",
            cls.WIKIPEDIA.value: "wikipedia",
            cls.WIKIDATA.value: "wikidata",
            cls.WOLFRAMALPHA.value: "wolframalpha",
            cls.GITHUB.value: "github",
            cls.STACKOVERFLOW.value: "stackexchange",
            cls.REDDIT.value: "reddit",
            cls.HACKERNEWS.value: "hackernews",
            cls.PYPI.value: "pypi",
            cls.NPM.value: "npm",
            cls.CRATES.value: "crates",
            cls.DOCKERHUB.value: "dockerhub",
            cls.HUGGINGFACE.value: "huggingface",
            cls.ARXIV.value: "arxiv",
            cls.SEMANTICSCHOLAR.value: "semanticscholar",
            cls.REUTERS.value: "reuters",
            cls.GOOGLE_NEWS.value: "google_news",
            cls.WIKINEWS.value: "wikinews",
            cls.YOUTUBE.value: "youtube",
        }
        return mapping.get(shortcut, "general")
