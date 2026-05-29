"""
crawler/pricing.py
==================
Phase 3 of the vendor crawl — lightweight pricing extraction.

Runs after post_vendor_validate_and_quality() for each vendor:
  1. Fetches cfg.pricing_seed_urls (up to cfg.pricing_max_pages pages)
     using the Playwright page that is already open in runner.py
  2. Passes scraped text to LLM with all sub-offerings for this vendor
  3. Saves results to offering_pricing table with:
       pricing_source  = 'crawled'
       confidence_score = 0.90  (CONFIDENCE_CRAWLED)
       exact_text       = verbatim proof snippet from the page

For vendors with pricing_seed_urls=[] (enterprise / contact-sales):
  • Skipped silently — offering_pricing rows will be written at API
    query time with pricing_source='llm_inferred', confidence_score=0.30

Sub-offerings already in offering_pricing are updated (upsert), not duplicated.
"""
from __future__ import annotations

import json
import logging
import time

import psycopg2.extras

import db
import llm_client as llm
from crawler.config import LLM_MODEL, VendorConfig
from crawler.fetcher import get_page_content
from crawler.html_parser import extract_text_from_html

log = logging.getLogger("tes.crawler.pricing")

# ── Max chars of scraped text passed to LLM (keeps token cost controlled) ─────
_PAGE_CHAR_CAP = 14_000

