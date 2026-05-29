"""HTTP and Playwright-based page fetching with multi-layer bypass support."""
from __future__ import annotations

import json
import logging
import random
import time
from urllib.request import Request as UrlRequest, urlopen

from playwright.sync_api import Page

from crawler.config import PAGE_TIMEOUT_MS, PROXY_URL, FLARESOLVERR_URL
from crawler.html_parser import random_ua, is_blocked_or_error

log = logging.getLogger("tes.crawler.fetcher")

# ── Optional anti-bot libraries ───────────────────────────────────────────────
try:
    from curl_cffi import requests as _curl_requests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False
    log.warning("curl_cffi not installed — TLS fingerprint impersonation disabled")

try:
    import cloudscraper as _cloudscraper_lib
    _HAS_CLOUDSCRAPER = True
except ImportError:
    _HAS_CLOUDSCRAPER = False
    log.warning("cloudscraper not installed — Cloudflare JS solver disabled")

try:
    from playwright_stealth import Stealth
    _HAS_STEALTH = True
except ImportError:
    _HAS_STEALTH = False
    log.warning("playwright_stealth not installed — stealth mode disabled")


def apply_stealth(context) -> None:
    """Apply playwright-stealth to a browser context if available."""
    if _HAS_STEALTH:
        try:
            Stealth().apply_stealth_sync(context)
        except Exception as e:
            log.debug("[STEALTH] Patch error: %s", e)


def http_fetch(url: str, timeout: int = 20) -> str | None:
    """Layer 1: curl_cffi with Chrome TLS impersonation, fallback to urllib."""
    ua = random_ua()
    if _HAS_CURL_CFFI:
        log.debug("Layer 1a (curl_cffi): attempting url=%s", url)
        try:
            proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
            resp = _curl_requests.get(
                url,
                impersonate="chrome124",
                timeout=timeout,
                proxies=proxies,
                headers={"Accept-Language": "en-US,en;q=0.9", "User-Agent": ua},
            )
            if resp.status_code == 200:
                log.info("Layer 1a (curl_cffi) succeeded: url=%s size=%d chars", url, len(resp.text))
                return resp.text
            log.debug("Layer 1a (curl_cffi) non-200: url=%s status=%d", url, resp.status_code)
        except Exception as e:
            log.debug("Layer 1a (curl_cffi) error: url=%s error=%s", url, e)

    log.debug("Layer 1b (urllib): attempting url=%s", url)
    try:
        req = UrlRequest(url, headers={
            "User-Agent":      ua,
            "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control":   "no-cache",
        })
        with urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            log.info("Layer 1b (urllib) succeeded: url=%s size=%d chars", url, len(html))
            return html
    except Exception as e:
        log.debug("Layer 1b (urllib) error: url=%s error=%s", url, e)
        return None


def cloudscraper_fetch(url: str, timeout: int = 30) -> str | None:
    """Layer 2: cloudscraper solves Cloudflare JS challenges."""
    if not _HAS_CLOUDSCRAPER:
        return None
    log.debug("Layer 2 (cloudscraper): attempting url=%s", url)
    try:
        proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
        scraper = _cloudscraper_lib.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        resp = scraper.get(url, timeout=timeout, proxies=proxies)
        if resp.status_code == 200:
            log.info("Layer 2 (cloudscraper) succeeded: url=%s size=%d chars", url, len(resp.text))
            return resp.text
        log.debug("Layer 2 (cloudscraper) non-200: url=%s status=%d", url, resp.status_code)
    except Exception as e:
        log.debug("Layer 2 (cloudscraper) error: url=%s error=%s", url, e)
    return None


def flaresolverr_fetch(url: str, timeout: int = 60) -> str | None:
    """Layer 3: FlareSolverr reverse-proxy (requires service at FLARESOLVERR_URL)."""
    if not FLARESOLVERR_URL:
        return None
    log.debug("Layer 3 (flaresolverr): attempting url=%s endpoint=%s", url, FLARESOLVERR_URL)
    try:
        payload = json.dumps({
            "cmd": "request.get",
            "url": url,
            "maxTimeout": timeout * 1000,
        }).encode()
        req = UrlRequest(
            f"{FLARESOLVERR_URL.rstrip('/')}/v1",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=timeout + 10) as resp:
            result = json.loads(resp.read().decode())
        if result.get("status") == "ok":
            html = result["solution"]["response"]
            log.info("Layer 3 (flaresolverr) succeeded: url=%s size=%d chars", url, len(html))
            return html
        log.debug("Layer 3 (flaresolverr) non-ok status: url=%s result_status=%s", url, result.get("status"))
    except Exception as e:
        log.debug("Layer 3 (flaresolverr) error: url=%s error=%s", url, e)
    return None


def http_fetch_all(url: str) -> str | None:
    """Try all HTTP layers in order; return first non-blocked result."""
    for fn, label in [
        (http_fetch,          "curl_cffi/urllib"),
        (cloudscraper_fetch,  "cloudscraper"),
        (flaresolverr_fetch,  "flaresolverr"),
    ]:
        html = fn(url)
        if html and not is_blocked_or_error(html):
            return html
        if html:
            log.warning("Bypass layer still blocked: url=%s layer=%s — trying next layer", url, label)
    log.error("All HTTP fetch layers failed: url=%s", url)
    return None


