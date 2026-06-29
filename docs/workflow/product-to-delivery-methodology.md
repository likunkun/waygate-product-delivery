# Product-To-Delivery Methodology

## Overview

This methodology turns product intent into implementation-ready version work. It should stay flexible during exploration and become strict only at commitment points.

The workflow has eight phases:

1. Product Blueprint
2. Architecture Framing
3. Roadmap Planning
4. Version Open Spec
5. Prototype Review
6. Multi-Agent Scope Review
7. Test Obligation Audit
8. Implementation And Acceptance Handoff

## Phase 1 - Product Blueprint

Purpose: clarify why the product exists before discussing modules or tickets.

Inputs:

- user idea;
- target audience;
- known pain points;
- known constraints.

Outputs:

- product value statement;
- target users;
- key user jobs;
- current non-goals;
- success and failure signals.

Gate type: record plus human confirmation. This is not a hard deterministic gate.

Advisory checks:

- unclear target user;
- solution described before problem;
- no explicit non-goals;
- success criteria are only implementation tasks.

## Phase 2 - Architecture Framing

Purpose: establish technical shape and constraints before roadmap planning.

Inputs:

- approved product blueprint;
- existing systems or target repository notes;
- runtime and integration constraints.

Outputs:

- architecture brief;
- module boundaries;
- main data flows;
- integration assumptions;
- operational risks.

Gate type: advisory review. The phase should surface risks but should not block just because architecture is not final.

## Phase 3 - Roadmap Planning

Purpose: split product capability into versions and prevent future backlog from contaminating the current version.

Inputs:

- product blueprint;
- architecture brief;
- known constraints.

Outputs:

- roadmap;
- version list;
- current-version objective;
- future backlog;
- version success criteria.

Gate type: semi-hard. A version cannot start until current-version goals, non-goals, and acceptance focus are explicit.

## Phase 4 - Version Open Spec

Purpose: create the first structured contract for a version.

Inputs:

- selected version from roadmap;
- product blueprint and architecture brief;
- current-version objective and non-goals.

Outputs:

- Open Spec requirements document;
- scope boundary;
- acceptance criteria;
- initial user tasks;
- initial journeys;
- risks and open questions.

Gate type: hard at version-freeze boundary. The version must have structured scope and acceptance artifacts before implementation planning.

## Phase 5 - Prototype Review

Purpose: use a 1:1 local HTML prototype to expose missing requirements and user scenarios before implementation.

Inputs:

- version Open Spec package;
- target user tasks;
- visible surface list.

Outputs:

- local HTML prototype;
- prototype review notes;
- user scenario corrections;
- missing scope items;
- accepted prototype limitations.

Gate type: human review first, structured traceability second. If the version includes UI/Web behavior, the prototype should map surfaces to user tasks, ACs, and journeys.

## Phase 6 - Multi-Agent Scope Review

Purpose: use independent agents to challenge the version scope and scenario coverage.

Inputs:

- Open Spec package;
- prototype review notes;
- architecture brief;
- roadmap scope boundary.

Outputs:

- missing scenario candidates;
- ambiguity list;
- out-of-scope risks;
- proposed changes requiring human approval.

Gate type: advisory. Agents cannot approve, reject, or silently change scope. Findings must become either accepted changes, backlog items, or rejected risks.

## Phase 7 - Test Obligation Audit

Purpose: verify that planned tests cover product behavior, especially user stories, user journeys, and failure paths.

Inputs:

- approved version scope;
- user stories;
- journeys;
- failure paths;
- test cases;
- prototype review obligations.

Outputs:

- test obligation matrix;
- E2E coverage map;
- known uncovered obligations;
- structured exemptions;
- advisory risks.

Gate type: mixed.

Hard failures:

- active user story has no mapped test or accepted exemption;
- critical user journey lacks E2E coverage or accepted exemption;
- required failure path lacks negative, recovery, or E2E coverage;
- test case references unknown requirement, journey, or user task;
- aggregate test command has no per-case proof.

Advisory risks:

- test level may be too shallow;
- support unit may hide product behavior;
- failure path taxonomy may be incomplete;
- natural-language risks may need more negative or recovery tests.

## Phase 8 - Implementation And Acceptance Handoff

Purpose: hand a frozen version to implementation without losing product intent.

Inputs:

- approved Open Spec package;
- prototype review notes;
- test obligation audit;
- architecture brief;
- roadmap version boundary.

Outputs:

- Waygate intake package, Claude workflow prompt, or Codex goal setup;
- implementation success criteria;
- required verification commands;
- evidence expectations;
- final acceptance checklist.

Gate type: hard. No implementation handoff should happen until scope, prototype obligations, and test obligations are approved or explicitly exempted.

## Operating Rule

Every phase is recorded. Only commitment boundaries are hard-gated. This keeps discovery flexible while making implementation and acceptance auditable.

