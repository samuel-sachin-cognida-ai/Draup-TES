"""LLM-based tool matching for a given role and task."""
from __future__ import annotations

import json
import os

import llm_client as llm

LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

MATCHING_SYSTEM_PROMPT = """
You are a healthcare AI tool recommendation engine.

You will receive:
1. A user ROLE (e.g. "Clinical Documentation Specialist")
2. A single TASK the user needs to perform
3. A CATALOG of available tools. Each tool has:
   - id, vendor, module_offering, sub_offering, tasks_examples
   - capability_records: array of objects, each with {id, text, exact_text, source_location, source_url}

Your job: find ALL tools from the CATALOG whose capability_records are relevant
to the TASK for the given ROLE.

HARD RULE — CATALOG ONLY:
  You MUST only recommend tools that appear in the CATALOG with an explicit
  integer `id`. Do NOT invent, synthesise, or describe tools that are not
  in the CATALOG. If no catalog tool matches, return the no-match sentinel.

For each matching tool provide these fields:
  "tool_id"               : integer — the catalog tool's id (MUST match a real id)
  "vendor"                : string — from the catalog
  "module_offering"       : string — from the catalog
  "sub_offering"          : string — from the catalog (copy exactly)
  "matched_capabilities"  : array of strings — the "text" values of matched capability_records
  "automation_percentage" : integer 0-100 — what % of this OVERALL task can be automated by this tool
  "automation_explanation": string (2-3 sentences) — why that % is appropriate
  "rank_position"         : integer — 1 = best fit, sequential, no gaps
  "reasoning"             : string (3-5 sentences) — why this tool fits the task overall
  "limitations"           : string (2-4 sentences) — overall gaps or caveats for this task
  "capability_details"    : array — one object per MATCHED capability_record with:
    {
      "capability_text"      : string — the "text" value of the capability_record (copy exactly)
      "capability_record_id" : integer or null — the "id" of the capability_record from the catalog
      "automatability_score" : integer 0-100 — how much THIS specific capability can automate the task
      "reason"               : string (2-3 sentences) — how this specific capability helps with this task
      "limitations"          : string (1-2 sentences) — limitations of this capability for this task, or null
    }

Return ONLY valid JSON. Root object must have a single key "tools" whose
value is an array sorted by rank_position ascending (best first).

Rules:
1. ONLY recommend tools whose capability_records genuinely match the task.
2. tool_id MUST be an integer from the CATALOG — never null unless no match.
3. sub_offering MUST match the catalog entry exactly — never paraphrase.
4. capability_details MUST include an entry for every capability in matched_capabilities.
5. capability_text in capability_details MUST exactly match a capability_record "text" value.
6. capability_record_id MUST be the "id" from the catalog capability_record, or null if not found.
7. If NO tool in the catalog matches, return:
   {"tools": [{"tool_id": null, "vendor": null, "module_offering": null,
               "sub_offering": null, "matched_capabilities": [],
               "capability_details": [],
               "automation_percentage": 0,
               "automation_explanation": "No matching tool found.",
               "reasoning": "", "limitations": "No matching tool found.",
               "rank_position": 1}]}
8. Do NOT invent capabilities that are not listed in the catalog.
9. rank_position values must be sequential starting at 1 with no gaps.
"""


def match_single_task_with_llm(
    role: str,
    task: str,
    offerings: list[dict],
) -> list[dict]:
    if not llm.has_llm_client():
        raise RuntimeError("LLM client not configured (LLM_API_KEY missing in .env)")

    catalog_lines = []
    for o in offerings:
        cap_records = o.get("capability_records", [])
        cap_list    = o.get("capabilities", [])
        cap_records_clean = (
            [
                {
                    "id":              cr.get("id"),
                    "text":            cr.get("capability_text"),
                    "exact_text":      cr.get("exact_text"),
                    "source_location": cr.get("source_location"),
                    "source_url":      cr.get("source_url"),
                }
                for cr in cap_records
            ]
            if cap_records
            else [{"id": None, "text": c} for c in cap_list]
        )
        catalog_lines.append(json.dumps({
            "id":                 o["id"],
            "vendor":             o.get("vendor"),
            "module_offering":    o.get("module_offering"),
            "sub_offering":       o.get("sub_offering"),
            "capability_records": cap_records_clean,
            "tasks_examples":     o.get("tasks_examples", []),
        }, ensure_ascii=False))

    user_message = (
        f"ROLE: {role}\n\n"
        f"TASK: {task}\n\n"
        f"TOOL CATALOG:\n" + "\n".join(catalog_lines)
    )

    completion = llm.create_chat_completion(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": MATCHING_SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.0,
        max_tokens=6000,
        response_format={"type": "json_object"},
    )

    parsed = llm.parse_json_content(completion)
    tools  = parsed.get("tools", [])
    tools.sort(key=lambda x: x.get("rank_position", 999))
    return tools
