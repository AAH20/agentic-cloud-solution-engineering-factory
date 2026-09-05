from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Requirement:
    id: str
    statement: str
    category: str
    priority: str
    acceptance_test: str


@dataclass(frozen=True)
class Economics:
    implementation_usd: float
    monthly_cloud_usd: float
    monthly_operations_usd: float
    monthly_avoided_cost_usd: float
    monthly_revenue_uplift_usd: float
    confidence: str

    @property
    def monthly_net_value_usd(self) -> float:
        return self.monthly_avoided_cost_usd + self.monthly_revenue_uplift_usd - self.monthly_cloud_usd - self.monthly_operations_usd

    @property
    def payback_months(self) -> float | None:
        value = self.monthly_net_value_usd
        return round(self.implementation_usd / value, 2) if value > 0 else None

    @property
    def year_one_roi_percent(self) -> float:
        benefits = 12 * (self.monthly_avoided_cost_usd + self.monthly_revenue_uplift_usd)
        costs = self.implementation_usd + 12 * (self.monthly_cloud_usd + self.monthly_operations_usd)
        return round(((benefits - costs) / costs) * 100, 2) if costs else 0.0


@dataclass
class Option:
    id: str
    name: str
    services: list[str]
    supported_requirements: list[str]
    availability_score: int
    security_score: int
    operability_score: int
    portability_score: int
    economics: Economics
    risks: list[str] = field(default_factory=list)

    def weighted_score(self, weights: dict[str, float]) -> float:
        score = (
            self.availability_score * weights["availability"]
            + self.security_score * weights["security"]
            + self.operability_score * weights["operability"]
            + self.portability_score * weights["portability"]
        )
        return round(score, 2)


@dataclass(frozen=True)
class Decision:
    requirement_id: str
    architecture_option: str
    component: str
    control: str
    validation: str
    cost_line: str
    deliverable: str
    evidence_class: str


def parse_requirements(payload: dict[str, Any]) -> list[Requirement]:
    return [Requirement(**item) for item in payload["requirements"]]
