"""LLM prompt templates for extraction and validation passes."""
from __future__ import annotations

from crawler.config import VendorConfig

# ── Universal sector taxonomy ─────────────────────────────────────────────────
# The LLM uses this to assign module_offering as "{product_brand} for {Sector}".
# Add new sectors here; the rest of the system adapts automatically.

_UNIVERSAL_SECTOR_DESCRIPTIONS: dict[str, str] = {
    "Healthcare":          "healthcare providers, payers, patients, clinical workflows, EHR, prior authorization, medical documentation, care management, hospital operations",
    "Life Sciences":       "pharmaceutical companies, biotech, drug discovery, clinical trials, genomics, medical devices, life science research, lab informatics",
    "Legal":               "law firms, in-house legal teams, corporate counsel, government legal, contracts, litigation, legal research, discovery, regulatory compliance",
    "Financial Services":  "banking, insurance, investment management, fintech, capital markets, risk management, AML/KYC, fraud detection, wealth management, payments",
    "Manufacturing":       "production operations, supply chain, quality control, factory operations, MES, ERP for manufacturing, inventory, procurement, industrial equipment",
    "Human Resources":     "employee management, recruiting, talent management, payroll, workforce planning, benefits, onboarding, HR service delivery, people analytics",
    "Government":          "government agencies, public sector, federal/state/local government, defense, public services, regulatory bodies, citizen services",
    "Education":           "universities, schools, educational institutions, e-learning, student services, academic administration, research institutions",
    "Retail":              "retail operations, e-commerce, merchandising, customer experience, personalization, inventory management for retail",
    "Supply Chain":        "logistics, supply chain optimization, demand forecasting, procurement, vendor management, warehousing, transportation",
    "Energy":              "oil and gas, utilities, renewable energy, grid management, energy trading, power generation, energy operations",
    "Telecommunications":  "telecom operators, network management, connectivity, 5G, OSS/BSS operations, subscriber management, customer service for telecom",
    "Media & Entertainment": "media companies, content creation, streaming, entertainment, publishing, broadcasting, advertising",
    "Cybersecurity":       "security operations, threat detection, incident response, identity management, vulnerability management, SOC, compliance security",
    "Customer Service":    "customer support, contact center, helpdesk, customer experience management, case management, service operations",
}

# ── Per-sector validation context ─────────────────────────────────────────────
# Controls scope_check and gap_scope strings used in Pass-2 validation prompts.

