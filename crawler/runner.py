"""Per-vendor crawl loop and CLI entry point."""
from __future__ import annotations

import argparse
import logging
import os
import random
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

import db
import llm_client as llm
import crawler.state as state
from crawler.config import (
    LLM_WORKERS, MAX_PAGES_PER_VENDOR, PAGE_TIMEOUT_MS,
    PROXY_URL, REQUEST_DELAY_S, VENDOR_CONFIGS, VendorConfig,
)
from crawler.fetcher import apply_stealth, get_page_content
from crawler.html_parser import extract_text_from_html, extract_links, random_ua
from crawler.pipeline import extract_from_page, post_vendor_validate_and_quality
from crawler.url_filter import normalize_url, is_allowed_url, is_relevant_link

log = logging.getLogger("crawler.runner")

# JSONL backups land in the data/ directory next to this package
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _jsonl_path(slug: str) -> str:
    os.makedirs(_DATA_DIR, exist_ok=True)
    return os.path.join(_DATA_DIR, f"{slug}_data.jsonl")


def _browser_args() -> list[str]:
    return [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-accelerated-2d-canvas",
        "--no-first-run",
        "--no-zygote",
        "--disable-gpu",
    ]


def _browser_context_kwargs(proxy_url: str) -> dict:
    kwargs: dict = dict(
        viewport={"width": 1920, "height": 1080},
        user_agent=random_ua(),
        locale="en-US",
        timezone_id="America/New_York",
        java_script_enabled=True,
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
        },
    )
    if proxy_url:
        kwargs["proxy"] = {"server": proxy_url}
    return kwargs