def dismiss_consent_banners(page: Page) -> None:
    selectors = [
        '#onetrust-accept-btn-handler',            # ServiceNow / OneTrust
        'button#wcpConsentBannerCtrlAcceptAllBtn', # Microsoft WCP consent
        'button:has-text("Accept all cookies")',   # Microsoft variant
        'button:has-text("Accept all")', 'button:has-text("Accept All")',
        'button:has-text("Accept cookies")', 'button:has-text("I accept")',
        'button:has-text("Agree")', 'button:has-text("Got it")',
        'button:has-text("I agree")',
    ]
    for sel in selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
                break
        except Exception:
            pass


def get_page_content(
    page: Page,
    url: str,
    browser_mode: str,
    extra_wait_ms: int = 0,
) -> tuple[str | None, str | None]:
    """Fetch a page using Playwright (with HTTP fallback). Returns (html, final_url)."""
    if browser_mode == "http_only":
        html = http_fetch_all(url)
        return (html, url) if html else (None, None)

    last_exc = None
    max_attempts = 1 if browser_mode == "headed" else 2
    for attempt in range(max_attempts):
        try:
            resp = page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")

            try:
                page.wait_for_load_state("networkidle", timeout=25_000)
            except Exception:
                pass

            # Wait for actual paragraph content — critical for JS-heavy SPAs
            # (mirrors the pattern in the legacy OpenAI crawler)
            try:
                page.wait_for_selector(
                    "main p, article p, section p,"
                    "[class*='content'] p, [class*='rich-text'] p, "
                    "[data-bi-area], .ms-hero, .c-heading, "
                    ".sp-hero, .sp-widget, [class*='NowTemplate'], "
                    "[class*='hero-content'], [class*='section-content']",
                    timeout=30_000,
                )
            except Exception:
                pass

            wait_ms = max(extra_wait_ms, random.randint(2000, 4000))
            page.wait_for_timeout(wait_ms)

            for _ in range(random.randint(2, 5)):
                page.mouse.wheel(0, random.randint(500, 2000))
                page.wait_for_timeout(random.randint(800, 1500))

            # Scroll to page bottom to trigger all lazy-loaded content sections,
            # then re-wait for network idle before grabbing HTML.
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2500)
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)

            dismiss_consent_banners(page)
            page.wait_for_timeout(2000)  # allow re-render after banner dismissal

            status    = resp.status if resp else 0
            final_url = page.url
            html      = page.content()

            log.info("Playwright fetched page: url=%s status=%s size=%d chars", url, status, len(html))

            if status in (404, 410, 403, 401):
                log.debug("Skipping page with terminal HTTP status: url=%s status=%d", url, status)
                return None, None

            # For headed mode: Cloudflare JS challenge auto-resolves in ~5-10 s but
            # may still be active when we first read the HTML. Detect the interstitial
            # and wait it out before handing off to is_blocked_or_error.
            if browser_mode == "headed":
                _lo = html.lower()[:3000]
                if any(s in _lo for s in ("just a moment", "ray id:", "checking your browser")):
                    log.warning(
                        "Cloudflare interstitial detected — waiting 20s for auto-resolve: url=%s", url
                    )
                    page.wait_for_timeout(20_000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=10_000)
                    except Exception:
                        pass
                    html = page.content()

            if not is_blocked_or_error(html):
                log.info("Playwright layer succeeded: url=%s final_url=%s size=%d chars", url, final_url, len(html))
                return html, final_url

            log.warning("Playwright blocked for url=%s — falling back to HTTP bypass chain", url)
            fallback = http_fetch_all(url)
            if fallback:
                log.info("HTTP bypass chain succeeded after Playwright block: url=%s size=%d chars", url, len(fallback))
                return fallback, url

            if attempt == 0:
                sleep_t = (2 ** attempt) * random.randint(20, 40)
                log.warning("Backing off %ds before retry: url=%s attempt=%d", sleep_t, url, attempt + 1)
                time.sleep(sleep_t)
                try:
                    resp2 = page.goto(url, timeout=60_000, wait_until="domcontentloaded")
                    page.wait_for_load_state("networkidle", timeout=25_000)
                    page.wait_for_timeout(max(extra_wait_ms, random.randint(4000, 8000)))
                    dismiss_consent_banners(page)
                    html2 = page.content()
                    if not is_blocked_or_error(html2):
                        log.info("Retry succeeded after backoff: url=%s size=%d chars", url, len(html2))
                        return html2, page.url
                except Exception:
                    pass

            log.warning("Page inaccessible after all Playwright retries: url=%s", url)
            return None, None

        except Exception as e:
            last_exc = e
            log.debug("Playwright exception on attempt %d: url=%s error=%s", attempt + 1, url, e)
            if attempt == 0:
                continue

    fallback = http_fetch_all(url)
    if fallback:
        log.info("HTTP bypass chain succeeded after Playwright exception: url=%s size=%d chars", url, len(fallback))
        return fallback, url
    log.error("All fetch methods failed: url=%s last_error=%s", url, last_exc)
    return None, None
