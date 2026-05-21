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

Return ONLY valid JSON. Root object must have TWO top-level keys:

  "task_clarity_score" : integer 1-10 — evaluate how specific and actionable the TASK description
                         is for the given ROLE, independent of whether catalog tools exist.
                           1-3 = too vague to match meaningfully (e.g. "write something",
                                 "do analysis", "?", single words, placeholders like N/A or TODO)
                           4-6 = partially specific — some domain signal but missing key details
                           7-10 = specific and actionable — enough detail to match confidently

  "tools"              : array of matched tools sorted by rank_position ascending (best first).

ROLE FITNESS CHECK:
Before recommending any tool, ask: would this ROLE realistically adopt this tool as part of
their core job function — regardless of what domain or category that tool belongs to?
- Consider the role's actual day-to-day work. Physical, trade, and field roles (e.g. Janitor,
  Electrician, Plumber, Chef, Construction Worker, Security Guard, Delivery Driver) perform
  hands-on physical work. No enterprise AI tool — whether it is a coding assistant, a finance
  platform, a healthcare AI, a CRM, an ITSM tool, a cybersecurity product, an HR platform, or
  any other category — is a genuine fit for a purely physical task performed by such a role.
- Textual overlap alone is NOT sufficient. A "cleaning checklist" for a Janitor is not a match
  for any software tool just because both involve lists or documentation.
- Apply this check universally across all tool categories in the catalog. Do not limit the
  fitness check to specific domains — if the role would not use a tool of that type in their
  real job, it is not a match.
- If the role's core function is fundamentally misaligned with the tool's purpose, return the
  no-match sentinel even if some capability text appears similar.
- When in genuine doubt between a weak match and no match, prefer no match.

TASK FITNESS CHECK:
Before recommending any tool, independently assess whether the TASK's subject matter is
genuinely represented in the CATALOG you received — not just whether something sounds loosely
similar.
Step 1 — Identify the task's core domain: what field, technology, or subject does this task
  actually belong to? (e.g. broadcast media, SCADA/grid operations, marine biology, education,
  agriculture, retail scheduling, real estate, etc.)
Step 2 — Scan the catalog: do any of the 20 offerings actually address that domain or provide
  capabilities that directly serve that type of work?
Step 3 — Apply a strict relevance gate:
  - If the task domain is absent from the catalog (e.g. the catalog has healthcare and legal
    tools but the task is about power grid telemetry), return the no-match sentinel.
  - Keyword coincidence is NOT a match. A tool that mentions "monitoring" or "reporting" does
    not match a SCADA monitoring task just because both use the word "monitoring".
  - The catalog tool must address the actual subject matter of the task — not just share
    surface-level vocabulary.
  - A weak or tangential connection is not sufficient. Only recommend a tool if you are
    confident it genuinely covers what the task requires.
- If the task passes the ROLE FITNESS CHECK but fails the TASK FITNESS CHECK, still return
  the no-match sentinel. Both checks must pass independently.

Rules:
1. ONLY recommend tools whose capability_records genuinely match BOTH the task AND the role's
   core function. Both the ROLE FITNESS CHECK and the TASK FITNESS CHECK must pass before
   recommending any tool.
2. tool_id MUST be an integer from the CATALOG — never null unless no match.
3. sub_offering MUST match the catalog entry exactly — never paraphrase.
4. capability_details MUST include an entry for every capability in matched_capabilities.
5. capability_text in capability_details MUST exactly match a capability_record "text" value.
6. capability_record_id MUST be the "id" from the catalog capability_record, or null if not found.
7. If NO tool in the catalog matches, return:
   {"task_clarity_score": <score>, "tools": [{"tool_id": null, "vendor": null,
               "module_offering": null, "sub_offering": null, "matched_capabilities": [],
               "capability_details": [], "automation_percentage": 0,
               "automation_explanation": "No matching tool found.",
               "reasoning": "", "limitations": "No matching tool found.",
               "rank_position": 1}]}
8. Do NOT invent capabilities that are not listed in the catalog.
9. rank_position values must be sequential starting at 1 with no gaps.
10. Always include task_clarity_score even when returning no-match.
11. Both the ROLE FITNESS CHECK and the TASK FITNESS CHECK are hard gates. A tool must pass
    both independently. Failing either one means returning the no-match sentinel.
"""


def match_single_task_with_llm(
    role: str,
    task: str,
    offerings: list[dict],
) -> dict:
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

    parsed              = llm.parse_json_content(completion)
    tools               = parsed.get("tools", [])
    task_clarity_score  = int(parsed.get("task_clarity_score", 10))
    tools.sort(key=lambda x: x.get("rank_position", 999))
    return {"tools": tools, "task_clarity_score": task_clarity_score}
