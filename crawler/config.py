"""Vendor configuration: VendorConfig dataclass and the VENDOR_CONFIGS registry."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

# ── Tuning constants ──────────────────────────────────────────────────────────
LLM_MODEL            = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_WORKERS          = int(os.getenv("LLM_WORKERS", "3"))
MAX_PAGES_PER_VENDOR = int(os.getenv("MAX_PAGES", "10"))
REQUEST_DELAY_S      = float(os.getenv("REQUEST_DELAY", "1.5"))
PAGE_TIMEOUT_MS      = 30_000
TARGET_SUB_OFFERINGS = int(os.getenv("TARGET_SUB_OFFERINGS", "25"))

# ── Bypass / proxy config ─────────────────────────────────────────────────────
PROXY_URL        = os.getenv("PROXY_URL", "")
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "")


@dataclass
class VendorConfig:
    name: str
    slug: str
    group: str
    module_offering: str
    seed_urls: list[str]
    allowed_domains: list[str]
    allowed_path_prefixes: list[str]
    blocked_domains: list[str]        = field(default_factory=list)
    blocked_path_patterns: list[str]  = field(default_factory=list)
    disallowed_terms: list[str]       = field(default_factory=list)
    too_generic_terms: list[str]      = field(default_factory=list)
    browser_mode: str                 = "stealth"
    extra_wait_ms: int                = 0
    link_keywords: list[str] | None   = None
    target_sub_offerings: int         = TARGET_SUB_OFFERINGS


_SHARED_GENERIC_TERMS = [
    "healthcare", "clinical", "patient", "workflow", "connector",
    "solution", "assistant", "tool", "capability", "integration", "platform",
    "enterprise", "api",
]

VENDOR_CONFIGS: dict[str, VendorConfig] = {

    # ── Frontier LLMs ─────────────────────────────────────────────────────────

    "anthropic": VendorConfig(
        name="Anthropic",
        slug="anthropic",
        group="frontier_llm",
        module_offering="Claude for Healthcare",
        seed_urls=[
            "https://www.anthropic.com/news/healthcare-life-sciences",
            "https://www.anthropic.com/solutions/healthcare",
            "https://claude.com/solutions/healthcare",
            "https://claude.com/connectors",
            "https://claude.com/customers",
        ],
        allowed_domains=["anthropic.com", "www.anthropic.com", "claude.com", "docs.claude.com"],
        blocked_domains=[
            "support.claude.com", "platform.claude.com",
            "console.anthropic.com", "status.anthropic.com",
            "trust.anthropic.com",
        ],
        allowed_path_prefixes=[
            "/solutions/healthcare",
            "/news/healthcare",
            "/news/claude-for-healthcare",
            "/customers",
            "/connectors",
        ],
        blocked_path_patterns=[
            r"/solutions/life-sciences", r"/solutions/financial",
            r"/solutions/education", r"/solutions/government",
            r"/solutions/coding", r"/solutions/agents",
            r"/solutions/security", r"/solutions/customer-support",
            r"/product/claude-code", r"/product/cowork",
            r"/careers", r"/legal", r"/pricing",
            r"/engineering", r"/transparency", r"/constitution",
            r"/research",
            r"/news/claude-3", r"/news/claude-opus", r"/news/claude-sonnet",
        ],
        disallowed_terms=[
            "life science", "drug discovery", "genomics", "biotech",
            "claude code", "cowork", "coding assistant",
            "single-cell", "rna", "bioinformatics", "genomic",
            "clinical trial protocol",
            "10x genomics", "benchling", "biorender", "chembl", "synapse",
            "scvi", "nextflow", "allotrope", "scrna",
            "regulatory submission", "regulatory compliance",
            "haiku", "sonnet", "opus",
        ],
        too_generic_terms=_SHARED_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital",
            "hipaa", "ehr", "fhir", "care", "pharmacy", "payer", "provider",
            "prior-auth", "prior_auth", "authorization", "connector",
            "insurance", "claims", "appeals", "triage",
        ],
        target_sub_offerings=15,
    ),

    "openai": VendorConfig(
        name="OpenAI",
        slug="openai",
        group="frontier_llm",
        module_offering="ChatGPT for Healthcare",
        seed_urls=[
            "https://openai.com/solutions/industries/healthcare/",
            "https://openai.com/index/openai-for-healthcare/",
            "https://openai.com/index/introducing-chatgpt-health/",
            "https://openai.com/index/making-chatgpt-better-for-clinicians/",
            "https://openai.com/index/healthbench/",
            "https://openai.com/academy/healthcare/",
        ],
        allowed_domains=["openai.com", "chatgpt.com", "platform.openai.com"],
        blocked_domains=[
            "careers.openai.com", "safety.openai.com",
            "status.openai.com", "help.openai.com", "trust.openai.com",
        ],
        allowed_path_prefixes=[
            "/solutions/industries/healthcare",
            "/index/openai-for-healthcare",
            "/index/introducing-chatgpt-health",
            "/index/making-chatgpt-better-for-clinicians",
            "/index/healthbench",
            "/academy/healthcare",
        ],
        blocked_path_patterns=[
            r"/research", r"/science",
            r"/index/gpt-4", r"/index/dall-e", r"/index/sora",
            r"/index/whisper", r"/index/codex",
            r"/safety", r"/careers", r"/legal", r"/privacy",
            r"/solutions/education", r"/solutions/government",
            r"/solutions/nonprofits", r"/solutions/retail",
        ],
        disallowed_terms=[
            "dall-e", "sora", "codex", "whisper", "gpt-3",
            "gaming", "retail", "education platform",
            "agent builder", "agents sdk", "realtime api", "mcpkit",
        ],
        too_generic_terms=_SHARED_GENERIC_TERMS,
        browser_mode="headed",
        extra_wait_ms=10000,
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital",
            "hipaa", "care", "clinician", "healthcare",
        ],
        target_sub_offerings=15,
    ),

    # ── Cloud platforms ───────────────────────────────────────────────────────

    "aws_bedrock": VendorConfig(
        name="AWS",
        slug="aws_bedrock",
        group="cloud_platform",
        module_offering="AWS Bedrock for Healthcare",
        seed_urls=[
            "https://aws.amazon.com/health/",
            "https://aws.amazon.com/health/generative-ai/",
            "https://aws.amazon.com/healthscribe/",
            "https://aws.amazon.com/healthlake/",
            "https://aws.amazon.com/comprehend/medical/",
            "https://aws.amazon.com/transcribe/medical/",
            "https://aws.amazon.com/solutions/health/",
            "https://aws.amazon.com/products/connect/health/",
            "https://aws.amazon.com/health/imaging/",
            "https://aws.amazon.com/health/omics/",
            "https://aws.amazon.com/health/gen-ai/",
            "https://aws.amazon.com/blogs/industries/healthcare/",
        ],
        allowed_domains=["aws.amazon.com"],
        allowed_path_prefixes=[
            "/health", "/healthlake", "/healthscribe",
            "/comprehend/medical", "/transcribe/medical",
            "/solutions/health", "/blogs/industries/healthcare",
            "/connect/health", "/products/connect/health",
            "/health/imaging", "/health/omics", "/health/gen-ai",
            "/about-aws/whats-new",
        ],
        blocked_path_patterns=[
            r"/pricing", r"/faqs$", r"/free",
            r"/bedrock$", r"/bedrock/features$",
        ],
        disallowed_terms=[
            "gaming", "retail", "automotive", "education",
            "financial services", "media", "manufacturing",
        ],
        too_generic_terms=_SHARED_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital",
            "hipaa", "ehr", "fhir", "care", "pharmacy",
            "scribe", "healthscribe", "healthlake", "imaging",
            "omics", "bedrock", "comprehend",
        ],
        target_sub_offerings=20,
    ),

    "google_gemini": VendorConfig(
        name="Google",
        slug="google_gemini",
        group="cloud_platform",
        module_offering="Google Gemini for Healthcare",
        seed_urls=[
            "https://cloud.google.com/solutions/healthcare-life-sciences",
            "https://cloud.google.com/solutions/healthcare-delivery",
            "https://cloud.google.com/use-cases/ai-in-healthcare",
            "https://health.google/ai-models/",
            "https://cloud.google.com/blog/topics/healthcare-life-sciences",
            "https://cloud.google.com/healthcare-api",
            "https://health.google/",
        ],
        allowed_domains=[
            "cloud.google.com",
            "health.google",
            "blog.google",
            "ai.google",
        ],
        allowed_path_prefixes=[
            "/solutions/healthcare",
            "/solutions/healthcare-delivery",
            "/use-cases/ai-in-healthcare",
            "/healthcare", "/healthcare-api",
            "/healthcare-data-engine",
            "/medical-imaging",
            "/blog/topics/healthcare",
            "/blog/products/google-cloud",
            "/transform/",
            "/technology/health",
            "/health", "/ai-models",
            "/",
        ],
        blocked_path_patterns=[
            r"/pricing", r"/billing", r"/legal", r"/terms",
            r"^/vertex-ai$",
            r"^/products/gemini$",
        ],
        disallowed_terms=[
            "retail", "gaming", "automotive", "financial services",
            "drug discovery", "genomics", "bioinformatics",
        ],
        too_generic_terms=_SHARED_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital",
            "hipaa", "ehr", "fhir", "care", "medlm", "healthcare",
            "scribe", "handoff", "radiology", "imaging",
            "medgemma", "himss", "claims", "payer", "provider",
        ],
        target_sub_offerings=20,
    ),

    "microsoft_copilot": VendorConfig(
        name="Microsoft",
        slug="microsoft_copilot",
        group="cloud_platform",
        module_offering="Microsoft Copilot for Healthcare",
        seed_urls=[
            "https://www.microsoft.com/en-us/industry/health/microsoft-cloud-for-healthcare",
            "https://www.microsoft.com/en-us/microsoft-cloud/healthcare",
            "https://www.microsoft.com/en-us/ai/health",
            "https://www.microsoft.com/en-us/ai/health/providers",
            "https://www.microsoft.com/en-us/ai/health/payors",
            "https://azure.microsoft.com/en-us/products/health-data-services/",
        ],
        allowed_domains=["microsoft.com", "www.microsoft.com", "azure.microsoft.com"],
        allowed_path_prefixes=[
            "/en-us/industry/health",
            "/en-us/microsoft-cloud/healthcare",
            "/en-us/ai/health",
            "/en-us/products/health-data-services",
        ],
        blocked_path_patterns=[
            r"/pricing", r"/legal", r"/support",
            r"/microsoft-copilot/for-individuals",
            r"/microsoft-365/copilot",
            r"/en-us/ai/government",
            r"/en-us/ai/life-sciences",
        ],
        disallowed_terms=["gaming", "retail", "automotive", "education"],
        too_generic_terms=_SHARED_GENERIC_TERMS,
        browser_mode="headed",
        extra_wait_ms=20000,  # Microsoft pages are very JS-heavy; 8000 was insufficient
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital",
            "hipaa", "ehr", "fhir", "care",
        ],
        target_sub_offerings=20,
    ),

    # ── Enterprise AI ─────────────────────────────────────────────────────────

    "servicenow": VendorConfig(
        name="ServiceNow",
        slug="servicenow",
        group="enterprise_ai",
        module_offering="ServiceNow for Healthcare",
        seed_urls=[
            "https://www.servicenow.com/solutions/healthcare.html",
            "https://www.servicenow.com/industries/healthcare.html",
            "https://www.servicenow.com/solutions/ai.html",
            "https://www.servicenow.com/products/ai-agents.html",
            "https://www.servicenow.com/solutions/generative-ai.html",
            "https://www.servicenow.com/products/prior-authorization-automation.html",
            "https://www.servicenow.com/products/healthcare-service-management.html",
        ],
        allowed_domains=["servicenow.com", "www.servicenow.com"],
        allowed_path_prefixes=[
            "/solutions/healthcare", "/industries/healthcare",
            "/solutions/ai", "/solutions/generative-ai",
            "/products/ai", "/products/now-intelligence",
            "/products/prior-authorization-automation",
            "/products/healthcare-service-management",
        ],
        blocked_path_patterns=[r"^/blog", r"^/events", r"^/training", r"^/partners", r"^/legal"],
        disallowed_terms=["retail", "gaming", "financial services", "manufacturing"],
        too_generic_terms=_SHARED_GENERIC_TERMS,
        browser_mode="headed",   # Cloudflare blocks headless; must run headed
        extra_wait_ms=15000,
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital",
            "hipaa", "care", "healthcare",
            "prior-auth", "prior_auth", "authorization",
            "ai-agent", "generative", "now-intelligence",
            "intelligent", "workflow", "automation",
        ],
        target_sub_offerings=20,
    ),

    "sap": VendorConfig(
        name="SAP",
        slug="sap",
        group="enterprise_ai",
        module_offering="SAP for Healthcare",
        seed_urls=[
            "https://www.sap.com/industries/life-sciences-healthcare.html",
            "https://www.sap.com/industries/healthcare.html",
            "https://www.sap.com/products/business-ai.html",
            "https://www.sap.com/solutions/technology-platform/joule.html",
        ],
        allowed_domains=["sap.com", "www.sap.com", "news.sap.com"],
        allowed_path_prefixes=[
            "/industries/healthcare",
            "/industries/life-sciences-healthcare",
            "/products/business-ai",
            "/products/scm/intelligent-clinical-supply-management",
            "/products/artificial-intelligence",
            "/solutions/technology-platform/joule",
            "/",
        ],
        blocked_path_patterns=[
            r"/events", r"/legal", r"/partners",
            r"/blog",
            r"/training",
            r"/support",
        ],
        disallowed_terms=[
            "retail", "gaming", "automotive",
            "financial services", "manufacturing",
            "supply chain",
        ],
        too_generic_terms=_SHARED_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            "health", "clinical", "medical", "patient",
            "hipaa", "care", "healthcare",
            "life-sciences", "pharma", "batch",
            "joule", "cell-gene", "serialization",
        ],
        target_sub_offerings=20,
    ),

    "oracle": VendorConfig(
        name="Oracle",
        slug="oracle",
        group="enterprise_ai",
        module_offering="Oracle Health AI",
        seed_urls=[
            "https://www.oracle.com/health/",
            "https://www.oracle.com/health/whats-new/",
            "https://www.oracle.com/health/modernize-health/",
            "https://www.oracle.com/health/clinical-suite/electronic-health-record/",
            "https://www.oracle.com/industries/healthcare/ai/",
            "https://www.oracle.com/health/ai-center-excellence/",
            "https://www.oracle.com/health/clinical-digital-assistant/",
        ],
        allowed_domains=["oracle.com", "www.oracle.com"],
        allowed_path_prefixes=[
            "/health",
            "/industries/healthcare",
            "/news/announcement",
        ],
        blocked_path_patterns=[
            r"/blog", r"/events", r"/legal", r"/support",
            r"/artificial-intelligence$",
            r"/artificial-intelligence/generative-ai$",
        ],
        disallowed_terms=[
            "retail", "gaming", "automotive", "education",
            "financial services", "manufacturing", "supply chain",
            "amwell", "footsnap", "global pathogen",
            "gpas", "animal health", "gxp compliance",
        ],
        too_generic_terms=_SHARED_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital",
            "hipaa", "ehr", "fhir", "care", "oracle-health",
            "ai", "intelligence",
            "whats-new", "modernize", "clinical-suite",
            "announcement", "life-sciences",
        ],
        target_sub_offerings=25,
    ),

    # ── Vertical AI ───────────────────────────────────────────────────────────

    "harvey": VendorConfig(
    name="Harvey",
    slug="harvey",
    group="vertical_ai",
    module_offering="Harvey for Legal",  # Keep as-is — Harvey has no healthcare product, only legal for healthcare orgs
    seed_urls=[
        # Healthcare & Life Sciences practice area — most important
        "https://www.harvey.ai/agents?practice=healthcare-life-sciences",
        "https://www.harvey.ai/solutions/in-house",          # in-house counsel (where healthcare legal teams live)
        "https://www.harvey.ai/blog/harvey-in-practice-in-house-regulatory-and-compliance",

        # Healthcare customer stories
        "https://www.harvey.ai/customers/bayer",             # pharma/life sciences customer

        # Core product pages with healthcare workflows
        "https://www.harvey.ai/agents",                      # lists Healthcare & Life Sciences agents
        "https://www.harvey.ai/products",
        "https://www.harvey.ai/platform",
    ],
    allowed_domains=["harvey.ai", "www.harvey.ai"],
    allowed_path_prefixes=["/"],
    blocked_path_patterns=[
        r"/blog/harvey-raises",       # funding news, irrelevant
        r"/blog/harvey-to-open",      # office news, irrelevant
        r"/blog/harvey-releases-study",
        r"/jobs", r"/privacy", r"/company",
    ],
    disallowed_terms=[
        # Non-healthcare legal sectors
        "banking", "finance", "capital markets", "real estate",
        "tax", "trusts", "estates", "immigration",
        "mergers and acquisitions", "private equity",
        "energy", "environmental", "arbitration",
        "securities", "antitrust",
    ],
    too_generic_terms=_SHARED_GENERIC_TERMS,
    browser_mode="stealth",
    link_keywords=[
        "health", "healthcare", "life-science", "lifescience",
        "pharma", "clinical", "medical", "patient",
        "hipaa", "compliance", "regulatory", "in-house",
        "bayer", "hospital", "payer", "provider",
    ],
    target_sub_offerings=15,  # Harvey has limited healthcare-specific content, keep target realistic
),

    "glean": VendorConfig(
        name="Glean",
        slug="glean",
        group="vertical_ai",
        module_offering="Glean for Healthcare",
        seed_urls=[
            "https://www.glean.com/industries/healthcare",
            "https://www.glean.com/product/assistant",
            "https://www.glean.com/solutions",
            "https://www.glean.com/product",
            "https://www.glean.com/platform",
            "https://www.glean.com/features",
        ],
        allowed_domains=["glean.com", "www.glean.com"],
        allowed_path_prefixes=["/"],
        blocked_path_patterns=[r"/blog", r"/careers", r"/legal", r"/press", r"/privacy"],
        disallowed_terms=[],
        too_generic_terms=_SHARED_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[],
        target_sub_offerings=20,
    ),
}
