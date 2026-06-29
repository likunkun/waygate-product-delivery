# System Boundaries

## Purpose

This document defines how Product Delivery Workflow Agent relates to Waygate, Claude workflow, Codex goal, and Open Spec.

## Boundary Summary

| System | Owns | Does Not Own |
| --- | --- | --- |
| Product Delivery Workflow Agent | Product blueprint, architecture framing, roadmap, version Open Spec preparation, prototype review records, multi-agent scope review, test obligation audit, and handoff package. | Waygate core state machine, verifier execution, final acceptance, or implementation code changes. |
| Waygate | Requirements gate, Unit Plan gate, verifier evidence, final acceptance, approval artifacts, events, blocked/revise routing, and deterministic controller validation. | Early product exploration or subjective product strategy decisions. |
| Open Spec | Version requirements, specification, technical solution, test cases, and handoff documents. | Runtime orchestration or evidence execution. |
| Claude workflow | Optional multi-agent or multi-step execution automation. | Long-lived cross-tool audit source of truth. |
| Codex goal | Optional implementation completion loop for an approved version. | Product discovery, acceptance policy, or independent final approval. |

## Data Flow

```text
Product idea
  -> Product Delivery Workflow Agent
  -> product blueprint
  -> architecture brief
  -> roadmap
  -> version Open Spec package
  -> prototype review notes
  -> multi-agent review
  -> test obligation audit
  -> handoff package
  -> Waygate / Claude workflow / Codex goal
  -> verifier evidence and final acceptance
```

## Artifact Ownership

Product Delivery Workflow Agent should write its own artifacts first. It should not directly edit Waygate controller state. A future integration may generate inputs that Waygate can import through official CLI routes.

Suggested future artifact layout:

```text
product-delivery/
  product-brief.md
  architecture-brief.md
  roadmap.md
  versions/
    v1.0/
      openspec/
      prototypes/
      prototype-review.md
      multi-agent-scope-review.md
      test-obligation-audit.md
      handoff.md
```

## Gate Model

The project uses three levels of control:

| Level | Meaning | Examples |
| --- | --- | --- |
| Record | Capture exploration without pretending it is complete. | Product value, early architecture, prototype observations. |
| Advisory | Surface risks for human decision. | Multi-agent gap review, test-depth concerns, architecture risk. |
| Hard Gate | Block transition to a more committed stage. | Version freeze, implementation handoff, missing E2E coverage for critical journeys, final evidence. |

## Integration Policy

- Use Waygate as the control plane when a version is ready for formal Requirements, Unit Plan, Verifier, and Final Acceptance.
- Use Claude workflow when a stage benefits from scripted multi-agent execution.
- Use Codex goal when the version has enough approved scope and tests for implementation.
- Keep early product exploration outside Waygate hard validators until the version boundary is frozen.

