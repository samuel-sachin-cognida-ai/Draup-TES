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
    product_brand: str
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
    max_pages: int                      = 0
    sector: str                         = "enterprise"


_GENERIC_TERMS = [
    "solution", "assistant", "tool", "capability", "integration", "platform",
    "enterprise", "api", "workflow", "connector", "dashboard", "module",
]

_ANTHROPIC_BLOCKED_DOMAINS = [
    "support.claude.com", "platform.claude.com",
    "console.anthropic.com", "status.anthropic.com", "trust.anthropic.com",
]
_OPENAI_BLOCKED_DOMAINS = [
    "careers.openai.com", "safety.openai.com",
    "status.openai.com", "help.openai.com", "trust.openai.com",
]

# Industry link keywords added to every vendor so sector pages are always followed
_INDUSTRY_LINK_KEYWORDS = [
    # healthcare / life sciences
    "health", "healthcare", "clinical", "medical", "hospital", "patient",
    "payer", "provider", "hipaa", "ehr", "fhir", "life-science", "pharma",
    "drug", "genomics", "biotech", "radiology", "telehealth",
    # legal
    "legal", "law", "contract", "litigation", "attorney", "counsel",
    "compliance", "regulatory", "discovery",
    # financial services
    "finance", "financial", "banking", "insurance", "fintech", "investment",
    "fraud", "risk", "wealth", "capital", "trading",
    # manufacturing / supply chain
    "manufactur", "supply-chain", "factory", "production", "quality", "mes",
    "inventory", "procurement", "industrial",
    # HR / workforce
    "hr", "human-resource", "employee", "workforce", "talent", "recruiting",
    "payroll", "onboarding", "benefits",
    # government / public sector
    "government", "federal", "public-sector", "defense", "citizen",
    # education
    "education", "university", "school", "academic", "learning", "student",
    # retail / commerce
    "retail", "ecommerce", "merchandis", "commerce", "consumer",
    # energy / utilities
    "energy", "utilities", "renewable", "grid",
    # telecom
    "telecom", "5g", "network", "connectivity", "subscriber",
    # media / entertainment
    "media", "entertainment", "streaming", "publishing", "broadcast",
    # cybersecurity
    "security", "cybersecurity", "threat", "identity", "soc", "vulnerability",
    # customer service
    "customer-service", "contact-center", "helpdesk", "support",
    # general industry signals
    "solution", "industry", "industries", "use-case", "case-study",
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
            # ── Industry solution hubs ────────────────────────────────────────
            "https://www.anthropic.com/solutions",
            "https://claude.com/solutions",
            # ── Specific sector pages ─────────────────────────────────────────
            "https://www.anthropic.com/solutions/healthcare",
            "https://www.anthropic.com/solutions/legal",
            "https://www.anthropic.com/solutions/financial-services",
            "https://www.anthropic.com/solutions/education",
            "https://www.anthropic.com/solutions/government",
            "https://www.anthropic.com/news/healthcare-life-sciences",
            # ── Cross-sector evidence ─────────────────────────────────────────
            "https://www.anthropic.com/customers",
            "https://claude.com/customers",
            "https://claude.com/connectors",
            # ── Product / platform pages ──────────────────────────────────────
            "https://www.anthropic.com/api",
            "https://www.anthropic.com/claude-in-slack",
            "https://www.anthropic.com/claude-for-sheets",
            "https://docs.anthropic.com/en/home",
            "https://www.anthropic.com/claude-code",
            "https://claude.ai/code",
            "https://www.anthropic.com/product/cowork",
            "https://claude.ai/cowork",
            "https://www.anthropic.com/news/claude-for-microsoft-365",
            "https://claude.ai/microsoft",
            "https://www.anthropic.com/news/claude-for-chrome",
            "https://www.anthropic.com/solutions/legal-professionals",
            "https://www.anthropic.com/solutions/financial-analysis",
            "https://www.anthropic.com/solutions/life-sciences",
            "https://www.anthropic.com/solutions/small-business",
            "https://www.anthropic.com/solutions/education-professionals",
            "https://www.anthropic.com/news/claude-platform-on-aws",
            "https://www.anthropic.com/pricing",
            "https://www.anthropic.com/team",
            "https://www.anthropic.com/news/agent-sdk",
            "https://www.anthropic.com/research/advanced-tool-use",
            "https://claude.ai/connectors/lifestyle",
            "https://claude.ai/connectors/productivity",
        ],
        allowed_domains=["anthropic.com", "www.anthropic.com", "claude.com", "claude.ai",
                         "docs.anthropic.com"],
        blocked_domains=_ANTHROPIC_BLOCKED_DOMAINS,
        allowed_path_prefixes=[
            "/api", "/claude-code", "/product", "/news", "/pricing",
            "/team", "/research", "/solutions", "/engineering",
            "/connectors", "/microsoft", "/cowork", "/code",
            "/customers",
            "/en",  # docs.anthropic.com
            "/claude-in-slack", "/claude-for-sheets",
        ],
        blocked_path_patterns=[
            r"/careers", r"/legal$", r"/transparency", r"/constitution",
            r"/news/claude-3", r"/news/claude-opus", r"/news/claude-sonnet",
        ],
        disallowed_terms=[
            "haiku", "sonnet", "opus",
        ],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            # developer / API surface
            "api", "developer", "sdk", "model", "token", "inference", "batch",
            "prompt", "caching", "context-window", "streaming", "tool-use",
            "function-calling", "structured-output", "computer-use",
            "managed-agent", "agent-sdk", "mcp", "skills",
            # coding / software dev
            "code", "coding", "claude-code", "software", "engineer", "developer",
            "ide", "github", "repository", "pull-request", "debugging", "refactor",
            # agentic / desktop automation
            "cowork", "agentic", "automation", "task-management", "file-management",
            "multi-step", "desktop",
            # Microsoft 365 / productivity
            "excel", "powerpoint", "word", "outlook", "microsoft-365", "office",
            "spreadsheet", "slides", "document",
            # browsing / web agent
            "chrome", "browser", "browsing-agent", "web-agent",
            # vertical bundles
            "legal-professional", "attorney-bundle",
            "financial-analysis", "investment-professional",
            "life-sciences-bundle", "small-business", "smb",
            "education-professional",
            # deployment / cloud
            "aws", "bedrock", "vertex", "azure", "foundry",
            "claude-platform", "on-aws", "enterprise-plan", "team-plan",
            # connector ecosystem
            "connector", "quickbooks", "hubspot", "canva", "docusign",
            # pricing / plans
            "pricing", "pro", "max", "team", "enterprise-plan", "subscription",
            # healthcare-specific
            "prior-auth", "claims", "appeals", "triage", "lifescience",
            "clinical-trial",
            # legal-specific
            "litigation", "firm", "in-house",
            # financial-specific
            "credit", "capital",
            # cross-sector
            "customers",
        ] + _INDUSTRY_LINK_KEYWORDS,
        target_sub_offerings=200,
        max_pages=200,
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
            # ── Industry hubs ─────────────────────────────────────────────────
            "https://openai.com/solutions",
            "https://openai.com/enterprise",
            "https://openai.com/customers",
            # ── Sector-specific pages ─────────────────────────────────────────
            "https://openai.com/solutions/industries/healthcare",
            "https://openai.com/solutions/industries/healthcare/",
            "https://openai.com/index/openai-for-healthcare/",
            "https://openai.com/solutions/industries/legal",
            "https://openai.com/solutions/industries/legal/",
            "https://openai.com/index/openai-for-legal/",
            "https://openai.com/solutions/industries/financial-services",
            "https://openai.com/solutions/industries/financial-services/",
            "https://openai.com/index/openai-for-financial-services/",
            "https://openai.com/solutions/industries/education",
            "https://openai.com/solutions/industries/government",
            # ── New product / platform pages ──────────────────────────────────
            "https://openai.com/codex",
            "https://openai.com/index/introducing-codex/",
            "https://openai.com/index/introducing-the-codex-app/",
            "https://openai.com/index/introducing-atlas/",
            "https://openai.com/operator",
            "https://openai.com/index/introducing-deep-research/",
            "https://openai.com/index/introducing-chatgpt-search/",
            "https://openai.com/dall-e-3",
            "https://openai.com/index/gpt-4o-image-generation/",
            "https://openai.com/index/introducing-the-realtime-api/",
            "https://openai.com/index/voice-mode/",
            "https://openai.com/index/introducing-chatgpt-health/",
            "https://openai.com/academy/healthcare/",
            "https://platform.openai.com/docs/overview",
            "https://openai.com/index/new-tools-for-building-agents/",
            "https://openai.com/index/chatgpt-for-excel/",
            "https://openai.com/chatgpt/business",
            "https://openai.com/chatgpt/enterprise",
            "https://openai.com/index/powering-product-discovery-in-chatgpt/",
            "https://openai.com/index/a-new-personal-finance-experience-in-chatgpt/",
            "https://openai.com/chatgpt/edu",
        ],
        allowed_domains=["openai.com", "chatgpt.com", "platform.openai.com"],
        blocked_domains=_OPENAI_BLOCKED_DOMAINS,
        allowed_path_prefixes=[
            "/codex", "/operator", "/index", "/dall-e", "/voice",
            "/chatgpt", "/api", "/platform", "/docs", "/academy",
            "/solutions", "/customers", "/enterprise",
        ],
        blocked_path_patterns=[
            r"/research", r"/science", r"/safety", r"/careers", r"/legal$", r"/privacy",
            r"/index/gpt-4$", r"/index/sora", r"/index/whisper",
        ],
        disallowed_terms=[
            "sora", "gaming", "whisper standalone",
        ],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="headed",
        extra_wait_ms=10000,
        link_keywords=[
            # coding / software
            "codex", "software-engineer", "code", "coding", "ide", "github",
            "pull-request", "bug-fix", "repository", "cli",
            # browser / agentic
            "atlas", "operator", "browser", "computer-use", "web-automation",
            "agentic", "agent", "workspace-agent", "multi-agent",
            # research / knowledge
            "deep-research", "research", "canvas", "search",
            # image / media
            "image", "dall-e", "gpt-image", "image-gen", "image-edit",
            # voice / audio
            "voice", "realtime", "audio", "speech", "tts",
            # health / personal
            "health", "chatgpt-health", "medical-records", "wellness",
            "personal-finance", "finance-experience",
            # productivity / office
            "excel", "sheets", "spreadsheet", "office", "word",
            # shopping / commerce
            "shopping", "checkout", "instant-checkout", "product-discovery",
            "ecommerce", "retail",
            # developer / API
            "api", "responses-api", "assistants-api", "sdk", "developer",
            "tool-use", "function-calling", "structured-output", "batch",
            "fine-tuning", "embeddings", "moderation",
            # plans / deployment
            "business", "enterprise-plan", "edu", "go-plan", "pro-plan",
            "team", "admin", "workspace",
            # cross-sector
            "customers", "enterprise",
        ] + _INDUSTRY_LINK_KEYWORDS,
        target_sub_offerings=200,
        max_pages=200,
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
            # ── Top-level hubs ────────────────────────────────────────────────
            "https://aws.amazon.com/industries/",
            "https://aws.amazon.com/bedrock/",
            # ── Healthcare & Life Sciences ────────────────────────────────────
            "https://aws.amazon.com/health/",
            "https://aws.amazon.com/health/generative-ai/",
            "https://aws.amazon.com/healthscribe/",
            "https://aws.amazon.com/healthlake/",
            "https://aws.amazon.com/comprehend/medical/",
            "https://aws.amazon.com/transcribe/medical/",
            "https://aws.amazon.com/health/life-sciences/",
            # ── Financial Services ────────────────────────────────────────────
            "https://aws.amazon.com/financial-services/",
            "https://aws.amazon.com/financial-services/generative-ai/",
            "https://aws.amazon.com/financial-services/banking/",
            "https://aws.amazon.com/financial-services/insurance/",
            "https://aws.amazon.com/financial-services/capital-markets/",
            "https://aws.amazon.com/fraud-detector/",
            # ── Manufacturing & Supply Chain ──────────────────────────────────
            "https://aws.amazon.com/manufacturing/",
            "https://aws.amazon.com/supply-chain/",
            # ── Retail ────────────────────────────────────────────────────────
            "https://aws.amazon.com/retail/",
            # ── Media & Entertainment ─────────────────────────────────────────
            "https://aws.amazon.com/media/",
            # ── Government ────────────────────────────────────────────────────
            "https://aws.amazon.com/government-education/",
            # ── Energy ────────────────────────────────────────────────────────
            "https://aws.amazon.com/energy/",
            # ── Cross-sector blog ─────────────────────────────────────────────
            "https://aws.amazon.com/blogs/industries/",
            # ── New product / platform pages ──────────────────────────────────
            "https://aws.amazon.com/bedrock/agentcore/",
            "https://aws.amazon.com/bedrock/agents/",
            "https://aws.amazon.com/bedrock/nova/",
            "https://aws.amazon.com/bedrock/nova-act/",
            "https://aws.amazon.com/bedrock/nova-forge/",
            "https://aws.amazon.com/bedrock/knowledge-bases/",
            "https://aws.amazon.com/bedrock/guardrails/",
            "https://aws.amazon.com/bedrock/model-evaluation/",
            "https://aws.amazon.com/bedrock/prompt-management/",
            "https://aws.amazon.com/bedrock/marketplace/",
            "https://aws.amazon.com/s3/vectors/",
            "https://aws.amazon.com/q/developer/",
            "https://kiro.dev/",
            "https://aws.amazon.com/quick/",
            "https://aws.amazon.com/connect/",
            "https://aws.amazon.com/connect/ai/",
            "https://aws.amazon.com/sagemaker/",
            "https://aws.amazon.com/sagemaker/ai/",
            "https://aws.amazon.com/machine-learning/trainium/",
            "https://aws.amazon.com/machine-learning/inferentia/",
            "https://aws.amazon.com/bedrock/claude-platform/",
            "https://aws.amazon.com/bedrock/developer-experience/",
            "https://aws.amazon.com/bedrock/fine-tuning/",
        ],
        allowed_domains=["aws.amazon.com", "kiro.dev"],
        allowed_path_prefixes=[
            "/bedrock", "/q", "/connect", "/sagemaker",
            "/machine-learning", "/s3/vectors", "/quick",
            "/industries", "/health", "/healthlake", "/healthscribe",
            "/comprehend", "/transcribe",
            "/financial-services", "/fraud-detector",
            "/manufacturing", "/supply-chain",
            "/retail", "/government-education", "/energy", "/media",
            "/blogs/industries", "/about-aws/whats-new",
        ],
        blocked_path_patterns=[
            r"/pricing", r"/faqs$", r"/free",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            # agent infrastructure
            "agentcore", "agent", "multi-agent", "a2a", "mcp",
            "managed-agent", "agentic", "action-fabric",
            # Nova models
            "nova", "nova-act", "nova-forge", "nova-lite", "nova-pro",
            # developer / model access
            "bedrock", "model-access", "inference", "api", "sdk",
            "fine-tuning", "knowledge-base", "rag", "vector", "embeddings",
            "guardrail", "prompt-management", "batch",
            "marketplace", "open-weight", "mistral", "llama",
            "claude-platform", "openai-compatible",
            # coding / developer tools
            "q-developer", "amazon-q", "code", "coding",
            "kiro", "ide", "swe-bench", "pull-request",
            "cloudformation", "terraform", "cdk",
            # data / MLOps
            "sagemaker", "mlops", "training", "inference-endpoint",
            "s3-vectors", "rds", "opensearch", "aurora",
            # chips
            "trainium", "inferentia", "chip", "accelerator",
            # customer experience
            "connect", "contact-center", "ivr", "ccaas",
            # AI work assistant
            "quick", "ai-assistant", "work-assistant",
            # healthcare-specific
            "scribe", "imaging", "lifescience", "comprehend",
            # financial-specific
            "capital", "trading", "payments",
            # manufacturing
            "mes",
        ] + _INDUSTRY_LINK_KEYWORDS,
        target_sub_offerings=200,
        max_pages=200,
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
            # ── Workspace: industry solutions + NotebookLM ────────────────────
            "https://workspace.google.com/solutions/legal/",
            "https://workspace.google.com/solutions/finance/",
            "https://workspace.google.com/solutions/healthcare/",
            "https://workspace.google.com/products/notebooklm/",
            "https://notebooklm.google.com/",
            # ── DeepMind: AlphaFold ───────────────────────────────────────────
            "https://deepmind.google/technologies/alphafold/",
            # ── blog.google health ────────────────────────────────────────────
            "https://blog.google/technology/health/",
            # ── ai.google: MedGemma ──────────────────────────────────────────
            "https://ai.google/discover/medgemma",
            # ── Cloud: top-level industries hub ──────────────────────────────
            "https://cloud.google.com/industries",
            # ── Cloud: Healthcare & Life Sciences ─────────────────────────────
            "https://cloud.google.com/solutions/healthcare-life-sciences",
            "https://cloud.google.com/solutions/healthcare-delivery",
            "https://cloud.google.com/use-cases/ai-in-healthcare",
            "https://cloud.google.com/healthcare-api",
            # ── Cloud: Financial Services ─────────────────────────────────────
            "https://cloud.google.com/solutions/financial-services",
            "https://cloud.google.com/use-cases/ai-in-financial-services",
            # ── Cloud: Legal ──────────────────────────────────────────────────
            "https://cloud.google.com/solutions/legal",
            "https://cloud.google.com/use-cases/ai-in-legal",
            # ── Cloud: other industries ───────────────────────────────────────
            "https://cloud.google.com/solutions/retail",
            "https://cloud.google.com/solutions/manufacturing",
            "https://cloud.google.com/solutions/media-entertainment",
            "https://cloud.google.com/solutions/government",
            "https://cloud.google.com/solutions/education",
            "https://cloud.google.com/solutions/supply-chain-logistics",
            "https://cloud.google.com/solutions/supply-chain",
            # ── Cloud: cross-sector blog & customers ──────────────────────────
            "https://cloud.google.com/blog/topics/healthcare-life-sciences",
            "https://cloud.google.com/blog/topics/financial-services",
            "https://cloud.google.com/customers",
            # ── New product / platform pages ──────────────────────────────────
            "https://ai.google.dev/gemini-api/docs",
            "https://aistudio.google.com/",
            "https://ai.google/get-started/",
            "https://cloud.google.com/gemini/docs/codeassist/overview",
            "https://cloud.google.com/products/gemini-code-assist",
            "https://blog.google/technology/developers/gemini-cli/",
            "https://jules.google/",
            "https://blog.google/technology/developers/jules-coding-agent/",
            "https://cloud.google.com/products/agent-builder",
            "https://cloud.google.com/agentspace",
            "https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder/overview",
            "https://deepmind.google/technologies/veo/",
            "https://blog.google/technology/ai/veo-3/",
            "https://deepmind.google/technologies/imagen-3/",
            "https://cloud.google.com/vertex-ai/generative-ai/docs/image/overview",
            "https://flow.google/",
            "https://blog.google/technology/ai/google-flow-ai-filmmaking/",
            "https://gemini.google/live/",
            "https://blog.google/products/gemini/gemini-live/",
            "https://deepmind.google/technologies/project-astra/",
            "https://blog.google/products/search/ai-mode/",
            "https://gemini.google/deep-research/",
            "https://one.google.com/about/google-ai-plans/",
            "https://workspace.google.com/intl/en/features/gemini/",
            "https://workspace.google.com/gemini/",
            "https://workspace.google.com/products/google-ai/",
            "https://blog.google/products/gemini/notebooks-gemini-notebooklm/",
        ],
        allowed_domains=[
            "cloud.google.com", "health.google", "ai.google", "ai.google.dev",
            "aistudio.google.com", "blog.google",
            "workspace.google.com", "deepmind.google",
            "notebooklm.google.com", "gemini.google",
            "one.google.com", "jules.google", "flow.google",
        ],
        allowed_path_prefixes=[
            # cloud.google.com
            "/products", "/gemini", "/agentspace", "/vertex-ai", "/solutions",
            "/industries", "/use-cases",
            "/healthcare", "/healthcare-api", "/healthcare-data-engine", "/medical-imaging",
            "/blog/topics", "/blog/products/google-cloud",
            "/customers",
            # blog.google
            "/technology", "/products",
            "/health",
            # deepmind.google
            "/technologies",
            # workspace
            "/gemini", "/products/gemini", "/products/google-ai", "/intl",
            "/solutions",
            # ai.google / ai.google.dev
            "/gemini-api", "/get-started",
            "/discover",
            # one.google.com
            "/about",
            # gemini.google sub-paths
            "/live", "/deep-research",
            # notebooklm.google.com
            "/enterprise",
        ],
        blocked_path_patterns=[
            r"/pricing", r"/billing", r"/terms",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            # developer / API
            "gemini-api", "ai-studio", "api", "sdk", "developer",
            "token", "context-window", "multimodal", "long-context",
            "fine-tuning", "grounding", "embeddings", "batch",
            "vertex-ai", "model-garden", "agent-builder", "agentspace",
            "function-calling", "tool-use", "live-api",
            # coding
            "code-assist", "gemini-code", "jules", "coding-agent",
            "ide", "github", "pull-request", "cli",
            # agentic
            "astra", "project-astra", "agent", "multi-agent", "mcp",
            "computer-use", "browser-agent",
            # creative / media
            "veo", "veo-3", "video-gen", "video", "filmmaking",
            "flow", "imagen", "imagen-3", "image-gen",
            "music-gen", "lyria",
            # voice / live
            "live", "gemini-live", "voice", "realtime",
            # research / knowledge
            "deep-research", "notebooklm", "notebooks",
            # search
            "ai-mode", "search", "ai-overviews",
            # workspace
            "workspace", "gmail", "docs", "sheets", "slides",
            "meet", "calendar", "google-ai-pro", "google-ai-ultra",
            # consumer plans
            "google-one", "pro-plan", "ultra-plan", "subscription",
            # healthcare / life sciences specifics
            "medlm", "medgemma", "scribe", "radiology", "imaging",
            "claims", "txgemma", "alphafold", "deepmind", "amie",
            "med-gemini", "ambient", "digital-front-door",
            # financial specifics
            "aml", "anti-money", "underwriting", "asset",
            # document AI
            "document-ai",
            # cross-sector
            "customers", "document-ai",
        ] + _INDUSTRY_LINK_KEYWORDS,
        target_sub_offerings=200,
        max_pages=200,
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
            # ── Top-level industry hubs ───────────────────────────────────────
            "https://www.microsoft.com/en-us/industry",
            "https://www.microsoft.com/en-us/microsoft-cloud/industries",
            # ── Healthcare ────────────────────────────────────────────────────
            "https://www.microsoft.com/en-us/industry/health/microsoft-cloud-for-healthcare",
            "https://www.microsoft.com/en-us/microsoft-cloud/healthcare",
            "https://azure.microsoft.com/en-us/products/health-data-services/",
            # ── Financial Services ────────────────────────────────────────────
            "https://www.microsoft.com/en-us/industry/financial-services/microsoft-cloud-for-financial-services",
            "https://www.microsoft.com/en-us/industry/financial-services",
            "https://azure.microsoft.com/en-us/solutions/financial-services/",
            # ── Legal ─────────────────────────────────────────────────────────
            "https://www.microsoft.com/en-us/industry/legal",
            # ── Manufacturing ─────────────────────────────────────────────────
            "https://www.microsoft.com/en-us/industry/manufacturing",
            "https://azure.microsoft.com/en-us/solutions/manufacturing/",
            # ── Retail ────────────────────────────────────────────────────────
            "https://www.microsoft.com/en-us/industry/retail",
            # ── Government ────────────────────────────────────────────────────
            "https://www.microsoft.com/en-us/industry/government",
            # ── Education ─────────────────────────────────────────────────────
            "https://www.microsoft.com/en-us/education",
            # ── Energy ────────────────────────────────────────────────────────
            "https://www.microsoft.com/en-us/industry/energy",
            # ── Azure AI solutions hub ────────────────────────────────────────
            "https://azure.microsoft.com/en-us/solutions/ai/",
            # ── New product / platform pages ──────────────────────────────────
            "https://github.com/features/copilot",
            "https://github.blog/category/ai/",
            "https://www.microsoft.com/en-us/microsoft-copilot/microsoft-copilot-studio",
            "https://copilotstudio.microsoft.com/",
            "https://www.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot",
            "https://www.microsoft.com/en-us/microsoft-365/copilot/copilot-for-work",
            "https://www.microsoft.com/en-us/security/business/ai-machine-learning/microsoft-security-copilot",
            "https://azure.microsoft.com/en-us/products/microsoft-copilot-for-security/",
            "https://azure.microsoft.com/en-us/products/copilot/",
            "https://azure.microsoft.com/en-us/products/ai-foundry/",
            "https://azure.microsoft.com/en-us/products/ai-services/openai-service/",
            "https://azure.microsoft.com/en-us/products/ai-services/ai-search/",
            "https://azure.microsoft.com/en-us/products/cognitive-services/",
            "https://powerplatform.microsoft.com/en-us/",
            "https://www.microsoft.com/en-us/power-platform/products/power-automate",
            "https://www.microsoft.com/en-us/dynamics-365/solutions/ai",
            "https://www.microsoft.com/en-us/dynamics-365/copilot",
            "https://www.microsoft.com/en-us/microsoft-copilot/blog/agent-365/",
            "https://www.microsoft.com/en-us/windows/copilot-plus-pcs",
            "https://www.microsoft.com/en-us/microsoft-copilot",
            "https://www.microsoft.com/en-us/microsoft-teams/copilot-in-teams",
        ],
        allowed_domains=[
            "microsoft.com", "www.microsoft.com", "azure.microsoft.com",
            "github.com", "github.blog", "powerplatform.microsoft.com",
            "copilotstudio.microsoft.com",
        ],
        allowed_path_prefixes=[
            # microsoft.com
            "/en-us/microsoft-copilot", "/en-us/microsoft-365",
            "/en-us/security", "/en-us/dynamics-365",
            "/en-us/power-platform", "/en-us/windows",
            "/en-us/industry", "/en-us/education", "/en-us/microsoft-cloud",
            "/en-us/ai", "/en-us/solutions", "/en-us/industries",
            # azure.microsoft.com
            "/en-us/products", "/en-us/solutions",
            # github.com
            "/features", "/blog",
            # github.blog
            "/category",
            # powerplatform
            "/en-us",
        ],
        blocked_path_patterns=[
            r"/pricing", r"/legal$", r"/support",
            r"/en-us/ai/government$",
            r"/en-us/industry$",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="headed",
        extra_wait_ms=20000,
        link_keywords=[
            # coding / developer
            "github-copilot", "code", "coding", "ide", "pull-request",
            "codex", "developer", "devops", "github-actions",
            # agent builder / low-code
            "copilot-studio", "agent", "multi-agent", "power-automate",
            "power-platform", "low-code", "no-code", "flow",
            # M365 productivity
            "microsoft-365", "word", "excel", "powerpoint", "outlook",
            "teams", "onenote", "sharepoint", "loop",
            "copilot-chat", "copilot-pages",
            # security
            "security-copilot", "defender", "entra", "purview", "intune",
            "sentinel", "siem", "xdr", "identity",
            # cloud / DevOps
            "azure-copilot", "azure", "cloud-ops",
            "ai-foundry", "azure-openai", "openai-service",
            "fine-tuning", "model-catalog", "ai-search",
            "cognitive-services", "vision", "speech", "language",
            # CRM / ERP
            "dynamics-365", "crm", "erp", "sales-copilot",
            "customer-service-copilot", "field-service",
            "supply-chain-copilot", "finance-copilot",
            # governance
            "agent-365", "control-plane", "governance", "admin",
            # consumer / devices
            "copilot-plus-pc", "windows-copilot", "bing",
            # cross-sector
            "cloud", "copilot",
        ] + _INDUSTRY_LINK_KEYWORDS,
        target_sub_offerings=200,
        max_pages=200,
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
            # ── Top-level industries hub ──────────────────────────────────────
            "https://www.servicenow.com/industries.html",
            # ── Healthcare ────────────────────────────────────────────────────
            "https://www.servicenow.com/solutions/healthcare.html",
            "https://www.servicenow.com/industries/healthcare.html",
            "https://www.servicenow.com/products/prior-authorization-automation.html",
            "https://www.servicenow.com/products/healthcare-service-management.html",
            # ── Financial Services ────────────────────────────────────────────
            "https://www.servicenow.com/solutions/financial-services.html",
            "https://www.servicenow.com/industries/financial-services.html",
            "https://www.servicenow.com/industries/banking.html",
            "https://www.servicenow.com/industries/insurance.html",
            # ── HR ────────────────────────────────────────────────────────────
            "https://www.servicenow.com/products/hr-service-delivery.html",
            "https://www.servicenow.com/solutions/hr.html",
            "https://www.servicenow.com/products/employee-experience.html",
            # ── Manufacturing ─────────────────────────────────────────────────
            "https://www.servicenow.com/industries/manufacturing.html",
            # ── Government ────────────────────────────────────────────────────
            "https://www.servicenow.com/industries/government.html",
            # ── Telecommunications ────────────────────────────────────────────
            "https://www.servicenow.com/industries/telecommunications.html",
            # ── Retail ────────────────────────────────────────────────────────
            "https://www.servicenow.com/industries/retail.html",
            # ── AI platform ───────────────────────────────────────────────────
            "https://www.servicenow.com/solutions/ai.html",
            "https://www.servicenow.com/solutions/generative-ai.html",
            "https://www.servicenow.com/products/ai.html",
            # ── New product / platform pages ──────────────────────────────────
            "https://www.servicenow.com/products/now-assist.html",
            "https://www.servicenow.com/solutions/autonomous-workforce.html",
            "https://www.servicenow.com/products/ai-agents.html",
            "https://www.servicenow.com/solutions/action-fabric.html",
            "https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-opens-its-full-system-of-action-to-every-AI-Agent-in-the-enterprise/default.aspx",
            "https://www.servicenow.com/products/ai-control-tower.html",
            "https://www.servicenow.com/products/context-engine.html",
            "https://www.servicenow.com/products/workflow-data-fabric.html",
            "https://www.servicenow.com/products/employee-works.html",
            "https://www.servicenow.com/solutions/otto.html",
            "https://www.servicenow.com/products/itsm.html",
            "https://www.servicenow.com/products/it-operations-management.html",
            "https://www.servicenow.com/products/ai-for-it.html",
            "https://www.servicenow.com/products/customer-service-management.html",
            "https://www.servicenow.com/products/ai-for-customer-service.html",
            "https://www.servicenow.com/products/legal-service-delivery.html",
            "https://www.servicenow.com/products/source-to-pay.html",
            "https://www.servicenow.com/products/finance-and-supply-chain.html",
            "https://www.servicenow.com/products/security-operations.html",
            "https://www.servicenow.com/products/governance-risk-compliance.html",
            "https://www.servicenow.com/products/raptordb.html",
            "https://www.servicenow.com/success/learning/servicenow-university.html",
        ],
        allowed_domains=["servicenow.com", "www.servicenow.com", "newsroom.servicenow.com"],
        allowed_path_prefixes=[
            "/solutions", "/products", "/success", "/press-releases", "/industries",
        ],
        blocked_path_patterns=[
            r"^/blog", r"^/events", r"^/training", r"^/partners", r"^/legal",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="headed",
        extra_wait_ms=15000,
        link_keywords=[
            # core AI platform
            "now-assist", "autonomous", "ai-specialist", "ai-agent",
            "action-fabric", "mcp", "open-agent", "agent-integration",
            "ai-control-tower", "governance", "context-engine",
            "workflow-data-fabric", "raptordb", "employee-works", "otto",
            # IT / operations
            "itsm", "itom", "it-operations", "incident", "change-management",
            "cmdb", "asset-management", "observability",
            # customer service
            "csm", "customer-service", "case-management", "field-service",
            # HR
            "hr", "employee", "workforce", "talent", "onboarding",
            # legal / finance / procurement
            "legal", "contract", "procurement", "source-to-pay",
            "accounts-payable", "finance", "supply-chain",
            # security / risk
            "security-operations", "secops", "grc", "risk", "compliance",
            "vulnerability", "threat",
            # training
            "university", "simstudio", "learning-guide",
            # healthcare-specific
            "prior-auth", "authorization",
            # platform signals
            "generative", "now-intelligence",
        ] + _INDUSTRY_LINK_KEYWORDS,
        target_sub_offerings=200,
        max_pages=200,
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
            # ── Top-level industries hub ──────────────────────────────────────
            "https://www.sap.com/industries.html",
            # ── Healthcare & Life Sciences ────────────────────────────────────
            "https://www.sap.com/industries/life-sciences-healthcare.html",
            "https://www.sap.com/industries/life-sciences.html",
            "https://www.sap.com/industries/healthcare.html",
            # ── Financial Services ────────────────────────────────────────────
            "https://www.sap.com/industries/banking.html",
            "https://www.sap.com/industries/insurance.html",
            "https://www.sap.com/industries/financial-services.html",
            "https://www.sap.com/products/financial-management.html",
            # ── Manufacturing ─────────────────────────────────────────────────
            "https://www.sap.com/industries/discrete-manufacturing.html",
            "https://www.sap.com/industries/process-manufacturing.html",
            "https://www.sap.com/industries/industrial-machinery.html",
            "https://www.sap.com/products/manufacturing/mes.html",
            # ── Retail ────────────────────────────────────────────────────────
            "https://www.sap.com/industries/retail.html",
            "https://www.sap.com/industries/consumer-products.html",
            # ── Government / Public Sector ────────────────────────────────────
            "https://www.sap.com/industries/public-sector.html",
            # ── Energy & Utilities ────────────────────────────────────────────
            "https://www.sap.com/industries/energy-utilities.html",
            # ── Automotive ────────────────────────────────────────────────────
            "https://www.sap.com/industries/automotive.html",
            # ── Supply Chain ──────────────────────────────────────────────────
            "https://www.sap.com/products/scm/supply-chain-planning.html",
            # ── New product / platform pages ──────────────────────────────────
            "https://www.sap.com/products/artificial-intelligence/joule.html",
            "https://www.sap.com/solutions/technology-platform/joule.html",
            "https://www.sap.com/products/technology-platform/low-code.html",
            "https://www.sap.com/products/business-ai/build.html",
            "https://www.sap.com/products/technology-platform/ai-core.html",
            "https://www.sap.com/products/technology-platform/generative-ai-hub.html",
            "https://www.sap.com/products/technology-platform/analytics-cloud.html",
            "https://www.sap.com/products/technology-platform/datasphere.html",
            "https://www.sap.com/products/technology-platform/process-intelligence.html",
            "https://www.signavio.com/",
            "https://www.sap.com/products/technology-platform/integration-suite.html",
            "https://www.sap.com/products/erp/s4hana.html",
            "https://www.sap.com/products/erp/s4hana-cloud.html",
            "https://www.sap.com/products/spend-management/ariba-procurement.html",
            "https://www.sap.com/products/hcm/successfactors.html",
            "https://www.sap.com/products/hcm/hr-software.html",
            "https://www.sap.com/products/crm.html",
            "https://www.sap.com/products/crm/sap-emarsys-marketing.html",
            "https://www.sap.com/products/erp/rise.html",
            "https://www.sap.com/products/erp/grow.html",
            "https://www.sap.com/products/business-ai.html",
        ],
        allowed_domains=["sap.com", "www.sap.com", "news.sap.com", "www.signavio.com"],
        allowed_path_prefixes=[
            "/products", "/solutions", "/industries",
            "/platform", "/use-cases",  # www.signavio.com
        ],
        blocked_path_patterns=[
            r"/events", r"/legal", r"/partners", r"/blog", r"/training", r"/support",
        ],
        disallowed_terms=[],
        too_generic_terms=_GENERIC_TERMS,
        browser_mode="stealth",
        link_keywords=[
            # AI copilot / platform
            "joule", "business-ai", "ai-core", "generative-ai-hub",
            "btp", "business-technology-platform",
            "ai-sdk", "llm", "embedding",
            # low-code / agent builder
            "sap-build", "low-code", "no-code",
            # analytics / data
            "analytics-cloud", "datasphere", "data-warehouse",
            "planning", "predictive", "embedded-analytics",
            # process intelligence
            "signavio", "process-mining", "process-intelligence",
            # integration
            "integration-suite", "api-management", "event-mesh",
            # ERP
            "s4hana", "s-4hana", "erp", "rise", "grow",
            "finance-module", "controlling", "asset-management",
            # procurement / supply chain
            "ariba", "procurement", "spend-management", "source-to-pay", "supplier",
            # HR
            "successfactors", "hr", "human-capital", "payroll",
            "talent", "recruiting", "workforce",
            # CRM / commerce
            "crm", "customer-experience", "emarsys", "cx",
            "commerce-cloud", "sales-cloud", "service-cloud",
            # industry-specific
            "batch", "cell-gene", "serialization",
            "treasury", "ledger", "machinery",
        ] + _INDUSTRY_LINK_KEYWORDS,
        target_sub_offerings=200,
        max_pages=200,
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
            # ── Top-level industries hub ──────────────────────────────────────
            "https://www.oracle.com/industries/",
            # ── Healthcare ────────────────────────────────────────────────────
            "https://www.oracle.com/health/",
            "https://www.oracle.com/health/whats-new/",
            "https://www.oracle.com/health/ai-center-excellence/",
            "https://www.oracle.com/health/clinical-digital-assistant/",
            # ── Financial Services ────────────────────────────────────────────
            "https://www.oracle.com/industries/financial-services/",
            "https://www.oracle.com/industries/financial-services/banking/",
            "https://www.oracle.com/industries/financial-services/insurance/",
            "https://www.oracle.com/financial-services/generative-ai/",
            # ── Manufacturing ─────────────────────────────────────────────────
            "https://www.oracle.com/industries/manufacturing/",
            "https://www.oracle.com/scm/manufacturing/",
            "https://www.oracle.com/erp/manufacturing/",
            # ── Retail ────────────────────────────────────────────────────────
            "https://www.oracle.com/industries/retail/",
            # ── Government ────────────────────────────────────────────────────
            "https://www.oracle.com/industries/government/",
            # ── Education ─────────────────────────────────────────────────────
            "https://www.oracle.com/industries/education/",
            # ── Utilities / Energy ────────────────────────────────────────────
            "https://www.oracle.com/industries/utilities/",
            # ── Announcements ─────────────────────────────────────────────────
            "https://www.oracle.com/news/announcement/",
            # ── New product / platform pages ──────────────────────────────────
            "https://www.oracle.com/artificial-intelligence/generative-ai/",
            "https://www.oracle.com/artificial-intelligence/generative-ai/generative-ai-service/",
            "https://www.oracle.com/artificial-intelligence/ai-services/",
            "https://www.oracle.com/artificial-intelligence/vision/",
            "https://www.oracle.com/artificial-intelligence/speech/",
            "https://www.oracle.com/artificial-intelligence/language/",
            "https://www.oracle.com/artificial-intelligence/document-understanding/",
            "https://www.oracle.com/artificial-intelligence/anomaly-detection/",
            "https://www.oracle.com/database/select-ai/",
            "https://www.oracle.com/artificial-intelligence/ai-agents/",
            "https://www.oracle.com/erp/ai/",
            "https://www.oracle.com/human-capital-management/ai/",
            "https://www.oracle.com/cx/ai/",
            "https://apex.oracle.com/en/platform/features/ai/",
            "https://www.oracle.com/autonomous-database/",
            "https://www.oracle.com/database/vector-search/",
            "https://www.oracle.com/artificial-intelligence/data-science/",
            "https://www.oracle.com/chatbots/",
            "https://www.oracle.com/business-analytics/analytics-cloud/",
            "https://www.oracle.com/artificial-intelligence/developer-experience/",
        ],
        allowed_domains=["oracle.com", "www.oracle.com", "apex.oracle.com"],
        allowed_path_prefixes=[
            "/artificial-intelligence", "/database",
            "/autonomous-database", "/chatbots",
            "/erp", "/human-capital-management", "/cx",
            "/business-analytics", "/scm",
            "/industries", "/health",
            "/financial-services",
            "/news/announcement",
            "/en",  # apex.oracle.com
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
            # generative AI / LLM
            "generative-ai", "llm", "foundation-model", "oci-genai",
            "cohere", "meta-llama", "ai-service",
            "vector-search", "rag", "embedding",
            # AI services
            "vision", "speech", "language", "document-understanding",
            "anomaly-detection", "forecasting",
            # database AI
            "select-ai", "natural-language", "autonomous-database",
            "oracle-database-23ai", "23ai",
            # agents / copilots
            "ai-agent", "fusion-agent", "oracle-agent",
            "digital-assistant", "chatbot",
            # ERP / finance AI
            "erp-ai", "finance-copilot", "accounting-ai",
            "accounts-payable", "expense", "planning-ai",
            # HCM / HR AI
            "hcm-ai", "hr-ai", "talent-management", "workforce-ai",
            "recruiting-ai", "payroll-ai",
            # CX / CRM AI
            "cx-ai", "crm-ai", "sales-ai", "service-ai",
            "marketing-ai", "b2c-commerce",
            # developer
            "apex", "apex-ai", "data-science", "mlops",
            "oci", "cloud-infrastructure",
            # analytics
            "analytics-cloud", "bi", "business-intelligence",
            "narrative-reporting",
            # healthcare-specific
            "oracle-health", "whats-new", "clinical-digital-assistant",
            # financial-specific
            "flexcube",
            # cross-sector
            "announcement",
        ] + _INDUSTRY_LINK_KEYWORDS,
        target_sub_offerings=200,
        max_pages=200,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # HARVEY  (vertical_ai)
    # ══════════════════════════════════════════════════════════════════════════
    "harvey_ai": VendorConfig(
        name="Harvey",
        slug="harvey_ai",
        group="vertical_ai",
        product_brand="Harvey AI",
        sector="enterprise",
        seed_urls=[
            # ── Top-level and solution overview ───────────────────────────────
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
            # ── Specific product pages ─────────────────────────────────────────
            "https://www.harvey.ai/research",
            "https://www.harvey.ai/products/draft",
            "https://www.harvey.ai/products/diligence",
            "https://www.harvey.ai/products/translate",
            "https://www.harvey.ai/products/vault",
            "https://www.harvey.ai/products/tax",
            "https://www.harvey.ai/products/accounting",
            "https://www.harvey.ai/agents/research",
            "https://www.harvey.ai/agents/drafting",
            "https://www.harvey.ai/agents/diligence",
            "https://www.harvey.ai/agents/contract-review",
            "https://www.harvey.ai/agents/regulatory",
            "https://www.harvey.ai/solutions/life-sciences",
            "https://www.harvey.ai/solutions/tax",
            "https://www.harvey.ai/solutions/accounting-firms",
            "https://www.harvey.ai/api",
            "https://www.harvey.ai/enterprise",
            "https://www.harvey.ai/blog/harvey-for-tax",
            "https://www.harvey.ai/blog/harvey-translate",
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
            "research", "draft", "drafting", "document", "brief", "memo", "opinion",
            "diligence", "due-diligence", "m-and-a", "mergers", "acquisition",
            "private-equity", "transaction",
            "contract-review", "contract-analysis", "clm", "redline",
            "translate", "translation", "multilingual",
            "vault", "document-repository", "knowledge-management",
            "tax", "accounting", "k-1", "tax-form", "transfer-pricing",
            "regulatory", "fda", "ema", "clinical-trial", "submissions",
            "autonomous-agent", "multi-step", "workflow-agent",
            "api", "fine-tuning", "custom-model", "enterprise-api",
            # from old config
            "law-firm", "in-house", "corporate", "securities",
            "bayer",
            # cross-sector
            "agents", "products", "platform", "customers", "solutions",
        ] + _INDUSTRY_LINK_KEYWORDS,
        target_sub_offerings=200,
        max_pages=200,
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # GLEAN  (vertical_ai)
    # ══════════════════════════════════════════════════════════════════════════
    "glean_ai": VendorConfig(
        name="Glean",
        slug="glean_ai",
        group="vertical_ai",
        product_brand="Glean",
        sector="enterprise",
        seed_urls=[
            # ── All-industries hub ────────────────────────────────────────────
            "https://www.glean.com/industries",
            # ── Specific sectors ──────────────────────────────────────────────
            "https://www.glean.com/industries/healthcare",
            "https://www.glean.com/industries/financial-services",
            "https://www.glean.com/industries/legal",
            "https://www.glean.com/industries/technology",
            "https://www.glean.com/industries/retail",
            "https://www.glean.com/industries/manufacturing",
            # ── Product pages ─────────────────────────────────────────────────
            "https://www.glean.com/product/assistant",
            "https://www.glean.com/product",
            "https://www.glean.com/solutions",
            "https://www.glean.com/customers",
            "https://www.glean.com/product/work-ai",
            "https://www.glean.com/product/search",
            "https://www.glean.com/product/ai-answers",
            "https://www.glean.com/product/agents",
            "https://www.glean.com/product/agent-platform",
            "https://www.glean.com/product/apps",
            "https://www.glean.com/connectors",
            "https://www.glean.com/developers",
            "https://www.glean.com/product/api",
            "https://www.glean.com/product/analytics",
            "https://www.glean.com/product/work-hub",
            "https://www.glean.com/trust",
            "https://www.glean.com/product/security",
            "https://www.glean.com/integrations/slack",
            "https://www.glean.com/integrations/microsoft-teams",
            "https://www.glean.com/perspectives",
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
            "search", "work-ai", "knowledge", "ai-answers",
            "retrieval", "rag", "zero-hallucination", "enterprise-search",
            "agent", "agents", "agent-platform", "autonomous",
            "multi-agent", "orchestration", "workflow",
            "apps", "app-builder", "custom-app", "skill",
            "connector", "integration", "data-source",
            "salesforce", "jira", "confluence", "servicenow",
            "zendesk", "github", "sharepoint", "google-drive",
            "slack", "teams", "notion",
            "api", "sdk", "developer", "mcp",
            "analytics", "insights", "usage", "adoption",
            "work-hub", "intranet", "company-hub",
            "trust", "security", "compliance", "soc2", "gdpr",
            # from old config
            "technology", "tech",
            # cross-sector
            "industry", "industries", "customers", "solutions",
        ] + _INDUSTRY_LINK_KEYWORDS,
        target_sub_offerings=200,
        max_pages=200,
    ),
}
