"""Task processing: cache lookup, LLM matching, and response building."""
from __future__ import annotations

import re

import db
from api.matching import match_single_task_with_llm
from api.scoring import get_role_domain, compute_task_coverage_pct, compute_tes_score, industry_match_val

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
# Prevents cross-domain false positives (e.g. Janitor matched to a software tool).
# Consistent with the >40 qualifying threshold in compute_tes_score.
_MIN_COVERAGE_PCT = 40.0


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
        print(f"[API] Warning: could not enrich capability details: {e}")
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
    }


def rows_to_tool_list(rows: list[dict]) -> list[dict]:
    """Convert cached DB rows to the API response format."""
    result = []
    for r in rows:
        cap_details = r.get("capability_details", [])
        if cap_details and not cap_details[0].get("source"):
            cap_details = _enrich_cap_details_with_source(cap_details, r.get("tool_id"))
        result.append(_build_tool_response({**r, "capability_details": cap_details}))
    return result


def llm_tools_to_response(tools: list[dict]) -> list[dict]:
    """Convert freshly-matched LLM tools to the API response format."""
    catalog = {o["id"]: o for o in db.fetch_all_offerings()}
    result  = []
    for t in tools:
        tool_id     = t.get("tool_id")
        offering    = catalog.get(tool_id, {})
        cap_details = _enrich_cap_details_with_source(t.get("capability_details", []), tool_id)
        result.append(_build_tool_response(
            {**t, "capability_details": cap_details},
            source_evidence=offering.get("source_evidence"),
        ))
    return result


def process_single_task(
    role: str,
    task: str,
    vendor_filter: str | None = None,
) -> dict:
    print(f"[TASK] task={task!r}")

    # 0. Option 3: generic-word filter — reject before any DB/LLM call
    if not _task_has_specific_content(task):
        print(f"[TASK] Rejected by generic-word filter: {task!r}")
        return {
            "task": task, "cached": False, "recommended_tools": [],
            "note": "Task description is too generic or unclear. Please describe a specific action or workflow.",
        }

    # 1. Semantic vector cache check
    try:
        task_embedding = db.get_task_embedding(role, task)
        vector_cached  = db.fetch_cached_by_embedding(task_embedding)
    except Exception as e:
        print(f"[TASK] Vector cache check failed (non-fatal): {e}")
        task_embedding = None
        vector_cached  = None

    if vector_cached is not None:
        if vendor_filter:
            vector_cached = [
                r for r in vector_cached
                if (r.get("vendor") or "").lower() == vendor_filter.lower()
            ]
        print(f"[TASK] Cache HIT (semantic) – {len(vector_cached)} tool(s)")
        return {"task": task, "cached": True, "recommended_tools": rows_to_tool_list(vector_cached)}

    # 2. Cache miss — fetch top-20 relevant offerings, then call LLM
    print("[TASK] Cache MISS – calling LLM")
    relevant_offerings = db.fetch_relevant_offerings(role, task, top_k=20)
    if not relevant_offerings:
        return {
            "task": task, "cached": False, "recommended_tools": [],
            "note": "No tools in the catalog yet. Run the crawler first.",
        }

    llm_result          = match_single_task_with_llm(role, task, relevant_offerings)
    tools_all           = llm_result["tools"]
    task_clarity_score  = llm_result.get("task_clarity_score", 10)

    # Option 4: LLM-reported clarity score — discard matches when task is too vague
    print(f"[TASK] task_clarity_score={task_clarity_score}")
    if task_clarity_score <= _CLARITY_THRESHOLD:
        print(f"[TASK] Rejected by clarity score ({task_clarity_score} <= {_CLARITY_THRESHOLD})")
        return {
            "task": task, "cached": False, "recommended_tools": [],
            "note": f"Task description is too vague for reliable matching (clarity {task_clarity_score}/10). Please provide more specific details.",
        }

    # Phantom-tool guard: reject tool_ids not in the top-20 catalog
    valid_catalog_ids = {o["id"] for o in relevant_offerings}
    before    = len(tools_all)
    tools_all = [t for t in tools_all if t.get("tool_id") in valid_catalog_ids]
    if len(tools_all) < before:
        print(f"[TASK] WARNING – removed {before - len(tools_all)} phantom tool(s)")
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
        print(f"[SCORE] Coverage filter: removed {before_cov - len(tools_all)} tool(s) below {_MIN_COVERAGE_PCT}%")

    tes = compute_tes_score(tools_all)
    for t in tools_all:
        t["tes_score"] = tes

    print(f"[SCORE] tes_score={tes:.1f}  tools_scored={len(tools_all)}  role_domain={role_domain}")
    for t in tools_all:
        print(f"  tool_id={t.get('tool_id')}  coverage={t.get('task_coverage_pct', 0):.1f}  evidence_weight={t.get('evidence_weight', 0.5)}")
    # ──────────────────────────────────────────────────────────────────────────

    try:
        db.save_task_recommendations(role, task, tools_all, task_embedding)
        print(f"[TASK] Cached {len(tools_all)} tool(s)")
    except Exception as e:
        import traceback
        print(f"[TASK] ERROR – cache write failed: {e}")
        traceback.print_exc()

    if vendor_filter:
        tools = [t for t in tools_all if (t.get("vendor") or "").lower() == vendor_filter.lower()]
    else:
        tools = tools_all

    print(f"[TASK] Done – {len(tools)} tool(s) matched")
    return {"task": task, "cached": False, "recommended_tools": llm_tools_to_response(tools)}
