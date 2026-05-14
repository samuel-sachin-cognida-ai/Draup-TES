"""Vendor configuration: VendorConfig dataclass and the VENDOR_CONFIGS registry."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

# ── Tuning constants ──────────────────────────────────────────────────────────
LLM_MODEL            = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_WORKERS          = int(os.getenv("LLM_WORKERS", "3"))
MAX_PAGES_PER_VENDOR = int(os.getenv("MAX_PAGES", "20"))
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
    product_brand: str                  # e.g. "Anthropic Claude", "OpenAI ChatGPT"
    seed_urls: list[str]
    allowed_domains: list[str]
    allowed_path_prefixes: list[str]
    blocked_domains: list[str]          = field(default_factory=list)
    blocked_path_patterns: list[str]    = field(default_factory=list)
    disallowed_terms: list[str]         = field(default_factory=list)
    too_generic_terms: list[str]        = field(default_factory=list)
    browser_mode: str                   = "stealth"
    extra_wait_ms: int                  = 0
    link_keywords: list[str] | None     = None
    target_sub_offerings: int           = TARGET_SUB_OFFERINGS
    max_pages: int                      = 0   # 0 = use global MAX_PAGES_PER_VENDOR
    sector: str                         = "enterprise"


# Generic terms too vague to be useful sub-offering names (across all sectors)
_GENERIC_TERMS = [
    "solution", "assistant", "tool", "capability", "integration", "platform",
    "enterprise", "api", "workflow", "connector", "dashboard", "module",
]

# Shared blocked domains per vendor family
_ANTHROPIC_BLOCKED_DOMAINS = [
    "support.claude.com", "platform.claude.com",
    "console.anthropic.com", "status.anthropic.com", "trust.anthropic.com",
]
_OPENAI_BLOCKED_DOMAINS = [
    "careers.openai.com", "safety.openai.com",
    "status.openai.com", "help.openai.com", "trust.openai.com",
]


VENDOR_CONFIGS: dict[str, VendorConfig] = {

    # ══════════════════════════════════════════════════════════════════════════
    # ANTHROPIC  (frontier_llm)
    # ══════════════════════════════════════════════════════════════════════════

    "anthropic": VendorConfig(
        name="Anthropic",
        slug="anthropic",
        group="frontier_llm",
        product_brand="Anthropic Claude",
        sector="enterprise",
        seed_urls=[
            # Industry solution hubs (one page links to all verticals)
            "https://www.anthropic.com/solutions",
            "https://claude.com/solutions",
            # Specific sector pages
            "https://www.anthropic.com/solutions/healthcare",
            "https://www.anthropic.com/solutions/legal",
            "https://www.anthropic.com/solutions/financial-services",
            "https://www.anthropic.com/solutions/education",
            "https://www.anthropic.com/solutions/government",
            # Life-sciences / research coverage
            "https://www.anthropic.com/news/healthcare-life-sciences",
            # Cross-sector evidence
            "https://www.anthropic.com/customers",
            "https://claude.com/customers",
            "https://claude.com/connectors",
        ],
        allowed_domains=["anthropic.com", "www.anthropic.com", "claude.com", "claude.ai"],
        blocked_domains=_ANTHROPIC_BLOCKED_DOMAINS,
        allowed_path_prefixes=[
            "/solutions", "/news", "/customers", "/connectors",
        ],
        blocked_path_patterns=[
            r"/solutions/coding", r"/solutions/agents",
            r"/product/claude-code", r"/product/cowork",
            r"/careers", r"/legal$", r"/pricing",
            r"/engineering", r"/transparency", r"/constitution", r"/research",
            r"/news/claude-3", r"/news/claude-opus", r"/news/claude-sonnet",
        ],
        disallowed_terms=[
            "claude code", "cowork", "coding assistant",
            "haiku", "sonnet", "opus",
        ],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            # healthcare
            "health", "clinical", "medical", "patient", "hospital", "hipaa",
            "ehr", "fhir", "care", "pharmacy", "payer", "provider",
            "prior-auth", "claims", "appeals", "triage",
            # life sciences
            "life-science", "lifescience", "pharma", "biotech", "genomic",
            "drug", "clinical-trial",
            # legal
            "legal", "law", "contract", "compliance", "attorney", "counsel",
            "litigation", "discovery", "regulatory", "firm", "in-house",
            # financial
            "finance", "financial", "banking", "insurance", "investment",
            "fintech", "credit", "risk", "fraud", "wealth", "capital",
            # government / education
            "government", "federal", "public-sector",
            "education", "university", "school", "academic",
            # generic enterprise
            "connector", "customers", "solutions", "industry",
        ],
        target_sub_offerings=60,
        max_pages=50,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # OPENAI  (frontier_llm)
    # ══════════════════════════════════════════════════════════════════════════

    "openai": VendorConfig(
        name="OpenAI",
        slug="openai",
        group="frontier_llm",
        product_brand="OpenAI ChatGPT",
        sector="enterprise",
        seed_urls=[
            # Industry hubs
            "https://openai.com/solutions",
            "https://openai.com/enterprise",
            # Sector-specific pages
            "https://openai.com/solutions/industries/healthcare/",
            "https://openai.com/index/openai-for-healthcare/",
            "https://openai.com/index/introducing-chatgpt-health/",
            "https://openai.com/academy/healthcare/",
            "https://openai.com/solutions/industries/legal/",
            "https://openai.com/index/openai-for-legal/",
            "https://openai.com/solutions/industries/financial-services/",
            "https://openai.com/index/openai-for-financial-services/",
            "https://openai.com/solutions/industries/education/",
            "https://openai.com/solutions/industries/government/",
            # Cross-sector evidence
            "https://openai.com/customers",
        ],
        allowed_domains=["openai.com", "chatgpt.com", "platform.openai.com"],
        blocked_domains=_OPENAI_BLOCKED_DOMAINS,
        allowed_path_prefixes=[
            "/solutions", "/index", "/academy", "/customers", "/enterprise",
        ],
        blocked_path_patterns=[
            r"/research", r"/science", r"/safety", r"/careers", r"/legal$", r"/privacy",
            r"/index/gpt-4", r"/index/dall-e", r"/index/sora",
            r"/index/whisper", r"/index/codex",
        ],
        disallowed_terms=[
            "dall-e", "sora", "codex", "whisper", "gpt-3",
            "gaming", "agent builder",
        ],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="headed",
        extra_wait_ms=10000,
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital", "hipaa", "care",
            "life-science", "pharma", "biotech",
            "legal", "law", "contract", "compliance", "attorney", "litigation",
            "finance", "financial", "banking", "insurance", "investment", "fintech",
            "government", "federal", "public-sector",
            "education", "university", "school", "academic",
            "retail", "ecommerce",
            "customers", "solutions", "industries", "enterprise",
        ],
        target_sub_offerings=60,
        max_pages=45,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # AWS BEDROCK  (cloud_platform)
    # ══════════════════════════════════════════════════════════════════════════

    "aws_bedrock": VendorConfig(
        name="AWS",
        slug="aws_bedrock",
        group="cloud_platform",
        product_brand="AWS Bedrock",
        sector="enterprise",
        seed_urls=[
            # Top-level industries hub (links to every vertical)
            "https://aws.amazon.com/industries/",
            # AWS Bedrock hub (all industry AI use cases)
            "https://aws.amazon.com/bedrock/",
            # Healthcare & Life Sciences
            "https://aws.amazon.com/health/",
            "https://aws.amazon.com/health/generative-ai/",
            "https://aws.amazon.com/healthscribe/",
            "https://aws.amazon.com/healthlake/",
            "https://aws.amazon.com/comprehend/medical/",
            "https://aws.amazon.com/transcribe/medical/",
            "https://aws.amazon.com/health/life-sciences/",
            # Financial Services
            "https://aws.amazon.com/financial-services/",
            "https://aws.amazon.com/financial-services/generative-ai/",
            "https://aws.amazon.com/financial-services/banking/",
            "https://aws.amazon.com/financial-services/insurance/",
            "https://aws.amazon.com/financial-services/capital-markets/",
            "https://aws.amazon.com/fraud-detector/",
            # Manufacturing & Supply Chain
            "https://aws.amazon.com/manufacturing/",
            "https://aws.amazon.com/supply-chain/",
            # Retail
            "https://aws.amazon.com/retail/",
            # Media & Entertainment
            "https://aws.amazon.com/media/",
            # Government
            "https://aws.amazon.com/government-education/",
            # Energy
            "https://aws.amazon.com/energy/",
            # Cross-sector blog
            "https://aws.amazon.com/blogs/industries/",
        ],
        allowed_domains=["aws.amazon.com"],
        allowed_path_prefixes=[
            "/industries", "/health", "/healthlake", "/healthscribe",
            "/comprehend/medical", "/transcribe/medical", "/transcribe",
            "/solutions/health", "/blogs/industries",
            "/financial-services", "/solutions/financial-services",
            "/manufacturing", "/supply-chain",
            "/retail",
            "/media",
            "/government-education",
            "/energy",
            "/about-aws/whats-new",
            "/bedrock",
            "/fraud-detector",
        ],
        blocked_path_patterns=[
            r"/pricing", r"/faqs$", r"/free",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital", "hipaa",
            "ehr", "fhir", "care", "pharmacy", "scribe", "imaging",
            "life-science", "lifescience", "pharma", "genomic", "drug",
            "finance", "financial", "banking", "insurance", "investment",
            "capital", "trading", "compliance", "risk", "fraud", "payments",
            "manufactur", "production", "supply-chain", "factory", "industrial",
            "quality", "mes", "inventory", "procurement",
            "retail", "ecommerce",
            "media", "entertainment", "streaming",
            "government", "federal", "public-sector",
            "energy", "utilities", "renewable",
            "bedrock", "comprehend", "industry", "industries",
        ],
        target_sub_offerings=70,
        max_pages=55,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # GOOGLE GEMINI  (cloud_platform)
    # ══════════════════════════════════════════════════════════════════════════

    "google_gemini": VendorConfig(
        name="Google",
        slug="google_gemini",
        group="cloud_platform",
        product_brand="Google Gemini",
        sector="enterprise",
        seed_urls=[
            # ── New domains first — guaranteed to be reached within max_pages ──
            # Workspace: Legal/Finance/Healthcare sub-offerings + NotebookLM
            "https://workspace.google.com/solutions/legal/",
            "https://workspace.google.com/solutions/finance/",
            "https://workspace.google.com/solutions/healthcare/",
            "https://workspace.google.com/products/notebooklm/",
            "https://notebooklm.google.com/",
            # DeepMind: AlphaFold
            "https://deepmind.google/technologies/alphafold/",
            # blog.google health: Med-Gemini, TxGemma, AMIE
            "https://blog.google/technology/health/",
            # ai.google: MedGemma
            "https://ai.google/discover/medgemma",
            # ── Original cloud.google.com seeds (unchanged) ───────────────────
            # Top-level industries hub
            "https://cloud.google.com/industries",
            # Healthcare & Life Sciences
            "https://cloud.google.com/solutions/healthcare-life-sciences",
            "https://cloud.google.com/solutions/healthcare-delivery",
            "https://cloud.google.com/use-cases/ai-in-healthcare",
            "https://cloud.google.com/healthcare-api",
            # Financial Services
            "https://cloud.google.com/solutions/financial-services",
            "https://cloud.google.com/use-cases/ai-in-financial-services",
            # Legal
            "https://cloud.google.com/solutions/legal",
            "https://cloud.google.com/use-cases/ai-in-legal",
            # Retail
            "https://cloud.google.com/solutions/retail",
            # Manufacturing
            "https://cloud.google.com/solutions/manufacturing",
            # Media & Entertainment
            "https://cloud.google.com/solutions/media-entertainment",
            # Government
            "https://cloud.google.com/solutions/government",
            # Education
            "https://cloud.google.com/solutions/education",
            # Supply Chain
            "https://cloud.google.com/solutions/supply-chain",
            # Cross-sector
            "https://cloud.google.com/blog/topics/healthcare-life-sciences",
            "https://cloud.google.com/blog/topics/financial-services",
            "https://cloud.google.com/customers",
        ],
        allowed_domains=[
            "cloud.google.com", "health.google", "blog.google", "ai.google",
            "workspace.google.com",
            "deepmind.google",
            "notebooklm.google.com",
        ],
        allowed_path_prefixes=[
            # Original paths (unchanged)
            "/industries", "/solutions", "/use-cases",
            "/healthcare", "/healthcare-api", "/healthcare-data-engine", "/medical-imaging",
            "/blog/topics", "/blog/products/google-cloud",
            "/health", "/technology/health",
            "/customers",
            # Added for new domains
            "/products",       # workspace.google.com/products/notebooklm/
            "/gemini",         # workspace.google.com/gemini/
            "/discover",       # ai.google/discover/medgemma, deepmind.google/discover/
            "/technologies",   # deepmind.google/technologies/alphafold/
            "/enterprise",     # notebooklm.google.com/enterprise/
        ],
        blocked_path_patterns=[
            r"/pricing", r"/billing", r"/terms",
            r"^/vertex-ai$", r"^/products/gemini$",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            # Original keywords (unchanged)
            "health", "clinical", "medical", "patient", "hospital", "hipaa",
            "ehr", "fhir", "care", "medlm", "medgemma", "scribe",
            "radiology", "imaging", "payer", "provider", "claims",
            "life-science", "pharma", "genomic", "drug", "biotech",
            "finance", "financial", "banking", "insurance", "investment",
            "capital", "trading", "compliance", "risk", "fraud", "payments",
            "wealth", "asset",
            "legal", "law", "contract", "attorney", "litigation", "regulatory",
            "manufactur", "production", "supply-chain", "factory",
            "retail", "ecommerce", "merchandis",
            "media", "entertainment", "streaming",
            "government", "federal", "public-sector",
            "education", "university", "school",
            "energy", "utilities",
            "industry", "industries", "customers",
            # Added for Excel coverage
            "txgemma", "alphafold", "deepmind", "amie", "med-gemini",
            "notebooklm", "workspace", "agentspace",
            "aml", "anti-money", "underwriting",
            "ambient", "digital-front-door",
            "document-ai",
        ],
        target_sub_offerings=100,
        max_pages=80,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # MICROSOFT COPILOT  (cloud_platform)
    # ══════════════════════════════════════════════════════════════════════════

    "microsoft_copilot": VendorConfig(
        name="Microsoft",
        slug="microsoft_copilot",
        group="cloud_platform",
        product_brand="Microsoft Copilot",
        sector="enterprise",
        seed_urls=[
            # Top-level industry hub
            "https://www.microsoft.com/en-us/industry",
            "https://www.microsoft.com/en-us/microsoft-cloud/industries",
            # Healthcare
            "https://www.microsoft.com/en-us/industry/health/microsoft-cloud-for-healthcare",
            "https://www.microsoft.com/en-us/microsoft-cloud/healthcare",
            "https://azure.microsoft.com/en-us/products/health-data-services/",
            # Financial Services
            "https://www.microsoft.com/en-us/industry/financial-services/microsoft-cloud-for-financial-services",
            "https://www.microsoft.com/en-us/industry/financial-services",
            "https://azure.microsoft.com/en-us/solutions/financial-services/",
            # Legal
            "https://www.microsoft.com/en-us/industry/legal",
            # Manufacturing
            "https://www.microsoft.com/en-us/industry/manufacturing",
            "https://azure.microsoft.com/en-us/solutions/manufacturing/",
            # Retail
            "https://www.microsoft.com/en-us/industry/retail",
            # Government
            "https://www.microsoft.com/en-us/industry/government",
            # Education
            "https://www.microsoft.com/en-us/education",
            # Energy
            "https://www.microsoft.com/en-us/industry/energy",
            # Azure AI services hub (cross-sector AI products)
            "https://azure.microsoft.com/en-us/solutions/ai/",
        ],
        allowed_domains=["microsoft.com", "www.microsoft.com", "azure.microsoft.com"],
        allowed_path_prefixes=[
            "/en-us/industry", "/en-us/microsoft-cloud",
            "/en-us/ai", "/en-us/products/health-data-services",
            "/en-us/solutions", "/en-us/education",
            "/en-us/industries",
        ],
        blocked_path_patterns=[
            r"/pricing", r"/legal$", r"/support",
            r"/en-us/ai/government$",   # keep /industry/government, block bare /ai/government
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="headed",
        extra_wait_ms=20000,
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital", "hipaa", "ehr", "fhir", "care",
            "life-science", "pharma", "biotech",
            "finance", "financial", "banking", "insurance", "investment", "compliance", "risk", "fraud",
            "legal", "law", "contract", "attorney", "counsel", "litigation",
            "manufactur", "production", "supply-chain", "factory",
            "retail", "ecommerce",
            "government", "federal", "public-sector",
            "education", "university", "school",
            "energy", "utilities",
            "industry", "industries", "cloud", "copilot",
        ],
        target_sub_offerings=80,
        max_pages=60,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # SERVICENOW  (enterprise_ai)
    # ══════════════════════════════════════════════════════════════════════════

    "servicenow_ai": VendorConfig(
        name="ServiceNow",
        slug="servicenow_ai",
        group="enterprise_ai",
        product_brand="ServiceNow AI Platform",
        sector="enterprise",
        seed_urls=[
            # Top-level industries hub
            "https://www.servicenow.com/industries.html",
            # Healthcare
            "https://www.servicenow.com/solutions/healthcare.html",
            "https://www.servicenow.com/industries/healthcare.html",
            "https://www.servicenow.com/products/prior-authorization-automation.html",
            "https://www.servicenow.com/products/healthcare-service-management.html",
            # Financial Services
            "https://www.servicenow.com/solutions/financial-services.html",
            "https://www.servicenow.com/industries/financial-services.html",
            "https://www.servicenow.com/industries/banking.html",
            "https://www.servicenow.com/industries/insurance.html",
            # HR
            "https://www.servicenow.com/products/hr-service-delivery.html",
            "https://www.servicenow.com/solutions/hr.html",
            "https://www.servicenow.com/products/employee-experience.html",
            # Manufacturing
            "https://www.servicenow.com/industries/manufacturing.html",
            # Government
            "https://www.servicenow.com/industries/government.html",
            # Telecommunications
            "https://www.servicenow.com/industries/telecommunications.html",
            # Retail
            "https://www.servicenow.com/industries/retail.html",
            # AI platform
            "https://www.servicenow.com/solutions/ai.html",
            "https://www.servicenow.com/solutions/generative-ai.html",
            "https://www.servicenow.com/products/ai.html",
        ],
        allowed_domains=["servicenow.com", "www.servicenow.com"],
        allowed_path_prefixes=[
            "/solutions", "/industries", "/products",
        ],
        blocked_path_patterns=[
            r"^/blog", r"^/events", r"^/training", r"^/partners", r"^/legal",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="headed",
        extra_wait_ms=15000,
        link_keywords=[
            "health", "clinical", "medical", "patient", "hipaa", "care",
            "prior-auth", "authorization",
            "finance", "financial", "banking", "insurance", "compliance", "risk",
            "hr", "human-resources", "employee", "workforce", "talent",
            "recruiting", "onboarding", "payroll",
            "manufactur", "production", "supply-chain",
            "government", "federal", "public-sector",
            "telecom", "5g", "network",
            "retail", "ecommerce",
            "generative", "now-intelligence", "ai-agent", "workflow",
            "industries", "solutions",
        ],
        target_sub_offerings=70,
        max_pages=55,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # SAP  (enterprise_ai)
    # ══════════════════════════════════════════════════════════════════════════

    "sap_business_ai": VendorConfig(
        name="SAP",
        slug="sap_business_ai",
        group="enterprise_ai",
        product_brand="SAP Business AI",
        sector="enterprise",
        seed_urls=[
            # Top-level industries hub
            "https://www.sap.com/industries.html",
            # Healthcare & Life Sciences
            "https://www.sap.com/industries/life-sciences-healthcare.html",
            "https://www.sap.com/industries/healthcare.html",
            # Financial Services
            "https://www.sap.com/industries/banking.html",
            "https://www.sap.com/industries/insurance.html",
            "https://www.sap.com/industries/financial-services.html",
            "https://www.sap.com/products/financial-management.html",
            # Manufacturing
            "https://www.sap.com/industries/discrete-manufacturing.html",
            "https://www.sap.com/industries/process-manufacturing.html",
            "https://www.sap.com/industries/industrial-machinery.html",
            "https://www.sap.com/products/manufacturing/mes.html",
            # Retail
            "https://www.sap.com/industries/retail.html",
            "https://www.sap.com/industries/consumer-products.html",
            # Government / Public Sector
            "https://www.sap.com/industries/public-sector.html",
            # Energy & Utilities
            "https://www.sap.com/industries/energy-utilities.html",
            # Automotive
            "https://www.sap.com/industries/automotive.html",
            # Supply Chain
            "https://www.sap.com/products/scm/supply-chain-planning.html",
            # AI products
            "https://www.sap.com/products/business-ai.html",
            "https://www.sap.com/solutions/technology-platform/joule.html",
        ],
        allowed_domains=["sap.com", "www.sap.com", "news.sap.com"],
        allowed_path_prefixes=[
            "/industries", "/products", "/solutions",
        ],
        blocked_path_patterns=[
            r"/events", r"/legal", r"/partners", r"/blog", r"/training", r"/support",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            "health", "clinical", "medical", "patient", "pharma", "life-sciences",
            "hipaa", "care", "batch", "cell-gene", "serialization",
            "finance", "financial", "banking", "insurance", "treasury",
            "accounting", "ledger", "compliance", "regulatory", "risk",
            "manufactur", "production", "supply-chain", "factory", "industrial",
            "machinery", "quality", "mes", "inventory", "procurement",
            "retail", "consumer-products", "ecommerce",
            "government", "public-sector",
            "energy", "utilities", "automotive",
            "joule", "business-ai", "erp",
        ],
        target_sub_offerings=80,
        max_pages=60,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # ORACLE  (enterprise_ai)
    # ══════════════════════════════════════════════════════════════════════════

    "oracle_ai": VendorConfig(
        name="Oracle",
        slug="oracle_ai",
        group="enterprise_ai",
        product_brand="Oracle AI",
        sector="enterprise",
        seed_urls=[
            # Top-level industries hub
            "https://www.oracle.com/industries/",
            # Healthcare
            "https://www.oracle.com/health/",
            "https://www.oracle.com/health/whats-new/",
            "https://www.oracle.com/health/ai-center-excellence/",
            "https://www.oracle.com/health/clinical-digital-assistant/",
            # Financial Services
            "https://www.oracle.com/industries/financial-services/",
            "https://www.oracle.com/industries/financial-services/banking/",
            "https://www.oracle.com/industries/financial-services/insurance/",
            "https://www.oracle.com/financial-services/generative-ai/",
            # Manufacturing
            "https://www.oracle.com/industries/manufacturing/",
            "https://www.oracle.com/scm/manufacturing/",
            "https://www.oracle.com/erp/manufacturing/",
            # Retail
            "https://www.oracle.com/industries/retail/",
            # Government
            "https://www.oracle.com/industries/government/",
            # Education
            "https://www.oracle.com/industries/education/",
            # Utilities / Energy
            "https://www.oracle.com/industries/utilities/",
            # AI hub
            "https://www.oracle.com/artificial-intelligence/",
            # Announcements (cross-sector)
            "https://www.oracle.com/news/announcement/",
        ],
        allowed_domains=["oracle.com", "www.oracle.com"],
        allowed_path_prefixes=[
            "/industries", "/health", "/financial-services",
            "/scm", "/erp", "/artificial-intelligence",
            "/news/announcement",
        ],
        blocked_path_patterns=[
            r"/blog", r"/events", r"/legal", r"/support",
        ],
        disallowed_terms=[
            "amwell", "animal health", "gxp compliance",
        ],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            "health", "clinical", "medical", "patient", "hospital", "hipaa",
            "ehr", "fhir", "care", "oracle-health", "whats-new",
            "life-science", "pharma", "genomic",
            "finance", "financial", "banking", "insurance", "investment",
            "flexcube", "compliance", "risk", "fraud", "payments",
            "manufactur", "production", "supply-chain", "factory",
            "quality", "inventory", "procurement", "erp", "scm",
            "retail", "ecommerce",
            "government", "federal", "public-sector",
            "education", "university",
            "utilities", "energy",
            "announcement", "industries", "artificial-intelligence",
        ],
        target_sub_offerings=80,
        max_pages=65,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # HARVEY  (vertical_ai) — Legal-first, also Financial Services & Healthcare
    # ══════════════════════════════════════════════════════════════════════════

    "harvey_ai": VendorConfig(
        name="Harvey",
        slug="harvey_ai",
        group="vertical_ai",
        product_brand="Harvey AI",
        sector="enterprise",
        seed_urls=[
            "https://www.harvey.ai/",
            "https://www.harvey.ai/solutions/law-firms",
            "https://www.harvey.ai/solutions/in-house",
            "https://www.harvey.ai/solutions/government",
            "https://www.harvey.ai/agents",
            "https://www.harvey.ai/products",
            "https://www.harvey.ai/platform",
            "https://www.harvey.ai/customers",
            "https://www.harvey.ai/solutions/financial",
            "https://www.harvey.ai/agents?practice=financial-services",
            "https://www.harvey.ai/agents?practice=healthcare-life-sciences",
            "https://www.harvey.ai/customers/bayer",
        ],
        allowed_domains=["harvey.ai", "www.harvey.ai"],
        allowed_path_prefixes=["/"],
        blocked_path_patterns=[
            r"/blog/harvey-raises", r"/blog/harvey-to-open",
            r"/blog/harvey-releases-study",
            r"/jobs", r"/privacy", r"/company",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            "legal", "law", "law-firm", "in-house", "government",
            "contract", "litigation", "compliance", "attorney",
            "counsel", "corporate", "regulatory", "discovery", "due-diligence",
            "financial", "finance", "banking", "investment", "capital",
            "mergers", "acquisitions", "private-equity", "securities",
            "health", "healthcare", "life-science", "pharma", "clinical",
            "medical", "patient", "bayer",
            "agents", "products", "platform", "customers", "solutions",
        ],
        target_sub_offerings=45,
        max_pages=35,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # GLEAN  (vertical_ai) — Enterprise search across all industries
    # ══════════════════════════════════════════════════════════════════════════

    "glean_ai": VendorConfig(
        name="Glean",
        slug="glean_ai",
        group="vertical_ai",
        product_brand="Glean",
        sector="enterprise",
        seed_urls=[
            # All-industries hub
            "https://www.glean.com/industries",
            # Specific sectors
            "https://www.glean.com/industries/healthcare",
            "https://www.glean.com/industries/financial-services",
            "https://www.glean.com/industries/legal",
            "https://www.glean.com/industries/technology",
            "https://www.glean.com/industries/retail",
            "https://www.glean.com/industries/manufacturing",
            # Product
            "https://www.glean.com/product/assistant",
            "https://www.glean.com/product",
            "https://www.glean.com/solutions",
            "https://www.glean.com/customers",
        ],
        allowed_domains=["glean.com", "www.glean.com"],
        allowed_path_prefixes=["/"],
        blocked_path_patterns=[
            r"/blog", r"/careers", r"/legal", r"/press", r"/privacy",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            "health", "healthcare", "clinical", "medical", "patient",
            "life-science", "pharma",
            "finance", "financial", "banking", "insurance", "investment",
            "legal", "law", "contract", "compliance", "attorney",
            "manufactur", "production", "supply-chain",
            "retail", "ecommerce",
            "government", "federal",
            "education", "university",
            "technology", "tech",
            "industry", "industries", "solution", "customers",
        ],
        target_sub_offerings=50,
        max_pages=40,
    ),
}
