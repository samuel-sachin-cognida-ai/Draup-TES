"""URL filtering, normalization, and healthcare-relevance checks."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from crawler.config import VendorConfig

# Link-following: discovered URLs must contain at least one of these keywords
_HEALTHCARE_LINK_KEYWORDS = [
    "health", "clinical", "medical", "patient", "hospital",
    "hipaa", "ehr", "fhir", "hl7", "care", "pharmacy",
    "diagnostic", "radiology", "life-science", "lifescience",
    "wellness", "provider", "payer", "telehealth", "telemedicine",
    "solution", "industry", "industries", "customer", "stories",
    "case-study", "enterprise", "connector", "workflow",
    "integration", "agent", "news", "blog", "tutorial", "resource",
    "announcement", "use-case",
]

_SKIP_EXTENSIONS = frozenset({
    ".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".mp4", ".mp3", ".css", ".js", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".xml",
})

_GENERIC_SKIP_SEGMENTS = frozenset({
    "login", "signup", "sign-up", "register", "account",
    "settings", "profile", "dashboard", "cart", "checkout",
    "search", "404", "500", "rss", "feed", "sitemap",
    "cookie", "terms", "contact", "download", "status",
    "press", "brand", "media-kit",
})


def normalize_url(url: str) -> str:
    return url.split("#")[0].rstrip("/")


def is_allowed_url(url: str, cfg: VendorConfig) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    netloc      = parsed.netloc.lower()
    netloc_bare = netloc.removeprefix("www.")

    if any(bd in netloc for bd in cfg.blocked_domains):
        return False

    allowed_bare = [d.removeprefix("www.") for d in cfg.allowed_domains]
    if not any(netloc_bare == d or netloc_bare.endswith("." + d) for d in allowed_bare):
        return False

    path = parsed.path.lower()

    if any(path.endswith(ext) for ext in _SKIP_EXTENSIONS):
        return False

    segments = set(path.strip("/").split("/"))
    if segments & _GENERIC_SKIP_SEGMENTS:
        return False

    if "/" not in cfg.allowed_path_prefixes:
        if not any(
            path == p.lower().rstrip("/") or path.startswith(p.lower())
            for p in cfg.allowed_path_prefixes
        ):
            return False

    for pattern in cfg.blocked_path_patterns:
        if re.search(pattern, path):
            return False

    return True


def is_healthcare_relevant_link(
    url: str,
    seed_set: frozenset,
    link_keywords: list[str] | None = None,
) -> bool:
    if normalize_url(url) in seed_set:
        return True
    if link_keywords is not None and len(link_keywords) == 0:
        return True
    path = urlparse(url).path.lower()
    keywords = link_keywords if link_keywords is not None else _HEALTHCARE_LINK_KEYWORDS
    return any(kw in path for kw in keywords)
