"""Task processing: cache lookup, LLM matching, and response building."""
from __future__ import annotations

import logging
import os as _os
import re

import db
import llm_client as _llm
from api.matching import match_single_task_with_llm
from api.scoring import get_role_domain, compute_task_coverage_pct, compute_tes_score, industry_match_val

log = logging.getLogger("tes.api.processing")

# ── Option 3: Generic-word filter ─────────────────────────────────────────────
# Generic nouns/adjectives that carry no domain signal on their own.
_GENERIC_WORDS: frozenset[str] = frozenset({
    "something", "anything", "everything", "nothing", "stuff", "things", "thing",
    "tasks", "task", "work", "done", "business", "analysis", "information",
    "better", "good", "great", "best", "more", "less", "much", "many", "few",
    "lot", "lots", "various", "certain", "specific", "general", "other",
    "another", "every", "each", "right", "well", "way", "ways", "kind",
    "type", "sort", "area", "areas", "aspect", "aspects", "level", "levels",
})
# Generic verbs that are too broad on their own (not meaningful without a specific object).
_GENERIC_VERBS: frozenset[str] = frozenset({
    "write", "do", "make", "get", "give", "help", "improve", "create",
    "build", "run", "perform", "complete", "attend", "use", "add", "update",
    "handle", "manage", "support", "work", "try", "take", "put", "set",
})
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "must", "can", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "and", "or",
    "but", "if", "i", "me", "my", "we", "our", "you", "your", "he", "she",
    "they", "their", "what", "which", "who", "not", "no", "so", "just",
    "also", "up", "out", "about", "than", "then", "when", "how", "all",
    "both", "some", "any", "its", "it",
})

# Minimum characters a task must have after stripping whitespace.
_MIN_TASK_CHARS = 8


def _task_has_specific_content(task: str) -> bool:
    """Return False when the task carries no actionable domain signal.

    Catches:
      • Too-short inputs ("x", "?", "help")
      • Placeholder text ("N/A", "TODO", "TBD")
      • Generic filler ("write something", "do analysis", "improve stuff")
    """
    stripped = task.strip()

    if len(stripped) < _MIN_TASK_CHARS:
        return False

    upper = stripped.upper()
    if upper in {"N/A", "NA", "TODO", "TBD", "TBC", "NONE", "NULL", "N.A.", "N.A"}:
        return False

    # Remove punctuation, lower-case, split into words
    words = set(re.sub(r"[^a-z\s]", "", stripped.lower()).split())
    meaningful = words - _STOP_WORDS

    # No meaningful words at all
    if not meaningful:
        return False

    # All meaningful words are generic filler (nouns) or generic verbs → no domain signal
    if meaningful.issubset(_GENERIC_WORDS | _GENERIC_VERBS):
        return False

    return True


# ── Option 4: clarity score threshold ─────────────────────────────────────────
# LLM-reported scores at or below this value trigger a "too vague" early exit.
_CLARITY_THRESHOLD = 3

# ── Option 5: coverage threshold ──────────────────────────────────────────────
# LLM-matched tools with task_coverage_pct at or below this value are discarded.
_MIN_COVERAGE_PCT = 45.0


# ── Pricing ────────────────────────────────────────────────────────────────────
LLM_MODEL = _os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

_INFER_PRICING_PROMPT = """\
You are a pricing estimation assistant for enterprise AI tools.

Given a vendor name and sub-offering, provide your best pricing estimate
based solely on your training knowledge.

Return ONLY a valid JSON object (not an array) with these exact keys:
  pricing_model   : pay_per_token | per_seat | tiered | contact_sales | free | usage_based | unknown
  pricing_summary : <= 25 words describing the cost structure
  input_cost      : string or null
  output_cost     : string or null
  tiers           : [] or [{name, price, features}, ...]
  notes           : <= 20 words or null

Be honest about uncertainty. If pricing is not public: pricing_model = "contact_sales".
Return ONLY the JSON object. No markdown. No explanation outside the JSON.
"""


