"""Task processing: cache lookup, LLM matching, and response building."""
from __future__ import annotations

import db
from api.matching import match_single_task_with_llm
from api.scoring import get_role_domain, compute_task_coverage_pct, compute_tes_score, industry_match_val


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

    tools_all = match_single_task_with_llm(role, task, relevant_offerings)

    # Phantom-tool guard: reject tool_ids not in the top-20 catalog
    valid_catalog_ids = {o["id"] for o in relevant_offerings}
    before    = len(tools_all)
    tools_all = [t for t in tools_all if t.get("tool_id") in valid_catalog_ids]
    if len(tools_all) < before:
        print(f"[TASK] WARNING – removed {before - len(tools_all)} phantom tool(s)")
    for i, t in enumerate(tools_all, 1):
        t["rank_position"] = i

    # ── Scoring block ──────────────────────────────────────────────────────────
    _SCORE_FLOOR = 0.30  # worst match in the retrieved set floors at 30%

    catalog = {o["id"]: o for o in relevant_offerings}
    role_domain = get_role_domain(role)

    # Rank-normalise distances across matched tools: best=1.0, worst=_SCORE_FLOOR
    distances = [
        catalog.get(t.get("tool_id"), {}).get("_cosine_distance", 0.5)
        for t in tools_all
    ]
    d_min = min(distances) if distances else 0.0
    d_max = max(distances) if distances else 1.0

    for t in tools_all:
        tool_id  = t.get("tool_id")
        offering = catalog.get(tool_id, {})
        distance = offering.get("_cosine_distance", 0.5)
        if d_max > d_min:
            cosine_sim = 1.0 - (1.0 - _SCORE_FLOOR) * (distance - d_min) / (d_max - d_min)
        else:
            cosine_sim = 1.0
        ind_match  = industry_match_val(role_domain, offering.get("industry", "general"))
        t["task_coverage_pct"] = compute_task_coverage_pct(cosine_sim, ind_match)
        t["evidence_weight"]   = offering.get("evidence_weight") if offering.get("evidence_weight") is not None else 0.50
        t["evidence_grade"]    = offering.get("evidence_grade") or "C"

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
