"""URL filtering, normalization, and relevance checks."""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from crawler.config import VendorConfig

log = logging.getLogger("tes.crawler.filter")

# Default link-following keywords used when no per-vendor keywords are configured.
# Covers broad enterprise/industry signals so no valid sector page gets dropped.
_DEFAULT_LINK_KEYWORDS = [
    # industries / sectors
    "health", "clinical", "medical", "patient", "hospital",
    "hipaa", "ehr", "fhir", "hl7", "care", "pharmacy",
    "diagnostic", "radiology", "life-science", "lifescience",
    "wellness", "provider", "payer", "telehealth", "telemedicine",
    "legal", "law", "contract", "litigation", "attorney", "counsel",
    "compliance", "regulatory", "discovery",
    "finance", "financial", "banking", "insurance", "investment",
    "fintech", "capital", "trading", "fraud", "risk", "wealth",
    "manufactur", "production", "supply-chain", "factory", "industrial",
    "quality", "mes", "inventory", "procurement",
    "hr", "human-resources", "employee", "workforce", "talent",
    "recruiting", "onboarding", "payroll",
    "government", "federal", "public-sector", "defense",
    "education", "university", "school", "academic", "learning",
    "retail", "ecommerce", "merchandis",
    "energy", "utilities", "renewable", "grid",
    "telecom", "5g", "network",
    "media", "entertainment", "streaming", "publishing",
    "security", "cybersecurity", "threat", "soc",
    # generic enterprise signals
    "solution", "industry", "industries", "customer", "stories",
    "case-study", "enterprise", "connector", "workflow",
    "integration", "agent", "news", "blog", "tutorial", "resource",
    "announcement", "use-case", "product", "platform",
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
        log.debug("Rejected url=%s reason=non-http scheme=%s", url, parsed.scheme)
        return False

    netloc      = parsed.netloc.lower()
    netloc_bare = netloc.removeprefix("www.")

    if any(bd in netloc for bd in cfg.blocked_domains):
        log.debug("Rejected url=%s reason=blocked domain netloc=%s", url, netloc)
        return False

    allowed_bare = [d.removeprefix("www.") for d in cfg.allowed_domains]
    if not any(netloc_bare == d or netloc_bare.endswith("." + d) for d in allowed_bare):
        log.debug("Rejected url=%s reason=domain not in allowlist netloc=%s", url, netloc_bare)
        return False

    path = parsed.path.lower()

    if any(path.endswith(ext) for ext in _SKIP_EXTENSIONS):
        ext = next(ext for ext in _SKIP_EXTENSIONS if path.endswith(ext))
        log.debug("Rejected url=%s reason=bad extension ext=%s", url, ext)
        return False

    segments = set(path.strip("/").split("/"))
    bad_segs = segments & _GENERIC_SKIP_SEGMENTS
    if bad_segs:
        log.debug("Rejected url=%s reason=skip segment segments=%s", url, bad_segs)
        return False

    if "/" not in cfg.allowed_path_prefixes:
        if not any(
            path == p.lower().rstrip("/") or path.startswith(p.lower())
            for p in cfg.allowed_path_prefixes
        ):
            log.debug(
                "Rejected url=%s reason=bad path prefix path=%s allowed_prefixes=%s",
                url, path, cfg.allowed_path_prefixes,
            )
            return False

    for pattern in cfg.blocked_path_patterns:
        if re.search(pattern, path):
            log.debug("Rejected url=%s reason=blocked pattern pattern=%s path=%s", url, pattern, path)
            return False

    return True


def is_relevant_link(
    url: str,
    seed_set: frozenset,
    link_keywords: list[str] | None = None,
) -> bool:
    if normalize_url(url) in seed_set:
        log.debug("Relevant (seed match): url=%s", url)
        return True
    if link_keywords is not None and len(link_keywords) == 0:
        return True
    path = urlparse(url).path.lower()
    keywords = link_keywords if link_keywords is not None else _DEFAULT_LINK_KEYWORDS
    matched_kw = next((kw for kw in keywords if kw in path), None)
    if matched_kw:
        log.debug("Relevant (keyword match): url=%s keyword=%s", url, matched_kw)
        return True
    log.debug("Rejected as irrelevant: url=%s path=%s", url, path)
    return False