# ── System prompt for CRAWLED pricing extraction ──────────────────────────────
_CRAWLED_SYSTEM_PROMPT = """\
You are a pricing data extraction assistant.

You receive ACTUAL TEXT scraped from a vendor's official pricing or product pages,
and a list of sub-offering names from a product database.

For each sub-offering, find and extract pricing ONLY from the provided page text.

Return a JSON ARRAY — one object per sub-offering — with these exact keys:
  sub_offering    : (string) copy verbatim from the input list
  pricing_model   : one of:
                    pay_per_token | per_seat | tiered | contact_sales |
                    free | usage_based | unknown
  pricing_summary : <= 25 words describing the cost structure
  input_cost      : string or null  (e.g. "$3.00 per 1M input tokens")
  output_cost     : string or null  (e.g. "$15.00 per 1M output tokens")
  tiers           : array of {name, price, features} objects, or []
  notes           : <= 20 words on limits, discounts, or caveats, or null
  exact_text      : VERBATIM snippet from the page confirming this pricing
                    (max 400 chars) — or null if not found in the text
  source_url      : the page URL where pricing was found, or null

Rules:
  - Do NOT hallucinate. Only use pricing numbers visible in the page text.
  - exact_text MUST be a verbatim quote from the page, not a paraphrase.
  - If a sub-offering's pricing is not in the text:
      pricing_model = "unknown", exact_text = null
  - API / developer / model sub-offerings  -> likely pay_per_token
  - Team / enterprise / business plans     -> likely per_seat or contact_sales
  - Return ONLY the JSON array. No markdown. No explanation outside the JSON.
"""


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _fetch_vendor_sub_offerings(product_brand: str) -> list[dict]:
    """Load all sub-offerings for this vendor from extracted_offerings."""
    conn = db.get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """SELECT id, vendor, sub_offering, module_offering
               FROM extracted_offerings
               WHERE vendor ILIKE %s
               ORDER BY id;""",
            (product_brand,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        log.debug(
            "Loaded %d sub-offering(s) for pricing from extracted_offerings: vendor=%r",
            len(rows), product_brand,
        )
        return rows
    except Exception as e:
        log.error(
            "Failed to load sub-offerings for vendor=%r: %s", product_brand, e,
            exc_info=True,
        )
        return []
    finally:
        cur.close()
        conn.close()


# ── Crawl helpers ──────────────────────────────────────────────────────────────

def _crawl_pricing_pages(cfg: VendorConfig, page) -> list[dict]:
    """
    Fetch up to cfg.pricing_max_pages seed URLs.
    Returns a list of {"url": str, "text": str} dicts (the pricing corpus).
    """
    corpus:  list[dict] = []
    visited: set[str]   = set()

    for url in cfg.pricing_seed_urls[: cfg.pricing_max_pages]:
        if url in visited:
            continue
        visited.add(url)

        log.info(
            "Pricing crawl [%d/%d]: url=%s",
            len(visited), min(len(cfg.pricing_seed_urls), cfg.pricing_max_pages), url,
        )

        html, final_url = get_page_content(
            page, url, cfg.browser_mode, cfg.extra_wait_ms
        )
        if not html:
            log.warning("Pricing page returned no content — skipping: url=%s", url)
            continue

        time.sleep(1.5)   # polite delay between pricing page fetches

        text     = extract_text_from_html(html)
        text_len = len(text.strip())

        if text_len < 200:
            log.warning(
                "Pricing page too short (%d chars) — skipping: url=%s", text_len, url
            )
            continue

        log.info(
            "Pricing page extracted: url=%s  text=%d chars", url, text_len
        )
        corpus.append({"url": final_url or url, "text": text})

    log.info(
        "Pricing crawl complete: %d/%d page(s) usable for vendor=%r",
        len(corpus),
        min(len(cfg.pricing_seed_urls), cfg.pricing_max_pages),
        cfg.name,
    )
    return corpus


# ── LLM extraction ─────────────────────────────────────────────────────────────

def _extract_pricing_with_llm(
    sub_offerings: list[dict],
    corpus: list[dict],
    batch_size: int = 10,
) -> list[dict]:
    """
    Send sub-offerings in batches to the LLM with the scraped corpus.
    Returns a flat list of pricing dicts.
    """
    # Build corpus text up to PAGE_CHAR_CAP
    corpus_text = ""
    pages_used  = 0
    for pg in corpus:
        snippet   = f"\n\n--- PAGE: {pg['url']} ---\n{pg['text']}"
        remaining = _PAGE_CHAR_CAP - len(corpus_text)
        if remaining <= 0:
            break
        corpus_text += snippet[:remaining]
        pages_used  += 1

    log.debug(
        "Corpus for LLM: %d chars from %d page(s)", len(corpus_text), pages_used
    )

    all_results: list[dict] = []
    total = len(sub_offerings)

    for start in range(0, total, batch_size):
        batch     = sub_offerings[start : start + batch_size]
        batch_num = start // batch_size + 1
        total_b   = (total + batch_size - 1) // batch_size

        log.info(
            "Pricing LLM batch %d/%d: %d sub-offering(s)",
            batch_num, total_b, len(batch),
        )

        sub_list = "\n".join(f"  - {r['sub_offering']}" for r in batch)
        user_msg = (
            f"=== SCRAPED PRICING PAGE CONTENT ===\n{corpus_text}\n\n"
            f"=== SUB-OFFERINGS TO PRICE ===\n{sub_list}\n\n"
            f"Return the JSON array."
        )

        try:
            completion = llm.create_chat_completion(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": _CRAWLED_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=4_000,
                response_format={"type": "json_object"},
            )
            raw = llm.parse_json_content(completion)

            # Normalise: LLM might wrap array in a dict key
            if isinstance(raw, dict):
                for key in ("results", "offerings", "pricing", "data", "items"):
                    if key in raw and isinstance(raw[key], list):
                        raw = raw[key]
                        break
                else:
                    raw = [raw]  # single-item response

            all_results.extend(raw)

            # Warn about any sub-offerings the LLM dropped
            returned = {r.get("sub_offering") for r in raw}
            expected = {r["sub_offering"] for r in batch}
            missing  = expected - returned
            if missing:
                log.warning(
                    "Pricing LLM batch %d/%d: %d sub-offering(s) missing from "
                    "response — saving as pricing_model='unknown': %s",
                    batch_num, total_b, len(missing), sorted(missing),
                )
                for name in missing:
                    all_results.append({
                        "sub_offering":    name,
                        "pricing_model":   "unknown",
                        "pricing_summary": "Not found in pricing pages.",
                        "input_cost":      None,
                        "output_cost":     None,
                        "tiers":           [],
                        "notes":           "Pricing page did not contain data for this sub-offering.",
                        "exact_text":      None,
                        "source_url":      None,
                    })

        except Exception as e:
            log.error(
                "Pricing LLM call failed for batch %d/%d: %s",
                batch_num, total_b, e,
                exc_info=True,
            )
            # Graceful fallback — mark all as unknown so they can be retried
            for r in batch:
                all_results.append({
                    "sub_offering":    r["sub_offering"],
                    "pricing_model":   "unknown",
                    "pricing_summary": "LLM extraction failed — retry.",
                    "input_cost":      None,
                    "output_cost":     None,
                    "tiers":           [],
                    "notes":           "LLM call failed. Re-run crawler to retry.",
                    "exact_text":      None,
                    "source_url":      None,
                })

    return all_results


# ── Public entry point ─────────────────────────────────────────────────────────

def crawl_and_extract_pricing(
    cfg: VendorConfig,
    page,
    stats: dict,
    lock,
) -> None:
    """
    Phase 3: Lightweight pricing crawl for one vendor.
    Called from crawler/runner.py after post_vendor_validate_and_quality().

    If cfg.pricing_seed_urls is empty: silently skipped (enterprise/contact-sales vendors).
    All results are written to offering_pricing (upsert — safe to re-run).
    """
    if not cfg.pricing_seed_urls:
        log.debug(
            "Pricing Phase 3 skipped — no pricing_seed_urls for vendor=%r "
            "(likely contact-sales; pricing will be LLM-inferred at query time)",
            cfg.name,
        )
        return

    if not llm.has_llm_client():
        log.warning(
            "Pricing Phase 3 skipped — LLM client not configured (LLM_API_KEY missing)"
        )
        return

    log.info(
        "Pricing Phase 3 starting: vendor=%r  pricing_pages=%d  max=%d",
        cfg.name, len(cfg.pricing_seed_urls), cfg.pricing_max_pages,
    )

    # ── Step 1: Load sub-offerings from DB ────────────────────────────────────
    sub_offerings = _fetch_vendor_sub_offerings(cfg.product_brand)
    if not sub_offerings:
        log.warning(
            "Pricing Phase 3: no sub-offerings in DB for vendor=%r — skipping. "
            "Run the main crawl first to populate extracted_offerings.",
            cfg.name,
        )
        return

    log.info(
        "Pricing Phase 3: %d sub-offering(s) to price for vendor=%r",
        len(sub_offerings), cfg.name,
    )

    # ── Step 2: Crawl pricing pages ───────────────────────────────────────────
    corpus = _crawl_pricing_pages(cfg, page)
    if not corpus:
        log.warning(
            "Pricing Phase 3: no usable pricing pages fetched for vendor=%r. "
            "Possible causes: pages blocked, domains restricted, or pricing_seed_urls "
            "need updating. Sub-offerings will fall back to LLM inference at query time.",
            cfg.name,
        )
        return

    # ── Step 3: LLM extraction ────────────────────────────────────────────────
    priced = _extract_pricing_with_llm(sub_offerings, corpus)

    # ── Step 4: Save to DB ────────────────────────────────────────────────────
    id_map = {r["sub_offering"]: r["id"] for r in sub_offerings}

    saved = unknown = skipped = 0
    for item in priced:
        sub = item.get("sub_offering", "")
        oid = id_map.get(sub)
        if not oid:
            log.debug(
                "Pricing result for unrecognised sub_offering=%r — skipping", sub
            )
            skipped += 1
            continue

        db.save_offering_pricing({
            "offering_id":     oid,
            "vendor":          cfg.product_brand,
            "sub_offering":    sub,
            "pricing_model":   item.get("pricing_model", "unknown"),
            "pricing_summary": item.get("pricing_summary"),
            "input_cost":      item.get("input_cost"),
            "output_cost":     item.get("output_cost"),
            "tiers":           item.get("tiers", []),
            "notes":           item.get("notes"),
            "exact_text":      item.get("exact_text"),
            "source_url":      item.get("source_url") or corpus[0]["url"],
            "pricing_source":  "crawled",
            "confidence_score": db.CONFIDENCE_CRAWLED,
        })

        if item.get("pricing_model") in (None, "unknown"):
            unknown += 1
        else:
            saved += 1

    log.info(
        "Pricing Phase 3 complete: vendor=%r  priced=%d  unknown=%d  skipped=%d",
        cfg.name, saved, unknown, skipped,
    )
    if unknown:
        log.warning(
            "Pricing Phase 3: %d sub-offering(s) remain pricing_model='unknown' "
            "for vendor=%r — they will be inferred by LLM at API query time.",
            unknown, cfg.name,
        )

    with lock:
        stats["pricing_saved"]   = stats.get("pricing_saved",   0) + saved
        stats["pricing_unknown"] = stats.get("pricing_unknown", 0) + unknown
