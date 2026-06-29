# Product Delivery Agent Plugin Roadmap And Version Plan

This roadmap describes the planned evolution of the Waygate Product Delivery Agent as a Codex-native agent plugin. Version labels are planning labels, not release promises.

## Roadmap

Product shape: Codex-native Product Delivery Agent Plugin.

The plugin is dormant by default. It only enters product delivery mode after the user explicitly starts it for a project.

Core route:

1. Turn the methodology into an executable roadmap.
2. Define the local artifact and state protocol.
3. Validate the main workflow with a repo or local skill.
4. Add hooks to preserve continuity across compaction, resume, and long sessions.
5. Package the stable workflow as a Codex plugin.

Key rules:

- V1 supports both UI and non-UI projects.
- Only UI projects enable a local 1:1 HTML prototype gate.
- Non-UI projects use a behavior contract confirmation gate instead of an HTML prototype.
- Every project must pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Waygate's recommended baseline skills must be assigned to the relevant workflow stages.
- V1 produces roadmap and version-planning artifacts first; implementation design, detailed interfaces, and runtime automation come later.

## Version Plan

### V0.1 - Roadmap And Product Definition

Goal: define the product shape, capability boundary, version route, and skill allocation.

Scope:

- Define the product as a Codex-native Agent Plugin.
- Define an explicit project-level `start` and `stop` switch.
- Define the UI and non-UI project branches.
- Map the main flow from product idea to Codex Goal handoff.
- Map Waygate baseline skills to workflow stages.
- Produce roadmap and version planning only; do not enter implementation design.

### V0.2 - Artifact And State Protocol

Goal: define the local state and artifact protocol the plugin will use.

Scope:

- Define the `.product-delivery/` workspace.
- Define `state.json` responsibilities for stage, project type, confirmation points, and artifact paths.
- Define the core document templates:
  - product brief
  - version scope
  - UI prototype review
  - non-UI behavior contract
  - test coverage audit
  - handoff
- Define that state files take precedence over chat context.

### V0.3 - Local Skill Workflow Prototype

Goal: validate the product delivery workflow with a repo or local skill before packaging a plugin.

Scope:

- Support `start`, `status`, `pause`, `resume`, and `stop`.
- Guide the user through product blueprint, version scope, and project type selection.
- Route UI projects into prototype confirmation.
- Route non-UI projects into behavior contract confirmation.
- Generate a test coverage audit and Codex Goal handoff draft.

### V0.4 - Skill Allocation And Review Gates

Goal: explicitly include the Waygate README recommended skills in the workflow.

Skill allocation:

| Stage | Skills |
| --- | --- |
| Agent startup | `superpowers:using-superpowers` |
| Long-running work and recovery | `planning-with-files` |
| Product blueprint and scope shaping | `superpowers:brainstorming` |
| Version plan and implementation plan | `superpowers:writing-plans` |
| Test coverage audit | `test-strategy` or `testing-strategy` |
| UI, Web, and prototype work | `ui-ux-pro-max` |
| Browser-visible verification | `webapp-testing` |
| Pre-handoff evidence expectations | `superpowers:verification-before-completion` |
| Later implementation execution | `superpowers:test-driven-development`, `superpowers:executing-plans`, or `superpowers:subagent-driven-development` |
| Later rework and failure analysis | `superpowers:systematic-debugging` |
| Later refinement | `code-simplifier` |
| Later review loop | `superpowers:requesting-code-review` and `superpowers:receiving-code-review` |
| Document-specific work | `pdf`, `docx`, and `pptx` only when the corresponding file type is involved |

### V0.5 - Hooks And Recovery Guardrails

Goal: preserve workflow continuity across compaction, resume, and long sessions.

Scope:

- Inject the current state when an active project starts or resumes.
- Add current stage context before user prompts in active projects.
- Check that state is written before compaction.
- Check missing artifacts or confirmation records before stopping.
- Keep hooks silent for inactive projects.

### V0.6 - UI Prototype Gate

Goal: provide local 1:1 HTML prototype confirmation for UI projects.

Applies only when `project_type = ui`.

Scope:

- Generate or guide creation of a local HTML prototype.
- Cover key pages, states, and user journeys.
- Require user confirmation before test coverage audit.
- Carry prototype limitations into the handoff.

### V0.7 - Non-UI Behavior Contract Gate

Goal: provide a behavior confirmation gate for non-UI projects.

Applies only when `project_type = non_ui`.

Scope:

- Define API, CLI, service, or background job entry points.
- Define input/output contracts, error paths, state transitions, and boundaries.
- Require user confirmation before test coverage audit.

### V0.8 - Test Coverage Audit

Goal: confirm test obligations before implementation handoff.

Scope:

- Map user stories, journeys, failure paths, acceptance criteria, and planned tests.
- For UI projects, check browser E2E coverage or explicit exemptions.
- For non-UI projects, check API, service, or CLI E2E coverage or explicit exemptions.
- Block handoff when critical coverage is missing and not exempted.

### V0.9 - Codex Goal Handoff

Goal: generate a frozen version package that can be handed to implementation Codex.

Scope:

- Generate the handoff document.
- Generate a Codex Goal prompt.
- Include scope, non-goals, confirmation results, test obligations, verification commands, and prohibited work.
- Require scope changes after freeze to return to version scope confirmation.

### V1.0 - Codex Plugin Packaging

Goal: package the stable workflow as an installable Codex plugin.

Scope:

- Package the skill, hooks, templates, and validation scripts.
- Provide repo marketplace configuration.
- Keep the plugin dormant after installation.
- Enter active mode only after `start`.
- Exit intervention after `stop`.
- Preserve existing `.product-delivery/` artifacts across plugin upgrades.

## Assumptions

- The current phase only produces roadmap and version planning.
- Detailed implementation design, public interfaces, test plans, and file schemas are intentionally deferred.
- The first implementation handoff target is Codex Goal.
- Waygate integration is future work and does not directly mutate Waygate state in V1.
