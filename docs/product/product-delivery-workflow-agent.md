# Product Delivery Workflow Agent

## Product Positioning

Product Delivery Workflow Agent is an upper-layer workflow agent for turning a product idea into an approved, test-covered, implementation-ready version package. It is built around a practical working method:

1. discuss product value and blueprint;
2. discuss technical architecture;
3. expand capabilities into roadmap and version planning;
4. drive each version through Open Spec, local prototype review, multi-agent scope review, test obligation audit, implementation handoff, and final evidence review.

The agent does not replace Waygate. It prepares better product and version artifacts before Waygate or an implementation backend takes over.

## Target Users

- Product-minded developers using AI agents to build full product versions.
- Solo builders who need a repeatable product-to-implementation method.
- Technical leads who want agent work to remain tied to product value, user journeys, and evidence.
- Teams that already use Waygate, Open Spec, Claude workflow, or Codex goal but need a cleaner upper-layer operating model.

## Value Proposition

The agent reduces the gap between "agent wrote code" and "the product version matches intent." It does this by forcing product thinking to appear before implementation:

- product value and non-goals are recorded before scope expands;
- architecture is discussed before module-level work begins;
- roadmap separates current-version commitments from later backlog;
- local 1:1 HTML prototypes expose missing user scenarios early;
- multi-agent review surfaces scope and journey gaps;
- test obligation audit checks user stories, user journeys, and failure paths before implementation handoff.

## Non-Goals

- It is not a code generation tool.
- It is not a replacement for Waygate final evidence gates.
- It does not directly mutate Waygate `session.json` or approval artifacts.
- It does not claim to prove complete real-world test coverage.
- It does not remove human product judgment from prototype and scope review.

## Success Criteria

The product succeeds when a user can:

- turn a product idea into a structured product blueprint;
- turn the blueprint into architecture and roadmap;
- start a version with an Open Spec package;
- review a local HTML prototype and feed findings back into requirements;
- use multi-agent review to detect likely missing scenarios;
- audit whether tests cover user stories, journeys, and failure paths;
- hand a frozen version to Waygate, Claude workflow, or Codex goal with clear scope and evidence expectations.

