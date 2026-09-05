from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_traceability(result: dict[str, Any]) -> str:
    lines = [
        "# Requirement traceability",
        "",
        "| Requirement | Component | Control | Validation | Cost | Deliverable | Evidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in result["traceability"]:
        lines.append("| " + " | ".join(str(row[key]).replace("|", "\\|") for key in ("requirement_id", "component", "control", "validation", "cost_line", "deliverable", "evidence_class")) + " |")
    return "\n".join(lines) + "\n"


def render_executive_proposal(result: dict[str, Any]) -> str:
    economics = result["economics"]
    gates = "\n".join(f"- {'PASS' if passed else 'REVIEW'} — {name.replace('_', ' ')}" for name, passed in result["hard_gates"].items())
    risks = "\n".join(f"- {risk}" for risk in result["risks"])
    return f"""# Solution decision — {result['engagement_id']}

## Recommendation

Select **{result['selected_name']}**. The decision passed deterministic requirement, traceability, claim and value gates.

## Modeled economics

| Metric | Value |
|---|---:|
| Implementation | ${economics['implementation_usd']:,.0f} |
| Monthly cloud | ${economics['monthly_cloud_usd']:,.0f} |
| Monthly operations | ${economics['monthly_operations_usd']:,.0f} |
| Monthly net value | ${economics['monthly_net_value_usd']:,.0f} |
| Payback | {economics['payback_months']} months |
| Year-one ROI | {economics['year_one_roi_percent']}% |

These are modeled values based on declared assumptions, not realized customer outcomes.

## Qualification gates

{gates}

## Principal risks

{risks}

## Evidence boundary

{result['claim_boundary']}

Evidence receipt: `{result['evidence_digest']}`
"""


def render_sow(result: dict[str, Any]) -> str:
    deliverables = sorted({row["deliverable"] for row in result["traceability"]})
    lines = ["# Draft statement of work", "", "## Scope", "", *[f"- {item}" for item in deliverables], "", "## Commercial basis", "", f"Implementation baseline: ${result['economics']['implementation_usd']:,.0f} excluding consumption, taxes and third-party licenses.", "", "## Acceptance", "", "Each deliverable is accepted only after its linked validation completes and evidence is retained.", "", "## Exclusions", "", "Production deployment, data migration, legal certification and third-party product commitments require explicit authorization and discovery.", ""]
    return "\n".join(lines)


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "decision.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "executive-proposal.md").write_text(render_executive_proposal(result))
    (output / "traceability.md").write_text(render_traceability(result))
    (output / "statement-of-work.md").write_text(render_sow(result))
