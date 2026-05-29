"""Extracted offering storage, deduplication, and retrieval."""
from __future__ import annotations

import hashlib
import json
import logging

import psycopg2.extras

from db.connection import get_pg_connection
from db.embeddings import get_offering_embedding, get_task_embedding, find_similar_offering
from db.text_utils import normalize_text, clean_string_list, is_english_text, sanitize_string_field, sanitize_string_list

log = logging.getLogger("tes.db.offerings")

_CAPABILITY_PLACEHOLDER = "no specific capabilities listed"

_HEALTHCARE_KEYS = {"payer", "provider", "patient", "healthcare", "health"}
_LEGAL_KEYS      = {"legal", "law", "compliance"}
_FINANCE_KEYS    = {"financial", "finance", "banking", "investment"}


def _normalise_industry(focus_list: list) -> str:
    """Return canonical industry tag from industry_focus list (first non-General value wins)."""
    for raw in focus_list:
        if not isinstance(raw, str):
            continue
        v = raw.lower().strip()
        if v == "general":
            continue
        if any(k in v for k in _HEALTHCARE_KEYS):
            return "healthcare"
        if any(k in v for k in _LEGAL_KEYS):
            return "legal"
        if any(k in v for k in _FINANCE_KEYS):
            return "finance"
    return "general"


# ── Content hashing ────────────────────────────────────────────────────────────