def _infer_pricing_from_llm(vendor: str, sub_offering: str) -> dict | None:
    """
    Call the LLM to estimate pricing for a sub-offering when no crawled data exists.
    Returns a pricing dict or None on failure.
    """
    if not _llm.has_llm_client():
        return None
    try:
        completion = _llm.create_chat_completion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _INFER_PRICING_PROMPT},
                {"role": "user",   "content": f"Vendor: {vendor}\nSub-offering: {sub_offering}"},
            ],
            temperature=0.0,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        result = _llm.parse_json_content(completion)
        if not isinstance(result, dict):
            log.warning(
                "LLM pricing inference returned non-dict for %r/%r", vendor, sub_offering
            )
            return None
        log.debug(
            "LLM pricing inferred: vendor=%r  sub=%r  model=%s",
            vendor, sub_offering, result.get("pricing_model"),
        )
        return result
    except Exception as e:
        log.warning(
            "LLM pricing inference failed for %r/%r: %s", vendor, sub_offering, e
        )
        return None


def _get_or_infer_pricing(
    tool_id:      int | None,
    vendor:       str | None,
    sub_offering: str | None,
) -> dict | None:
    """
    Return pricing data for a matched tool:

    1. Check offering_pricing table (crawled, confidence=0.90) — return immediately if found
       and pricing_model is not 'unknown'.
    2. If missing or pricing_model='unknown': call LLM to infer (confidence=0.30).
    3. Cache the LLM result so the same query doesn't re-infer next time.

    Returns None if tool_id is None or all attempts fail.
    """
    if not tool_id:
        return None

    # Step 1: DB lookup
    try:
        existing = db.fetch_pricing_for_offering(tool_id)
    except Exception as e:
        log.warning("Pricing DB lookup failed for tool_id=%s: %s", tool_id, e)
        existing = None

    if existing and existing.get("pricing_model") not in (None, "unknown"):
        log.debug(
            "Pricing found in DB (source=%s confidence=%.2f): tool_id=%s",
            existing.get("pricing_source"), existing.get("confidence_score", 0), tool_id,
        )
        return existing

    # Step 2: LLM inference (only when vendor and sub_offering are known)
    if not vendor or not sub_offering:
        return existing  # return what we have (may be None or unknown)

    log.debug(
        "No crawled pricing for tool_id=%s — inferring via LLM: %r / %r",
        tool_id, vendor, sub_offering,
    )
    inferred = _infer_pricing_from_llm(vendor, sub_offering)
    if not inferred:
        return existing

    # Step 3: Cache the inferred result
    pricing_row = {
        **inferred,
        "offering_id":     tool_id,
        "vendor":          vendor,
        "sub_offering":    sub_offering,
        "pricing_source":  "llm_inferred",
        "confidence_score": db.CONFIDENCE_LLM_INFERRED,
    }
    try:
        db.save_offering_pricing(pricing_row)
        log.info(
            "LLM-inferred pricing cached: tool_id=%s  model=%s  confidence=%.2f",
            tool_id, inferred.get("pricing_model"), db.CONFIDENCE_LLM_INFERRED,
        )
    except Exception as e:
        log.warning("Failed to cache LLM-inferred pricing for tool_id=%s: %s", tool_id, e)

    return {
        **inferred,
        "pricing_source":   "llm_inferred",
        "confidence_score": db.CONFIDENCE_LLM_INFERRED,
    }


def _enrich_cap_details_with_source(
    cap_details: list[dict],
    tool_id: int | None,
) -> list[dict]:
    """Attach source evidence (url, location, date, exact_text) to each capability detail."""
    if not cap_details or not tool_id:
        return cap_details
    try:
        cap_records = db.fetch_capability_records(tool_id)
        rec_by_id   = {r["id"]: r for r in cap_records}
        rec_by_text = {r["capability_text"].lower().strip(): r for r in cap_records}
        enriched = []
        for cd in cap_details:
            cap_text = (cd.get("capability_text") or cd.get("text") or "").strip()
            cr_id    = cd.get("capability_record_id")
            rec      = rec_by_id.get(cr_id) if cr_id else None
            if rec is None:
                rec = rec_by_text.get(cap_text.lower())
            enriched_cd = dict(cd)
            enriched_cd["capability_text"] = cap_text
            if rec:
                enriched_cd["source"] = {
                    "url":            rec.get("source_url"),
                    "location":       rec.get("source_location"),
                    "date_extracted": rec.get("source_date").isoformat() if rec.get("source_date") else None,
                    "exact_text":     rec.get("exact_text"),
                }
            else:
                enriched_cd["source"] = None
            enriched.append(enriched_cd)
        return enriched
    except Exception as e:
        log.warning("Could not enrich capability details for tool_id=%s: %s", tool_id, e)
        return cap_details


