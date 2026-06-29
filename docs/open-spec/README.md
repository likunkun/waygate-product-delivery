# Open Spec Packages

This directory contains versioned Open Spec packages for the Product Delivery Agent Plugin roadmap.

| Version | Package | Goal |
| --- | --- | --- |
| V0.1 | [Roadmap And Product Definition](./v0.1-roadmap-and-product-definition/01-requirements.md) | Complete the product shape, capability boundary, version route, and skill allocation for the Codex-native Product Delivery Agent Plugin. |
| V0.2 | [Artifact And State Protocol](./v0.2-artifact-and-state-protocol/01-requirements.md) | Define the local state and artifact protocol the plugin will use. |
| V0.3 | [Local Skill Workflow Prototype](./v0.3-local-skill-workflow-prototype/01-requirements.md) | Validate the product delivery workflow with a repo or local skill before packaging a plugin. |
| V0.4 | [Skill Allocation And Review Gates](./v0.4-skill-allocation-and-review-gates/01-requirements.md) | Explicitly include the Waygate README recommended skills in the workflow. |
| V0.5 | [Hooks And Recovery Guardrails](./v0.5-hooks-and-recovery-guardrails/01-requirements.md) | Preserve workflow continuity across compaction, resume, and long sessions. |
| V0.6 | [UI Prototype Gate](./v0.6-ui-prototype-gate/01-requirements.md) | Provide local 1:1 HTML prototype confirmation for UI projects. |
| V0.7 | [Non-UI Behavior Contract Gate](./v0.7-non-ui-behavior-contract-gate/01-requirements.md) | Provide a behavior confirmation gate for non-UI projects. |
| V0.8 | [Test Coverage Audit](./v0.8-test-coverage-audit/01-requirements.md) | Confirm test obligations before implementation handoff. |
| V0.9 | [Codex Goal Handoff](./v0.9-codex-goal-handoff/01-requirements.md) | Generate a frozen version package that can be handed to implementation Codex. |
| V0.10 | [Feature Closure Gate](./v0.10-feature-closure-gate/01-requirements.md) | Require formal closure gate and a version-specific closure artifact after implementation. |
| V1.0 | [Codex Plugin Packaging](./v1.0-codex-plugin-packaging/01-requirements.md) | Package the stable workflow as an installable Codex plugin. |

## Rules

- V1 supports both UI and non-UI projects.
- Only UI projects use the local 1:1 HTML prototype gate.
- Non-UI projects use behavior contract confirmation.
- All projects pass product blueprint, version scope, test coverage audit, and Codex Goal handoff.
- Codex Goal handoff does not replace formal closure after implementation.
- Chat summaries and `progress.md` are summaries only; they do not replace the version-specific closure artifact.
- Plugin behavior is dormant until explicit project-level `start` and exits intervention after `stop`.
