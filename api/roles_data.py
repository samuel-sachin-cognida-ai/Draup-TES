"""Static reference data: healthcare roles and their common tasks."""

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
}
