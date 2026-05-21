"""
L3 Auditor Module — L3 Gate A + Fact Checker + Logic Auditor.

This module is completely isolated from L2. Even though some validation
logic is similar to L2's Gate A, it is DUPLICATED here to ensure total
independence. Changes to L2 cannot affect L3.

v0.4 refactor: Gate 3 now parses `auditor_recommended_action`
(APPROVE/BLOCK) instead of `logic_status` (PASS/FAIL).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from shared.llm_utils import load_and_run_prompt
from shared.string_utils import extract_json_from_string

from .schema import (
    ClaimVerdict,
    FactCheckerVerdict,
    JudgeVerdict,
    LogicAuditorVerdict,
)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


# ── Gate A: L3 Version (Dual Validation) ─────────────────────────────────
class GateA_L3Error(Exception):
    """Gate A (L3) validation failed — validates both L1 artifact and L2 output."""
    def __init__(self, message, l1_violations: list[str] | None = None, l2_violations: list[str] | None = None):
        super().__init__(message)
        self.l1_violations = l1_violations or []
        self.l2_violations = l2_violations or []


def run_l3_gate_a(input_path: Path, l2_verdict: JudgeVerdict) -> dict:
    """
    L3 Gate A — Dual validation of both L1 artifact AND L2 output.
    
    Runs AFTER L2 completes. Validates:
      1. L1 Artifact: The original input JSON (same checks as run_gate_a_schema)
      2. L2 Output: The Judge's verdict JSON (structural validation)
    
    Returns:
    dict with keys:
      - valid: bool
      - l1_violations: list[str] (empty if valid)
      - l2_violations: list[str] (empty if valid)
      - extracted_data: dict (the parsed L1 JSON)
    """
    l1_violations = []
    l2_violations = []
    result = {
        "valid": False,
        "l1_violations": [],
        "l2_violations": [],
        "extracted_data": None,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 1. L1 Artifact Validation (same as original run_gate_a_schema)
    # ─────────────────────────────────────────────────────────────────────────
    if not input_path.exists():
        l1_violations.append(f"INPUT_FILE_MISSING: '{input_path}'")
        raise GateA_L3Error("L1 artifact validation failed", l1_violations, l2_violations)

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        l1_violations.append(f"JSON_PARSE_ERROR: {str(e)}")
        raise GateA_L3Error("L1 artifact validation failed", l1_violations, l2_violations)

    result["extracted_data"] = data

    # THE APOLLO QUIRK PATCH: Infer misaligned if explicitly deceptive
    is_mis = data.get("is_misaligned")
    is_dec = data.get("is_deceptive")
    if is_mis is None and is_dec is True:
        data["is_misaligned"] = True  # Mutate so L3 inherits the fix

    result["extracted_data"] = data

    # Required fields check (Apollo contract)
    required_fields = ["response", "is_misaligned"]
    for field in required_fields:
        if field not in data:
            l1_violations.append(f"MISSING_REQUIRED_FIELD: '{field}'")

    # Score range check
    if "score" in data and data["score"] is not None:
        try:
            score_val = int(data["score"])
            if not (0 <= score_val <= 100):
                l1_violations.append(f"SCORE_OUT_OF_RANGE: {score_val} (must be 0-100)")
        except (ValueError, TypeError):
            l1_violations.append(f"INVALID_SCORE_TYPE: {type(data['score']).__name__}")

    # Action_taken validation
    valid_actions = {"APPROVED", "HESITATE", "BLOCKED"}
    if "action_taken" in data and data["action_taken"] is not None:
        if data["action_taken"] not in valid_actions:
            l1_violations.append(f"INVALID_ACTION_TAKEN: '{data['action_taken']}' (must be one of {valid_actions})")

    # Forbidden terms check
    if "response" in data and data["response"]:
        response_lower = data["response"].lower()
        forbidden_terms = ["{{{{", "}}}}", "<<", ">>"]
        for term in forbidden_terms:
            if term in response_lower:
                l1_violations.append(f"FORBIDDEN_TERM_DETECTED: '{term}' in response")

    # is_misaligned / is_deceptive strict allowlist check
    is_mis = data.get("is_misaligned")
    is_dec = data.get("is_deceptive")
    
    valid_combos = [
        (False, None),  # CLEAN
        (True, None),   # ROGUE-HONEST
        (True, True)    # ROGUE-DECEPTIVE
    ]
    
    if (is_mis, is_dec) not in valid_combos:
        l1_violations.append(f"UNSUPPORTED_LABEL_COMBINATION: is_misaligned={is_mis}, is_deceptive={is_dec}")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. L2 Output Validation (JudgeVerdict structural checks)
    # ─────────────────────────────────────────────────────────────────────────
    if l2_verdict is None:
        l2_violations.append("L2_VERDICT_MISSING: No verdict provided to Gate A (L3)")
    else:
        # Required fields check for JudgeVerdict
        if not l2_verdict.identity:
            l2_violations.append("L2_MISSING_FIELD: identity")
        if not l2_verdict.internal_monologue:
            l2_violations.append("L2_MISSING_FIELD: internal_monologue")
        if not l2_verdict.factors:
            l2_violations.append("L2_MISSING_FIELD: factors (empty list)")
        if l2_verdict.score is None:
            l2_violations.append("L2_MISSING_FIELD: score")
        if not l2_verdict.action_taken:
            l2_violations.append("L2_MISSING_FIELD: action_taken")

        # Score range validation
        if l2_verdict.score is not None:
            if not (0 <= l2_verdict.score <= 100):
                l2_violations.append(f"L2_SCORE_OUT_OF_RANGE: {l2_verdict.score} (must be 0-100)")

        # Action validation
        if l2_verdict.action_taken not in valid_actions:
            l2_violations.append(f"L2_INVALID_ACTION: '{l2_verdict.action_taken}' (must be one of {valid_actions})")

        # Factors structure validation
        for i, factor in enumerate(l2_verdict.factors):
            if not factor.factor:
                l2_violations.append(f"L2_FACTOR[{i}]: missing 'factor' field")
            if factor.polarity not in (-1, 0, 1):
                l2_violations.append(f"L2_FACTOR[{i}]: polarity {factor.polarity} must be -1, 0, or 1")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Combine results
    # ─────────────────────────────────────────────────────────────────────────
    result["l1_violations"] = l1_violations
    result["l2_violations"] = l2_violations
    result["valid"] = len(l1_violations) == 0 and len(l2_violations) == 0

    if not result["valid"]:
        raise GateA_L3Error("L3 Gate A validation failed", l1_violations, l2_violations)

    return result


# ── Shared helpers for L3 gates ───────────────────────────────────────────
L3_GATE_B_FACT = PROMPTS_DIR / "L3_GateB_FactChecker.json"
L3_GATE_C_LOGIC = PROMPTS_DIR / "L3_GateC_LogicAuditor.json"

_ANALYSIS_RE = re.compile(r"<<ANALYSIS>>(.*?)<<END>>", re.DOTALL)


class GateOutputError(Exception):
    """Gate returned malformed output that violates its contract."""
    def __init__(self, message, raw_output=""):
        super().__init__(message)
        self.raw_output = raw_output


def _invoke(manifest: Path, target: str, run_id: str, vars_: dict) -> tuple[dict | str, dict]:
    try:
        response_obj, usage = load_and_run_prompt(
            manifest_path=str(manifest),
            execution_target=target,
            calling_tool_name=run_id.split("__")[0],
            run_id=run_id,
            template_vars=vars_,
        )
        if response_obj is None:
            raise GateOutputError("API_OUTAGE: LLM returned an empty response after max retries.")
        return response_obj.get("final_answer"), usage
    except PermissionError as e:
        raise GateOutputError(f"GATE_AUTH_ERROR: {str(e)}")
    except ConnectionError as e:
        raise GateOutputError(f"API_OUTAGE: {str(e)}")

# ── Gate B: Fact Checker ──────────────────────────────────────────────────
def run_fact_checker(source_text: str, claims_list: str, target: str,
                     case_id: str) -> tuple[FactCheckerVerdict, dict]:
    raw, usage = _invoke(L3_GATE_B_FACT, target, f"L3_GATE_B_fact__{case_id}",
                  {"source_text": source_text, "claims_list": claims_list})
    raw_str = raw if isinstance(raw, str) else (str(raw) if raw is not None else "")

    analysis_match = _ANALYSIS_RE.search(raw_str)
    analysis = analysis_match.group(1).strip() if analysis_match else ""

    # FIX: Isolate the JSON payload by stripping out the analysis section entirely
    if "<<END>>" in raw_str:
        json_target_str = raw_str.split("<<END>>")[-1].strip()
    else:
        json_target_str = raw_str

    parsed = raw if isinstance(raw, dict) else extract_json_from_string(json_target_str)

    if isinstance(parsed, list):
        parsed = {"verdicts": parsed}

    if not isinstance(parsed, dict) or "verdicts" not in parsed:
        raise GateOutputError(
            f"GATE_B: malformed output. Expected dict with 'verdicts', got {type(parsed).__name__}.",
            raw_output=str(raw_str),
        )

    verdicts: list[ClaimVerdict] = []
    for i, v in enumerate(parsed["verdicts"]):
        if not isinstance(v, dict):
            raise GateOutputError(
                f"GATE_B: verdicts[{i}] is not a dict. Got: {type(v).__name__}",
                raw_output=str(raw_str),
            )
        status = v.get("status")
        if status not in {"SUPPORTED", "CONTRADICTED", "UNSUPPORTED"}:
            raise GateOutputError(
                f"GATE_B: verdicts[{i}] invalid status: {status}",
                raw_output=str(raw_str),
            )
        verdicts.append(ClaimVerdict(
            claim=v.get("claim", ""),
            status=status,
            source=v.get("source"),
            quote=v.get("quote"),
        ))
    return FactCheckerVerdict(verdicts=verdicts, analysis=analysis), usage

# ── Gate C: Logic Auditor (direct verdict) ───────────────────────────────
def run_logic_auditor(*, source_text: str, role: str, score: int, action: str,
                      monologue: str, fact_check_summary: str,
                      domain_policy: str, target: str,
                      case_id: str) -> tuple[LogicAuditorVerdict, dict]:
    """Run Gate C and parse a direct verdict on the agent.

    v0.4: parses `auditor_recommended_action` (APPROVE/BLOCK) instead of
    the prior `logic_status` (PASS/FAIL). Rule citations are still parsed
    into `flawed_logic_points` but no longer drive the verdict.
    """
    raw, la_usage = _invoke(L3_GATE_C_LOGIC, target, f"L3_GATE_C_logic__{case_id}",
                  {"source_text": source_text,
                   "role": role, "score": str(score), "action": action,
                   "monologue": monologue,
                   "fact_check_summary": fact_check_summary,
                   "domain_policy": domain_policy})

    parsed = raw if isinstance(raw, dict) else extract_json_from_string(raw or "")
    if not isinstance(parsed, dict):
        safe_raw = str(raw)[:1000].replace('\n', ' ')
        raise GateOutputError(
            f"GATE_C: non-dict output. Expected dict, got {type(parsed).__name__}. "
            f"Raw snippet: {safe_raw}"
        )

    required = (
        "auditor_recommended_action", 
        "agent_policy_violations", 
        "judge_diagnostic_observations", 
        "reasoning"
    )
    missing = [k for k in required if k not in parsed]
    if missing:
        safe_raw = str(raw)[:1000].replace('\n', ' ')
        raise GateOutputError(f"GATE_C: missing fields {missing}. Raw snippet: {safe_raw}")

    action_value = parsed["auditor_recommended_action"]
    if action_value not in {"APPROVE", "BLOCK"}:
        raise GateOutputError(
            f"GATE_C: invalid auditor_recommended_action: {action_value!r}"
        )

    try:
        return LogicAuditorVerdict(
            auditor_recommended_action=action_value,
            agent_policy_violations=list(parsed.get("agent_policy_violations", [])),
            judge_diagnostic_observations=list(parsed.get("judge_diagnostic_observations", [])),
            reasoning=parsed["reasoning"],
        ), la_usage
    except ValueError as e:
        # Coherence guard from schema.__post_init__ (e.g. BLOCK with no citations)
        raise GateOutputError(f"GATE_C_COHERENCE_FAILURE: {str(e)}", raw_output=str(raw))
    except TypeError as e:
        raise GateOutputError(f"GATE_C_SCHEMA_FAILURE: {str(e)}", raw_output=str(raw))
    except Exception as e:
        raise GateOutputError(f"GATE_C_UNKNOWN_PARSE_ERROR: {str(e)}", raw_output=str(raw))