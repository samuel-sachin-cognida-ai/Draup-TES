"""LLM extraction pipeline: Pass 1 (per-page) and Pass 2 (post-vendor audit)."""
from __future__ import annotations

import json
import logging
import threading
import time

import psycopg2.extras
from playwright.sync_api import Page

import db
import llm_client as llm
from crawler.config import LLM_MODEL, REQUEST_DELAY_S, VendorConfig
from crawler.fetcher import get_page_content
from crawler.html_parser import extract_text_from_html
from crawler.prompts import (
    extraction_system_prompt,
    validate_and_quality_system_prompt,
)
from crawler.url_filter import normalize_url, is_allowed_url
import crawler.state as state

log = logging.getLogger("tes.crawler.pipeline")

# Per-file JSONL write locks (thread-safe)
_jsonl_locks: dict[str, threading.Lock] = {}
_jsonl_locks_meta = threading.Lock()


def _get_jsonl_lock(path: str) -> threading.Lock:
    with _jsonl_locks_meta:
        if path not in _jsonl_locks:
            _jsonl_locks[path] = threading.Lock()
        return _jsonl_locks[path]


def normalize_capabilities(offerings: list[dict]) -> None:
    """Convert plain-string capabilities to rich objects (text/exact_text/source_location)."""
    for item in offerings:
        raw_caps = item.get("capabilities", [])
        if raw_caps and isinstance(raw_caps[0], str):
            item["capabilities"] = [
                {"text": c, "exact_text": "", "source_location": ""}
                for c in raw_caps
                if c
            ]


def extract_from_page(
    url: str,
    text: str,
    cfg: VendorConfig,
    raw_data_id: int,
    discovered: set[str],
    stats: dict,
    lock: threading.Lock,
    jsonl_path: str,
) -> None:
    """Pass 1: LLM extracts, validates, and cleans offerings from a single page."""
    if not llm.has_llm_client():
        return

    page_text = text[:40_000]
    log.debug("Pass 1 extraction: url=%s text_chars=%d", url, len(text))

    try:
        completion = llm.create_chat_completion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": extraction_system_prompt(cfg)},
                {"role": "user",   "content": f"URL: {url}\n\nPAGE TEXT:\n{page_text}"},
            ],
            temperature=0.0,
            max_tokens=6000,
            response_format={"type": "json_object"},
        )
        extracted = llm.parse_json_content(completion)
        offerings = extracted.get("offerings", []) if isinstance(extracted, dict) else []
        if not isinstance(offerings, list):
            offerings = []

        if not offerings:
            log.info("Pass 1: no offerings extracted from %s", url)
            with lock:
                stats["llm_tasks_sent"] += 1
            return

        normalize_capabilities(offerings)
        offerings = [db.prepare_offering_for_storage(item) for item in offerings]

        log.info("Pass 1: extracted %d offering(s) from %s", len(offerings), url)
        with lock:
            stats["llm_tasks_sent"] += 1

        jlock = _get_jsonl_lock(jsonl_path)
        log.debug("Saving %d offering(s) to JSONL backup: %s", len(offerings), jsonl_path)
        try:
            with jlock:
                with open(jsonl_path, "a", encoding="utf-8") as f:
                    for item in offerings:
                        if isinstance(item, dict):
                            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        except Exception:
            pass

        db.save_extracted_to_db(
            raw_data_id=raw_data_id,
            url=url,
            extracted={"offerings": offerings},
            product_brand=cfg.product_brand,
            discovered_sub_offerings=discovered,
            target_sub_offerings=cfg.target_sub_offerings,
            stats=stats,
            stats_lock=lock,
            disallowed_terms=cfg.disallowed_terms,
            too_generic_terms=cfg.too_generic_terms,
        )

    except json.JSONDecodeError as e:
        log.error("Pass 1 JSON parse error: url=%s  error=%s", url, e, exc_info=True)
        with lock:
            stats["llm_errors"] += 1
    except Exception as e:
        log.error("Pass 1 extraction failed: url=%s  error=%s", url, e, exc_info=True)
        with lock:
            stats["llm_errors"] += 1


def _bulk_delete(ids: list[int], label: str = "") -> int:
    """Delete offering rows by ID. Returns number of rows deleted."""
    if not ids:
        return 0
    conn = db.get_pg_connection()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM extracted_offerings WHERE id = ANY(%s);", (ids,))
        conn.commit()
        return cur.rowcount
    except Exception as e:
        conn.rollback()
        log.error("[%s] Bulk delete error: %s", label, e)
        return 0
    finally:
        cur.close()
        conn.close()


