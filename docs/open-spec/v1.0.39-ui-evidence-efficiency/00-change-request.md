# V1.0.39 Change Request

Status: approved

## Problem

UI delivery repeats collection, serialization, hashing, pixel work, and reviewer ingestion for the same runtime facts. The runtime validates evidence but does not provide a canonical capture protocol, so target projects assemble several overlapping payloads manually.

## Approved Change

Introduce a trusted raw capture layer and derive independent gate projections from it. Add non-closure iteration feedback, automatic standard/strict classification, same-build evidence reuse, final evidence aggregation, batched post-implementation review, and performance telemetry.

## Preserved Invariants

- Lifecycle request schema remains `v1` and its actions do not change.
- Closure schema remains `v0.11`.
- Product baseline and test coverage remain the only two formal user confirmations.
- UI closure still requires role-accurate ordinary-path full-stack E2E, semantic/visual conformance, independent review, and canonical validation.
- Non-UI deliveries are unchanged.

## Non-Goals

- No closure-valid fast/patch lane.
- No cross-build passing-result inheritance.
- No weaker pixel, geometry, actor, ordinary-path, or business-API rules.
- No bundled Playwright dependency, OpenCode target, or lifecycle action.
- No automatic migration of active pre-1.0.39 deliveries.

## Supersession

This CR adds a narrow performance-and-trust hardening exception to the post-1.0 patch policy. It does not supersede historical delivery evidence or recovery contracts.
