"""Compile a private-inference offer from declared costs and endpoint measurements."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import math
from pathlib import Path
import re


CENT = Decimal("0.01")
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,199}$")
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,61}[a-z0-9]$")
REQUIRED_COSTS = {
    "gpu_hourly_usd", "billable_hours_per_month", "gpu_count",
    "ops_hours_per_month", "ops_hourly_usd", "other_monthly_usd",
    "delivery_hours", "delivery_hourly_usd", "target_gross_margin_fraction",
}


class OfferError(ValueError):
    pass


def _number(value: object, name: str, *, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise OfferError(f"{name} must be a number") from None
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise OfferError(f"{name} must be {'positive' if positive else 'nonnegative'}")
    return result


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def _safe_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200 or "\n" in value:
        raise OfferError(f"{name} must be a single nonempty line of at most 200 characters")
    return value.strip()


def compile_offer(intake: dict, benchmark: dict) -> dict:
    if not isinstance(intake, dict) or not isinstance(benchmark, dict):
        raise OfferError("intake and benchmark must be JSON objects")
    engagement_id = _safe_text(intake.get("engagement_id"), "engagement_id")
    customer = _safe_text(intake.get("customer"), "customer")
    model = _safe_text(intake.get("model"), "model")
    deployment_name = _safe_text(intake.get("deployment_name"), "deployment_name")
    if not MODEL_PATTERN.fullmatch(model) or ".." in model:
        raise OfferError("model must be a safe model identifier")
    if not NAME_PATTERN.fullmatch(deployment_name):
        raise OfferError("deployment_name must be a lowercase Kubernetes name")
    region = _safe_text(intake.get("region"), "region")
    costs = intake.get("costs")
    if not isinstance(costs, dict) or REQUIRED_COSTS - costs.keys():
        raise OfferError("costs object is incomplete")
    values = {name: _number(costs[name], name, positive=name in {
        "gpu_hourly_usd", "billable_hours_per_month", "gpu_count", "delivery_hourly_usd"
    }) for name in REQUIRED_COSTS}
    if values["gpu_count"] != int(values["gpu_count"]):
        raise OfferError("gpu_count must be an integer")
    if values["gpu_count"] != 1:
        raise OfferError("the first deployment template supports exactly one GPU")
    margin = values["target_gross_margin_fraction"]
    if margin >= 1:
        raise OfferError("target_gross_margin_fraction must be below 1")
    required_rps = float(_number(intake.get("required_rps"), "required_rps", positive=True))
    max_latency = float(_number(intake.get("max_p95_latency_s"), "max_p95_latency_s", positive=True))
    max_ttft = float(_number(intake.get("max_p95_ttft_s"), "max_p95_ttft_s", positive=True))
    if benchmark.get("schema_version") != "1.0" or benchmark.get("model") != model:
        raise OfferError("benchmark schema/model does not match the intake")
    source = benchmark.get("provenance")
    if source not in {"synthetic_fixture", "operator_supplied_measurement"}:
        raise OfferError("benchmark provenance must be explicit")
    required_metrics = ("requested", "succeeded", "failed", "concurrency",
                        "successful_requests_per_s", "latency_p95_s", "ttft_p95_s")
    if any(key not in benchmark for key in required_metrics):
        raise OfferError("benchmark is missing required metrics")
    requested = benchmark["requested"]
    succeeded = benchmark["succeeded"]
    failed = benchmark["failed"]
    concurrency = benchmark["concurrency"]
    if (not all(type(v) is int for v in (requested, succeeded, failed, concurrency))
            or requested < 1 or concurrency < 1 or succeeded < 0 or failed < 0
            or succeeded + failed != requested or concurrency > requested):
        raise OfferError("benchmark request counts are inconsistent")
    metrics = {}
    for key in ("successful_requests_per_s", "latency_p95_s", "ttft_p95_s"):
        raw = benchmark[key]
        if not isinstance(raw, (float, int)) or not math.isfinite(raw) or raw < 0:
            raise OfferError(f"benchmark {key} must be a finite nonnegative number")
        metrics[key] = raw
    gates = {
        "all_requests_succeeded": failed == 0 and succeeded == requested,
        "throughput_met": metrics["successful_requests_per_s"] >= required_rps,
        "latency_met": metrics["latency_p95_s"] <= max_latency,
        "ttft_met": metrics["ttft_p95_s"] <= max_ttft,
        "minimum_sample_met": requested >= 30,
    }
    compute = values["gpu_hourly_usd"] * values["billable_hours_per_month"] * values["gpu_count"]
    operations = values["ops_hours_per_month"] * values["ops_hourly_usd"]
    monthly_cost = compute + operations + values["other_monthly_usd"]
    monthly_price = monthly_cost / (1 - margin)
    setup_cost = values["delivery_hours"] * values["delivery_hourly_usd"]
    result = {
        "schema_version": "1.0", "engagement_id": engagement_id, "customer": customer,
        "model": model, "deployment_name": deployment_name, "region": region,
        "benchmark_provenance": source, "benchmark": {key: benchmark[key] for key in required_metrics},
        "acceptance_gates": gates,
        "quote": {
            "currency": "USD", "monthly_compute_cost_usd": _money(compute),
            "monthly_operations_cost_usd": _money(operations),
            "other_monthly_cost_usd": _money(values["other_monthly_usd"]),
            "monthly_total_cost_usd": _money(monthly_cost),
            "monthly_price_usd": _money(monthly_price),
            "setup_labor_cost_usd": _money(setup_cost),
            "target_gross_margin_fraction": str(margin),
            "price_basis": "Declared inputs, not a supplier quote; excludes taxes and unlisted costs",
        },
        "status": "review_required" if source == "operator_supplied_measurement" and all(gates.values())
                  else "not_ready",
        "claim_boundary": "Draft offer only. Source measurements are self-declared; no live deployment, customer acceptance, or savings verified.",
    }
    return result


def render_deployment(offer: dict) -> str:
    if offer["status"] != "review_required":
        raise OfferError("deployment handoff requires passing operator-supplied measurements")
    name = offer["deployment_name"]
    model = offer["model"]
    return f"""# Private AI inference reference deployment; cluster-internal only.
