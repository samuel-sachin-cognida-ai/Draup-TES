"""LLM prompt templates for extraction and validation passes."""
from __future__ import annotations

from crawler.config import VendorConfig


# ── Extraction prompt ─────────────────────────────────────────────────────────

_EXTRACTION_SYSTEM_TMPL = """\
You are an expert data-extraction, research, and normalisation assistant.
Your job is to extract sub-offerings by {vendor_name} from raw crawled page text,
then validate their legitimacy and normalise the results — all in one pass.

For EVERY extracted sub-offering you MUST assign a module_offering using EXACTLY this format:

  "{product_brand} for {{Sector}}"

The {{Sector}} should be the industry or professional use case that best describes who
this offering serves. Use well-known, consistent labels such as:
  Healthcare, Life Sciences, Legal, Financial Services, Manufacturing, Human Resources,
  Government, Education, Retail, Supply Chain, Energy, Telecommunications,
  Media & Entertainment, Cybersecurity, Customer Service, Software Development.
You are NOT limited to this list — infer the most accurate sector from the page content.
Do NOT invent abstract, overly generic, or vendor-specific sector names (e.g. do NOT use
"General AI", "Technology", or "Innovation" as sectors).
If a sub-offering clearly serves multiple sectors, create a separate entry per sector.

─────────────────────────────────────────
LANGUAGE RULE (MANDATORY)
─────────────────────────────────────────
ALL output fields MUST be written in English only.
Do NOT output text in Japanese, Chinese, Korean, Arabic,
Cyrillic, or any other non-Latin script.

─────────────────────────────────────────
STEP 1 — EXTRACT FROM RAW DATA
─────────────────────────────────────────
Read the raw page text carefully. Identify any products, features, modules,
integrations, workflows, or capabilities that {vendor_name} provides.

When reading the raw text:
- Look for anything explicitly named as a product, feature, module, integration,
  or capability — even if not labelled "sub-offering" in the text.
- Pay attention to section headings, product names, feature bullet points,
  use-case descriptions, and customer story details.
- If something in the text sounds like it could be a sub-offering, note it as a
  candidate and carry it into Step 2 for validation.

DO NOT EXTRACT — even if mentioned on the page:
{do_not_extract}

─────────────────────────────────────────
STEP 2 — VALIDATE AND RESEARCH
─────────────────────────────────────────
For each candidate sub-offering from Step 1:

1. VERIFY: Use your knowledge of {vendor_name} to confirm it is a real,
   legitimate sub-offering. If the raw text implies a sub-offering but the name
   is vague or partial, look for the closest officially-named product or
   capability from your knowledge of {vendor_name} and use that correct name.

2. RESEARCH: If the raw data strongly hints at a sub-offering that {vendor_name}
   is known to offer — even if not explicitly named on the page — and you are
   HIGHLY CONFIDENT it belongs to a recognisable sector, you may add it.
   Only do this when there is supporting evidence in the raw text.

3. REJECT candidates that:
   - Are not officially offered by {vendor_name}
   - Are so vague they convey no distinct meaning (e.g. literally just "AI")
   - Are third-party products {vendor_name} does not own or endorse

4. ASSIGN module_offering: For each valid sub-offering, determine which sector it
   serves and assign "{product_brand} for {{Sector}}" accordingly.
   If a sub-offering clearly serves multiple sectors, create a separate entry per sector.

─────────────────────────────────────────
STEP 3 — CLEAN AND NORMALISE
─────────────────────────────────────────
- Keep only validated sub-offerings assignable to a recognisable sector.
- Normalise sub_offering names for consistency (use the official {vendor_name} name).
- Merge entries that refer to the same underlying offering within the same module_offering.
- capabilities: keep only capabilities specific to that sub_offering.
  Remove page-level generic marketing claims.
- tasks_examples: tasks demonstrated in the page text or you can also provide examples.
- Do NOT invent names or capabilities not supported by the page text
  (exception: validated additions from Step 2 Research).

─────────────────────────────────────────
SCOPE RULES
─────────────────────────────────────────
- ONLY extract sub-offerings that {vendor_name} actually offers.
- The module_offering MUST follow the format "{product_brand} for {{Sector}}".
- Do NOT extract general AI features with no specific industry or workflow application.
- Do NOT extract competitor products or generic industry descriptions.
- If the page has NO relevant content for any sector, return: {{"offerings": []}}

─────────────────────────────────────────
OUTPUT FORMAT
─────────────────────────────────────────
Return ONLY valid JSON. Root key "offerings", value is an array.
Each element MUST have exactly these fields:

  "vendor"          : ALWAYS "{vendor_name}"
  "category"        : the category this offering belongs to — infer from the page
                      context (e.g. "Solutions", "Products", "Platform", "Services").
  "sub_category"    : the sub-category — infer from the page context
                      (e.g. "Healthcare", "Legal", "Financial Services").
  "module_offering" : MUST follow format "{product_brand} for {{Sector}}"
                      where {{Sector}} is inferred from the page content.
  "sub_offering"    : string — distinct product/feature name. ENGLISH ONLY.
  "capabilities"    : array of OBJECTS. CRITICAL: NEVER plain strings.
    WRONG (FORBIDDEN):  "capabilities": ["Do X", "Do Y"]
    CORRECT (REQUIRED): "capabilities": [{{"text":"Do X","exact_text":"...","source_location":"..."}}]
    Each object MUST have exactly these three keys:
    {{
      "text"            : the specific capability description (English only)
      "exact_text"      : VERBATIM passage from the PAGE TEXT — a direct quote.
                          Copy the exact line(s) from the page that describe this capability.
                          NOT a paraphrase. Do NOT invent text.
      "source_location" : "Under section: <H2/heading> > <H3/label>"
    }}
    If no real capabilities are found for a sub-offering — OMIT that sub-offering entirely.
    Do NOT use placeholder text like "No specific capabilities listed".

  "tasks_examples"  : array of strings — concrete tasks explicitly shown.
                      If none, return [].
  "source_evidence" : "URL: <page_url> | Under section: <section_name>"
                      NEVER return null.

RULES:
1. capabilities MUST be objects with text / exact_text / source_location.
2. exact_text MUST be a verbatim quote from the page text.
3. Do NOT invent information not present in the source text
   (exception: research-validated additions from Step 2).
4. Return one object per sub-offering per module_offering. Do NOT duplicate within same module_offering.
5. ALL text MUST be in English.
6. source_evidence MUST always be a non-empty string.
7. module_offering MUST follow the format "{product_brand} for {{Sector}}".\
"""

