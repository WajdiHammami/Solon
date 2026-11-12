"""Remove the publishing outlet's identity from text shown to the bias model.

Bias detection must judge the article, not the outlet's reputation, so the
outlet's name (with or without a leading "The"), its domain and the domain's
root label (``nbcnews`` from ``www.nbcnews.com``) are replaced with
:data:`PLACEHOLDER`. Matching is case-insensitive and on word boundaries, so
ordinary words that merely contain a name are left alone.
"""

import re
from urllib.parse import urlparse

PLACEHOLDER = "[outlet]"

# Root labels too generic to strip safely (e.g. "news" from news.com).
_MIN_ROOT_LENGTH = 4


def outlet_aliases(source_name: str, url: str) -> list[str]:
    """Strings identifying the outlet, longest first."""
    aliases: set[str] = set()
    name = source_name.strip()
    if name:
        aliases.add(name)
        if name.lower().startswith("the ") and len(name) > 4:
            aliases.add(name[4:])
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host:
        aliases.add(host)
        root = host.split(".")[0]
        if len(root) >= _MIN_ROOT_LENGTH:
            aliases.add(root)
    return sorted(aliases, key=len, reverse=True)


def blind(text: str, source_name: str, url: str) -> str:
    """``text`` with every outlet alias replaced by :data:`PLACEHOLDER`."""
    for alias in outlet_aliases(source_name, url):
        pattern = rf"(?<![\w.]){re.escape(alias)}(?![\w])"
        text = re.sub(pattern, PLACEHOLDER, text, flags=re.IGNORECASE)
    return text


def blind_title(title: str, source_name: str, url: str) -> str:
    """Like :func:`blind`, also dropping NewsAPI's trailing " - <Source>"."""
    suffix = " - " + source_name
    if source_name and title.lower().endswith(suffix.lower()) and len(title) > len(suffix):
        title = title[: -len(suffix)].rstrip()
    return blind(title, source_name, url)
