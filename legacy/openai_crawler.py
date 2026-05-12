"""
openai_crawler.py
=================
Crawler for OpenAI's Healthcare offerings (ChatGPT Enterprise, GPT-4o in health,
HealthGPT integrations, etc.).

Seed URLs are chosen to be:
  - Specific enough to land on Healthcare pages & use-cases
  - Not so deep that we miss related content (customers, case studies, API docs)
  - Restricted to official openai.com / chatgpt.com domains only

Run:
    python openai_crawler.py
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
from urllib.parse import urljoin, urlparse, parse_qs, quote_plus
from urllib.request import urlopen, Request as UrlRequest
from urllib.error import URLError

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth  # pip install playwright-stealth

import db
import llm_client as llm

# ──────────────────────────────────────────────
# CLOUDFLARE FALLBACK: plain HTTP fetch
# ──────────────────────────────────────────────
_FALLBACK_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

def _plain_fetch(url: str, timeout: int = 20) -> str | None:
    """
    Attempt a plain urllib GET — no JS, but no automation signals either.
    Useful as a fallback when Playwright triggers Cloudflare on static pages.
    Returns HTML string or None on failure.
    """
    try:
        req = UrlRequest(url, headers={
            "User-Agent": _FALLBACK_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None



load_dotenv()

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
LLM_MODEL   = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_WORKERS = int(os.getenv("LLM_WORKERS", "3"))
MAX_PAGES   = int(os.getenv("MAX_PAGES_OPENAI", os.getenv("MAX_PAGES", "80")))
TARGET_SUB_OFFERINGS = int(os.getenv("TARGET_SUB_OFFERINGS_OPENAI", "25"))

MODULE_OFFERING = "ChatGPT for Healthcare"
VENDOR_TAG      = "openai"

# ──────────────────────────────────────────────
# SEED URLS
# Rationale:
#   /solutions/industries/healthcare/            → primary OpenAI healthcare solutions page
#   /index/openai-for-healthcare/               → Jan 2026 launch: ChatGPT for Healthcare +
#                                                  OpenAI API for Healthcare
#   /index/introducing-chatgpt-health/          → Jan 2026: ChatGPT Health (consumer)
#                                                  with b.well, Apple Health, MyFitnessPal
#   /index/making-chatgpt-better-for-clinicians/ → Apr 2026: ChatGPT for Clinicians
#                                                  (free for verified physicians/NPs/PAs)
#   /index/healthbench/                         → HealthBench benchmark; surfaces all
#                                                  healthcare eval capabilities/use cases
#   /academy/healthcare/                        → OpenAI Academy healthcare hub;
#                                                  prompt templates & clinical workflows
#   /index/chatgpt-enterprise                   → enterprise features (HIPAA BAA,
#                                                  encryption, audit logs, CMKs)
#   /api                                        → OpenAI API for healthcare integrations
#   /stories                                    → customer stories from health systems
# We deliberately do NOT seed /research, /careers, /legal, /safety, /sora etc.
# ──────────────────────────────────────────────
SEED_URLS = [
    # Core healthcare product announcement pages
    "https://openai.com/solutions/industries/healthcare/",
    "https://openai.com/index/openai-for-healthcare/",
    "https://openai.com/index/introducing-chatgpt-health/",
    "https://openai.com/index/making-chatgpt-better-for-clinicians/",
    # Evaluation & benchmarks (surfaces capabilities and use cases)
    "https://openai.com/index/healthbench/",
    # Resource hub with clinical workflow prompt templates
    "https://openai.com/academy/healthcare/",
    # Enterprise / API
    "https://openai.com/chatgpt/enterprise",  # /index/ version 404s
    "https://openai.com/api",
    # Customer stories from health systems
    "https://openai.com/stories",
]

DOMAIN_ALLOW = ["openai.com", "chatgpt.com", "platform.openai.com"]
DOMAIN_NOT_ALLOWED = [
    "careers.openai.com",
    "safety.openai.com",
    "status.openai.com",
    "help.openai.com",
    "trust.openai.com",
    "prompt=",              # chatgpt.com/?prompt=... direct chat links
]

# Pages definitely not about healthcare offerings
OUT_OF_SCOPE_PATTERNS = [
    "/research", "/science", "/index/gpt-4",
    "/index/dall-e", "/index/sora", "/index/whisper",
    "/index/codex", "/index/clip",
    "/safety", "/careers", "/legal", "/privacy",
    "/terms", "/brand", "/press",
    "/customer-stories/gaming", "/customer-stories/education",
    "/customer-stories/finance", "/customer-stories/legal",
    "/customer-stories/retail",
    "/solutions/education", "/solutions/government",
    "/solutions/nonprofits", "/solutions/retail",
    "/product/dall-e", "/product/sora",
    "/events", "/transparency",
]

SKIP_PATH_PATTERNS = [
    "/login", "/signup", "/sign-up", "/register",
    "/account", "/settings", "/profile",
    "/cart", "/checkout", "/404",
    "/rss", "/feed", "/sitemap",
    "/cookie", "/terms",
    "/download",
]

# Keywords that indicate pages relevant to healthcare offerings
KEYWORDS = [
    "healthcare", "health", "clinical", "medical", "patient",
    "hospital", "hipaa", "ehr", "fhir", "hl7",
    "enterprise", "stories", "news", "blog",
    "api", "integration", "workflow", "agent",
    "for-business", "business", "chatgpt",
    "solution", "customer", "case-study",
    "prior-auth", "scribing", "documentation",
    "diagnostic", "radiology", "pharmacy",
]

BLOCKED_PATTERNS     = [
    "Rate exceeded", "Too many requests", "Access denied",
    # Cloudflare / bot-protection challenges
    "Just a moment", "Verification successful",
    "Checking your browser", "Enable JavaScript and cookies",
    "cf-browser-verification", "challenge-platform",
    "Please wait", "_cf_chl",
]
UNREACHABLE_PATTERNS = [
    "this page could not be found", "this site can't be reached",
    "err_name_not_resolved", "err_connection_timed_out",
    "err_connection_refused", "dns_probe_finished_nxdomain",
    "404 not found", "page not found",
]

DISALLOWED_TERMS = [
    "dall-e", "sora", "codex", "whisper", "gpt-3",
    "gaming", "retail", "education platform", "legal tech",
]
TOO_GENERIC_TERMS = [
    "healthcare", "clinical", "patient", "workflow", "connector",
    "solution", "assistant", "tool", "capability", "integration", "platform",
    "enterprise", "api",
]

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
    # Trust HTTP status codes — don't pattern-match on 200 responses.
    # OpenAI's Next.js bundle contains strings like "page not found" in
    # its JS, causing false positives on valid pages.
    if status_code in (404, 410):
        return True
    if status_code and status_code >= 400:
        # For non-200 errors, also check content patterns as a fallback
        cl = content.lower()
        return any(p in cl for p in UNREACHABLE_PATTERNS)
    return False


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

    text = soup.get_text(separator=" ")
    return " ".join(text.split())


# ──────────────────────────────────────────────
# PROMPTS  (OpenAI/ChatGPT for Healthcare)
# ──────────────────────────────────────────────
EXTRACTION_SYSTEM_PROMPT = '''
You are an expert data-extraction assistant. Your ONLY job is to extract
information about "ChatGPT for Healthcare" — the healthcare-specific
product offering by OpenAI.

─────────────────────────────────────────
LANGUAGE RULE (MANDATORY)
─────────────────────────────────────────
ALL output fields MUST be written in English only.
Do NOT output any text in Japanese, Chinese, Korean, Arabic,
Cyrillic, or any other non-Latin script.

─────────────────────────────────────────
SCOPE RULES
─────────────────────────────────────────
- ONLY extract sub-offerings that belong to "ChatGPT for Healthcare".
- Relevant sub-offerings include: GPT-powered clinical workflows,
  healthcare-specific ChatGPT Enterprise features, official healthcare
  integrations, AI-assisted documentation tools, diagnostic support
  tools, prior authorization automation, ambient scribing features,
  FHIR/HL7 integration capabilities, and any named OpenAI product
  or feature that OpenAI explicitly targets at the healthcare industry.
- Extract based ONLY on evidence in the provided page text.
  Do NOT invent or assume sub-offerings.
- Do NOT extract general ChatGPT features that are not healthcare-specific
  (e.g. generic text generation, coding tools, DALL-E, Sora).
- Do NOT extract offerings for education, gaming, retail, or other
  non-healthcare verticals.
- Do NOT extract use cases described by customers in their own words
  unless they are explicitly named as an OpenAI product feature
  on an official OpenAI page.
- DO extract sub-offerings demonstrated in interactive UI examples,
  workflow demos, or product walkthroughs shown by OpenAI on the page.
- If the page has NO ChatGPT for Healthcare content, return:
  {"offerings": []}

─────────────────────────────────────────
SUB-OFFERING NAMING RULES  (priority order)
─────────────────────────────────────────
1. Section heading or H2/H3 title text
2. Bold or emphasized text
3. Link anchor text
4. Body paragraph text
5. Image alt text or filenames (lowest priority)

Always use the most complete and specific name OpenAI uses.
Keep the official type indicator if present (e.g. Integration,
Connector, Feature, Tool, Workflow).

─────────────────────────────────────────
OUTPUT FORMAT
─────────────────────────────────────────
Return ONLY valid JSON. Root key "offerings", value is an array.
Each element:
  "vendor"          : ALWAYS "OpenAI"
  "category"        : ALWAYS "Solutions"
  "sub_category"    : ALWAYS "Industries"
  "module_offering" : ALWAYS "ChatGPT for Healthcare"
  "sub_offering"    : string — distinct feature/tool/workflow name. ENGLISH ONLY.
  "capabilities"    : array of strings — every specific ability, feature, or
                      function this sub-offering provides. NEVER return null.
                      If nothing described: ["No specific capabilities listed on this page"]
  "tasks_examples"  : array of strings — concrete tasks explicitly demonstrated or
                      described by OpenAI for this sub-offering. If none, return [].
  "source_evidence" : string — the URL of the page AND the exact location on that page
                      where this sub-offering was found. Always combine both into one string.
                      Format: "URL: <page_url> | Under section: <section_name> > <subsection_or_label>"
                      Use the most specific location indicator available, in priority order:
                      (1) Section heading or H2/H3 title (e.g. "Under section: Clinical Documentation")
                      (2) Bold/emphasized label or UI element text (e.g. "> bold label: Ambient Scribe")
                      (3) Link anchor text (e.g. "> link: Ambient Scribe Tool")
                      (4) Paragraph opening (first ~15 words) (e.g. "> paragraph: OpenAI provides...")
                      Examples:
                        "URL: https://openai.com/healthcare | Under section: Clinical Documentation > bold label: Ambient Scribe"
                        "URL: https://openai.com/solutions | Under section: Healthcare > H3: Prior Auth Automation"
                      NEVER return null — use "URL: <url> | Page body text" as a last resort.

RULES:
1. vendor, category, sub_category, module_offering are FIXED values.
2. For array fields ALWAYS return an array, never null.
3. capabilities MUST have at least one entry.
4. capabilities must be specific to that exact sub_offering only.
5. Return one object per sub-offering. Do NOT duplicate.
6. Do NOT invent information not present in the source text.
7. ALL text MUST be in English.
8. source_evidence MUST always be a non-empty string.
'''

REFINEMENT_SYSTEM_PROMPT = '''
You are a strict normalization and quality-improvement layer for extracted
"ChatGPT for Healthcare" offerings from OpenAI.

You will receive:
  1) URL
  2) PAGE TEXT
  3) A JSON array of preliminary extracted offerings

PART 1 — GAP CHECK
Re-read the PAGE TEXT. If the preliminary extraction is missing a
sub-offering that clearly belongs to ChatGPT for Healthcare, add it.
Apply the same scope rules as extraction.

PART 2 — NORMALIZE AND CLEAN
- Keep only entries that belong to "ChatGPT for Healthcare".
- Normalize sub_offering names using the priority order in the extraction prompt.
- Merge entries that are the same underlying offering.
- capabilities: specific to that sub_offering only; remove generic page-level claims.
- tasks_examples: only tasks explicitly demonstrated by OpenAI. If none → [].
- Do NOT invent names or capabilities.

LANGUAGE RULE: ALL output text MUST be in English only.

Return ONLY valid JSON:
{
  "offerings": [
    {
      "vendor": "OpenAI",
      "category": "Solutions",
      "sub_category": "Industries",
      "module_offering": "ChatGPT for Healthcare",
      "sub_offering": "...",
      "capabilities": ["..."],
      "tasks_examples": ["..."],
      "source_evidence": "URL: <page_url> | Under section: <section_name> > <subsection_or_label>"
    }
  ]
}
'''

VALIDATION_SYSTEM_PROMPT = '''
You are a healthcare AI product analyst specializing in OpenAI products.
Your job is to audit a list of alleged "ChatGPT for Healthcare" sub-offerings
and decide which ones are LEGITIMATE, officially named sub-offerings that
OpenAI actually ships as part of "ChatGPT for Healthcare".

You will receive a JSON array of objects, each with:
  - "sub_offering"   : the name that was extracted
  - "capabilities"   : what the extractor said it can do
  - "source_urls"    : the page(s) it was found on
  - "row_ids"        : database IDs (pass them back unchanged)

For EACH entry, decide:
  - "legitimate"  : true or false
  - "reasoning"   : 2-4 sentences explaining your decision.

VALIDATION CHECKS (apply ALL):
1. OFFICIAL NAME CHECK: Is this an officially named feature, integration, or
   workflow that OpenAI explicitly offers under a healthcare context?
   Known legitimate categories include: ChatGPT Enterprise for Health Systems,
   ambient scribing integrations, clinical documentation assistants,
   FHIR/HL7 integrations, diagnostic support tools, prior authorization
   automation, and official healthcare customer deployments with named
   OpenAI product features.
2. DUPLICATE CHECK: Keep ONLY the most complete/specific name if two entries
   refer to the same underlying offering.
3. SOURCE CHECK: Is the source URL an official OpenAI or ChatGPT page?
4. SPECIFICITY CHECK: Is the name too vague or generic?
5. LANGUAGE CHECK: Non-English/non-Latin sub_offering → NOT legitimate.

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


def extract_with_llm(url: str, text: str, raw_data_id: int) -> None:
    if not llm.has_llm_client():
        return
    with sub_offerings_lock:
        if len(discovered_sub_offerings) >= TARGET_SUB_OFFERINGS:
            print(f"[LLM] Target reached — skipping {url}")
            return

    page_text = text[:40000]
    try:
        completion = llm.create_chat_completion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user",   "content": f"URL: {url}\n\nPAGE TEXT:\n{page_text}"},
            ],
            temperature=0.0,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        extracted  = llm.parse_json_content(completion)
        offerings  = extracted.get("offerings", [])

        if not offerings:
            print(f"[LLM] No healthcare offerings found on {url}")
            return

        offerings = _refine_offerings(url, page_text, offerings)
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

    except json.JSONDecodeError as e:
        print(f"[LLM] JSON parse error for {url}: {e}")
    except Exception as e:
        print(f"[LLM] Error processing {url}: {e}")


# ──────────────────────────────────────────────
# POST-CRAWL VALIDATION
# ──────────────────────────────────────────────
def _post_crawl_validate() -> None:
    import psycopg2.extras
    if not llm.has_llm_client():
        return

    print("\n" + "=" * 60)
    print("[VALIDATE] Starting post-crawl validation…")
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

    # Language purge
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
    print("ChatGPT / OpenAI for Healthcare Crawler")
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
            # Use headed mode on Windows/Mac to bypass Cloudflare bot detection.
            # headless=False makes the browser appear as a real user session;
            # Cloudflare's JS challenge checks navigator.webdriver and other
            # headless signals that a headed browser doesn't expose.
            import sys
            _headless = False  # Always headed — Cloudflare blocks headless browsers

            browser = p.chromium.launch(
                headless=_headless,
                slow_mo=150,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                java_script_enabled=True,
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                },
            )
            # Remove the webdriver flag that Cloudflare checks
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            Stealth().apply_stealth_sync(context)  # hide automation fingerprints (v2 API)
            page = context.new_page()

            # Warm up session — visiting homepage first makes subsequent
            # pages look like natural navigation, not a direct bot hit
            print("[WARMUP] Visiting homepage to establish session...")
            try:
                page.goto("https://openai.com", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(random.randint(6000, 9000))
            except Exception as e:
                print(f"[WARMUP] Failed: {e}")

            with open("openai_healthcare_data.jsonl", "a", encoding="utf-8") as f:
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
                                response = page.goto(url, timeout=60000, wait_until="domcontentloaded")
                                try:
                                    page.wait_for_selector(
                                        "main p, article p, [class*='content'] p, [class*='rich-text'] p",
                                        timeout=8000
                                    )
                                except Exception:
                                    pass
                                page.wait_for_timeout(random.randint(4000, 6000))
                                break
                            except Exception:
                                if attempt == 1:
                                    raise

                        for _ in range(random.randint(2, 5)):
                            page.mouse.wheel(0, random.randint(500, 1500))
                            page.wait_for_timeout(random.randint(800, 1500))

                        try:
                            content = page.content()
                        except Exception:
                            page.wait_for_timeout(10000)
                            content = page.content()

                        # If Cloudflare challenge, try plain HTTP fallback first
                        if is_blocked_page(content):
                            print(f"[BLOCKED] Cloudflare challenge — trying plain HTTP fallback…")
                            fallback_html = None if "openai.com" in url else _plain_fetch(url)
                            if fallback_html and not is_blocked_page(fallback_html):
                                print(f"[FALLBACK] Plain fetch succeeded for {url}")
                                content = fallback_html
                                status = 200
                            else:
                                # Plain fetch also blocked — sleep and retry with Playwright
                                sleep_t = random.randint(30, 60)
                                print(f"[BLOCKED] Plain fetch also blocked — sleeping {sleep_t}s then retrying Playwright…")
                                time.sleep(sleep_t)
                                try:
                                    response = page.goto(url, timeout=60000, wait_until="domcontentloaded")
                                    try:
                                        page.wait_for_selector(
                                            "main p, article p, [class*='content'] p, [class*='rich-text'] p",
                                            timeout=8000
                                        )
                                    except Exception:
                                        pass
                                    page.wait_for_timeout(random.randint(6000, 10000))
                                    content = page.content()
                                except Exception as _e:
                                    print(f"[BLOCKED] Playwright retry failed for {url}: {_e}")

                        status = response.status if response else None

                        # Debug: always show status + content preview
                        _preview = content[:300].replace("\n", " ").strip() if content else "(empty)"
                        print(f"[DEBUG] status={status} content_len={len(content) if content else 0}")
                        print(f"[DEBUG] preview: {_preview[:200]}")

                        # Skip only genuine 404/410 or still-blocked pages
                        if is_unreachable(status, content) or is_blocked_page(content):
                            if is_blocked_page(content):
                                print(f"[BLOCKED] Still blocked after all retries, skipping: {url}")
                            else:
                                print(f"[SKIP] Not found: {url} (status={status})")
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