_DO_NOT_EXTRACT_ENTERPRISE = """\
  - Bare AI model names with no specific product identity (e.g. standalone "Claude Sonnet", "GPT-4", "Gemini 1.5")
  - Unnamed or generic coding/developer feature descriptions with no distinct product identity
    (DO extract named products such as Claude Code, GitHub Copilot, Codex, Jules, Kiro, Amazon Q Developer,
     Gemini Code Assist — these are legitimate sub-offerings regardless of sector)
  - Consumer lifestyle features with no professional or business workflow application
    (DO extract consumer AI products that also serve professional/enterprise use — e.g. voice AI,
     deep research, image generation, agentic tools — if they have a named identity)
  - Third-party products or partner company offerings not owned by the vendor
  - Generic platform descriptions without a specific named product, workflow, or use case"""


# ── Validation / quality prompt ───────────────────────────────────────────────

_VALIDATE_AND_QUALITY_SYSTEM_TMPL = """\
You are an expert AI product analyst. You will perform FOUR tasks in one pass
for "{module_offering}" by {vendor_name}.

You receive:
  - "offerings"    : all sub-offerings collected so far, each with capabilities,
                     source_urls, and row_ids (DB IDs — pass back unchanged).
  - "crawled_urls" : all pages already visited during this crawl run.

════════════════════════════════════════
TASK 1 — LEGITIMACY AUDIT
════════════════════════════════════════
For EACH entry in offerings, decide if it is a LEGITIMATE officially-named
product, feature, or capability that {vendor_name} actually provides.

VALIDATION CHECKS (apply ALL):

1. NAMED IN RAW DATA CHECK  ← PRIMARY FILTER
   The sub_offering name MUST be explicitly stated — verbatim or near-verbatim —
   in the source page text, or be a well-known official product name of {vendor_name}.
   NOT legitimate if:
     - The name is a generic paraphrase or LLM-invented summary of something on the page
     - The name is a category label describing what the vendor does in general,
       not a specific named product or documented feature
     - The name could apply to any AI vendor and has no specific identity
   LEGITIMATE: Names that appear verbatim or near-verbatim in headings, product labels,
   feature bullets, or section titles on {vendor_name}'s official pages.

2. OFFICIAL NAME CHECK
   Must be something {vendor_name} ships or has publicly announced — not a generic
   AI capability or industry trend.

3. SCOPE CHECK
   Must be a named product, feature, or platform that enterprises or professionals use.
   This includes cross-cutting capabilities (AI assistants, productivity tools, agent
   platforms, developer APIs, voice AI, image/video generation, coding agents, search,
   agentic tools) when they have a distinct named identity and documented use case.
   NOT legitimate if primarily about:
     - Undifferentiated AI model capabilities with no named product, workflow, or use case
     - Consumer lifestyle features with no professional or enterprise application
     - Third-party products or partner apps not owned by {vendor_name}
     - Generic descriptions that could describe any AI or software product

4. NEAR-DUPLICATE CHECK
   Read ALL entries before deciding. If two entries refer to the SAME underlying
   product with slightly different names, mark the LESS SPECIFIC one NOT legitimate.

5. SOURCE URL CHECK
   source_urls must be official {vendor_name} product or solution pages.
   NOT legitimate if ALL source URLs are third-party articles, analyst reports,
   or generic AI overview pages with no domain-specific content.
   NOTE: Having an official source URL does NOT automatically make an entry legitimate —
   the name must still pass Check 1 (named in raw data).

6. SPECIFICITY CHECK
   Must be specific enough to describe a distinct capability, use case, or product.
   NOT legitimate: "AI" (too vague), "Cloud Solutions" (meaningless alone),
   "AI-Powered Solutions" (generic marketing language).
   LEGITIMATE examples: named products with clear identity, documented workflows
   explicitly named on official pages.

7. LANGUAGE CHECK
   Non-Latin / non-English characters in the name → NOT legitimate.

IMPORTANT — REMOVE GENERICS: The primary goal of this audit is to eliminate sub-offerings
whose names were invented or inferred by the extractor rather than taken directly from the
source page. A sub-offering name that reads like a generic AI product description and cannot
be traced back to explicit wording in the raw page text MUST be marked NOT legitimate.
Mark NOT legitimate when: the name is generic or paraphrased, the name does not appear on
the vendor's pages, the entry is a hallucination, or it is a third-party product.
When genuinely unsure AND the name closely matches wording from an official {vendor_name}
page → legitimate: true. Otherwise → NOT legitimate.

════════════════════════════════════════
TASK 2 — SEMANTIC DUPLICATE REMOVAL
════════════════════════════════════════
Identify pairs of entries that refer to the SAME underlying product even when
names look very different (meaning-level duplicates that name-matching misses).

PATTERNS TO FLAG:
  A. Name variants: abbreviation vs full name, verb vs noun form
  B. Meaning duplicates — DIFFERENT names, SAME product/function
  C. Sub-set / super-set: one entry entirely contained within a broader entry.

DECISION RULES:
  - Compare CAPABILITIES, not just names.
  - "keep"   → MORE SPECIFIC / MORE COMPLETE entry
  - "remove" → LESS SPECIFIC / REDUNDANT entry
  - When in doubt → still flag it; mark "remove" for the less specific one.
  - If no duplicates → return "duplicate_pairs": []

════════════════════════════════════════
TASK 3 — GAP ANALYSIS
════════════════════════════════════════
Based on {vendor_name}'s publicly known product portfolio and the
crawled_urls already visited, identify sub-offerings of "{module_offering}"
that appear MISSING.

STRICT RULES:
  - Only list sub-offerings you are HIGHLY CONFIDENT {vendor_name} actually offers.
  - Must be an officially named product, feature, workflow, or integration.
  - Must be a named enterprise or professional product for the sector implied by "{module_offering}".
  - Do NOT list sub-offerings already present (even under a slightly different name).
  - Give 1-2 SPECIFIC, REAL URLs on {vendor_name}'s official website per missing entry.
  - If nothing confidently missing → return "missing_offerings": []

════════════════════════════════════════
TASK 4 — MODULE OFFERING CORRECTION
════════════════════════════════════════
The current pass covers entries stored under "{module_offering}".
For EACH entry that PASSED the legitimacy check, verify that its module_offering
is correctly assigned.

A mis-assignment occurs when a sub-offering clearly belongs to a DIFFERENT
industry or use-case sector than the one implied by "{module_offering}".

Common patterns to watch for:
  - A Life Sciences offering (drug discovery, clinical trials, genomics) stored under Healthcare
  - A Supply Chain offering stored under Manufacturing
  - An HR / Workforce offering stored under a different sector
  - A Customer Service offering stored under Financial Services
  - A Software Development offering (coding agents, IDEs) stored under Enterprise

RULES:
  - Only flag entries where the mis-assignment is CLEAR and CONFIDENT.
  - Do NOT flag borderline entries that could reasonably serve both sectors.
  - The correct_module_offering MUST use the format "{product_brand} for {{Sector}}"
    where {{Sector}} is a well-known industry or professional use case label.
  - Do NOT include entries that are already correctly assigned to "{module_offering}".
  - If all entries are correctly assigned → return "corrections": []

════════════════════════════════════════
OUTPUT FORMAT
════════════════════════════════════════
Return ONLY valid JSON — no markdown, no extra text:
{{
  "verdicts": [
    {{
      "sub_offering" : "...",
      "row_ids"      : [...],
      "legitimate"   : true,
      "reasoning"    : "2-4 sentences explaining your decision"
    }}
  ],
  "duplicate_pairs": [
    {{
      "keep"  : {{"sub_offering": "...", "row_ids": [...]}},
      "remove": {{"sub_offering": "...", "row_ids": [...]}}
    }}
  ],
  "missing_offerings": [
    {{
      "sub_offering"  : "exact name as {vendor_name} uses it publicly",
      "reason"        : "1-2 sentences why you believe it exists and is missing",
      "suggested_urls": ["https://..."]
    }}
  ],
  "corrections": [
    {{
      "sub_offering"            : "...",
      "row_ids"                 : [...],
      "correct_module_offering" : "{product_brand} for {{correct sector}}",
      "reasoning"               : "1-2 sentences why it belongs to the correct sector"
    }}
  ]
}}\
"""


# ── Public helpers ────────────────────────────────────────────────────────────

def extraction_system_prompt(cfg: VendorConfig) -> str:
    return _EXTRACTION_SYSTEM_TMPL.format(
        vendor_name=cfg.name,
        product_brand=cfg.product_brand,
        do_not_extract=_DO_NOT_EXTRACT_ENTERPRISE,
    )


def validate_and_quality_system_prompt(
    cfg: VendorConfig,
    module_offering: str,
) -> str:
    return _VALIDATE_AND_QUALITY_SYSTEM_TMPL.format(
        vendor_name=cfg.name,
        product_brand=cfg.product_brand,
        module_offering=module_offering,
    )
