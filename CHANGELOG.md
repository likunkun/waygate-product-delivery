# Changelog

## 1.0.12

- Limits Product Delivery user confirmation gates to scope freeze, UI prototype, and planned test coverage.
- Converts implementation launch authorization into canonical runtime evidence that auto-refreshes before handoff.
- Keeps the main flow moving through review, handoff, implementation, evidence, and closure unless a real blocker remains.

## 1.0.11

- Release consistency patch for the post-`1.0.10` line.
- Aligns the project roadmap around a compact future path:
  - `V1.0.x` remains a patch line for gate leaks, packaging failures, validator failures, and version drift.
  - `V1.1 多 Agent 评审编排产品化` becomes the next meaningful capability version.
  - `V1.1.x` absorbs orchestration support work instead of creating artificial Runtime API, schema, or dashboard versions.
  - `V2.0 外部工作流集成` remains deferred until local Product Delivery closure authority is stable.
- Keeps runtime behavior unchanged; the release focuses on version metadata, generated package alignment, and planning clarity.

## 1.0.10

- Current baseline before this cleanup.
- Provides the Waygate Product Delivery package under `plugins/waygate-product-delivery/`.
- Keeps canonical closure validation, transition journal requirements, and split multi-agent test coverage / test implementation gates.
