"""
claude_crawler.py
=================
Crawler for Claude / Anthropic's Healthcare offerings.

Seed URLs are carefully chosen:
  - Specific enough to land on Healthcare pages directly
  - Not so deep that we miss related content (connectors, skills, news)
  - Restricted to official Anthropic/Claude domains only

Run:
    python claude_crawler.py
"""

from __future__ import annotations

import json
import os
import random
import re
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.request import urlopen, Request as UrlRequest

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth  # pip install playwright-stealth

import db
import llm_client as llm

load_dotenv()

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
LLM_MODEL   = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_WORKERS = int(os.getenv("LLM_WORKERS", "3"))
MAX_PAGES   = int(os.getenv("MAX_PAGES", "60"))
TARGET_SUB_OFFERINGS = int(os.getenv("TARGET_SUB_OFFERINGS", "25"))

MODULE_OFFERING = "Claude for Healthcare"
VENDOR_TAG      = "anthropic"

# ──────────────────────────────────────────────
# SEED URLS
# Rationale:
#   /solutions/healthcare    → main product landing page (connectors, skills listed)
#   /news/healthcare…        → official announcements & feature reveals
#   /customers               → customer case studies (healthcare companies)
#   /connectors              → connector marketplace (many are healthcare)
#   docs.claude.com/…        → official integration/API docs for healthcare
# We deliberately do NOT seed /research, /careers, /legal, /pricing etc.
# ──────────────────────────────────────────────
SEED_URLS = [
    "https://claude.com/solutions/healthcare",
    "https://www.anthropic.com/solutions/healthcare",
    "https://www.anthropic.com/news/claude-for-healthcare",
    "https://www.anthropic.com/news/healthcare-life-sciences",
    "https://claude.com/resources/tutorials-category/healthcare",
    "https://claude.com/connectors",
    "https://claude.com/customers",
    "https://www.anthropic.com/news",
]

DOMAIN_ALLOW = ["anthropic.com", "claude.com", "docs.claude.com"]
DOMAIN_NOT_ALLOWED = [
    "support.claude.com", "platform.claude.com",
    "console.anthropic.com", "status.anthropic.com",
    "trust.anthropic.com", "resources.anthropic.com",
]

# Pages that are definitely NOT about Claude for Healthcare
OUT_OF_SCOPE_PATTERNS = [
    "/solutions/life-sciences", "/solutions/financial", "/solutions/education",
    "/solutions/government", "/solutions/nonprofits", "/solutions/coding",
    "/solutions/agents", "/solutions/security", "/solutions/code-modernization",
    "/solutions/customer-support",
    "/product/claude-code", "/product/cowork", "/product/overview",
    "/customers/novo-nordisk", "/customers/flatiron", "/customers/genmab",
    "/customers/sanofi", "/customers/schrödinger", "/customers/edison",
    "/customers/veeva", "/customers/axiom",
    "/news/claude-for-life-sciences", "/news/detecting",
    "/news/claude-code", "/news/anthropic-rwanda",
    "/engineering", "/research", "/pricing", "/transparency",
    "/economic", "/constitution", "/careers", "/legal", "/learn",
    "/events",
]

SKIP_PATH_PATTERNS = [
    "/login", "/signup", "/sign-up", "/register",
    "/account", "/settings", "/profile",
    "/cart", "/checkout", "/search", "/404",
    "/rss", "/feed", "/sitemap",
    "/press", "/brand", "/media-kit",
    "/cookie", "/privacy", "/terms",
    "/contact-sales", "/download", "/regional-compliance",
]

KEYWORDS = [
    "healthcare", "health", "clinical", "medical", "patient",
    "hospital", "hipaa", "ehr", "fhir",
    "solutions", "customers", "news", "tutorials", "resources",
    "connector", "skill", "workflow", "announcement",
    "guide", "integration", "agent",
]

