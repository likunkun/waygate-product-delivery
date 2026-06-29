# V0.10 Feature Closure Gate - 01 Requirements

| Field | Value |
| --- | --- |
| Version | V0.10 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V0.10 Feature Closure Gate. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Record runtime feature closure validator implementation and test evidence. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Add artifact metadata and evidence-path closure requirements. | CR-001 |

## Business Goal

Require implementation completion claims to be backed by a formal gate and a version-specific closure artifact.

## Scope

### In Scope

- Run or require a formal closure gate after implementation work.
- Produce a version-specific closure artifact.
- Record coverage matrix range, latest test case, E2E coverage, high-risk subresults, negative scope guard results, and required commands.
- Record evidence integrity fields for secrets and controller state.
- Treat chat summaries and `progress.md` as summaries only, not acceptance evidence.
- Implement runtime closure artifact validation and local closure artifact recording.

### Out Of Scope

- Executing implementation commands to create the evidence; V0.10 validates recorded command evidence.
- Waygate intake automation.
- Direct controller state mutation.
- Replacing V0.9 Codex Goal handoff.

## Functional Requirements

| ID | Priority | Requirement | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | P0 | When implementation reaches completion, the workflow shall require a formal closure gate before completion can be claimed. | Gate requirement is documented and blocks natural-language-only completion. |
| FR-002 | P0 | When the formal gate passes, the workflow shall produce a version-specific closure artifact. | Closure artifact fields are defined and include `status=passed`, artifact root, artifact generation command, and E2E evidence paths. |
| FR-003 | P0 | When closure evidence is recorded, the artifact shall include `latest_test_case`, `matrix_range`, E2E-covered TC, user stories, and journeys. | Coverage fields are listed as required artifact fields. |
| FR-004 | P0 | When negative scope guard is evaluated, the artifact shall record whether future or out-of-scope capabilities were absent. | Negative scope guard result is required. |
| FR-005 | P0 | When evidence integrity is evaluated, the artifact shall record `secret_values_recorded=false`, `controller_session_modified=false`, and `created_fake_controller_state=false`. | Evidence integrity fields are required. |
| FR-006 | P0 | When completion is summarized in chat or `progress.md`, that summary shall not replace the closure artifact. | Requirements state that closure artifact is the acceptance evidence entry. |
| FR-007 | P1 | When a prior closure is superseded, the replacement shall be linked to the CR that caused it. | CR supersession is documented as a closure rule. |

Runtime acceptance:

- `ProductDeliveryWorkflow.record_feature_closure(closure_artifact)` validates the version-specific closure artifact against V0.9 handoff fields.
- Missing summary-only artifacts, invalid status, missing closure flag, mismatched `matrix_range` or `latest_test_case`, missing E2E/user story/journey fields, missing artifact metadata, failed high-risk subresults, failed negative scope guard, missing command output, unsafe integrity fields, and supersession without CR all block closure.
- Passing closure writes `.product-delivery/artifacts/feature-closure.md` and sets stage to `feature_closure_passed`.

## Non-Functional Requirements

| ID | Category | Requirement | Measurement |
| --- | --- | --- | --- |
| NFR-001 | Auditability | Closure evidence must be durable and reviewable. | Artifact contains required fields and references CR/FR/TASK/TC/REV. |
| NFR-002 | Evidence integrity | Completion evidence must not rely on modified controller state or fake state. | Integrity fields are recorded in the artifact. |
| NFR-003 | Traceability | Closure must connect coverage, commands, and scope guard results to the version. | Artifact includes version-specific flag, matrix range, and command list. |

## Branch And Gate Requirements

- UI projects must carry browser E2E and negative scope guard obligations from V0.8 and V0.9 into closure.
- Non-UI projects must carry API/service/CLI E2E or equivalent behavior evidence into closure.
- Formal closure runs after implementation and after Codex Goal handoff execution, not before handoff.
- Missing closure artifact blocks completion claims.

## Risks And Assumptions

- Risk: natural-language summaries are mistaken for evidence. Mitigation: require closure artifact as the acceptance evidence entry.
- Risk: future scope leaks into the implemented version. Mitigation: require negative scope guard results.
- Risk: controller state is manually changed or faked. Mitigation: require explicit evidence integrity fields.
- Assumption: V0.10 validates recorded closure evidence but does not itself execute implementation verification commands.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Runtime command names are deferred. | Keeps this package focused on closure contract. | Recorded |
| Assumption | Closure artifact may later be implemented as Markdown, JSON, or both. | Does not affect current requirements. | Recorded |
| Nice-to-know | Exact plugin command shape for formal gate remains future work. | No current blocker. | Track in V1 implementation planning |
