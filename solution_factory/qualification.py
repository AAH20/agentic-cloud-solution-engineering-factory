from __future__ import annotations

import hashlib
import json
from typing import Any


CRITERIA = {
    "problem_urgency": {"weight": 15, "question": "What business event makes this project urgent now?"},
    "budget_confirmed": {"weight": 15, "question": "What budget range is approved for implementation and operations?"},
    "decision_owner": {"weight": 10, "question": "Who owns the decision, budget and final acceptance?"},
    "delivery_deadline": {"weight": 10, "question": "What is the required production date and what drives it?"},
    "technical_inventory": {"weight": 15, "question": "Which workloads, dependencies, data stores and integrations are in scope?"},
    "success_metrics": {"weight": 10, "question": "Which measurable outcomes determine acceptance and value?"},
    "delivery_capacity": {"weight": 15, "question": "Who will supply access, SMEs, testing and change approvals?"},
    "commercial_fit": {"weight": 10, "question": "Does the opportunity meet the provider's minimum value and margin policy?"},
}
VALID_STATES = {"confirmed", "partial", "unknown", "failed"}
STATE_FACTOR = {"confirmed": 1.0, "partial": 0.5, "unknown": 0.0, "failed": 0.0}
HARD_GATES = {"problem_urgency", "decision_owner", "delivery_capacity", "commercial_fit"}


class QualificationError(ValueError):
    pass


def qualify(payload: dict[str, Any]) -> dict[str, Any]:
    required = {"opportunity_id", "customer", "estimated_contract_value_usd", "criteria"}
    missing = required - payload.keys()
    if missing:
        raise QualificationError(f"missing fields: {', '.join(sorted(missing))}")
    try:
        contract_value = float(payload["estimated_contract_value_usd"])
    except (TypeError, ValueError) as exc:
        raise QualificationError("estimated_contract_value_usd must be numeric") from exc
    if contract_value < 0:
        raise QualificationError("estimated_contract_value_usd cannot be negative")

    supplied = payload["criteria"]
    unknown = set(supplied) - set(CRITERIA)
    if unknown:
        raise QualificationError(f"unknown criteria: {', '.join(sorted(unknown))}")

    assessment: list[dict[str, Any]] = []
    score = 0.0
    questions: list[str] = []
    for criterion, definition in CRITERIA.items():
        item = supplied.get(criterion, {})
        state = item.get("state", "unknown")
        if state not in VALID_STATES:
            raise QualificationError(f"{criterion} has invalid state: {state}")
        evidence = str(item.get("evidence", "")).strip()
        earned = definition["weight"] * STATE_FACTOR[state]
        score += earned
        if state != "confirmed":
            questions.append(definition["question"])
        assessment.append({
            "criterion": criterion,
            "state": state,
            "evidence": evidence,
            "weight": definition["weight"],
            "earned": earned,
            "hard_gate": criterion in HARD_GATES,
        })

    failed_gates = [
        row["criterion"] for row in assessment
        if row["hard_gate"] and row["state"] == "failed"
    ]
    unresolved_gates = [
        row["criterion"] for row in assessment
        if row["hard_gate"] and row["state"] in {"unknown", "partial"}
    ]
    unresolved_criteria = [
        row["criterion"] for row in assessment
        if row["state"] in {"unknown", "partial"}
    ]
    score = round(score, 2)
    if failed_gates or score < 40:
        decision = "DECLINE"
    elif unresolved_criteria or score < 75:
        decision = "CLARIFY"
    else:
        decision = "PURSUE"

    result = {
        "schema_version": "1.0",
        "opportunity_id": str(payload["opportunity_id"]),
        "customer": str(payload["customer"]),
        "estimated_contract_value_usd": contract_value,
        "decision": decision,
        "qualification_score": score,
        "failed_hard_gates": failed_gates,
        "unresolved_hard_gates": unresolved_gates,
        "unresolved_criteria": unresolved_criteria,
        "customer_questions": questions,
        "assessment": assessment,
        "claim_boundary": (
            "Deterministic pre-bid triage over customer-supplied evidence. The score does not "
            "predict win probability, customer creditworthiness, delivery success or realized margin."
        ),
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["evidence_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return result
