from typing import Dict

from tools.search.models import SearchEngine
from tools.search.modules.searx_space.engine import SearxSpaceEngine

# Registry for all search engine implementations
ENGINE_REGISTRY: Dict[str, SearchEngine] = {
    "searx_space": SearxSpaceEngine(),
}


def get_engine(name: str) -> SearchEngine:
    """Retrieve a search engine by name from the registry."""
    if name not in ENGINE_REGISTRY:
        raise ValueError(f"Search engine '{name}' not found in registry.")
    return ENGINE_REGISTRY[name]


def get_all_engines():
    """Retrieve all registered search engines."""
    return ENGINE_REGISTRY
