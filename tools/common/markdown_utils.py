import re
from typing import Optional

# Pre-compiled regex patterns for efficiency
RESULT_SPLIT_PATTERN = re.compile(r'\n##\s+\[')
TITLE_PATTERN = re.compile(r'^(.*?)\]')
URL_PATTERN = re.compile(r'\]\((.*?)\)')
IMAGE_CLEAN_PATTERN = re.compile(r'\[\!\[Image.*?\]\(.*?\)\].*?(\n|$)', re.MULTILINE)
PREFIX_URL_PATTERN = re.compile(r'^\[[a-zA-Z0-9./-_\s]+\]\(.*?\)')
CONTENT_LINK_PATTERN = re.compile(r'\[(.*?)\]\(https?://.*?\)', re.DOTALL)
MD_LINK_PATTERN = re.compile(r'\[.*?\]\(.*?\)')
MD_IMAGE_PATTERN = re.compile(r'!\[.*?\]\(.*?\)')
TIMESTAMP_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}T.*$')

def clean_markdown_snippet(snippet: str) -> str:
    """
    Cleans up a markdown snippet by removing images, prefix URLs,
    and timestamps to leave only the core text content.
    """
    snippet = IMAGE_CLEAN_PATTERN.sub('', snippet).strip()
    snippet = PREFIX_URL_PATTERN.sub('', snippet).strip()

    content_match = CONTENT_LINK_PATTERN.search(snippet)
    if content_match:
        clean_snippet = content_match.group(1)
    else:
        clean_snippet = MD_LINK_PATTERN.sub('', snippet).strip()

    clean_snippet = MD_IMAGE_PATTERN.sub('', clean_snippet).strip()
    clean_snippet = TIMESTAMP_PATTERN.sub('', clean_snippet).strip()

    return clean_snippet
