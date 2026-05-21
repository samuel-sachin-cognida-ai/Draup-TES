"""Static reference data: roles and their common tasks across sectors."""

ROLES_AND_TASKS: dict[str, list[str]] = {

    # ── PAYERS ─────────────────────────────────────────────────────────────────

    "Utilization Management (UM) Nurse": [
        "Review incoming prior auth requests against coverage policy",
        "Validate provider credentials (NPI) and codes (CPT, ICD-10)",
        "Check medical necessity against LCD / payer criteria",
        "Flag documentation gaps and request additional records",
        "Draft prior auth recommendation (approve / pend / refer to medical director)",
    ],

    "Medical Director / Physician Reviewer": [
        "Sign off on PA denials and complex approvals",
        "Conduct peer-to-peer reviews with treating physicians",
        "Review appeals where UM recommends uphold or overturn",
        "Provide clinical judgment on edge cases",
    ],

    "Prior Authorization Coordinator / Intake Specialist": [
        "Receive and log incoming PA submissions",
        "Route PA cases to UM nurses based on service category",
        "Track PA case status and turnaround times",
        "Maintain audit trail of review decisions",
    ],

    "Appeals Analyst / Appeals Coordinator": [
        "Analyze appeal submission against original denial reasons",
        "Cross-reference member records with coverage policy",
        "Draft appeal review summary addressing each denial reason",
        "Cite medical necessity criteria in decision",
        "Recommend approve appeal, uphold denial, or refer to medical director / peer-to-peer",
    ],

    "Claims Examiner": [
        "Process routine claims submissions for adjudication",
        "Apply initial coverage and medical necessity rules (may generate initial denial that later becomes an appeal)",
    ],

    "Member Services Representative": [
        "Triage inbound member messages and calls",
        "Flag urgent clinical concerns for escalation",
        "Draft routine replies for benefit, eligibility, and claims status questions",
        "Route non-clinical messages to appropriate departments",
    ],

    "Pharmacy Benefits / PBM PA Reviewer": [
        "Review drug prior auth requests against formulary and coverage criteria",
        "Validate NDC, diagnosis indication, and step-therapy history",
        "Draft PA recommendation for pharmacy director sign-off",
    ],

    # ── PROVIDERS ──────────────────────────────────────────────────────────────

    "Physician": [
        "Dictate and sign clinical notes",
        "Review and respond to patient portal messages",
        "Order procedures requiring prior authorization and provide clinical justification",
        "Support claims appeals (peer-to-peer, clinical narrative)",
    ],

    "Nurse": [
        "Triage patient portal messages",
        "Escalate urgent clinical issues to providers",
        "Draft routine responses for provider review",
    ],

    "Clinical Documentation Improvement (CDI) Specialist": [
        "Review clinical documentation for specificity and accuracy",
        "Query physicians on documentation gaps",
        "Support prior auth and appeals with documentation fixes",
    ],

    "Medical Coder": [
        "Validate AI-assigned ICD-10 codes against documentation",
        "Assign and audit CPT codes",
        "Verify coding on prior auth submissions",
    ],

    "Care Coordinator / Case Manager": [
        "Review AI-flagged urgent and high-risk patient messages",
        "Follow up on care plans",
        "Route non-clinical messages to appropriate departments",
    ],

    "Prior Authorization Specialist": [
        "Submit prior auth requests to payers",
        "Confirm NPI, CPT, ICD-10, and coverage policy alignment",
        "Track status and audit trails",
    ],

    "Revenue Cycle / Denials Specialist": [
        "Analyze denial reason codes",
        "Cross-reference records against policy criteria",
        "Draft appeal review with cited medical necessity criteria",
    ],

    "Scheduling / Front Office / Patient Access": [
        "Receive non-clinical messages routed from the triage queue (scheduling, billing, referrals)",
    ],

    # ── LEGAL ──────────────────────────────────────────────────────────────────

    "Corporate Counsel": [
        "Provide legal counsel on corporate matters",
        "Draft, review, and negotiate commercial contracts",
        "Advise on corporate governance matters",
        "Support mergers and acquisitions activities",
        "Manage coordination with outside counsel",
        "Develop and implement compliance programs",
        "Conduct legal research and analysis",
        "Provide training on legal and compliance matters",
    ],

    "Paralegal": [
        "Draft legal documents and correspondence",
        "Manage case files and matter records",
        "Conduct legal research and case law analysis",
        "Prepare discovery documents and evidence summaries",
        "Assist attorneys with trial preparation",
        "Track deadlines and court filings",
    ],

    "Contract Manager": [
        "Draft and redline commercial contracts",
        "Manage contract lifecycle from initiation through execution",
        "Track contract obligations, renewals, and expiration dates",
        "Conduct clause-level risk analysis against playbook standards",
        "Coordinate approvals across legal, finance, and procurement",
        "Maintain contract repository and reporting",
    ],

    "Legal Operations Manager": [
        "Manage outside counsel spend and e-billing workflows",
        "Oversee matter management and legal project tracking",
        "Evaluate and implement legal technology tools",
        "Develop and maintain legal department KPIs and dashboards",
        "Coordinate legal holds and document retention",
        "Drive process improvement across the legal function",
    ],

    # ── FINANCIAL SERVICES ─────────────────────────────────────────────────────

    "Financial Analyst": [
        "Build and maintain financial models for forecasting and valuation",
        "Analyze financial statements and KPIs",
        "Prepare variance analysis and management reporting packages",
        "Support budgeting and long-range planning processes",
        "Conduct industry and competitor benchmarking",
        "Present findings and recommendations to senior leadership",
    ],

    "Risk & Compliance Analyst": [
        "Identify and assess regulatory and operational risks",
        "Monitor regulatory changes and assess business impact",
        "Draft and update compliance policies and procedures",
        "Conduct compliance reviews and internal audits",
        "Prepare regulatory filings and examination responses",
        "Track and report on risk indicators and control effectiveness",
    ],

    "Insurance Underwriter": [
        "Evaluate risk profiles for new and renewal policies",
        "Analyze loss history, exposure data, and actuarial reports",
        "Price policies and set coverage terms and conditions",
        "Review and negotiate policy endorsements and exceptions",
        "Document underwriting decisions and rationale",
        "Collaborate with brokers and agents on complex accounts",
    ],

    "Loan Officer / Credit Analyst": [
        "Review loan applications and supporting financial documentation",
        "Conduct credit risk assessments and financial statement analysis",
        "Prepare credit memos and present recommendations to credit committee",
        "Monitor existing portfolio for covenant compliance and early warning signals",
        "Coordinate with clients on documentation and due diligence requests",
        "Ensure adherence to lending policies and regulatory requirements",
    ],

    "AML / KYC Analyst": [
        "Conduct customer due diligence (CDD) and enhanced due diligence (EDD) reviews",
        "Screen customers and transactions against sanctions and watchlists",
        "Investigate alerts generated by transaction monitoring systems",
        "Draft and file Suspicious Activity Reports (SARs)",
        "Maintain audit trails and case documentation",
        "Support regulatory examinations and internal audits",
    ],

    # ── HR ─────────────────────────────────────────────────────────────────────

    "HR Business Partner": [
        "Advise managers on employee relations, performance management, and workforce planning",
        "Partner with leadership on organizational design and change management",
        "Investigate employee complaints and support disciplinary processes",
        "Analyze HR metrics and present workforce insights to business leaders",
        "Coordinate talent review and succession planning activities",
        "Ensure compliance with employment law and HR policies",
    ],

    "Talent Acquisition Specialist": [
        "Write and post job descriptions across recruiting channels",
        "Source and screen candidates using ATS and LinkedIn",
        "Conduct initial phone screens and coordinate interview scheduling",
        "Manage candidate communications and pipeline status updates",
        "Extend offers and support onboarding coordination",
        "Report on recruiting metrics (time-to-fill, source quality, pipeline diversity)",
    ],

    # ── MANUFACTURING / OPERATIONS ─────────────────────────────────────────────

    "Supply Chain Analyst": [
        "Monitor supplier performance, lead times, and inventory levels",
        "Build demand forecasting models and identify supply risks",
        "Analyze procurement data to identify cost reduction opportunities",
        "Coordinate with suppliers on order changes and escalations",
        "Prepare supply chain KPI reports for operations leadership",
        "Support S&OP process with data analysis and scenario modeling",
    ],

    "Quality Assurance Engineer": [
        "Develop and maintain quality control plans and inspection procedures",
        "Analyze defect data and conduct root cause investigations",
        "Document non-conformances and corrective action plans (CAPAs)",
        "Conduct supplier audits and qualification reviews",
        "Prepare quality reports for regulatory submissions and customer requirements",
        "Drive continuous improvement initiatives using lean/Six Sigma methods",
    ],

    # ── PHARMA / MEDICAL AFFAIRS ───────────────────────────────────────────────

    "Medical Manager": [
        "Develop and implement medical strategies",
        "Lead cross-functional clinical trial teams",
        "Oversee medical communications",
        "Ensure regulatory compliance",
        "Manage key opinion leader relationships",
        "Provide medical expertise to business functions",
        "Monitor post-market surveillance data",
        "Lead medical training programs",
    ],

    # ── PATIENT SERVICES ───────────────────────────────────────────────────────

    "Patient Services Representative": [
        "Greet patients and visitors",
        "Schedule patient appointments",
        "Verify insurance and process payments",
        "Handle patient inquiries",
        "Maintain patient records",
        "Coordinate with clinical staff",
        "Process specialist referrals",
        "Assist with patient documentation",
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # ✅ SECTORS THAT SHOULD HAVE DATA — expect strong matches
    # ══════════════════════════════════════════════════════════════════════════

    # ── SOFTWARE DEVELOPMENT (should hit GitHub Copilot, Claude Code, Codex, Kiro, Jules, Amazon Q) ──

    "Software Engineer": [
        "Write and refactor code from natural-language specifications",
        "Review a pull request and suggest fixes for bugs and style issues",
        "Debug a failing unit test and identify the root cause",
        "Generate boilerplate for a new REST API endpoint",
        "Explain an unfamiliar codebase section to onboard faster",
        "Write unit tests for an existing function",
        "Convert a Python script to TypeScript",
    ],

    # ── IT SERVICE MANAGEMENT (should hit ServiceNow ITSM, Now Assist) ───────

    "IT Service Desk Analyst": [
        "Triage and classify incoming IT support tickets",
        "Draft resolution notes for a recurring network connectivity issue",
        "Escalate a P1 incident to the appropriate on-call team",
        "Generate a post-incident report summarising root cause and remediation",
        "Search the knowledge base for a documented fix to a software error",
        "Update the CMDB with changes from a completed change request",
    ],

    # ── CYBERSECURITY (should hit Microsoft Security Copilot, Sentinel, Defender) ──

    "SOC Analyst": [
        "Triage an alert from the SIEM for signs of lateral movement",
        "Summarise indicators of compromise (IOCs) from a threat intelligence report",
        "Write a KQL query to hunt for suspicious PowerShell executions",
        "Draft an incident response runbook for a ransomware containment scenario",
        "Correlate logs across endpoint, email, and network to investigate a phishing alert",
        "Prioritise open vulnerabilities by exploitability and business impact",
    ],

    # ── CUSTOMER SERVICE (should hit ServiceNow CSM, AWS Connect AI) ─────────

    "Customer Service Manager": [
        "Summarise the top complaint themes from last month's support tickets",
        "Draft a response template for billing dispute escalations",
        "Review agent performance metrics and identify coaching opportunities",
        "Create a self-service FAQ article from resolved ticket data",
        "Build an escalation routing rule for high-value account issues",
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # ⚠️ SECTORS NOT IN DB / SPARSE — expect few or no strong matches,
    #    low task_coverage_pct scores, LLM may struggle to match anything real
    # ══════════════════════════════════════════════════════════════════════════

    # ── MEDIA & ENTERTAINMENT (sparse — not a primary vendor sector in crawled data) ──

    "Broadcast Producer": [
        "Write a broadcast script for a nightly news segment",
        "Schedule guests and coordinate pre-interview briefing documents",
        "Compile a shot list and edit decision list for a live sports event",
        "Produce closed-caption files from recorded audio tracks",
        "Research story background and draft a reporter briefing pack",
    ],

    # ── ENERGY / UTILITIES (sparse — little vendor data in current DB) ────────

    "Grid Operations Engineer": [
        "Analyse real-time SCADA telemetry for anomalies in substation load",
        "Model renewable energy dispatch scenarios for demand forecasting",
        "Draft an outage notification to downstream industrial customers",
        "Review protective relay settings for compliance with NERC CIP standards",
        "Generate a daily grid stability report for operations management",
    ],

    # ── EDUCATION (sparse — not heavily crawled) ──────────────────────────────

    "University Lecturer": [
        "Create a course syllabus aligned with learning outcomes",
        "Design a multiple-choice assessment from lecture slide content",
        "Provide personalised written feedback on a student essay",
        "Summarise student survey responses to improve next semester's delivery",
        "Translate lecture notes into a condensed revision guide",
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # ❌ NEGATIVE TEST CASES — tasks are real but AI tools genuinely can't help;
    #    expect empty recommendations or very low scores (< 30%)
    # ══════════════════════════════════════════════════════════════════════════

    # ── PURELY PHYSICAL WORK — no enterprise AI tool can automate these ───────

    "Janitor": [
        "Mop and sanitise hallway floors on each building level",
        "Empty and replace bin liners across all office areas",
        "Refill soap dispensers and paper towel holders in restrooms",
        "Report a broken ceiling tile to the facilities manager",
        "Set up tables and chairs for a conference room event",
    ],

    # ── FIELD / PHYSICAL TRADE ROLE — same reasoning ─────────────────────────

    "Electrician": [
        "Install conduit and pull wire through a commercial building",
        "Terminate and label a 400-amp panel box",
        "Troubleshoot a tripped breaker in an industrial machine",
        "Perform a continuity test on a newly wired circuit",
        "Read a wiring schematic for a three-phase motor controller",
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # 🤡 SILLY / ABSURD TEST CASES — role or tasks are nonsensical in context;
    #    system should return no matches or very low scores
    # ══════════════════════════════════════════════════════════════════════════

    # ── FICTIONAL / GAME WORLD ────────────────────────────────────────────────

    "Pokemon Trainer": [
        "Catch a rare Shiny Charizard in the wild",
        "Build a competitive battle team with optimal EV spreads",
        "Win the Pokemon League championship tournament",
        "Trade a Haunter to trigger its Gengar evolution",
    ],

    # ── HISTORICAL / IMPOSSIBLE CONTEXT ──────────────────────────────────────

    "Medieval Knight": [
        "Sharpen a broadsword before tomorrow's jousting tournament",
        "Negotiate a truce between two feuding noble houses",
        "Train a squire in horseback combat techniques",
        "Inspect castle battlements for structural weaknesses",
    ],

    # ── EXTREME SPECIALIST — no enterprise AI vendor covers this domain ───────

    "Astronaut": [
        "Execute a manual docking procedure with the ISS in orbital approach",
        "Conduct a 6-hour EVA to replace a solar array panel",
        "Monitor life-support CO2 scrubber readings during a long-duration mission",
        "Report anomalous thruster behaviour to Mission Control",
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # 🔀 EDGE CASES — tests boundary and cross-sector behaviour
    # ══════════════════════════════════════════════════════════════════════════

    # ── CROSS-SECTOR ROLE: Legal + Healthcare + Life Sciences ─────────────────
    # Expect matches from multiple module_offerings across sectors

    "Pharmaceutical Regulatory Affairs Specialist": [
        "Prepare a drug submission dossier for FDA 510(k) review",
        "Draft a regulatory response to a CRL (Complete Response Letter)",
        "Review labelling changes for compliance with ICH guidelines",
        "Track global regulatory intelligence for a new biologics product",
        "Coordinate cross-functional teams for a clinical trial protocol amendment",
        "Conduct a gap analysis against EMA Module 2 CTD requirements",
    ],

    # ── VAGUE / ULTRA-GENERIC ROLE — tasks are too broad to match well ────────
    # Expect low-confidence results; LLM will try but scores should be weak

    "Business Person": [
        "Do business stuff",
        "Make more money for the company",
        "Attend meetings and take notes",
        "Send emails to people",
        "Make decisions",
    ],

    # ── SEMANTIC DUPLICATE TEST — tasks are the same as Claims Examiner ───────
    # but worded very differently; should semantically hit the same cached tools

    "Insurance Claims Processor": [
        "Check whether a submitted claim meets the policy coverage criteria",
        "Apply benefit rules and adjudicate the claim for payment or denial",
        "Flag claims with missing or inconsistent documentation for review",
        "Process a batch of routine claims through the adjudication system",
    ],
}
