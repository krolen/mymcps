from typing import Dict, List, Any

class SearchConstants:
    # SearXNG Configuration
    SEARXNG_URL = "http://192.168.0.100:8089"

    # Time ranges supported by SearXNG
    TIME_RANGES = ["day", "week", "month", "year"]

    # DuckDuckGo time range mapping (df parameter)
    DDG_TIME_RANGE_MAP = {
        "day": "d",
        "week": "w",
        "month": "m",
        "year": "y"
    }

    # Brave time range mapping (tf parameter)
    BRAVE_TIME_RANGE_MAP = {
        "day": "d",
        "week": "w",
        "month": "m",
        "year": "y"
    }

    # Brave time range mapping (tf parameter)
    BRAVE_TIME_RANGE_MAP = {
        "day": "d",
        "week": "w",
        "month": "m",
        "year": "y"
    }

    # Engine definitions
    ENGINES = {
        "brave": {
            "description": "Brave Search - General web search, privacy-focused",
            "categories": ["general"],
            "time_range_support": True
        },
        "duckduckgo": {
            "description": "DuckDuckGo - General web and programming search",
            "categories": ["general", "programming"],
            "time_range_support": True
        },
        "bing": {
            "description": "Microsoft Bing - Comprehensive general web search",
            "categories": ["general", "programming"],
            "time_range_support": True
        },
        "wikipedia": {
            "description": "Wikipedia - Factual encyclopedia knowledge",
            "categories": ["facts"],
            "time_range_support": False
        },
        "wikidata": {
            "description": "Wikidata - Structured factual data",
            "categories": ["facts"],
            "time_range_support": False
        },
        "wolframalpha": {
            "description": "Wolfram Alpha - Computational and mathematical queries",
            "categories": ["compute"],
            "time_range_support": False
        },
        "github": {
            "description": "GitHub - Source code and repository search",
            "categories": ["programming"],
            "time_range_support": False
        },
        "stackexchange": {
            "description": "Stack Exchange - Programming Q&A (Stack Overflow)",
            "categories": ["programming"],
            "time_range_support": False
        },
        "reddit": {
            "description": "Reddit - Community discussions and opinions",
            "categories": ["discussion", "programming"],
            "time_range_support": True
        },
        "hackernews": {
            "description": "Hacker News - Tech, startups, and programming news",
            "categories": ["discussion", "news"],
            "time_range_support": False
        },
        "pypi": {
            "description": "PyPI - Python package search",
            "categories": ["packages"],
            "time_range_support": False
        },
        "npm": {
            "description": "npm - JavaScript/Node package search",
            "categories": ["packages"],
            "time_range_support": False
        },
        "crates": {
            "description": "Crates.io - Rust package search",
            "categories": ["packages"],
            "time_range_support": False
        },
        "dockerhub": {
            "description": "Docker Hub - Container image search",
            "categories": ["packages"],
            "time_range_support": False
        },
        "huggingface": {
            "description": "Hugging Face - AI models and datasets",
            "categories": ["packages", "ai", "programming"],
            "time_range_support": False
        },
        "arxiv": {
            "description": "arXiv - Scientific preprints and research papers",
            "categories": ["science"],
            "time_range_support": True
        },
        "semanticscholar": {
            "description": "Semantic Scholar - AI-powered scientific research",
            "categories": ["science"],
            "time_range_support": False
        },
        "reuters": {
            "description": "Reuters - Global news",
            "categories": ["news"],
            "time_range_support": False
        },
        "google news": {
            "description": "Google News - News aggregation",
            "categories": ["news"],
            "time_range_support": True
        },
        "wikinews": {
            "description": "Wikinews - Collaborative news wiki",
            "categories": ["news", "wikimedia"],
            "time_range_support": False
        },
    }
