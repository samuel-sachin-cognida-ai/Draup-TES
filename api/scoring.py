"""Scoring formulas for task coverage, evidence grading, and TES score."""
from __future__ import annotations

ROLE_DOMAIN_MAP: dict[str, str] = {
    # ── PAYERS ────────────────────────────────────────────────────────────────
    "Utilization Management (UM) Nurse":                    "healthcare",
    "Medical Director / Physician Reviewer":                "healthcare",
    "Prior Authorization Coordinator / Intake Specialist":  "healthcare",
    "Appeals Analyst / Appeals Coordinator":                "healthcare",
    "Claims Examiner":                                      "healthcare",
    "Member Services Representative":                       "healthcare",
    "Pharmacy Benefits / PBM PA Reviewer":                  "healthcare",
    # ── PROVIDERS ─────────────────────────────────────────────────────────────
    "Physician":                                            "healthcare",
    "Nurse":                                               "healthcare",
    "Clinical Documentation Improvement (CDI) Specialist": "healthcare",
    "Medical Coder":                                        "healthcare",
    "Care Coordinator / Case Manager":                      "healthcare",
    "Prior Authorization Specialist":                       "healthcare",
    "Revenue Cycle / Denials Specialist":                   "healthcare",
    "Scheduling / Front Office / Patient Access":           "healthcare",
    # ── LEGAL ─────────────────────────────────────────────────────────────────
    "Corporate Counsel":                                    "legal",
    "Paralegal":                                            "legal",
    "Contract Manager":                                     "legal",
    "Legal Operations Manager":                             "legal",
    # ── FINANCIAL SERVICES ────────────────────────────────────────────────────
    "Financial Analyst":                                    "finance",
    "Risk & Compliance Analyst":                            "finance",
    "Insurance Underwriter":                                "finance",
    "Loan Officer / Credit Analyst":                        "finance",
    "AML / KYC Analyst":                                    "finance",
}


def get_role_domain(role: str) -> str:
    return ROLE_DOMAIN_MAP.get(role, "general")


def grade_url(url: str) -> tuple[str, float]:
    u = url.lower()
    if "/solutions/" in u or "/products/" in u:
        return ("A", 1.00)
    if "/case-study/" in u or "/customers/" in u:
        return ("B", 0.75)
    if "/blog/" in u or "/news/" in u or "/index/" in u:
        return ("C", 0.50)
    if "/benchmark/" in u or "/research/" in u:
        return ("D", 0.25)
    return ("A", 1.00)


def industry_match_val(role_domain: str, offering_industry: str) -> float:
    if role_domain == "general" or offering_industry == "general":
        return 1.0
    return 1.0 if role_domain == offering_industry else 0.0


def compute_task_coverage_pct(cosine_similarity: float, industry_match: float) -> float:
    return cosine_similarity * 0.80 + industry_match * 0.20


def compute_tes_score(tool_scores: list[dict]) -> float:
    if not tool_scores:
        return 0.0

    coverages = [t.get("task_coverage_pct") or 0.0 for t in tool_scores]
    best_coverage = max(coverages)

    qualifying = [c for c in coverages if c > 0.40]
    tool_breadth = min(len(qualifying), 5) / 5.0

    sorted_tools = sorted(
        tool_scores, key=lambda t: t.get("task_coverage_pct") or 0.0, reverse=True
    )
    top3 = sorted_tools[:3]
    evidence_weights = [
        t.get("evidence_weight") if t.get("evidence_weight") is not None else 0.50
        for t in top3
    ]
    evidence_weight_avg = sum(evidence_weights) / len(evidence_weights) if evidence_weights else 0.50

    return (best_coverage * 0.60 + tool_breadth * 0.20 + evidence_weight_avg * 0.20) * 100