def crawl_vendor(cfg: VendorConfig) -> dict:
    log.info("=" * 70)
    log.info("[START] %-30s  brand='%s'", cfg.name, cfg.product_brand)
    log.info("=" * 70)

    jsonl_path = _jsonl_path(cfg.slug)
    stats: dict = {
        "pages_visited":         0,
        "llm_tasks_sent":        0,
        "raw_saved":             0,
        "extracted_saved":       0,
        "duplicates_skipped":    0,
        "filtered_skipped":      0,
        "lang_skipped":          0,
        "llm_errors":            0,
        "validated_removed":     0,
        "quality_dupes_removed": 0,
        "quality_pages_crawled": 0,
        "quality_new_found":     0,
    }
    lock        = threading.Lock()
    discovered: set[str] = set()

    seed_set = frozenset(normalize_url(u) for u in cfg.seed_urls)
    frontier  = list(cfg.seed_urls)
    visited:  set[str] = set()
    llm_futures: list  = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=(cfg.browser_mode != "headed"),
            slow_mo=100,
            args=_browser_args(),
        )
        context = browser.new_context(**_browser_context_kwargs(PROXY_URL))

        if cfg.browser_mode in ("stealth", "headed"):
            apply_stealth(context)

        page = context.new_page()

        if cfg.seed_urls:
            home = "https://" + urlparse(cfg.seed_urls[0]).netloc
            try:
                page.goto(home, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
                page.wait_for_timeout(random.randint(2500, 4000))
                log.info("[WARMUP] Session at %s", home)
            except Exception:
                pass

        max_pages = cfg.max_pages or MAX_PAGES_PER_VENDOR
        with ThreadPoolExecutor(max_workers=LLM_WORKERS) as executor:
            while frontier and stats["pages_visited"] < max_pages:
                if state.stop_requested:
                    log.warning("[STOP] Stopping %s early.", cfg.name)
                    break

                with lock:
                    current_saved = stats.get("extracted_saved", 0)
                if current_saved >= cfg.target_sub_offerings:
                    log.info(
                        "[STOP] Target of %d sub-offerings reached for %s — stopping crawl.",
                        cfg.target_sub_offerings, cfg.name,
                    )
                    break

                url  = frontier.pop(0)
                norm = normalize_url(url)

                if norm in visited:
                    continue
                if not is_allowed_url(url, cfg):
                    continue
                visited.add(norm)

                log.info(
                    "[CRAWL] %-12s [%d/%d] %s",
                    cfg.slug, stats["pages_visited"] + 1,
                    max_pages, url,
                )

                html, final_url = get_page_content(page, url, cfg.browser_mode, cfg.extra_wait_ms)
                if not html:
                    continue

                time.sleep(REQUEST_DELAY_S)
                stats["pages_visited"] += 1

                text     = extract_text_from_html(html)
                text_len = len(text.strip())
                if text_len < 200:
                    log.info("[SKIP] Too little text (%d chars) — %r … : %s",
                             text_len, text.strip()[:120], url)
                    continue
                log.info("[TEXT] %s — extracted %d chars", url, text_len)

                if not db.is_english_text(text[:500]):
                    log.info("[SKIP] Non-English: %s", url)
                    continue

                effective_url = final_url or url
                raw_data_id   = db.save_raw_to_db(effective_url, text, cfg.slug)
                if raw_data_id:
                    with lock:
                        stats["raw_saved"] += 1
                    future = executor.submit(
                        extract_from_page,
                        effective_url, text, cfg,
                        raw_data_id, discovered, stats, lock, jsonl_path,
                    )
                    llm_futures.append(future)

                for link in extract_links(html, effective_url):
                    link_norm = normalize_url(link)
                    if (
                        link_norm not in visited
                        and is_allowed_url(link, cfg)
                        and is_relevant_link(link, seed_set, cfg.link_keywords)
                    ):
                        frontier.append(link)

            # Drain all LLM tasks before running validation
            pending = sum(1 for f in llm_futures if not f.done())
            if pending:
                log.info("[WAIT] Draining %d LLM task(s) for %s…", pending, cfg.name)
            for fut in as_completed(llm_futures):
                try:
                    fut.result()
                except Exception as e:
                    log.error("[LLM] Task error: %s", e)

        post_vendor_validate_and_quality(
            cfg, page, visited, discovered, stats, lock, jsonl_path,
        )

        context.close()
        browser.close()

    log.info(
        "[DONE] %-30s pages=%d  new=%d  dupes=%d  filtered=%d  removed=%d  "
        "q_dupes=%d  q_gap_pages=%d  q_new=%d  llm_err=%d",
        cfg.name,
        stats["pages_visited"], stats["extracted_saved"],
        stats["duplicates_skipped"], stats["filtered_skipped"],
        stats["validated_removed"],
        stats["quality_dupes_removed"], stats["quality_pages_crawled"],
        stats["quality_new_found"], stats["llm_errors"],
    )
    if discovered:
        log.info(
            "[OFFERINGS] %d unique sub-offerings for '%s':",
            len(discovered), cfg.product_brand,
        )
        for i, name in enumerate(sorted(discovered), 1):
            log.info("  %2d. %s", i, name)

    return stats


def _handle_signal(signum, _frame) -> None:
    state.stop_requested = True
    sig = "SIGINT" if signum == signal.SIGINT else f"signal {signum}"
    log.warning("[STOP] %s received — finishing current page…", sig)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Build a name→slugs index for vendor-name resolution
    _name_index: dict[str, list[str]] = {}
    for _slug, _cfg in VENDOR_CONFIGS.items():
        _name_index.setdefault(_cfg.name.lower(), []).append(_slug)

    _valid_names = sorted({c.name for c in VENDOR_CONFIGS.values()})

    parser = argparse.ArgumentParser(
        prog="generic_crawler",
        description=(
            "AI capabilities crawler — 2-pass LLM pipeline "
            "(extract+validate -> audit+quality) across sectors and vendors"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python generic_crawler.py                          # all vendors, all sectors\n"
            "  python generic_crawler.py --vendor anthropic       # all Anthropic sectors\n"
            "  python generic_crawler.py --vendor openai --vendor harvey\n"
            "  python generic_crawler.py --group enterprise_ai\n"
            "  python generic_crawler.py --list\n"
            "\nVendor names: " + ", ".join(_valid_names)
        ),
    )
    parser.add_argument(
        "--vendor", metavar="NAME", action="append", dest="vendors",
        help=(
            "Vendor name to crawl — runs ALL sectors for that vendor (repeatable). "
            "e.g. --vendor anthropic  runs healthcare + legal + financial. "
            "Use --list to see all vendors and their sectors."
        ),
    )
    parser.add_argument(
        "--group", metavar="GROUP",
        choices=["frontier_llm", "cloud_platform", "enterprise_ai", "vertical_ai"],
        help="Crawl all vendors in this group (all sectors).",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Print all vendors, their sectors, and module offerings, then exit.",
    )
    args = parser.parse_args()

    if args.list:
        # Group by vendor name, then sector within each vendor
        by_vendor: dict[str, list[tuple[str, VendorConfig]]] = {}
        for slug, cfg in VENDOR_CONFIGS.items():
            by_vendor.setdefault(cfg.name, []).append((slug, cfg))
        for vendor_name, entries in by_vendor.items():
            print(f"\n  {vendor_name}")
            for slug, cfg in entries:
                print(f"    [{cfg.group:<20}]  {cfg.product_brand}")
        print()
        return

    if args.vendors:
        targets: dict[str, VendorConfig] = {}
        for vendor_arg in args.vendors:
            key = vendor_arg.lower()
            if key in _name_index:
                # Match by vendor name — picks up all sectors
                for slug in _name_index[key]:
                    targets[slug] = VENDOR_CONFIGS[slug]
            elif vendor_arg in VENDOR_CONFIGS:
                # Fallback: exact slug still works
                targets[vendor_arg] = VENDOR_CONFIGS[vendor_arg]
            else:
                parser.error(
                    f"Unknown vendor: {vendor_arg!r}\n"
                    f"Valid vendor names: {', '.join(_valid_names)}"
                )
    elif args.group:
        targets = {s: c for s, c in VENDOR_CONFIGS.items() if c.group == args.group}
    else:
        targets = VENDOR_CONFIGS

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    log.info("Initialising database…")
    db.init_db()

    all_stats: dict[str, dict] = {}
    for slug, cfg in targets.items():
        if state.stop_requested:
            break
        try:
            all_stats[slug] = crawl_vendor(cfg)
        except KeyboardInterrupt:
            log.warning("[STOP] KeyboardInterrupt.")
            break
        except Exception as e:
            log.error("[VENDOR] Fatal error for %s: %s", cfg.name, e)
            all_stats[slug] = {"error": str(e)}

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  CRAWL SUMMARY  (2-pass: extract+validate -> audit+quality)")
    print("=" * 80)
    total_new = 0
    for slug, stats in all_stats.items():
        cfg = VENDOR_CONFIGS[slug]
        if "error" in stats:
            print(f"  {cfg.product_brand:<42} ERROR: {stats['error']}")
        else:
            n = stats.get("extracted_saved", 0)
            total_new += n
            print(
                f"  {cfg.product_brand:<42} "
                f"pages={stats.get('pages_visited', 0):>3}  "
                f"new={n:>3}  "
                f"dupes={stats.get('duplicates_skipped', 0):>3}  "
                f"removed={stats.get('validated_removed', 0):>2}  "
                f"q_dedup={stats.get('quality_dupes_removed', 0):>2}  "
                f"q_gap_pages={stats.get('quality_pages_crawled', 0):>2}  "
                f"q_new={stats.get('quality_new_found', 0):>2}"
            )
    print(f"\n  Total offerings persisted: {total_new}")
    print("=" * 80)
