# Production architecture

The compiler is the deterministic authority inside a wider agentic workflow. Model-driven agents may extract requirements, identify contradictions, research current provider capabilities and propose options. They cannot silently approve assumptions, change financial formulas, claim a deployment or publish a proposal.

## Trust boundaries

- Treat RFPs, websites, uploaded documents and tool output as untrusted data.
- Keep tenant data, prompts, vector indexes, credentials and evidence isolated.
- Use workload identity and short-lived task-scoped authorization.
- Execute IaC and generated code inside kernel-isolated sandboxes.
- Bind approval to the exact input, plan, artifact digest and policy version.
- Retain sources, model/provider identity, prompt version, tool calls and costs.
- Re-evaluate after requirement, provider, price or architecture-policy changes.

## Durable workflow

Production should use a durable state machine with explicit retries and compensations: `Intake → Clarification → Options → Review → Validate → Price → Approve → Publish → Observe`. External writes require idempotency keys. A restart must not publish twice or lose an approval boundary.

## Model portability

Agent adapters should support Azure AI Foundry, OpenAI, Anthropic, NVIDIA NIM and an OpenAI-compatible router. Evaluation—not brand preference—selects models per extraction accuracy, groundedness, latency, cost and data-location requirement.