def _build_tool_response(t: dict, source_evidence: str | None = None) -> dict:
    return {
        "tool_id":                t.get("tool_id"),
        "vendor":                 t.get("vendor"),
        "module_offering":        t.get("module_offering"),
        "sub_offering":           t.get("sub_offering"),
        "matched_capabilities":   t.get("matched_capabilities", []),
        "capability_details":     t.get("capability_details", []),
        "automation_percentage":  t.get("automation_percentage", 0),
        "automation_explanation": t.get("automation_explanation"),
        "rank_position":          t.get("rank_position", 0),
        "reasoning":              t.get("reasoning"),
        "limitations":            t.get("limitations"),
        "source_evidence":        source_evidence or t.get("source_evidence"),
        "task_coverage_pct":      t.get("task_coverage_pct"),
        "tes_score":              t.get("tes_score"),
        "evidence_grade":         t.get("evidence_grade"),
        "evidence_weight":        t.get("evidence_weight"),
        "pricing":                t.get("pricing"),
    }


def rows_to_tool_list(rows: list[dict]) -> list[dict]:
    """Convert cached DB rows to the API response format."""
    result = []
    for r in rows:
        cap_details = r.get("capability_details", [])
        if cap_details and not cap_details[0].get("source"):
            cap_details = _enrich_cap_details_with_source(cap_details, r.get("tool_id"))
        pricing = _get_or_infer_pricing(
            r.get("tool_id"),
            r.get("vendor"),
            r.get("sub_offering"),
        )
        result.append(_build_tool_response({**r, "capability_details": cap_details, "pricing": pricing}))
    return result


def llm_tools_to_response(tools: list[dict]) -> list[dict]:
    """Convert freshly-matched LLM tools to the API response format."""
    catalog = {o["id"]: o for o in db.fetch_all_offerings()}
    result  = []
    for t in tools:
        tool_id     = t.get("tool_id")
        offering    = catalog.get(tool_id, {})
        cap_details = _enrich_cap_details_with_source(t.get("capability_details", []), tool_id)
        pricing = _get_or_infer_pricing(
            tool_id,
            t.get("vendor"),
            t.get("sub_offering"),
        )
        result.append(_build_tool_response(
            {**t, "capability_details": cap_details, "pricing": pricing},
            source_evidence=offering.get("source_evidence"),
        ))
    return result


