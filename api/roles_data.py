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
}