# Pin the image by digest and validate GPU capacity, driver and model license before applying.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
spec:
  replicas: 1
  strategy: {{type: Recreate}}
  selector:
    matchLabels: {{app: {name}}}
  template:
    metadata:
      labels: {{app: {name}}}
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/path: /metrics
        prometheus.io/port: "8000"
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - name: vllm
          image: vllm/vllm-openai:v0.30.0
          args: ["--model", "{model}", "--host", "0.0.0.0", "--port", "8000"]
          ports: [{{name: http, containerPort: 8000}}]
          resources:
            requests: {{cpu: "2", memory: 8Gi, nvidia.com/gpu: "1"}}
            limits: {{cpu: "8", memory: 24Gi, nvidia.com/gpu: "1"}}
          volumeMounts:
            - {{name: shm, mountPath: /dev/shm}}
          startupProbe:
            httpGet: {{path: /health, port: http}}
            periodSeconds: 10
            failureThreshold: 90
          readinessProbe:
            httpGet: {{path: /health, port: http}}
            periodSeconds: 5
          livenessProbe:
            httpGet: {{path: /health, port: http}}
            periodSeconds: 15
            failureThreshold: 3
      volumes:
        - name: shm
          emptyDir: {{medium: Memory, sizeLimit: 2Gi}}
---
apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  type: ClusterIP
  selector: {{app: {name}}}
  ports: [{{name: http, port: 8000, targetPort: http}}]
"""


def write_offer(offer: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "offer.json").write_text(json.dumps(offer, indent=2) + "\n")
    lines = [f"# Draft private inference offer — {offer['engagement_id']}", "",
             f"Customer: {offer['customer']}", f"Model: `{offer['model']}`",
             f"Region: {offer['region']}", "",
             f"Setup labor cost basis: ${offer['quote']['setup_labor_cost_usd']}",
             f"Monthly operating cost basis: ${offer['quote']['monthly_total_cost_usd']}",
             f"Draft monthly price: ${offer['quote']['monthly_price_usd']}", "",
             "## Acceptance checks", ""]
    lines += [f"- {'PASS' if passed else 'FAIL'}: {name.replace('_', ' ')}"
              for name, passed in offer["acceptance_gates"].items()]
    lines += ["", "## Next delivery step", "",
              "Obtain customer approval, validate actual GPU capacity and image/model versions, deploy to a private cluster, then rerun the benchmark on the target workload.",
              "", offer["claim_boundary"], ""]
    (output / "proposal.md").write_text("\n".join(lines))
    if offer["status"] == "review_required":
        (output / "deployment.yaml").write_text(render_deployment(offer))
