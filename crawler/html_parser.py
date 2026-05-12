"""HTML text extraction and link utilities."""
from __future__ import annotations

import random
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler.url_filter import normalize_url

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_BLOCK_SIGNALS = frozenset({
    "just a moment...",
    "checking your browser before accessing",
    "ray id:",
    "ddos protection by cloudflare",
    "verify you are human",
    "are you a robot",
    "human verification",
    "captcha required",
    "403 forbidden",
})

_ERROR_SIGNALS = frozenset({
    "this page could not be found", "404 not found", "page not found",
    "this site can't be reached", "err_connection_refused",
    "dns_probe_finished_nxdomain",
})

_SKIP_CLS_RE = re.compile(
    r'\b(?:footer|header|nav|menu|sidebar|banner|promo|cta|signup|login'
    r'|subscribe|breadcrumb|social|share|popup|modal|cookie|notification'
    r'|advert|advertisement|pagination|toolbar|floating|sticky)\b'
)

_BLOCK_TAGS = frozenset({
    "p", "div", "section", "article", "main", "li", "ul", "ol",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "code", "td", "th", "tr", "dt", "dd", "br", "hr",
})

_REMOVE_TAGS = [
    "script", "style", "noscript", "svg", "footer",
    "nav", "header", "form", "iframe", "img", "video",
    "audio", "canvas", "button", "aside", "input",
    "textarea", "label", "select", "option", "meta",
    "link", "source", "picture", "figure", "figcaption",
    "dialog", "embed", "object", "portal", "track",
    "map", "area", "ins", "del", "sup", "sub",
]


def random_ua() -> str:
    return random.choice(_UA_POOL)


def is_blocked_or_error(html: str) -> bool:
    lo = html.lower()[:3000]
    return any(s in lo for s in _BLOCK_SIGNALS | _ERROR_SIGNALS)


def _semantic_cls(class_str: str) -> str:
    """Strip Tailwind non-semantic tokens before running the skip-class check."""
    return ' '.join(
        t for t in class_str.split()
        if '[' not in t and '(' not in t and ':' not in t and not t.startswith('@')
    )


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in _REMOVE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()

    for el in soup.find_all(True):
        if not el.attrs:
            continue
        classes    = _semantic_cls(" ".join(el.get("class", [])).lower())
        element_id = str(el.get("id", "")).lower()
        if _SKIP_CLS_RE.search(classes) or _SKIP_CLS_RE.search(element_id):
            el.decompose()

    for el in soup.find_all(_BLOCK_TAGS):
        el.insert_before("\n")
        el.insert_after("\n")

    text  = soup.get_text(separator="")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line.strip())


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        abs_url = urljoin(base_url, href)
        links.append(normalize_url(abs_url))
    return links
