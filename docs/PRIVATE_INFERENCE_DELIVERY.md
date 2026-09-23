# Private inference: deal to deployment

This is the first concrete service catalog item in the solution factory. It combines a customer workload request, a `gifp-bench`-compatible streaming benchmark, declared delivery costs and a single-GPU Kubernetes handoff. It produces a **draft offer** and acceptance gates. It does not send a quote, charge a card, change a cluster, or assert that a customer deployment occurred.

## Run the fictional example

```bash
python3 -m solution_factory.private_inference_cli \
  examples/private-inference-intake.json \
  examples/private-inference-benchmark.synthetic.json \
  --output /tmp/private-inference-offer
```

The example is marked `synthetic_fixture`; its status is `not_ready` even when its numerical gates pass. It creates `offer.json` and `proposal.md`, but deliberately withholds `deployment.yaml`.

## Bring an operator-supplied measurement

After a customer approves a test workload and an operator runs the [GPU Inference Platform benchmark](https://github.com/AAH20/gpu-inference-platform/blob/main/docs/PRODUCTION_PILOT.md) against an isolated endpoint, add `"provenance": "operator_supplied_measurement"` to its JSON report. The field is a declaration, **not cryptographic proof**; retain cluster, GPU, image digest, model revision, prompt set, date and raw telemetry separately. The report must use the same model as intake and include at least 30 requests. A failed request, insufficient throughput, excessive p95 latency or time to first token blocks the deployment handoff.

The offer compiler creates `deployment.yaml` only when the declared operator measurement passes. It still labels the offer `review_required`: a solutions engineer must review price assumptions, actual GPU fit, customer capacity, model license, security controls and contract terms before applying anything. The manifest is cluster-internal (`ClusterIP`) and has one replica, so it is not a highly available or internet-ready service. Pin the image by digest before use. The actual delivery path is:

```text
qualified customer request → operator benchmark → draft priced offer
→ human commercial approval → private cluster deployment
→ customer acceptance test → operations handoff → invoice
```

## Pricing and acceptance

`monthly_total_cost = GPU hourly rate × allocated hours × GPU count + operations hours × labor rate + other monthly cost`

`draft monthly price = monthly_total_cost / (1 - target gross margin)`

The example's $1/GPU-hour is a fictional assumption. The formula excludes taxes and any omitted network, storage, support, software and customer-acquisition costs. Setup labor is shown as a cost basis, not a customer price. Do not quote the computed target margin until all actual delivery costs are represented. Acceptance compares the supplied benchmark's successful requests per second, p95 end-to-end latency and p95 time to first token with the customer's intake thresholds. It does not evaluate answer quality, workload representativeness, availability or sustained load; those require separate customer tests before production sign-off.

## First paid pilot gate

One service integrator takes a real, consented private-inference requirement through approved quote, target-cluster deployment, measured acceptance and first paid invoice. Record engineer hours, quote turnaround, measured versus estimated GPU spend, deployment success, acceptance defects and realized project gross margin. Reuse the template only after this closes successfully; do not treat a generated proposal as a won deal.
