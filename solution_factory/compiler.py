from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from .models import Decision, Economics, Option, Requirement, parse_requirements


REQUIRED_FIELDS = {"engagement_id", "customer", "assumptions", "requirements", "options"}
REQUIRED_CATEGORIES = {"business", "platform", "network", "security", "operations", "commercial"}
VALID_PRIORITIES = {"must", "should", "could"}
VALID_EVIDENCE = {"implemented", "deployed", "simulated", "contract", "modeled"}


class ContractError(ValueError):
    pass


def validate_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_FIELDS - payload.keys()
    if missing:
        errors.append(f"missing top-level fields: {', '.join(sorted(missing))}")
        return errors
    ids: set[str] = set()
    for index, item in enumerate(payload["requirements"]):
        absent = {"id", "statement", "category", "priority", "acceptance_test"} - item.keys()
        if absent:
            errors.append(f"requirement[{index}] missing: {', '.join(sorted(absent))}")
            continue
        if item["id"] in ids:
            errors.append(f"duplicate requirement id: {item['id']}")
        ids.add(item["id"])
        if item["priority"] not in VALID_PRIORITIES:
            errors.append(f"{item['id']} has invalid priority")
    categories = {item.get("category") for item in payload["requirements"]}
    absent_categories = REQUIRED_CATEGORIES - categories
    if absent_categories:
        errors.append(f"missing discovery categories: {', '.join(sorted(absent_categories))}")
    return errors


def build_options(payload: dict[str, Any]) -> list[Option]:
    result = []
    for raw in payload["options"]:
        economics = Economics(**raw["economics"])
        result.append(Option(**{key: value for key, value in raw.items() if key != "economics"}, economics=economics))
    return result


def select_option(requirements: list[Requirement], options: list[Option], weights: dict[str, float]) -> tuple[Option, list[dict[str, Any]]]:
    must_ids = {item.id for item in requirements if item.priority == "must"}
    ranking = []
    eligible = []
    for option in options:
        coverage = len(must_ids.intersection(option.supported_requirements)) / max(len(must_ids), 1)
        score = option.weighted_score(weights)
        record = {
            "id": option.id,
            "name": option.name,
            "quality_score": score,
            "must_requirement_coverage_percent": round(coverage * 100, 2),
            "year_one_roi_percent": option.economics.year_one_roi_percent,
            "payback_months": option.economics.payback_months,
            "eligible": coverage == 1.0,
        }
        ranking.append(record)
        if coverage == 1.0:
            eligible.append((score, option.economics.year_one_roi_percent, option))
    if not eligible:
        raise ContractError("no architecture option satisfies every must-have requirement")
    eligible.sort(key=lambda row: (row[0], row[1]), reverse=True)
    ranking.sort(key=lambda row: (row["eligible"], row["quality_score"], row["year_one_roi_percent"]), reverse=True)
    return eligible[0][2], ranking


def build_traceability(requirements: list[Requirement], selected: Option, mapping: dict[str, dict[str, str]]) -> list[Decision]:
    decisions = []
    for requirement in requirements:
        entry = mapping.get(requirement.id)
        if not entry:
            raise ContractError(f"requirement {requirement.id} has no traceability mapping")
        evidence_class = entry.get("evidence_class", "contract")
        if evidence_class not in VALID_EVIDENCE:
            raise ContractError(f"requirement {requirement.id} has invalid evidence class")
        decisions.append(Decision(requirement_id=requirement.id, architecture_option=selected.id, **entry))
    return decisions


def compile_engagement(payload: dict[str, Any]) -> dict[str, Any]:
    errors = validate_contract(payload)
    if errors:
        raise ContractError("; ".join(errors))
    requirements = parse_requirements(payload)
    options = build_options(payload)
    weights = payload.get("weights", {"availability": 0.3, "security": 0.25, "operability": 0.3, "portability": 0.15})
    if round(sum(weights.values()), 6) != 1:
        raise ContractError("architecture weights must total 1.0")
    selected, ranking = select_option(requirements, options, weights)
    decisions = build_traceability(requirements, selected, payload["traceability"])
    unsupported = [item.id for item in requirements if item.id not in selected.supported_requirements]
    hard_gates = {
        "all_must_requirements_covered": all(item.priority != "must" or item.id in selected.supported_requirements for item in requirements),
        "every_requirement_traceable": len(decisions) == len(requirements),
        "no_unsupported_deployment_claims": all(item.evidence_class != "deployed" for item in decisions),
        "positive_modeled_net_value": selected.economics.monthly_net_value_usd > 0,
    }
    result: dict[str, Any] = {
        "engagement_id": payload["engagement_id"],
        "customer": payload["customer"],
        "claim_boundary": "Offline deterministic analysis using customer-supplied and synthetic inputs; no cloud resources were deployed.",
        "selected_option": selected.id,
        "selected_name": selected.name,
        "services": selected.services,
        "ranking": ranking,
        "economics": {
            **asdict(selected.economics),
            "monthly_net_value_usd": round(selected.economics.monthly_net_value_usd, 2),
            "payback_months": selected.economics.payback_months,
            "year_one_roi_percent": selected.economics.year_one_roi_percent,
        },
        "traceability": [asdict(item) for item in decisions],
        "unsupported_requirements": unsupported,
        "risks": selected.risks,
        "assumptions": payload["assumptions"],
        "hard_gates": hard_gates,
        "status": "qualified" if all(hard_gates.values()) else "review_required",
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["evidence_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return result