def process_single_task(
    role: str,
    task: str,
    vendor_filter: str | None = None,
) -> dict:
    log.info("Processing task: %r", task)

    # 0. Option 3: generic-word filter — reject before any DB/LLM call
    if not _task_has_specific_content(task):
        log.warning("Task rejected by generic-word filter (too vague or generic): %r", task)
        return {
            "task": task, "cached": False, "recommended_tools": [],
            "note": "Task description is too generic or unclear. Please describe a specific action or workflow.",
        }

    # 1. Semantic vector cache check
    try:
        task_embedding = db.get_task_embedding(role, task)
        vector_cached  = db.fetch_cached_by_embedding(task_embedding)
    except Exception as e:
        log.warning("Vector cache check failed (non-fatal, continuing without cache): %s", e)
        task_embedding = None
        vector_cached  = None

    if vector_cached is not None:
        if vendor_filter:
            vector_cached = [
                r for r in vector_cached
                if (r.get("vendor") or "").lower() == vendor_filter.lower()
            ]
        log.info("Cache HIT (semantic vector match): %d tool(s) returned", len(vector_cached))
        return {"task": task, "cached": True, "recommended_tools": rows_to_tool_list(vector_cached)}

    # 2. Cache miss — fetch top-20 relevant offerings, then call LLM
    log.info("Cache MISS — calling LLM for fresh match")
    relevant_offerings = db.fetch_relevant_offerings(role, task, top_k=20)
    if not relevant_offerings:
        return {
            "task": task, "cached": False, "recommended_tools": [],
            "note": "No tools in the catalog yet. Run the crawler first.",
        }

    llm_result          = match_single_task_with_llm(role, task, relevant_offerings)
    tools_all           = llm_result["tools"]
    task_clarity_score  = llm_result.get("task_clarity_score", 10)

    log.info(
        "LLM returned %d tool(s): clarity_score=%d tool_ids=%s",
        len(tools_all),
        task_clarity_score,
        [t.get("tool_id") for t in tools_all],
    )

    # Option 4: LLM-reported clarity score — discard matches when task is too vague
    log.debug("Task clarity score: %d/10", task_clarity_score)
    if task_clarity_score <= _CLARITY_THRESHOLD:
        log.warning(
            "Task rejected — clarity score too low: %d <= %d threshold: %r",
            task_clarity_score,
            _CLARITY_THRESHOLD,
            task,
        )
        return {
            "task": task, "cached": False, "recommended_tools": [],
            "note": f"Task description is too vague for reliable matching (clarity {task_clarity_score}/10). Please provide more specific details.",
        }

    # Phantom-tool guard: reject tool_ids not in the top-20 catalog
    valid_catalog_ids = {o["id"] for o in relevant_offerings}
    before    = len(tools_all)
    tools_all = [t for t in tools_all if t.get("tool_id") in valid_catalog_ids]
    if len(tools_all) < before:
        log.warning(
            "Phantom tool guard: removed %d tool(s) with IDs not in top-20 catalog",
            before - len(tools_all),
        )
    for i, t in enumerate(tools_all, 1):
        t["rank_position"] = i

    # ── Scoring block ──────────────────────────────────────────────────────────
    catalog = {o["id"]: o for o in relevant_offerings}
    role_domain = get_role_domain(role)

    for t in tools_all:
        tool_id  = t.get("tool_id")
        offering = catalog.get(tool_id, {})
        distance   = offering.get("_cosine_distance", 0.5)
        cosine_sim = 1.0 - distance
        ind_match  = industry_match_val(role_domain, offering.get("industry", "general"))
        t["task_coverage_pct"] = compute_task_coverage_pct(cosine_sim, ind_match)
        t["evidence_weight"]   = offering.get("evidence_weight") if offering.get("evidence_weight") is not None else 0.50
        t["evidence_grade"]    = offering.get("evidence_grade") or "C"

    # Option 5: drop tools that scored below the coverage threshold — these are
    # cross-domain false positives where the LLM forced a match on weak similarity.
    before_cov = len(tools_all)
    tools_all  = [t for t in tools_all if (t.get("task_coverage_pct") or 0) > _MIN_COVERAGE_PCT]
    if len(tools_all) < before_cov:
        log.warning(
            "Coverage filter: removed %d tool(s) below %.1f%% threshold",
            before_cov - len(tools_all),
            _MIN_COVERAGE_PCT,
        )

    tes = compute_tes_score(tools_all)
    for t in tools_all:
        t["tes_score"] = tes

    log.info(
        "Scoring complete: tes_score=%.1f tools=%d role_domain=%s",
        tes,
        len(tools_all),
        role_domain,
    )
    for t in tools_all:
        log.debug(
            "  tool_id=%-5s coverage=%.1f%% evidence_weight=%.2f",
            t.get("tool_id"),
            t.get("task_coverage_pct", 0),
            t.get("evidence_weight", 0.5),
        )
    # ──────────────────────────────────────────────────────────────────────────

    try:
        db.save_task_recommendations(role, task, tools_all, task_embedding)
        log.info("Saved %d tool(s) to recommendation cache", len(tools_all))
    except Exception as e:
        log.error("Cache write failed (tools still returned to client): %s", e, exc_info=True)

    if vendor_filter:
        tools = [t for t in tools_all if (t.get("vendor") or "").lower() == vendor_filter.lower()]
    else:
        tools = tools_all

    log.info("Task complete: %d tool(s) matched (vendor_filter=%r)", len(tools), vendor_filter)
    return {"task": task, "cached": False, "recommended_tools": llm_tools_to_response(tools)}