BLOCKED_PATTERNS     = ["Rate exceeded", "Too many requests", "Access denied"]
UNREACHABLE_PATTERNS = [
    "this page could not be found", "this site can't be reached",
    "err_name_not_resolved", "err_connection_timed_out",
    "err_connection_refused", "dns_probe_finished_nxdomain",
    "404 not found", "page not found",
]

DISALLOWED_TERMS = [
    "life science", "life-science", "drug discovery", "genomics",
    "biotech", "claude code", "cowork", "coding assistant",
]
TOO_GENERIC_TERMS = [
    "healthcare", "clinical", "patient", "workflow", "connector", "skill",
    "solution", "assistant", "tool", "capability", "integration", "platform",
]

# ──────────────────────────────────────────────
# PLAIN HTTP FALLBACK (Cloudflare bypass)
# ──────────────────────────────────────────────
_FALLBACK_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

def _plain_fetch(url: str, timeout: int = 20) -> str | None:
    """Plain urllib GET — no JS, no automation signals. Fallback when Playwright is blocked."""
    try:
        req = UrlRequest(url, headers={
            "User-Agent":      _FALLBACK_UA,
            "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


# ──────────────────────────────────────────────
# STATE / STATS
# ──────────────────────────────────────────────
RUN_STATS: dict = {
    "pages_visited": 0, "llm_tasks_sent": 0,
    "raw_saved": 0, "extracted_saved": 0,
    "duplicates_skipped": 0, "non_target_skipped": 0,
    "non_english_skipped": 0,
}
stats_lock = threading.Lock()

discovered_sub_offerings: set[str] = set()
sub_offerings_lock = threading.Lock()

stop_requested    = False
shutdown_complete = False
shutdown_lock     = threading.Lock()

_executor_ref:    ThreadPoolExecutor | None = None
_llm_futures_ref: list | None              = None


def increment_stat(key: str, amount: int = 1) -> None:
    with stats_lock:
        RUN_STATS[key] = RUN_STATS.get(key, 0) + amount


def print_run_summary(reason: str = "normal completion") -> None:
    with stats_lock:
        print(f"\n[SUMMARY] Crawler stopped ({reason})")
        for k, v in RUN_STATS.items():
            print(f"[SUMMARY] {k:<30}: {v}")
    with sub_offerings_lock:
        print(f"[SUMMARY] Unique sub-offerings found : {len(discovered_sub_offerings)}")
        for i, name in enumerate(sorted(discovered_sub_offerings), 1):
            print(f"           {i:>2}. {name}")


# ──────────────────────────────────────────────
# GRACEFUL SHUTDOWN
# ──────────────────────────────────────────────
def _graceful_shutdown(reason: str) -> None:
    global shutdown_complete
    with shutdown_lock:
        if shutdown_complete:
            return
        shutdown_complete = True

    print(f"\n[SHUTDOWN] Triggered by: {reason}")
    if _llm_futures_ref:
        print(f"[SHUTDOWN] Waiting for {len(_llm_futures_ref)} pending LLM task(s)…")
        for future in as_completed(_llm_futures_ref):
            try:
                future.result()
            except Exception as e:
                print(f"[LLM] Background task error during shutdown: {e}")
        print("[SHUTDOWN] All LLM tasks finished.")
    if _executor_ref:
        _executor_ref.shutdown(wait=False)

    _post_crawl_validate()
    print_run_summary(reason)


def handle_stop_signal(signum, _frame) -> None:
    global stop_requested
    stop_requested = True
    sig_name = "SIGINT" if signum == signal.SIGINT else f"signal {signum}"
    print(f"\n[STOP] Received {sig_name}. Finishing current page…")
    t = threading.Thread(target=_graceful_shutdown, args=(f"killed by {sig_name}",), daemon=True)
    t.start()
    t.join()


# ──────────────────────────────────────────────
# URL FILTERING
# ──────────────────────────────────────────────
def is_blocked_page(content: str) -> bool:
    cl = content.lower()
    return any(p.lower() in cl for p in BLOCKED_PATTERNS)


def is_unreachable(status_code, content: str) -> bool:
    if status_code in (404, 410):
        return True
    cl = content.lower()
    return any(p in cl for p in UNREACHABLE_PATTERNS)


def is_valid_domain(url: str) -> bool:
    return (
        any(d in url for d in DOMAIN_ALLOW)
        and not any(d in url for d in DOMAIN_NOT_ALLOWED)
    )


def is_out_of_scope(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(p in path for p in OUT_OF_SCOPE_PATTERNS)


def should_skip_path(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(s in path for s in SKIP_PATH_PATTERNS)


def should_skip_pagination(url: str) -> bool:
    for key, val in parse_qs(urlparse(url).query).items():
        if "page" in key.lower():
            try:
                if int(val[0]) > 2:
                    return True
            except Exception:
                pass
    return False


def is_worth_visiting(url: str, visited_paths: set) -> bool:
    parsed     = urlparse(url)
    clean_path = parsed.path.lower().rstrip("/")
    if not clean_path or clean_path == "/":
        return False
    if clean_path in visited_paths:
        return False
    if should_skip_path(url) or is_out_of_scope(url):
        return False
    if clean_path.endswith((".pdf", ".zip", ".png", ".jpg", ".jpeg",
                            ".gif", ".svg", ".mp4", ".mp3", ".css", ".js")):
        return False
    if not any(kw in clean_path for kw in KEYWORDS):
        return False
    visited_paths.add(clean_path)
    return True


def normalize(url: str) -> str:
    return url.split("#")[0].rstrip("/")


# ──────────────────────────────────────────────
# HTML CLEANING
# ──────────────────────────────────────────────
def extract_clean_text(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")

    for tag in ["script", "style", "noscript", "svg", "footer",
                 "nav", "header", "form", "iframe", "img", "video",
                 "audio", "canvas", "button", "aside", "input",
                 "textarea", "label", "select", "option", "meta",
                 "link", "source", "picture", "figure", "figcaption",
                 "advertisement", "ads", "menu", "menuitem",
                 "dialog", "embed", "object", "portal", "track",
                 "map", "area", "ins", "del", "sup", "sub"]:
        for el in soup.find_all(tag):
            el.decompose()

    skip_cls = [
        "footer", "header", "nav", "menu", "sidebar", "banner",
        "promo", "cta", "signup", "login", "subscribe", "breadcrumb",
        "social", "share", "popup", "modal", "cookie", "notification",
        "advert", "recommendation", "related", "comment",
        "newsletter", "pagination", "toolbar", "floating", "sticky",
    ]
    for el in soup.find_all(True):
        if not el.attrs:
            continue
        classes    = " ".join(el.get("class", [])).lower()
        element_id = str(el.get("id", "")).lower()
        if any(kw in classes for kw in skip_cls) or any(kw in element_id for kw in skip_cls):
            el.decompose()

    # Use newline separator for block-level elements so the LLM can produce
    # genuine verbatim exact_text quotes that are traceable to the source page.
    # Collapsing everything to a single space (separator=" ") destroys sentence
    # and paragraph boundaries, making real verbatim extraction impossible.
    BLOCK_TAGS = {
        "p", "div", "section", "article", "main", "li", "ul", "ol",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "blockquote", "pre", "code", "td", "th", "tr", "dt", "dd",
        "br", "hr",
    }
    for el in soup.find_all(BLOCK_TAGS):
        el.insert_before("\n")
        el.insert_after("\n")

    text = soup.get_text(separator="")
    # Collapse runs of spaces/tabs within each line, but keep newlines intact
    lines = [" ".join(line.split()) for line in text.splitlines()]
    # Remove blank lines and rejoin with newlines for readable structure
    cleaned = "\n".join(line for line in lines if line.strip())
    return cleaned


# ──────────────────────────────────────────────
# PROMPTS
# ──────────────────────────────────────────────
EXTRACTION_SYSTEM_PROMPT = '''
You are an expert data-extraction assistant. Your ONLY job is to extract
information about "Claude for Healthcare" — the healthcare-specific
product offering by Anthropic.

─────────────────────────────────────────
LANGUAGE RULE (MANDATORY)
─────────────────────────────────────────
ALL output fields MUST be written in English only.
Do NOT output any text in Japanese, Chinese, Korean, Arabic,
Cyrillic, or any other non-Latin script.

─────────────────────────────────────────
SCOPE RULES
─────────────────────────────────────────
- ONLY extract sub-offerings that belong to "Claude for Healthcare".
- Extract based ONLY on evidence in the provided page text.
- Valid sub-offerings: connectors, integrations, skills, agents, workflows
  explicitly named as part of Claude for Healthcare by Anthropic.
- Also extract consumer health integrations (e.g. Apple Health, Android Health
  Connect) and connectors described as "existing" or "already available"
  (e.g. PubMed) when the page places them under Claude for Healthcare.
- Do NOT extract offerings for Claude Code, Claude Cowork, Claude for Life
  Sciences, or any other Anthropic product.
- Do NOT extract customer quotes, testimonials, or case study descriptions.
- DO extract sub-offerings shown in interactive UI demos or walkthroughs.
- On pages covering both Healthcare and Life Sciences, ONLY extract
  sub-offerings under a "Claude for Healthcare" heading/section/label.
- If the page has NO Claude for Healthcare content, return: {"offerings": []}

─────────────────────────────────────────
OUTPUT FORMAT
─────────────────────────────────────────
Return ONLY valid JSON. Root key "offerings", value is an array.
Each element MUST have exactly these fields:

  "vendor"          : ALWAYS "Anthropic"
  "category"        : ALWAYS "Solutions"
  "sub_category"    : ALWAYS "Industries"
  "module_offering" : ALWAYS "Claude for Healthcare"
  "sub_offering"    : string — distinct connector/skill/workflow name. ENGLISH ONLY.
  "capabilities"    : array of OBJECTS. CRITICAL: NEVER plain strings — always objects.
    WRONG (FORBIDDEN):  "capabilities": ["Do X", "Do Y"]
    CORRECT (REQUIRED): "capabilities": [{"text":"Do X","exact_text":"...","source_location":"..."}, ...]
    Each object MUST have exactly these three keys:
    {
      "text"             : string — the specific capability description (ENGLISH ONLY)
      "exact_text"       : string — the EXACT verbatim passage (sentence or phrase)
                           from the PAGE TEXT where this capability was found.
                           The PAGE TEXT is newline-structured: each line is a real
                           sentence or label from the page. Find the line(s) that
                           best describe this capability and copy them word for word.
                           This MUST be a direct quote you can locate in PAGE TEXT,
                           NOT a paraphrase or summary. Do NOT invent text.
      "source_location"  : string — the section/heading where this capability appears.
                           Format: "Under section: <H2> > <H3/label>"
                           e.g. "Under section: Prior Authorization > Review Skill features"
    }
    NEVER return null or an empty array — if a sub-offering is named on the page
    but NO capabilities are described, OMIT that sub-offering from the output entirely.
    Do NOT use a placeholder like "No specific capabilities listed on this page" —
    if you cannot find real capabilities from the page text, exclude the sub-offering.

  "tasks_examples"  : array of strings — concrete tasks explicitly shown by Anthropic.
                      If none, return [].

  "source_evidence" : string — page URL + exact location where sub-offering was found.
                      Format: "URL: <page_url> | Under section: <section_name> > <label>"
                      NEVER return null.

RULES:
1. vendor, category, sub_category, module_offering are FIXED values.
2. capabilities MUST be an array of objects with text/exact_text/source_location.
3. capabilities must be specific to that exact sub_offering only.
4. Return one object per sub-offering. Do NOT duplicate.
5. Do NOT invent information not present in the source text.
6. ALL text MUST be in English.
7. source_evidence MUST always be a non-empty string.
8. exact_text in each capability MUST be a verbatim quote from the page text.
'''

REFINEMENT_SYSTEM_PROMPT = '''
You are a strict normalization and quality-improvement layer for extracted
"Claude for Healthcare" offerings.

You will receive:
  1) URL
  2) PAGE TEXT
  3) A JSON array of preliminary extracted offerings. Capabilities are objects
     with keys: text, exact_text, source_location.

PART 1 — GAP CHECK
Re-read the PAGE TEXT. If the preliminary extraction is missing a
sub-offering that clearly belongs to Claude for Healthcare, add it.
Apply the same scope rules as extraction.

PART 2 — NORMALIZE AND CLEAN
- Keep only entries that belong to "Claude for Healthcare".
- Normalize sub_offering names using the priority order in the extraction prompt.
- Merge entries that are the same underlying offering.
- capabilities: specific to that sub_offering only; remove generic page-level claims.
  Preserve exact_text and source_location from the input wherever possible.
- tasks_examples: only tasks explicitly demonstrated by Anthropic. If none → [].
- Do NOT invent names or capabilities.

LANGUAGE RULE: ALL output text MUST be in English only.

Return ONLY valid JSON:
{
  "offerings": [
    {
      "vendor": "Anthropic",
      "category": "Solutions",
      "sub_category": "Industries",
      "module_offering": "Claude for Healthcare",
      "sub_offering": "...",
      "capabilities": [
        {
          "text": "...",
          "exact_text": "...",
          "source_location": "..."
        }
      ],
      "tasks_examples": ["..."],
      "source_evidence": "URL: <page_url> | Under section: <section_name> > <subsection_or_label>"
    }
  ]
}
'''

VALIDATION_SYSTEM_PROMPT = '''
You are a healthcare AI product analyst at Anthropic. Your job is to
audit a list of alleged "Claude for Healthcare" sub-offerings and decide
which ones are LEGITIMATE, officially named sub-offerings that Anthropic
actually ships as part of "Claude for Healthcare".

You will receive a JSON array of objects, each with:
  - "sub_offering"   : the name that was extracted
  - "capabilities"   : what the extractor said it can do
  - "source_urls"    : the page(s) it was found on
  - "row_ids"        : database IDs (pass them back unchanged)

For EACH entry, decide:
  - "legitimate"  : true or false
  - "reasoning"   : 2-4 sentences explaining your decision.

VALIDATION CHECKS (apply ALL of these):
1. OFFICIAL NAME CHECK: Is this an officially named connector, skill, or
   workflow that Anthropic explicitly offers under "Claude for Healthcare"?
2. DUPLICATE CHECK: If two entries refer to the same underlying sub-offering
   with different names, keep ONLY the most complete/specific name.
3. SOURCE CHECK: Is the source URL an official Anthropic or Claude page?
4. SPECIFICITY CHECK: Is the name too vague or generic?
5. LANGUAGE CHECK: If the sub_offering name contains non-English or non-Latin
   characters, mark it NOT legitimate immediately.

IMPORTANT: Only mark NOT legitimate if CONFIDENT the entry is wrong.
If unsure, mark legitimate.

Return ONLY valid JSON with single key "verdicts" — array where each element has:
  - "sub_offering" : string (unchanged)
  - "row_ids"      : array of integers (unchanged)
  - "legitimate"   : boolean
  - "reasoning"    : string
'''


# ──────────────────────────────────────────────
# LLM FUNCTIONS
# ──────────────────────────────────────────────
def _refine_offerings(url: str, page_text: str, offerings: list[dict]) -> list[dict]:
    """Second LLM pass: gap-check and normalize the extracted offerings."""
    if not llm.has_llm_client() or not offerings:
        return offerings
    try:
        completion = llm.create_chat_completion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": REFINEMENT_SYSTEM_PROMPT},
                {"role": "user",   "content": json.dumps(
                    {"url": url, "page_text": page_text[:25000], "offerings": offerings},
                    ensure_ascii=False,
                )},
            ],
            temperature=0.0,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        result  = llm.parse_json_content(completion)
        refined = result.get("offerings", [])
        if isinstance(refined, list) and refined:
            print(f"[REFINE] {len(offerings)} → {len(refined)} offering(s) for {url}")
            return refined
    except Exception as e:
        print(f"[REFINE] Failed for {url}: {e}")
    return offerings


def _normalize_capabilities(offerings: list[dict]) -> None:
    """Ensure capabilities are rich objects (text/exact_text/source_location)."""
    for item in offerings:
        raw_caps = item.get("capabilities", [])
        if raw_caps and isinstance(raw_caps[0], str):
            item["capabilities"] = [
                {"text": c, "exact_text": "", "source_location": ""}
                for c in raw_caps if c
            ]


def extract_with_llm(url: str, text: str, raw_data_id: int) -> None:
    """Three-pass pipeline: extract → refine → (post-crawl validate at end of run)."""
    if not llm.has_llm_client():
        return
    with sub_offerings_lock:
        if len(discovered_sub_offerings) >= TARGET_SUB_OFFERINGS:
            print(f"[LLM] Target reached — skipping {url}")
            return

    page_text = text[:40000]
    try:
        # Pass 1 — extraction
        completion = llm.create_chat_completion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user",   "content": f"URL: {url}\n\nPAGE TEXT:\n{page_text}"},
            ],
            temperature=0.0,
            max_tokens=6000,
            response_format={"type": "json_object"},
        )
        extracted = llm.parse_json_content(completion)
        offerings = extracted.get("offerings", [])

        if not offerings:
            print(f"[LLM] No healthcare offerings found on {url}")
            return

        # Ensure rich capability format after extraction
        _normalize_capabilities(offerings)

        # Pass 2 — refinement / gap-check
        offerings = _refine_offerings(url, page_text, offerings)

        # Ensure rich capability format after refinement (refinement may return plain strings)
        _normalize_capabilities(offerings)

        offerings = [db.prepare_offering_for_storage(item) for item in offerings]
        print(f"[LLM] Extracted {len(offerings)} offering(s) from {url}")

        db.save_extracted_to_db(
            raw_data_id=raw_data_id,
            url=url,
            extracted={"offerings": offerings},
            module_offering_filter=MODULE_OFFERING,
            discovered_sub_offerings=discovered_sub_offerings,
            target_sub_offerings=TARGET_SUB_OFFERINGS,
            stats=RUN_STATS,
            stats_lock=stats_lock,
            disallowed_terms=DISALLOWED_TERMS,
            too_generic_terms=TOO_GENERIC_TERMS,
        )

        increment_stat("extracted_saved", 0)  # already counted inside save_extracted_to_db

    except json.JSONDecodeError as e:
        print(f"[LLM] JSON parse error for {url}: {e}")
    except Exception as e:
        print(f"[LLM] Error processing {url}: {e}")


# ──────────────────────────────────────────────
# POST-CRAWL VALIDATION  (Pass 3 — LLM audit)
# ──────────────────────────────────────────────
def _post_crawl_validate() -> None:
    """
    Third pass: LLM audits all collected sub-offerings and removes any
    that are not legitimate official Claude for Healthcare offerings.
    Also removes rows with non-English sub_offering names.
    """
    import psycopg2.extras
    if not llm.has_llm_client():
        return

    print("\n" + "=" * 60)
    print("[VALIDATE] Starting post-crawl LLM validation…")
    print("=" * 60)

    conn = db.get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT id, sub_offering, capabilities, tasks_examples, url
            FROM extracted_offerings
            WHERE module_offering = %s
            ORDER BY sub_offering, id;
        """, (MODULE_OFFERING,))
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

    if not rows:
        print("[VALIDATE] No offerings to validate.")
        return

    # Language purge first
    non_english_ids: list[int] = []
    clean_rows = []
    for r in rows:
        sub = r.get("sub_offering") or ""
        if not db.is_english_text(sub):
            non_english_ids.append(r["id"])
        else:
            clean_rows.append(r)

    if non_english_ids:
        conn = db.get_pg_connection()
        cur  = conn.cursor()
        try:
            cur.execute("DELETE FROM extracted_offerings WHERE id = ANY(%s);", (non_english_ids,))
            conn.commit()
            print(f"[VALIDATE][LANG] Deleted {cur.rowcount} non-English row(s).")
        except Exception as e:
            conn.rollback()
            print(f"[VALIDATE][LANG] Error: {e}")
        finally:
            cur.close()
            conn.close()

    rows = clean_rows
    if not rows:
        print("[VALIDATE] No offerings remain after language purge.")
        return

    # Group by sub_offering for LLM audit
    groups: dict[str, dict] = {}
    for r in rows:
        key = (r["sub_offering"] or "").strip().lower()
        if key not in groups:
            groups[key] = {
                "sub_offering": r["sub_offering"],
                "capabilities": [], "source_urls": [], "row_ids": [],
            }
        groups[key]["row_ids"].append(r["id"])
        if r["url"] not in groups[key]["source_urls"]:
            groups[key]["source_urls"].append(r["url"])
        for cap in (r["capabilities"] or []):
            if cap and cap not in groups[key]["capabilities"]:
                groups[key]["capabilities"].append(cap)

    audit_list = list(groups.values())
    print(f"[VALIDATE] {len(audit_list)} unique sub-offering(s) to review.")

    try:
        completion = llm.create_chat_completion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                {"role": "user",   "content": json.dumps(audit_list, indent=2, ensure_ascii=False)},
            ],
            temperature=0.0,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        result   = llm.parse_json_content(completion)
        verdicts = result.get("verdicts", [])
    except Exception as e:
        print(f"[VALIDATE] LLM error: {e} — keeping all offerings.")
        return

    ids_to_delete: list[int] = []
    for v in verdicts:
        name  = v.get("sub_offering", "?")
        legit = v.get("legitimate", True)
        print(f"  [{'KEEP' if legit else 'REMOVE':6}] {name} — {v.get('reasoning', '')}")
        if not legit:
            ids_to_delete.extend(v.get("row_ids", []))

    if ids_to_delete:
        conn = db.get_pg_connection()
        cur  = conn.cursor()
        try:
            cur.execute("DELETE FROM extracted_offerings WHERE id = ANY(%s);", (ids_to_delete,))
            print(f"[VALIDATE] Deleted {cur.rowcount} rejected row(s).")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[VALIDATE] Delete error: {e}")
        finally:
            cur.close()
            conn.close()
    else:
        print("[VALIDATE] All offerings passed — nothing to remove.")

    print("=" * 60)


# ──────────────────────────────────────────────
# MAIN CRAWLER
# ──────────────────────────────────────────────
def run_crawler() -> None:
    global stop_requested, _executor_ref, _llm_futures_ref

    signal.signal(signal.SIGINT, handle_stop_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_stop_signal)

    print("=" * 60)
    print("Claude for Healthcare Crawler")
    print(f"[CONFIG] LLM base            : {llm.LLM_BASE_URL}")
    print(f"[CONFIG] LLM model           : {LLM_MODEL}")
    print(f"[CONFIG] API keys loaded     : {len(llm.LLM_API_KEYS)}")
    print(f"[CONFIG] LLM workers         : {LLM_WORKERS}")
    print(f"[CONFIG] Target sub-offerings: {TARGET_SUB_OFFERINGS}")
    print(f"[CONFIG] Max pages           : {MAX_PAGES}")
    print("=" * 60)

    db.init_db()

    visited:       set[str] = set()
    visited_paths: set[str] = set()
    queue:         list[str] = list(SEED_URLS)

    llm_futures: list    = []
    executor             = ThreadPoolExecutor(max_workers=LLM_WORKERS)
    _executor_ref        = executor
    _llm_futures_ref     = llm_futures

    def drain_futures() -> None:
        still = []
        for fut in llm_futures:
            if fut.done():
                try:
                    fut.result()
                except Exception as e:
                    print(f"[LLM] Background error: {e}")
            else:
                still.append(fut)
        llm_futures.clear()
        llm_futures.extend(still)

    crawl_exception = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                slow_mo=100,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--disable-gpu",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                java_script_enabled=True,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;"
                        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                    ),
                },
            )
            Stealth().apply_stealth_sync(context)  # hide automation fingerprints (v2 API)
            page = context.new_page()

            with open("claude_healthcare_data.jsonl", "a", encoding="utf-8") as f:
                while queue:
                    drain_futures()

                    if stop_requested:
                        break
                    with sub_offerings_lock:
                        if len(discovered_sub_offerings) >= TARGET_SUB_OFFERINGS:
                            print("[CRAWLER] Target sub-offerings reached. Stopping.")
                            stop_requested = True
                            break

                    pages_so_far = RUN_STATS.get("pages_visited", 0)
                    if pages_so_far >= MAX_PAGES:
                        print(f"[SAFETY] MAX_PAGES ({MAX_PAGES}) reached. Stopping.")
                        stop_requested = True
                        break

                    url = queue.pop(0)
                    if url in visited:
                        continue

                    print(f"\nVisiting ({pages_so_far + 1}/{MAX_PAGES}): {url}")
                    visited.add(url)
                    increment_stat("pages_visited")

                    try:
                        response = None
                        for attempt in range(2):
                            try:
                                response = page.goto(url, timeout=30000)
                                page.wait_for_timeout(random.randint(2000, 4000))
                                break
                            except Exception:
                                if attempt == 1:
                                    raise

                        for _ in range(2):
                            page.mouse.wheel(0, 3000)
                            page.wait_for_timeout(1000)

                        content = page.content()

                        # Blocked? → try plain HTTP first, then sleep + Playwright retry
                        if is_blocked_page(content):
                            print(f"[BLOCKED] Playwright blocked on {url} — trying plain HTTP…")
                            fallback = _plain_fetch(url)
                            if fallback and not is_blocked_page(fallback):
                                print("[BLOCKED] Plain HTTP succeeded.")
                                content = fallback
                            else:
                                sleep_t = random.randint(30, 60)
                                print(f"[BLOCKED] Plain HTTP also blocked — sleeping {sleep_t}s then retrying Playwright…")
                                time.sleep(sleep_t)
                                try:
                                    response = page.goto(url, timeout=60000,
                                                         wait_until="domcontentloaded")
                                    page.wait_for_timeout(random.randint(6000, 10000))
                                    content = page.content()
                                except Exception as _retry_err:
                                    print(f"[BLOCKED] Playwright retry failed: {_retry_err}")

                        status = response.status if response else None
                        if is_unreachable(status, content):
                            print(f"[SKIP] Not found: {url}")
                            continue

                        clean_text = extract_clean_text(content)
                        f.write(json.dumps({"url": url, "text": clean_text}) + "\n")

                        raw_id = db.save_raw_to_db(url, clean_text, VENDOR_TAG)
                        if raw_id is not None:
                            increment_stat("raw_saved")
                            future = executor.submit(extract_with_llm, url, clean_text, raw_id)
                            llm_futures.append(future)
                            increment_stat("llm_tasks_sent")
                        else:
                            print(f"[CACHE] Page unchanged, skipping LLM: {url}")

                        soup = BeautifulSoup(content, "html.parser")
                        for link in soup.find_all("a", href=True):
                            full_url = normalize(urljoin(url, link["href"]))
                            if (
                                full_url not in visited
                                and is_valid_domain(full_url)
                                and is_worth_visiting(full_url, visited_paths)
                                and not should_skip_pagination(full_url)
                            ):
                                queue.append(full_url)

                    except Exception as e:
                        print(f"[FAIL] {url} — {e}")
                        continue

            page.close()
            browser.close()

    except Exception as e:
        crawl_exception = e
        print(f"\n[ERROR] Crawler error: {e}")

    if not stop_requested or not shutdown_complete:
        reason = "normal completion"
        if crawl_exception:
            reason = f"error: {crawl_exception}"
        _graceful_shutdown(reason)


if __name__ == "__main__":
    run_crawler()