def offering_content_hash(item: dict) -> str:
    capabilities   = item.get("capabilities",   []) or []
    tasks_examples = item.get("tasks_examples", []) or []
    payload = {
        "vendor":          normalize_text(item.get("vendor")),
        "category":        normalize_text(item.get("category")),
        "sub_category":    normalize_text(item.get("sub_category")),
        "module_offering": normalize_text(item.get("module_offering")),
        "sub_offering":    normalize_text(item.get("sub_offering")),
        "capabilities":    sorted(normalize_text(x) for x in capabilities   if x),
        "tasks_examples":  sorted(normalize_text(x) for x in tasks_examples if x),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Offering preparation ───────────────────────────────────────────────────────

def _build_fallback_tasks_examples(item: dict) -> list[str]:
    sub          = (item.get("sub_offering") or "this sub-offering").strip()
    capabilities = clean_string_list(item.get("capabilities", []))
    if not capabilities:
        return []
    return [
        f"Use {sub} to {cap[0].lower() + cap[1:]}"
        for cap in capabilities[:3]
        if len(cap) > 1
    ]


def prepare_offering_for_storage(item: dict) -> dict:
    prepared = dict(item)
    raw_caps = prepared.get("capabilities", [])

    if raw_caps and isinstance(raw_caps[0], dict):
        cap_texts = [c.get("text", "") for c in raw_caps if isinstance(c, dict)]
        prepared["capabilities_rich"] = raw_caps
        prepared["capabilities"] = clean_string_list(cap_texts)
    else:
        prepared["capabilities"] = clean_string_list(raw_caps)
        if not prepared.get("capabilities_rich"):
            prepared["capabilities_rich"] = None

    prepared["tasks_examples"] = clean_string_list(prepared.get("tasks_examples", []))
    if not prepared["tasks_examples"]:
        fb = _build_fallback_tasks_examples(prepared)
        if fb:
            prepared["tasks_examples"] = fb

    return prepared


# ── Capability records ─────────────────────────────────────────────────────────

def save_capability_records(
    cur,
    offering_id: int,
    capabilities_rich: list | None,
    capabilities_plain: list[str],
    source_url: str,
    source_evidence: str | None,
) -> None:
    """Save each capability as an individual capability_record row."""
    base_location = None
    if source_evidence:
        pipe_idx = source_evidence.find("|")
        if pipe_idx != -1:
            base_location = source_evidence[pipe_idx + 1:].strip()

    if capabilities_rich:
        for cap in capabilities_rich:
            if not isinstance(cap, dict):
                continue
            cap_text = (cap.get("text") or "").strip()
            if not cap_text or _CAPABILITY_PLACEHOLDER in cap_text.lower():
                continue
            exact_text     = cap.get("exact_text") or cap.get("passage") or None
            location       = cap.get("source_location") or base_location
            cap_source_url = cap.get("source_url") or source_url
            cur.execute(
                """INSERT INTO capability_records
                       (offering_id, capability_text, source_url, source_location, exact_text)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING;""",
                (offering_id, cap_text, cap_source_url, location, exact_text),
            )
    else:
        for cap_text in capabilities_plain:
            if not cap_text.strip() or _CAPABILITY_PLACEHOLDER in cap_text.lower():
                continue
            cur.execute(
                """INSERT INTO capability_records
                       (offering_id, capability_text, source_url, source_location, exact_text)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING;""",
                (offering_id, cap_text, source_url, base_location, None),
            )


# ── Save extracted offerings ───────────────────────────────────────────────────

def save_extracted_to_db(
    raw_data_id: int,
    url: str,
    extracted: dict,
    product_brand: str,
    discovered_sub_offerings: set[str],
    target_sub_offerings: int,
    stats: dict,
    stats_lock,
    disallowed_terms: list[str],
    too_generic_terms: list[str],
) -> None:
    conn = get_pg_connection()
    cur  = conn.cursor()
    try:
        offerings = extracted.get("offerings", [extracted])
        if isinstance(offerings, dict):
            offerings = [offerings]

        inserted = duplicates = skipped = lang_skipped = 0

        brand_lower = product_brand.strip().lower()

        for item in offerings:
            mo_raw = (item.get("module_offering") or "").strip()
            # Accept any module_offering that contains the product brand and " for "
            if not mo_raw or brand_lower not in mo_raw.lower() or " for " not in mo_raw.lower():
                skipped += 1
                with stats_lock:
                    stats["non_target_skipped"] = stats.get("non_target_skipped", 0) + 1
                log.debug("Skipped offering — wrong brand or format: module_offering=%r sub_offering=%r", mo_raw, item.get('sub_offering'))
                continue

            item = prepare_offering_for_storage(item)

            sub = sanitize_string_field(item.get("sub_offering"), "sub_offering")
            if sub is None:
                lang_skipped += 1
                with stats_lock:
                    stats["non_english_skipped"] = stats.get("non_english_skipped", 0) + 1
                continue
            item["sub_offering"] = sub

            caps  = sanitize_string_list(clean_string_list(item.get("capabilities",   [])), "capabilities")
            tasks = sanitize_string_list(clean_string_list(item.get("tasks_examples", [])), "tasks_examples")

            caps = [c for c in caps if _CAPABILITY_PLACEHOLDER not in c.lower()]

            rich = item.get("capabilities_rich")
            if rich:
                rich = [
                    c for c in rich
                    if isinstance(c, dict) and _CAPABILITY_PLACEHOLDER not in (c.get("text") or "").lower()
                ]
                item["capabilities_rich"] = rich or None

            item["capabilities"]   = caps
            item["tasks_examples"] = tasks

            sub_l = sub.lower()
            if any(term in sub_l for term in disallowed_terms):
                skipped += 1
                log.debug("Rejected offering — disallowed term in sub_offering: %r", sub)
                continue
            if len(sub.split()) <= 2 and any(term == sub_l for term in too_generic_terms):
                skipped += 1
                log.debug("Rejected offering — too generic (single/double word): %r", sub)
                continue
            if not caps:
                skipped += 1
                log.debug("Rejected offering — no capabilities extracted: %r", sub)
                continue

            content_hash = offering_content_hash(item)

            from api.scoring import grade_url
            grade_letter, grade_weight = grade_url(url)
            industry_val = _normalise_industry(item.get("industry_focus") or [])

            try:
                embedding  = get_offering_embedding(item)
                similar_id = find_similar_offering(embedding)
            except Exception as e:
                log.warning("Embedding error, vector dedup skipped for this offering: %s", e)
                embedding  = None
                similar_id = None

            if similar_id is not None:
                cur.execute(
                    "SELECT COUNT(*) FROM capability_records WHERE offering_id = %s;",
                    (similar_id,),
                )
                if cur.fetchone()[0] == 0:
                    save_capability_records(
                        cur=cur,
                        offering_id=similar_id,
                        capabilities_rich=item.get("capabilities_rich"),
                        capabilities_plain=caps,
                        source_url=url,
                        source_evidence=item.get("source_evidence"),
                    )
                duplicates += 1
                with stats_lock:
                    stats["duplicates_skipped"] = stats.get("duplicates_skipped", 0) + 1
                log.debug("Semantic duplicate detected: sub_offering=%r matched_id=%s", sub, similar_id)
                discovered_sub_offerings.add(sub.strip().lower())
                continue

            cur.execute(
                """INSERT INTO extracted_offerings
                       (raw_data_id, url, vendor, category, sub_category,
                        module_offering, sub_offering, capabilities,
                        tasks_examples, content_hash, source_evidence, embedding,
                        industry, evidence_grade, evidence_weight)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id;""",
                (
                    raw_data_id, url,
                    item.get("vendor"),
                    item.get("category"),
                    item.get("sub_category"),
                    item.get("module_offering"),
                    item.get("sub_offering"),
                    item.get("capabilities",   []),
                    item.get("tasks_examples", []),
                    content_hash,
                    item.get("source_evidence"),
                    embedding,
                    industry_val,
                    grade_letter,
                    grade_weight,
                ),
            )
            row = cur.fetchone()
            if row:
                offering_id = row[0]
                inserted += 1
                with stats_lock:
                    stats["extracted_saved"] = stats.get("extracted_saved", 0) + 1
                discovered_sub_offerings.add(sub.strip().lower())
                log.info("New sub-offering saved [%d]: %r", len(discovered_sub_offerings), sub)
                save_capability_records(
                    cur=cur,
                    offering_id=offering_id,
                    capabilities_rich=item.get("capabilities_rich"),
                    capabilities_plain=caps,
                    source_url=url,
                    source_evidence=item.get("source_evidence"),
                )

            if len(discovered_sub_offerings) >= target_sub_offerings:
                conn.commit()
                log.info("Target reached: %d/%d sub-offerings collected — stopping extraction", len(discovered_sub_offerings), target_sub_offerings)
                return

        conn.commit()
        if inserted:     log.info("Saved %d new offering(s) from %s", inserted, url)
        if duplicates:   log.debug("Skipped %d duplicate(s) from %s", duplicates, url)
        if skipped:      log.debug("Filtered %d offering(s) from %s (brand/term/generic/caps checks)", skipped, url)
        if lang_skipped: log.warning("Rejected %d non-English offering(s) from %s", lang_skipped, url)

    except Exception as e:
        conn.rollback()
        log.error("DB write failed, rolled back: url=%s  error=%s", url, e, exc_info=True)
    finally:
        cur.close()
        conn.close()


# ── Capability record fetching ─────────────────────────────────────────────────

def fetch_capability_records(offering_id: int) -> list[dict]:
    conn = get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """SELECT id, capability_text, source_url, source_location, source_date, exact_text
               FROM capability_records
               WHERE offering_id = %s
               ORDER BY id;""",
            (offering_id,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def fetch_capability_records_for_offerings(offering_ids: list[int]) -> dict[int, list[dict]]:
    """Batch fetch capability records for multiple offerings."""
    if not offering_ids:
        return {}
    conn = get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """SELECT id, offering_id, capability_text, source_url, source_location, source_date, exact_text
               FROM capability_records
               WHERE offering_id = ANY(%s)
               ORDER BY offering_id, id;""",
            (offering_ids,),
        )
        result: dict[int, list[dict]] = {}
        for row in cur.fetchall():
            d   = dict(row)
            oid = d["offering_id"]
            result.setdefault(oid, []).append(d)
        return result
    finally:
        cur.close()
        conn.close()


# ── Offering retrieval ─────────────────────────────────────────────────────────

def fetch_all_offerings(vendor_filter: str | None = None) -> list[dict]:
    conn = get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if vendor_filter:
            cur.execute(
                """SELECT id, vendor, category, sub_category,
                          module_offering, sub_offering, capabilities, tasks_examples,
                          source_evidence, url, industry, evidence_grade, evidence_weight
                   FROM extracted_offerings
                   WHERE vendor ILIKE %s
                   ORDER BY id;""",
                (vendor_filter,),
            )
        else:
            cur.execute(
                """SELECT id, vendor, category, sub_category,
                          module_offering, sub_offering, capabilities, tasks_examples,
                          source_evidence, url, industry, evidence_grade, evidence_weight
                   FROM extracted_offerings
                   ORDER BY id;"""
            )
        rows = [dict(r) for r in cur.fetchall()]
        offering_ids = [r["id"] for r in rows]
        cap_map = fetch_capability_records_for_offerings(offering_ids)
        for r in rows:
            r["capability_records"] = cap_map.get(r["id"], [])
        return rows
    finally:
        cur.close()
        conn.close()


def fetch_relevant_offerings(
    role: str,
    task: str,
    top_k: int = 20,
    vendor_filter: str | None = None,
) -> list[dict]:
    """Return the top_k offerings most semantically relevant to the role+task."""
    try:
        query_embedding = get_task_embedding(role, task)
    except Exception as e:
        log.warning("Could not generate query embedding, falling back to full catalog: %s", e)
        return fetch_all_offerings(vendor_filter)

    conn = get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        vendor_clause = "AND vendor ILIKE %s" if vendor_filter else ""
        params = [query_embedding, query_embedding]
        if vendor_filter:
            params.insert(1, vendor_filter)
        cur.execute(
            f"""SELECT id, vendor, category, sub_category, module_offering, sub_offering,
                       capabilities, tasks_examples, source_evidence, url,
                       industry, evidence_grade, evidence_weight,
                       embedding <=> %s::vector AS distance
               FROM extracted_offerings
               WHERE embedding IS NOT NULL
               {vendor_clause}
               ORDER BY embedding <=> %s::vector ASC
               LIMIT {top_k};""",
            params,
        )
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            log.warning("No embeddings found in DB — falling back to full catalog scan (run crawler to generate embeddings)")
            return fetch_all_offerings(vendor_filter)
        offering_ids = [r["id"] for r in rows]
        cap_map = fetch_capability_records_for_offerings(offering_ids)
        for r in rows:
            r["capability_records"] = cap_map.get(r["id"], [])
            r["_cosine_distance"] = r.pop("distance", 0.5)
        log.debug("Vector search complete: top %d offerings retrieved for task=%r", len(rows), task)
        return rows
    finally:
        cur.close()
        conn.close()
