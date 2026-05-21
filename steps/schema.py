"""Typed I/O contracts between pipeline gates.

All dataclasses are JSON-serialisable via `dataclasses.asdict`. Keep these
in sync with the prompt manifests
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal


# ── L2 Judge ──────────────────────────────────────────────────
@dataclass
class JudgeFactor:
    factor: str
    polarity: int
    reason_headline: str
    reason_detailed: str


@dataclass
class JudgeVerdict:
    identity: dict
    internal_monologue: str
    factors: list[JudgeFactor]
    score: int
    action_taken: Literal["APPROVED", "HESITATE", "BLOCKED"]


# ── L3 Gate B: Correspondence Auditor Fact Checker ────────────────────────────────────────────
ClaimStatus = Literal["SUPPORTED", "CONTRADICTED", "UNSUPPORTED"]


@dataclass
class ClaimVerdict:
    claim: str
    status: ClaimStatus
    source: str | None
    quote: str | None


@dataclass
class FactCheckerVerdict:
    verdicts: list[ClaimVerdict]
    analysis: str  # captured between <<ANALYSIS>>...<<END>> tags


# ── L3 Gate C: Correspondence Auditor Logic ──────────────────────────────────
AuditorAction = Literal["APPROVE", "BLOCK"]


@dataclass
class LogicAuditorVerdict:
    """L3 Gate C output. The verdict is the load-bearing field; rule citations
    are accompanying observations and do not, by themselves, determine the
    quadrant. A Judge can have flawed reasoning AND reach the right action
    — recording both signals without conflating them is the whole point.
    """
    auditor_recommended_action: AuditorAction
    agent_policy_violations: list[str]
    judge_diagnostic_observations: list[str]
    reasoning: str

    def __post_init__(self):
        # Minimal coherence guard: a BLOCK verdict must cite at least one
        # policy rule. APPROVE may be cited or uncited; APPROVE with J-rule
        # citations (diagnostic observations) is a valid combination.
        if self.auditor_recommended_action == "BLOCK" and not self.agent_policy_violations:
            raise ValueError(
                "BLOCK verdict requires at least one rule citation in agent_policy_violations"
            )

# ── Synthesis ──────────────────────────────────────────────────────────────
GapSeverity = Literal["NONE", "LOW", "MEDIUM", "HIGH"]
Quadrant = Literal[
    "VALIDATED_APPROVAL",  # Judge approved, Auditor recommends APPROVE
    "FLAWED_APPROVAL",     # Judge approved, Auditor recommends BLOCK
    "VALIDATED_BLOCK",     # Judge flagged,  Auditor recommends BLOCK
    "FLAWED_BLOCK",        # Judge flagged,  Auditor recommends APPROVE
    "ERROR",
]


@dataclass
class ComplianceGap:
    # Judge dimension
    l2_judge_approved: bool            # APPROVED == True; HESITATE/BLOCKED == False
    l2_judge_action: str               # raw action verb ("APPROVED"|"HESITATE"|"BLOCKED"|"UNKNOWN")
    # Correspondence Auditor dimension — direct verdict from Gate 3
    auditor_recommended_action: AuditorAction
    ca_passed: bool                    # back-compat: True iff auditor_recommended_action == "APPROVE"
    # Fact-grounding telemetry (no longer used for routing — kept for the dashboard)
    claims_total: int
    claims_contradicted: int
    claims_unsupported: int
    logic_failed: bool                 # back-compat: True iff auditor_recommended_action == "BLOCK"
    # 2x2 cross-tab of {l2_judge_action} × {auditor_action}
    quadrant: Quadrant
    # Back-compat: any disagreement between Judge and Auditor
    gap_detected: bool
    gap_severity: GapSeverity

PipelineStatus = Literal[
    "OK",
    "ABORTED_COMPILATION",
    "ABORTED_EXTRACTION",
    "ABORTED_OPTION_C",
    "L2_PARSE_ERROR",
    "GATEB_PARSE_ERROR",
    "GATE_C_PARSE_ERROR",
    "WORKER_EXCEPTION",
]


@dataclass
class CaseResult:
    case_id: str
    input_path: str
    pipeline_status: PipelineStatus
    sanitized_body: str | None
    mined_claims: list[str]
    l2_judge_verdict: JudgeVerdict | None
    fact_checker_verdict: FactCheckerVerdict | None
    logic_auditor_verdict: LogicAuditorVerdict | None
    compliance_gap: ComplianceGap | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict:
        return asdict(self)