def _bulk_update_module_offering(
    id_to_mo: list[tuple[int, str]],
    label: str = "",
) -> int:
    """Update module_offering for (id, new_module_offering) pairs. Returns updated count."""
    if not id_to_mo:
        return 0
    conn = db.get_pg_connection()
    cur  = conn.cursor()
    try:
        updated = 0
        for row_id, new_mo in id_to_mo:
            cur.execute(
                "UPDATE extracted_offerings SET module_offering = %s WHERE id = %s;",
                (new_mo, row_id),
            )
            updated += cur.rowcount
        conn.commit()
        return updated
    except Exception as e:
        conn.rollback()
        log.error("[%s] Bulk update error: %s", label, e)
        return 0
    finally:
        cur.close()
        conn.close()


def _token_overlap(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / min(len(ta), len(tb)) if ta and tb else 0.0


def _char_jaccard(a: str, b: str) -> float:
    def trigrams(s: str) -> set:
        s = s.lower()
        return {s[i:i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}
    ta, tb = trigrams(a), trigrams(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _run_pass2(
    cfg: VendorConfig,
    module_offering: str,
    page: Page,
    visited: set[str],
    discovered: set[str],
    stats: dict,
    lock: threading.Lock,
    jsonl_path: str,
    _is_rerun: bool = False,
) -> None:
    """
    Combined Pass 2 for a single module_offering / sector:
      1. Language purge
      2. Exact-name dedup
      3. Near-name clustering (token overlap + Jaccard)
      4. Single LLM call → legitimacy + semantic dedup + gap analysis + module_offering correction
      5. Apply legitimacy deletions and semantic dedup deletions
      6. Apply module_offering corrections (UPDATE rows to correct sector)
      7. Targeted re-crawl for missing offerings
      8. Recurse once if new offerings were added
    """
    label = "VALIDATE+QUALITY" + (" [RERUN]" if _is_rerun else "")
    log.info("--- Pass 2: %s ---", module_offering)

    # ── Read current state from DB ────────────────────────────────────────────
    conn = db.get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT id, sub_offering, capabilities, tasks_examples, url
            FROM extracted_offerings
            WHERE module_offering = %s
            ORDER BY sub_offering, id;
            """,
            (module_offering,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

    if not rows:
        log.info("[%s] No offerings to process.", label)
        return

    # ── Language purge ────────────────────────────────────────────────────────
    non_english_ids = [r["id"] for r in rows if not db.is_english_text(r.get("sub_offering") or "")]
    rows = [r for r in rows if r["id"] not in set(non_english_ids)]

    if non_english_ids:
        deleted = _bulk_delete(non_english_ids, label=f"{label}:LANG")
        log.warning("Pass 2: purged %d non-English offering(s) for %s", deleted, module_offering)

    if not rows:
        log.info("[%s] No offerings remain after language purge.", label)
        return

    # ── Exact-name dedup ──────────────────────────────────────────────────────
    groups: dict[str, dict] = {}
    for r in rows:
        key = (r["sub_offering"] or "").strip().lower()
        if key not in groups:
            groups[key] = {
                "sub_offering": r["sub_offering"],
                "capabilities": [],
                "source_urls":  [],
                "row_ids":      [],
            }
        groups[key]["row_ids"].append(r["id"])
        if r["url"] and r["url"] not in groups[key]["source_urls"]:
            groups[key]["source_urls"].append(r["url"])
        for cap in (r["capabilities"] or []):
            if cap and cap not in groups[key]["capabilities"]:
                groups[key]["capabilities"].append(cap)

    exact_dup_ids: list[int] = []
    for g in groups.values():
        if len(g["row_ids"]) > 1:
            keep = min(g["row_ids"])
            exact_dup_ids.extend(rid for rid in g["row_ids"] if rid != keep)
            g["row_ids"] = [keep]

    if exact_dup_ids:
        deleted = _bulk_delete(exact_dup_ids, label=f"{label}:EXACT-DEDUP")
        log.info("[%s][EXACT-DEDUP] Removed %d exact-name duplicate(s).", label, deleted)
        with lock:
            stats["duplicates_skipped"] = stats.get("duplicates_skipped", 0) + deleted

    # ── Near-name clustering ──────────────────────────────────────────────────
    group_keys   = list(groups.keys())
    merged_into: dict[str, str] = {}

    for i in range(len(group_keys)):
        ki = group_keys[i]
        if ki in merged_into:
            continue
        for j in range(i + 1, len(group_keys)):
            kj = group_keys[j]
            if kj in merged_into:
                continue
            if _token_overlap(ki, kj) >= 0.99 or _char_jaccard(ki, kj) >= 0.65:
                canonical, dup = (ki, kj) if len(ki) >= len(kj) else (kj, ki)
                merged_into[dup] = canonical
                groups[canonical]["row_ids"].extend(groups[dup]["row_ids"])
                for su in groups[dup]["source_urls"]:
                    if su not in groups[canonical]["source_urls"]:
                        groups[canonical]["source_urls"].append(su)
                for cap in groups[dup]["capabilities"]:
                    if cap and cap not in groups[canonical]["capabilities"]:
                        groups[canonical]["capabilities"].append(cap)
                log.info(
                    "[%s][NEAR-DEDUP] Merged %r -> %r (tok=%.0f%% cj=%.0f%%)",
                    label, dup, canonical,
                    _token_overlap(dup, canonical) * 100,
                    _char_jaccard(dup, canonical) * 100,
                )

    near_dup_ids = [rid for dk in merged_into for rid in groups[dk]["row_ids"]]
    if near_dup_ids:
        deleted = _bulk_delete(near_dup_ids, label=f"{label}:NEAR-DEDUP")
        log.info("[%s][NEAR-DEDUP] Removed %d near-name duplicate(s).", label, deleted)
        with lock:
            stats["duplicates_skipped"] = stats.get("duplicates_skipped", 0) + deleted

    audit_list = [v for k, v in groups.items() if k not in merged_into]
    log.info("[%s] %d unique sub-offering(s) going to LLM audit.", label, len(audit_list))

    if not audit_list:
        log.info("[%s] Nothing left to audit after dedup.", label)
        return

    # ── Single LLM call: legitimacy + semantic dedup + gap analysis ───────────
    crawled_urls = sorted(visited)[:60]
    try:
        completion = llm.create_chat_completion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": validate_and_quality_system_prompt(cfg, module_offering=module_offering)},
                {"role": "user",   "content": json.dumps(
                    {"offerings": audit_list, "crawled_urls": crawled_urls},
                    indent=2,
                    ensure_ascii=False,
                )},
            ],
            temperature=0.0,
            max_tokens=6000,
            response_format={"type": "json_object"},
        )
        result = llm.parse_json_content(completion)
    except Exception as e:
        log.error("Pass 2 LLM call failed for %s: %s", module_offering, e, exc_info=True)
        return

    # ── Apply legitimacy verdicts ─────────────────────────────────────────────
    verdicts     = result.get("verdicts", [])
    invalid_ids: list[int] = []
    log.info("[%s][LEGITIMACY] %d verdict(s):", label, len(verdicts))
    for v in verdicts:
        name  = v.get("sub_offering", "?")
        legit = v.get("legitimate", True)
        log.info("  [%s] %s — %s", "KEEP  " if legit else "REMOVE", name, v.get("reasoning", ""))
        if not legit:
            invalid_ids.extend(v.get("row_ids", []))

    if invalid_ids:
        deleted = _bulk_delete(invalid_ids, label=f"{label}:INVALID")
        log.info("[%s] Removed %d illegitimate row(s).", label, deleted)
        with lock:
            stats["validated_removed"] = stats.get("validated_removed", 0) + deleted
    else:
        log.info("[%s] All offerings passed legitimacy check.", label)

    # ── Apply semantic duplicate removals ─────────────────────────────────────
    dup_pairs   = result.get("duplicate_pairs", [])
    sem_dup_ids: list[int] = []

    if dup_pairs:
        log.info("[%s][SEM-DEDUP] %d semantic duplicate pair(s):", label, len(dup_pairs))
        for pair in dup_pairs:
            keep = pair.get("keep",   {})
            rem  = pair.get("remove", {})
            log.info("  KEEP   : %r", keep.get("sub_offering", "?"))
            log.info("  REMOVE : %r", rem.get("sub_offering", "?"))
            sem_dup_ids.extend(rem.get("row_ids", []))
    else:
        log.info("[%s][SEM-DEDUP] No semantic duplicates found.", label)

    if sem_dup_ids:
        deleted = _bulk_delete(sem_dup_ids, label=f"{label}:SEM-DEDUP")
        log.info("[%s][SEM-DEDUP] Removed %d semantic duplicate row(s).", label, deleted)
        with lock:
            stats["quality_dupes_removed"] = stats.get("quality_dupes_removed", 0) + deleted

    # ── Apply module_offering corrections ─────────────────────────────────────
    corrections = result.get("corrections", [])
    if corrections:
        log.info("[%s][CORRECTION] %d module_offering correction(s):", label, len(corrections))
        id_to_mo: list[tuple[int, str]] = []
        for c in corrections:
            name       = c.get("sub_offering", "?")
            correct_mo = (c.get("correct_module_offering") or "").strip()
            row_ids    = c.get("row_ids", [])
            log.info("  [MOVE] %r", name)
            log.info("         %r → %r", module_offering, correct_mo)
            log.info("         %s", c.get("reasoning", ""))
            if correct_mo and correct_mo.lower() != module_offering.lower():
                id_to_mo.extend((rid, correct_mo) for rid in row_ids)
        if id_to_mo:
            updated = _bulk_update_module_offering(id_to_mo, label=f"{label}:CORRECTION")
            log.info("[%s] Corrected module_offering on %d row(s).", label, updated)
            with lock:
                stats["corrections_applied"] = stats.get("corrections_applied", 0) + updated
    else:
        log.info("[%s][CORRECTION] All module_offering assignments verified correct.", label)

    # ── Targeted re-crawl for gap analysis ────────────────────────────────────
    missing = result.get("missing_offerings", [])
    if not missing:
        log.info("[%s][GAP] No missing sub-offerings identified.", label)
        return

    log.info("[%s][GAP] %d potentially missing sub-offering(s):", label, len(missing))
    urls_to_crawl: list[str] = []
    seen_suggested: set[str] = set()

    for m in missing:
        log.info("  [MISSING] %r", m.get("sub_offering", "?"))
        log.info("            %s", m.get("reason", ""))
        for u in m.get("suggested_urls", []):
            u_norm = normalize_url(u)
            if (
                u_norm not in visited
                and u_norm not in seen_suggested
                and is_allowed_url(u, cfg)
            ):
                urls_to_crawl.append(u)
                seen_suggested.add(u_norm)

    if not urls_to_crawl:
        log.info("[%s][GAP] All suggested URLs already crawled or out of scope.", label)
        return

    log.info("[%s][GAP] Crawling %d targeted URL(s)…", label, len(urls_to_crawl))
    new_count = 0

    for url in urls_to_crawl[:15]:
        if state.stop_requested:
            break

        log.info("Pass 2 gap-crawl: url=%s", url)
        html, final_url = get_page_content(page, url, cfg.browser_mode, cfg.extra_wait_ms)
        if not html:
            continue

        visited.add(normalize_url(url))
        time.sleep(REQUEST_DELAY_S)
        with lock:
            stats["quality_pages_crawled"] = stats.get("quality_pages_crawled", 0) + 1

        text = extract_text_from_html(html)
        if len(text.strip()) < 500 or not db.is_english_text(text[:500]):
            continue

        effective_url = final_url or url
        raw_data_id   = db.save_raw_to_db(effective_url, text, cfg.slug)
        if not raw_data_id:
            continue

        with lock:
            stats["raw_saved"] += 1

        before = stats.get("extracted_saved", 0)
        extract_from_page(
            effective_url, text, cfg,
            raw_data_id, discovered, stats, lock, jsonl_path,
        )
        added = stats.get("extracted_saved", 0) - before
        new_count += added
        if added:
            log.info("Pass 2 gap-crawl: +%d offering(s) from %s", added, url)

    with lock:
        stats["quality_new_found"] = stats.get("quality_new_found", 0) + new_count

    # ── Recurse once if new offerings were added ──────────────────────────────
    if new_count > 0 and not _is_rerun:
        log.info("[%s][GAP] Found %d new offering(s) — re-running combined audit.", label, new_count)
        _run_pass2(
            cfg=cfg,
            module_offering=module_offering,
            page=page,
            visited=visited,
            discovered=discovered,
            stats=stats,
            lock=lock,
            jsonl_path=jsonl_path,
            _is_rerun=True,
        )
    else:
        if new_count == 0:
            log.info("[%s][GAP] Targeted crawl yielded no new offerings.", label)


def post_vendor_validate_and_quality(
    cfg: VendorConfig,
    page: Page,
    visited: set[str],
    discovered: set[str],
    stats: dict,
    lock: threading.Lock,
    jsonl_path: str,
    _is_rerun: bool = False,
) -> None:
    """Run Pass 2 for every module_offering discovered in the DB for this vendor."""
    conn = db.get_pg_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            """SELECT DISTINCT module_offering
               FROM extracted_offerings
               WHERE module_offering ILIKE %s
               ORDER BY module_offering;""",
            (f"%{cfg.product_brand}%",),
        )
        discovered_mos = [row[0] for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

    if not discovered_mos:
        log.info("Pass 2: no module_offerings in DB for brand=%r — skipping", cfg.product_brand)
        return

    log.info(
        "Pass 2: auditing %d module_offering(s) for brand=%r",
        len(discovered_mos), cfg.product_brand,
    )
    for module_offering in discovered_mos:
        _run_pass2(
            cfg=cfg,
            module_offering=module_offering,
            page=page,
            visited=visited,
            discovered=discovered,
            stats=stats,
            lock=lock,
            jsonl_path=jsonl_path,
            _is_rerun=_is_rerun,
        )
