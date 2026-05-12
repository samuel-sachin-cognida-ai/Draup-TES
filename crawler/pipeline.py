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
from crawler.prompts import extraction_system_prompt, validate_and_quality_system_prompt
from crawler.url_filter import normalize_url, is_allowed_url
import crawler.state as state

log = logging.getLogger("crawler.pipeline")

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
            log.info("[LLM-P1] No offerings found on %s", url)
            with lock:
                stats["llm_tasks_sent"] += 1
            return

        normalize_capabilities(offerings)
        offerings = [db.prepare_offering_for_storage(item) for item in offerings]

        log.info("[LLM] Extracted %d offering(s) from %s", len(offerings), url)
        with lock:
            stats["llm_tasks_sent"] += 1

        jlock = _get_jsonl_lock(jsonl_path)
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
            module_offering_filter=cfg.module_offering,
            discovered_sub_offerings=discovered,
            target_sub_offerings=cfg.target_sub_offerings,
            stats=stats,
            stats_lock=lock,
            disallowed_terms=cfg.disallowed_terms,
            too_generic_terms=cfg.too_generic_terms,
        )

    except json.JSONDecodeError as e:
        log.error("[LLM] JSON parse error for %s: %s", url, e)
        with lock:
            stats["llm_errors"] += 1
    except Exception as e:
        log.error("[LLM] Error processing %s: %s", url, e)
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
    """
    Combined Pass 2:
      1. Language purge
      2. Exact-name dedup
      3. Near-name clustering (token overlap + Jaccard)
      4. Single LLM call → legitimacy verdicts + semantic dedup + gap analysis
      5. Apply all deletions atomically
      6. Targeted re-crawl for missing offerings
      7. Recurse once if new offerings were added
    """
    label = "VALIDATE+QUALITY" + (" [RERUN]" if _is_rerun else "")
    print("\n" + "=" * 65)
    print(f"[{label}] {cfg.module_offering}")
    print("=" * 65)

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
            (cfg.module_offering,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

    if not rows:
        print(f"[{label}] No offerings to process.")
        return

    # ── Language purge ────────────────────────────────────────────────────────
    non_english_ids = [r["id"] for r in rows if not db.is_english_text(r.get("sub_offering") or "")]
    rows = [r for r in rows if r["id"] not in set(non_english_ids)]

    if non_english_ids:
        deleted = _bulk_delete(non_english_ids, label=f"{label}:LANG")
        print(f"[{label}][LANG] Purged {deleted} non-English row(s).")

    if not rows:
        print(f"[{label}] No offerings remain after language purge.")
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
        print(f"[{label}][EXACT-DEDUP] Removed {deleted} exact-name duplicate(s).")
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
        print(f"[{label}][NEAR-DEDUP] Removed {deleted} near-name duplicate(s).")
        with lock:
            stats["duplicates_skipped"] = stats.get("duplicates_skipped", 0) + deleted

    audit_list = [v for k, v in groups.items() if k not in merged_into]
    print(f"[{label}] {len(audit_list)} unique sub-offering(s) going to LLM audit.")

    if not audit_list:
        print(f"[{label}] Nothing left to audit after dedup.")
        return

    # ── Single LLM call: legitimacy + semantic dedup + gap analysis ───────────
    crawled_urls = sorted(visited)[:60]
    try:
        completion = llm.create_chat_completion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": validate_and_quality_system_prompt(cfg)},
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
        log.error("[%s] LLM error: %s — skipping audit.", label, e)
        print("=" * 65)
        return

    # ── Apply legitimacy verdicts ─────────────────────────────────────────────
    verdicts     = result.get("verdicts", [])
    invalid_ids: list[int] = []
    print(f"\n[{label}][LEGITIMACY] {len(verdicts)} verdict(s):")
    for v in verdicts:
        name  = v.get("sub_offering", "?")
        legit = v.get("legitimate", True)
        print(f"  [{'KEEP  ' if legit else 'REMOVE'}] {name}")
        print(f"           {v.get('reasoning', '')}")
        if not legit:
            invalid_ids.extend(v.get("row_ids", []))

    if invalid_ids:
        deleted = _bulk_delete(invalid_ids, label=f"{label}:INVALID")
        print(f"\n[{label}] Removed {deleted} illegitimate row(s).")
        with lock:
            stats["validated_removed"] = stats.get("validated_removed", 0) + deleted
    else:
        print(f"\n[{label}] All offerings passed legitimacy check.")

    # ── Apply semantic duplicate removals ─────────────────────────────────────
    dup_pairs   = result.get("duplicate_pairs", [])
    sem_dup_ids: list[int] = []

    if dup_pairs:
        print(f"\n[{label}][SEM-DEDUP] {len(dup_pairs)} semantic duplicate pair(s):")
        for pair in dup_pairs:
            keep = pair.get("keep",   {})
            rem  = pair.get("remove", {})
            print(f"  KEEP   : {keep.get('sub_offering', '?')!r}")
            print(f"  REMOVE : {rem.get('sub_offering', '?')!r}")
            sem_dup_ids.extend(rem.get("row_ids", []))
    else:
        print(f"[{label}][SEM-DEDUP] No semantic duplicates found.")

    if sem_dup_ids:
        deleted = _bulk_delete(sem_dup_ids, label=f"{label}:SEM-DEDUP")
        print(f"[{label}][SEM-DEDUP] Removed {deleted} semantic duplicate row(s).")
        with lock:
            stats["quality_dupes_removed"] = stats.get("quality_dupes_removed", 0) + deleted

    # ── Targeted re-crawl for gap analysis ────────────────────────────────────
    missing = result.get("missing_offerings", [])
    if not missing:
        print(f"[{label}][GAP] No missing sub-offerings identified.")
        print("=" * 65)
        return

    print(f"\n[{label}][GAP] {len(missing)} potentially missing sub-offering(s):")
    urls_to_crawl: list[str] = []
    seen_suggested: set[str] = set()

    for m in missing:
        print(f"  [MISSING] {m.get('sub_offering', '?')!r}")
        print(f"            {m.get('reason', '')}")
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
        print(f"[{label}][GAP] All suggested URLs already crawled or out of scope.")
        print("=" * 65)
        return

    print(f"\n[{label}][GAP] Crawling {len(urls_to_crawl)} targeted URL(s)…")
    new_count = 0

    for url in urls_to_crawl[:15]:
        if state.stop_requested:
            break

        log.info("[%s][GAP-CRAWL] %s", label, url)
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
            log.info("[%s][GAP] +%d offering(s) from %s", label, added, url)

    with lock:
        stats["quality_new_found"] = stats.get("quality_new_found", 0) + new_count

    # ── Recurse once if new offerings were added ──────────────────────────────
    if new_count > 0 and not _is_rerun:
        print(f"\n[{label}][GAP] Found {new_count} new offering(s) — re-running combined audit.")
        post_vendor_validate_and_quality(
            cfg, page, visited, discovered, stats, lock, jsonl_path,
            _is_rerun=True,
        )
    else:
        if new_count == 0:
            print(f"[{label}][GAP] Targeted crawl yielded no new offerings.")
        print("=" * 65)