_SECTOR_CONTEXT: dict[str, dict] = {
    "healthcare": {
        "analyst_role": "healthcare AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for the HEALTHCARE industry (payers, providers, patients, healthcare IT).
   NOT legitimate if primarily about:
     - Life sciences / drug discovery / genomics / bioinformatics (use Life Sciences sector)
     - General AI model features not specific to healthcare
     - Non-healthcare industries (retail, finance, legal, education)
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for HEALTHCARE (payers, providers, patients, clinical workflows, EHR, care management) — NOT life sciences.",
    },
    "life_sciences": {
        "analyst_role": "life sciences AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for LIFE SCIENCES (pharmaceutical, biotech, drug discovery, clinical trials, genomics, medical devices, life science research).
   NOT legitimate if primarily about:
     - General clinical patient care (that belongs in Healthcare)
     - General AI model features not specific to life sciences
     - Non-life-sciences industries
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for LIFE SCIENCES (pharmaceutical, biotech, drug discovery, genomics, clinical trials, medical devices, lab informatics).",
    },
    "legal": {
        "analyst_role": "legal AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for the LEGAL industry (law firms, in-house legal, government legal, corporate counsel).
   NOT legitimate if primarily about:
     - Healthcare, clinical, or medical workflows unrelated to legal practice
     - General AI model features not specific to legal work
     - Non-legal industries (healthcare, retail, finance, education)
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for the LEGAL industry (law firms, in-house legal, corporate counsel, government legal, contracts, litigation, discovery).",
    },
    "financial_services": {
        "analyst_role": "financial services AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for FINANCIAL SERVICES (banking, insurance, investment management, fintech, capital markets).
   NOT legitimate if primarily about:
     - Healthcare, clinical, or medical workflows
     - General AI model features not specific to financial services
     - Non-financial industries (healthcare, manufacturing, education)
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for FINANCIAL SERVICES (banking, insurance, investment, fintech, capital markets, compliance, AML/KYC, fraud detection).",
    },
    "manufacturing": {
        "analyst_role": "manufacturing AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for MANUFACTURING (production, supply chain, quality control, factory operations, MES, ERP for manufacturing).
   NOT legitimate if primarily about:
     - Healthcare, clinical, or medical workflows
     - General AI features not specific to manufacturing
     - Non-manufacturing industries (healthcare, financial services, retail)
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for MANUFACTURING (production, supply chain, quality control, factory operations, MES, ERP for manufacturing, industrial equipment).",
    },
    "hr": {
        "analyst_role": "HR technology AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for HR / Human Resources (employee management, recruiting, talent management, payroll, workforce planning).
   NOT legitimate if primarily about:
     - Healthcare, clinical, or medical workflows
     - General AI features not specific to HR and people management
     - Non-HR domains (healthcare, finance, manufacturing)
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for HR / Human Resources (employee management, recruiting, talent, payroll, benefits, workforce planning, people analytics).",
    },
    "government": {
        "analyst_role": "government AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for GOVERNMENT / PUBLIC SECTOR (federal, state, local government agencies, defense, public services, regulatory bodies).
   NOT legitimate if primarily about:
     - Commercial enterprise use cases unrelated to government workflows
     - General AI model features
     - Non-government industries
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for GOVERNMENT / PUBLIC SECTOR (federal, state, local government, defense, public administration, regulatory bodies, citizen services).",
    },
    "education": {
        "analyst_role": "education technology AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for EDUCATION (universities, schools, e-learning platforms, academic administration, student services).
   NOT legitimate if primarily about:
     - Healthcare or enterprise workflows unrelated to education
     - General AI model features not specific to education
     - Non-education industries
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for EDUCATION (universities, schools, e-learning, academic administration, student and faculty services, research institutions).",
    },
    "retail": {
        "analyst_role": "retail AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for RETAIL (retail operations, e-commerce, merchandising, customer experience in retail).
   NOT legitimate if primarily about:
     - Healthcare, financial services, or manufacturing workflows
     - General AI model features not specific to retail
     - Non-retail industries
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for RETAIL (retail operations, e-commerce, merchandising, inventory, customer experience, personalization).",
    },
    "supply_chain": {
        "analyst_role": "supply chain AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for SUPPLY CHAIN (logistics, supply chain optimization, inventory, procurement, vendor management, warehousing).
   NOT legitimate if primarily about:
     - Healthcare, financial services, or retail workflows
     - General AI model features
     - Non-supply-chain industries
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for SUPPLY CHAIN (logistics, procurement, inventory management, warehousing, vendor management, demand forecasting).",
    },
    "energy": {
        "analyst_role": "energy industry AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for ENERGY (oil and gas, utilities, renewable energy, grid management, energy trading).
   NOT legitimate if primarily about:
     - Healthcare, financial services, or manufacturing workflows
     - General AI model features
     - Non-energy industries
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for ENERGY (oil and gas, utilities, renewable energy, grid management, energy operations, power generation).",
    },
    "telecommunications": {
        "analyst_role": "telecommunications AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for TELECOMMUNICATIONS (telecom operators, network management, connectivity, 5G, OSS/BSS, subscriber management).
   NOT legitimate if primarily about:
     - Healthcare, financial, or manufacturing workflows
     - General AI model features not specific to telecom
     - Non-telecom industries
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for TELECOMMUNICATIONS (telecom operators, network management, 5G, connectivity, OSS/BSS operations, subscriber services).",
    },
    "media_entertainment": {
        "analyst_role": "media and entertainment AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for MEDIA & ENTERTAINMENT (media companies, content creation, streaming, entertainment, publishing, broadcasting).
   NOT legitimate if primarily about:
     - Healthcare, financial, or manufacturing workflows
     - General AI model features not specific to media
     - Non-media industries
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for MEDIA & ENTERTAINMENT (content creation, streaming, broadcasting, publishing, entertainment production, advertising).",
    },
    "cybersecurity": {
        "analyst_role": "cybersecurity AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for CYBERSECURITY (security operations, threat detection, incident response, identity management, SOC, compliance security).
   NOT legitimate if primarily about:
     - Healthcare, financial services, or manufacturing workflows
     - General AI model features not specific to security
     - Non-security industries
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for CYBERSECURITY (security operations, threat detection, incident response, SOC, identity management, vulnerability management).",
    },
    "customer_service": {
        "analyst_role": "customer service AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for CUSTOMER SERVICE (customer support, contact center, helpdesk, customer experience management, service operations).
   NOT legitimate if primarily about:
     - Healthcare, financial, or manufacturing workflows
     - General AI model features not specific to customer service
     - Non-customer-service applications
     - Third-party products or partner apps not owned by the vendor""",
        "gap_scope": "Must be for CUSTOMER SERVICE (customer support, contact center operations, helpdesk, CX management, case management, service operations).",
    },
    "enterprise": {
        "analyst_role": "enterprise AI product analyst",
        "scope_check": """\
3. SCOPE CHECK
   Must be for a recognized enterprise or industry use case.
   NOT legitimate if primarily about:
     - Raw AI model capabilities with no specific industry or workflow application
     - Consumer-only features not applicable to enterprise workflows
     - Third-party products or partner apps not owned by the vendor
     - Generic descriptions that could describe any AI or software product""",
        "gap_scope": "Must be for an enterprise industry sector (healthcare, legal, financial services, manufacturing, HR, government, supply chain, etc.).",
    },
}

# Maps lower-cased sector name (from module_offering string) → _SECTOR_CONTEXT key
SECTOR_NAME_TO_KEY: dict[str, str] = {
    "healthcare":            "healthcare",
    "life sciences":         "life_sciences",
    "legal":                 "legal",
    "financial services":    "financial_services",
    "manufacturing":         "manufacturing",
    "human resources":       "hr",
    "hr":                    "hr",
    "government":            "government",
    "education":             "education",
    "retail":                "retail",
    "supply chain":          "supply_chain",
    "energy":                "energy",
    "telecommunications":    "telecommunications",
    "media & entertainment": "media_entertainment",
    "cybersecurity":         "cybersecurity",
    "customer service":      "customer_service",
}


def sector_key_from_module_offering(module_offering: str, product_brand: str) -> str:
    """Extract sector context key from '{product_brand} for {Sector}' string."""
    prefix = f"{product_brand} for "
    if module_offering.lower().startswith(prefix.lower()):
        sector_name = module_offering[len(prefix):].strip().lower()
    else:
        parts = module_offering.lower().split(" for ", 1)
        sector_name = parts[1].strip() if len(parts) > 1 else "enterprise"
    return SECTOR_NAME_TO_KEY.get(sector_name, "enterprise")


def _build_sector_blocks(product_brand: str) -> tuple[str, str]:
    """Return (sectors_list_block, sector_assignment_guide) for the extraction prompt."""
    list_lines  = []
    guide_lines = []
    for sector_name, desc in _UNIVERSAL_SECTOR_DESCRIPTIONS.items():
        list_lines.append(f'  - "{product_brand} for {sector_name}"')
        guide_lines.append(f'  - "{product_brand} for {sector_name}" → {desc}.')
    return "\n".join(list_lines), "\n".join(guide_lines)


# ── Extraction prompt template ────────────────────────────────────────────────

_EXTRACTION_SYSTEM_TMPL = """\
You are an expert data-extraction, research, and normalisation assistant.
Your job is to extract sub-offerings by {vendor_name} from raw crawled page text,
then validate their legitimacy and normalise the results — all in one pass.

{vendor_name} may offer solutions across many industry sectors. For EVERY extracted
sub-offering you MUST assign a module_offering using EXACTLY this format:

  "{product_brand} for {{Sector}}"

The {{Sector}} MUST be one of the recognised industries listed below.
Do NOT invent sector names outside this list.

RECOGNISED MODULE OFFERINGS (assign the closest match):
{sectors_block}

SECTOR ASSIGNMENT GUIDE:
{sector_assignment_guide}

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
   HIGHLY CONFIDENT it belongs to one of the recognised sectors, you may add it.
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
- Keep only validated sub-offerings assignable to one of the recognised sectors.
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
- If the page has NO relevant content for any listed sector, return: {{"offerings": []}}

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
                      where {{Sector}} is one of the recognised industries above.
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
  - Bare AI model names with no specific product identity (e.g. standalone "Claude Sonnet", "GPT-4", "Gemini")
  - General coding / developer tools (e.g. Claude Code, GitHub Copilot, Codex) unless they have a named enterprise workflow
  - Pure consumer / personal features with no enterprise application
  - Third-party products or partner company offerings not owned by the vendor
  - Generic platform descriptions without a specific named product, workflow, or use case"""


# ── Validation / quality prompt template ─────────────────────────────────────

_VALIDATE_AND_QUALITY_SYSTEM_TMPL = """\
You are a {analyst_role}. You will perform FOUR tasks in one pass
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
   Must be something {vendor_name} ships or has publicly announced as part of
   "{module_offering}" — not a generic AI capability or industry trend.

{scope_check}

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

7. SCOPE CHECK
   If clearly for a different industry and NOT described for the target sector → NOT legitimate.

8. LANGUAGE CHECK
   Non-Latin / non-English characters in the name → NOT legitimate.

IMPORTANT — REMOVE GENERICS: The primary goal of this audit is to eliminate sub-offerings
whose names were invented or inferred by the extractor rather than taken directly from the
source page. A sub-offering name that reads like a generic AI product description and cannot
be traced back to explicit wording in the raw page text MUST be marked NOT legitimate.
Mark NOT legitimate when: the name is generic or paraphrased, the name does not appear on
the vendor's pages, the entry is a hallucination, it belongs to a different industry, or it
is a third-party product. When genuinely unsure AND the name closely matches wording from an
official {vendor_name} domain-specific page → legitimate: true. Otherwise → NOT legitimate.

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
  - {gap_scope}
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
industry sector than the one implied by "{module_offering}".

Common patterns to watch for:
  - A Life Sciences offering (drug discovery, clinical trials, genomics) stored
    under Healthcare
  - A Supply Chain offering stored under Manufacturing
  - An HR / Workforce offering stored under a different sector
  - A Customer Service offering stored under Financial Services

RULES:
  - Only flag entries where the mis-assignment is CLEAR and CONFIDENT.
  - Do NOT flag borderline entries that could reasonably serve both sectors.
  - The correct_module_offering MUST use the format "{product_brand} for {{Sector}}"
    where {{Sector}} is exactly one of:
    Healthcare, Life Sciences, Legal, Financial Services, Manufacturing,
    Human Resources, Government, Education, Retail, Supply Chain, Energy,
    Telecommunications, Media & Entertainment, Cybersecurity, Customer Service.
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


def extraction_system_prompt(cfg: VendorConfig) -> str:
    sectors_block, sector_guide = _build_sector_blocks(cfg.product_brand)
    return _EXTRACTION_SYSTEM_TMPL.format(
        vendor_name=cfg.name,
        product_brand=cfg.product_brand,
        sectors_block=sectors_block,
        sector_assignment_guide=sector_guide,
        do_not_extract=_DO_NOT_EXTRACT_ENTERPRISE,
    )


def validate_and_quality_system_prompt(
    cfg: VendorConfig,
    module_offering: str,
    sector: str,
) -> str:
    ctx = _SECTOR_CONTEXT.get(sector, _SECTOR_CONTEXT["enterprise"])
    return _VALIDATE_AND_QUALITY_SYSTEM_TMPL.format(
        vendor_name=cfg.name,
        product_brand=cfg.product_brand,
        module_offering=module_offering,
        analyst_role=ctx["analyst_role"],
        scope_check=ctx["scope_check"],
        gap_scope=ctx["gap_scope"],
    )
