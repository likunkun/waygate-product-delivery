"""Versioned production responsibilities, stage plans and evidence contracts.

These functions perform no I/O. The host owns identity, process isolation,
file-content verification and the final integration of staged changes. A
producer's ``ready_for_integration`` claim never passes a review or a gate.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any


ROLE_CATALOG_VERSION = "1.2.0"
STAGE_PROFILE_VERSION = "1.2.0"
RUNTIME_POLICY = {"timeout_seconds": 1800, "max_recovery": 1,
                  "max_revision_rounds": 1, "model_control": "host_managed"}
_PERMISSIONS = {"read": ["role_brief", "input_snapshot_refs"],
                "write": ["staging_artifacts", "member_result_return"],
                "canonical_write": False}
_FORBIDDEN = ["change_scope", "change_TASK_status", "update_Goal", "close_delivery",
              "approve_review", "write_canonical_artifact", "write_outside_allowed_paths",
              "expand_input_scope", "delegate_work", "select_model", "publish_or_deploy"]


class ProductionProfileError(ValueError):
    """A production definition, dispatch brief or result violates its contract."""


def stable_hash(value: Any) -> str:
    """Hash canonical JSON, rejecting values that JSON cannot faithfully bind."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ProductionProfileError("contract must contain finite JSON values") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


_STRING = {"type": "string", "minLength": 1}
_STRINGS = {"type": "array", "items": _STRING}
_RESULT_PROPERTIES = {
    "task_hash": _STRING, "input_snapshot_hash": _STRING, "role_ids": _STRINGS,
    "status": {"enum": ["ready_for_integration", "needs_input", "needs_rework", "failed"]},
    "artifacts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "required": ["path", "sha256", "artifact_type"],
        "properties": {"path": _STRING, "sha256": _STRING, "artifact_type": _STRING}}},
    "changes": {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "required": ["path", "operation", "base_sha256", "result_sha256", "staged_path"],
        "properties": {"path": _STRING, "operation": {"enum": ["add", "modify", "delete"]},
                       "base_sha256": {"type": ["string", "null"]},
                       "result_sha256": {"type": ["string", "null"]},
                       "staged_path": {"type": ["string", "null"]}}}},
    "check_records": {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "required": ["check_id", "outcome", "reason", "evidence_refs"],
        "properties": {"check_id": _STRING, "reason": _STRING, "evidence_refs": _STRINGS,
                       "outcome": {"enum": ["satisfied", "blocked", "not_applicable"]}}}},
    "completion_evidence": {"type": "object", "additionalProperties": {
        "type": "array", "minItems": 1, "items": _STRING}},
    "risks": _STRINGS, "blockers": _STRINGS, "unresolved_questions": _STRINGS,
    "handoff": _STRING,
    "agent_id": {"type": ["string", "null"]},
    "spawn_source": {"type": ["string", "null"]},
    "identity_kind": {"enum": ["spawned", "simulated"]},
    "simulated_identity": {"type": ["string", "null"]},
}
_RESULT_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
                  "additionalProperties": False,
                  "required": [key for key in _RESULT_PROPERTIES if key not in {
                      "agent_id", "spawn_source", "identity_kind", "simulated_identity"}],
                  "properties": _RESULT_PROPERTIES}


def _definition_hash(card: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in card.items()
                        if key not in {"definition_hash", "template_hash", "provenance"}})


def _template_hash(card: dict[str, Any]) -> str:
    return stable_hash({"task_format": "production-work-package-v1.2", "instructions": {
        key: value for key, value in card.items()
        if key not in {"definition_hash", "template_hash", "provenance", "display_name"}}})


def _card(name: str, display_name: str, mission: str, inputs: list[str], optional: list[str],
          steps: list[str], checks: list[str], outputs: list[str], evidence: list[str],
          escalation: list[str], rubric: list[str], examples: dict[str, str]) -> dict[str, Any]:
    role_id = "production." + name
    card = {
        "role_id": role_id, "role_version": ROLE_CATALOG_VERSION, "display_name": display_name,
        "mission": mission,
        "when_to_invoke": "Only when the active stage profile assigns this responsibility to an approved work package.",
        "scope": outputs,
        "non_goals": ["Approve the product baseline or a review gate.",
                      "Advance TASK, Goal, delivery state, or formal closure.",
                      "Broaden the approved work package or operate a deployment environment."],
        "required_inputs": inputs, "optional_inputs": optional,
        "task_steps": steps + [
            "Verify input hashes against the bound snapshot before interpreting the source.",
            "Write only staged files; return exact destination paths and before/after hashes for integration.",
            "Record every mandatory check with a concrete reason and bound evidence; expose missing inputs explicitly."],
        "must_check": [role_id + "." + check for check in checks],
        "must_not_do": list(_FORBIDDEN), "required_capabilities": [
            "read_bound_artifact", "write_staging_artifact", "structured_output"],
        "permissions": copy.deepcopy(_PERMISSIONS), "required_outputs": outputs,
        "output_schema": copy.deepcopy(_RESULT_SCHEMA),
        "evidence_requirements": evidence + [
            "Each check cites an input snapshot path or declared output artifact, with a section anchor where useful.",
            "Completion references the produced artifact of the corresponding required output type.",
            "Execution claims require real logs; a written plan is not proof that a command or user journey passed."],
        "completion_criteria": ["Produce the staged " + item + " with a matching completion evidence reference."
                                for item in outputs] + [
            "All mandatory checks have justified positive outcomes and no blocker or question remains unresolved.",
            "The handoff identifies integration order and remaining reviewer responsibilities."],
        "escalation_conditions": escalation + [
            "A required source is unavailable, stale, or contradictory: needs_input with the source and owner.",
            "A correction needs a new destination, broader scope, or canonical mutation: stop and escalate to the coordinator."],
        "quality_rubric": rubric, "examples": examples,
        "runtime_policy": copy.deepcopy(RUNTIME_POLICY),
        "provenance": {"catalog_version": ROLE_CATALOG_VERSION,
                       "source": "waygate-product-delivery-v1.2-production-team"},
    }
    card["definition_hash"] = _definition_hash(card)
    card["template_hash"] = _template_hash(card)
    return card


# Each responsibility has its own method, source contract, evidence and worked
# examples. The coordinator is deliberately absent from this producer catalog.
_ROLE_CARDS = {card["role_id"]: card for card in [
    _card("product_requirements", "Product requirements",
          "Turn the approved user problem into a bounded product blueprint with observable acceptance outcomes.",
          ["product_intent"], ["prior_confirmations", "domain_research", "existing_product"],
          ["Identify the actor, job, current obstacle and intended observable result from explicit source statements.",
           "Separate required behavior, non-goals and assumptions; attach an original source to every scope decision.",
           "Write user stories and acceptance examples covering successful work, denied actions and recovery.",
           "Identify decisions that only the user or coordinator can make and report their effect on the proposed scope."],
          ["actor_and_job", "scope_traceability", "observable_acceptance", "assumption_ownership"],
          ["product_blueprint", "acceptance_criteria"],
          ["Every story maps an actor and intended outcome to the approved intent.",
           "Acceptance examples specify an initial state, action and independently observable outcome."],
          ["Two user statements imply incompatible acceptance outcomes.", "No authorized source identifies the target actor."],
          ["Faithfulness: each requirement has a source and no inferred feature becomes mandatory.",
           "Testability: success, rejection and recovery can be distinguished by observation.",
           "Boundedness: non-goals and unresolved owner decisions are visible."],
          {"pass": "For a CSV import, the blueprint names the finance operator, duplicate handling and a row-level rejection report, each traced to the supplied intent.",
           "insufficient": "A document saying 'make imports easy' lacks actors and observable outcomes; return needs_rework with missing acceptance examples.",
           "scope_violation": "Adding scheduled imports to an approved manual-only workflow broadens scope and must be proposed to the coordinator first.",
           "false_positive": "Do not flag the absence of scheduling when the source lists scheduling as a non-goal; cite that boundary.",
           "must_block": "One confirmed source demands duplicate overwrite and another forbids it; report needs_input instead of choosing a policy."}),
    _card("architecture_contract", "Architecture and contracts",
          "Define component boundaries and versioned contracts that implement the accepted product behavior without hidden coupling.",
          ["product_blueprint"], ["existing_architecture", "repository_inventory", "acceptance_criteria"],
          ["Map each accepted capability to an owning component and identify existing contracts it changes.",
           "Define request, response, error, identity and persistence boundaries including compatibility behavior.",
           "State invariants and failure ownership, then order implementation increments by concrete dependencies.",
           "Record alternatives and explain why the chosen boundary satisfies current constraints."],
          ["capability_mapping", "contract_completeness", "compatibility", "dependency_order"],
          ["architecture_contract", "version_plan"],
          ["Contract examples include invalid requests and retry behavior.",
           "The version plan names the dependent consumer for each breaking change."],
          ["An interface owner has not approved a required breaking change.", "Persistence invariants conflict with the accepted product outcome."],
          ["Coherence: every capability has one accountable component and explicit dependencies.",
           "Interoperability: schemas and errors are concrete enough for independent implementations.",
           "Change safety: rollout order and compatibility limits are explicit."],
          {"pass": "Define POST /imports with an idempotency key, a 202 job response, a stable 409 conflict and a backend-before-client implementation order.",
           "insufficient": "Boxes labelled frontend and backend without request schemas do not establish an implementable interface.",
           "scope_violation": "Replacing the database to simplify one import endpoint requires a new scope decision.",
           "false_positive": "A separate queue is unnecessary when the approved contract guarantees bounded synchronous work; cite the workload constraint.",
           "must_block": "The existing caller requires a field the proposed schema removes; escalate the incompatible consumer contract."}),
    _card("scenario_interaction", "Scenarios and interaction",
          "Produce the Open Spec behavior surface and complete user journeys, including visible exceptions and recovery.",
          ["product_blueprint", "architecture_contract"], ["acceptance_criteria", "existing_product", "domain_research"],
          ["Decompose each user story into start conditions, user actions, state transitions and observable outcomes.",
           "Write happy-path, permission, empty, failure, interruption and retry scenarios for the chosen project branch.",
           "Map each journey to architecture operations and identify unavailable or ambiguous transitions.",
           "Specify UI interaction states for a UI project or request/CLI behavior for a non-UI project."],
          ["journey_traceability", "transition_completeness", "visible_exceptions", "recovery_contract"],
          ["open_spec", "behavior_contract", "interaction_contract"],
          ["Every journey references a story and includes a visible final state.",
           "Denied and failed actions state whether data changed and how the user can recover."],
          ["A required journey has no permitted architecture operation.", "The product baseline does not define a destructive action's outcome."],
          ["Completeness: all user-visible exceptions have an explicit response.",
           "Consistency: transition names and data ownership agree across journeys.",
           "Executability: scenarios contain enough concrete detail to derive assertions."],
          {"pass": "An import journey covers upload, validating, completed-with-rejections and retry after network loss, with row-count outcomes for each state.",
           "insufficient": "A happy-path screenshot cannot explain permission denial or partial rejection recovery.",
           "scope_violation": "Inventing an administrator override changes the approved permission model.",
           "false_positive": "A CLI project need not include pointer-hover states; document that the non-UI behavior contract applies.",
           "must_block": "Cancel and retry can both commit the same import under the supplied contract; request an ownership decision."}),
    _card("ui_prototype", "UI prototype",
          "Create a reviewable UI prototype that expresses the accepted interaction contract across viewport and accessibility states.",
          ["product_blueprint", "interaction_contract"], ["design_system", "brand_assets", "architecture_contract"],
          ["Translate each interaction state into a navigable prototype with realistic content and clear action hierarchy.",
           "Define responsive layouts, keyboard focus, field labels and announced validation feedback.",
           "Exercise the critical journey and capture references for loading, empty, error and completion states.",
           "Document deliberate visual choices and constraints for implementation without claiming product acceptance."],
          ["state_coverage", "responsive_layout", "keyboard_access", "prototype_traceability"],
          ["ui_prototype", "prototype_evidence"],
          ["Evidence maps each prototype state to a specific interaction-contract transition.",
           "Viewport captures and keyboard observations identify the prototype revision tested."],
          ["A mandatory interaction cannot be expressed within the approved component constraints.", "Brand or accessibility requirements contradict the confirmed prototype direction."],
          ["Usability: primary actions and recovery paths are apparent with realistic data.",
           "Accessibility: focus, labels and feedback support the complete critical journey.",
           "Fidelity: captured states belong to the delivered prototype revision."],
          {"pass": "A staged import prototype includes keyboard file selection, row errors, a small-screen result list and revision-bound captures.",
           "insufficient": "A single polished desktop mockup omits loading and rejection states and cannot prove journey coverage.",
           "scope_violation": "Changing accepted copy from 'reject duplicate' to 'overwrite duplicate' alters behavior through a visual edit.",
           "false_positive": "A missing desktop sidebar on mobile is intentional when navigation remains available through the specified menu.",
           "must_block": "The supplied interaction contract gives no outcome for confirmation dismissal; report needs_input before inventing a destructive default."}),
    _card("test_design", "Test design",
          "Turn accepted stories and exceptions into an executable verification design that can distinguish real success from false passing evidence.",
          ["open_spec", "behavior_contract"], ["architecture_contract", "ui_prototype", "interaction_contract"],
          ["Assign at least one independent assertion to each story, critical journey and user-visible exception.",
           "Select unit, contract, integration and end-to-end coverage according to the failure boundary being tested.",
           "Specify fixtures, initial state, execution steps, observable assertions and cleanup requirements.",
           "Identify misleading mocks, empty execution and assertion-free paths that could produce false success."],
          ["story_coverage", "exception_coverage", "assertion_strength", "environment_feasibility"],
          ["test_design", "coverage_matrix"],
          ["Coverage rows cite Open Spec anchors and name exact observable assertions.",
           "End-to-end scenarios cover each required journey and visible exception, with explicit environment prerequisites."],
          ["An acceptance statement cannot be distinguished by an observable assertion.", "A required external environment is unavailable and no authorized substitute exists."],
          ["Traceability: every required behavior maps to an executable test.",
           "Discrimination: a realistic broken implementation would fail the assertion.",
           "Feasibility: fixtures and environment assumptions can actually be provided."],
          {"pass": "The duplicate-import test checks rejected row IDs, persisted row count and visible recovery text rather than only a 200 response.",
           "insufficient": "A checklist saying 'test errors' supplies neither fixtures nor expected state and cannot guide automation.",
           "scope_violation": "Rewriting the acceptance policy to avoid a difficult integration test changes the product baseline.",
           "false_positive": "A pure parser boundary case does not need a browser when end-to-end coverage already verifies the user-visible rejection.",
           "must_block": "The scenario requires cross-account denial but the environment supplies only one account and no identity fixture."}),
    _card("frontend", "Frontend implementation",
          "Implement the allocated client behavior against the accepted interaction, architecture and test contracts with staged, reviewable changes.",
          ["open_spec", "task_definition", "test_design", "architecture_contract"],
          ["ui_prototype", "interaction_contract", "frontend_source", "design_system"],
          ["Map the current TASK to client states, API calls and the exact approved destination files.",
           "Implement normal, loading, empty, denied and failure states using the accepted component conventions.",
           "Preserve semantic controls, keyboard interaction and responsive behavior while keeping state ownership explicit.",
           "Run the assigned client checks and record their actual outputs against the staged revision."],
          ["task_scope", "interaction_fidelity", "contract_errors", "client_verification"],
          ["frontend_changes", "frontend_verification"],
          ["Each changed client file maps to the current TASK and accepted interaction state.",
           "Verification logs distinguish executed tests from skipped or unavailable browser checks."],
          ["The client cannot implement the accepted behavior with the supplied API contract.", "Required visual evidence belongs to a different prototype revision."],
          ["Behavior: pending, error and recovery states match the accepted journey.",
           "Maintainability: component boundaries and state ownership fit the existing code.",
           "Evidence: checks inspect the staged implementation with meaningful assertions."],
          {"pass": "Implement duplicate-row errors and retry in the allocated import component, with keyboard navigation and an executed client test log.",
           "insufficient": "Compiling the bundle does not prove error rendering or a successful user journey.",
           "scope_violation": "Editing the shared authentication provider outside allocated paths requires a revised package.",
           "false_positive": "Do not label an intentional disabled submit state a defect when validation is pending under the interaction contract.",
           "must_block": "The contract has no error code for a required denial state; request an API decision instead of inventing a client-only policy."}),
    _card("backend", "Backend implementation",
          "Implement allocated service and persistence behavior while preserving declared invariants, compatibility and verifiable failure semantics.",
          ["open_spec", "task_definition", "test_design", "architecture_contract"],
          ["backend_source", "data_model", "security_requirements"],
          ["Identify the TASK's entry points, validation boundaries, persistence invariants and permitted files.",
           "Implement request handling, authorization, domain transitions and transactional behavior according to the contract.",
           "Handle retries, invalid data and external failures without silent partial writes or changed error semantics.",
           "Execute focused service and contract checks, and supply staged patches with their base hashes."],
          ["task_scope", "domain_invariants", "authorization_boundary", "service_verification"],
          ["backend_changes", "backend_verification"],
          ["Tests demonstrate persisted outcomes as well as response schemas and error codes.",
           "Retry and failure evidence identifies the invariant preserved and the exercised failure boundary."],
          ["Accepted behavior would violate an existing data invariant.", "The supplied contract does not define required authorization ownership."],
          ["Correctness: state transitions preserve invariants under retries and failure.",
           "Compatibility: consumers retain the agreed schema and error semantics.",
           "Verification: real domain outcomes are asserted beyond transport success."],
          {"pass": "A duplicate import returns the agreed conflict and leaves row count unchanged, verified by a real persistence test.",
           "insufficient": "A mocked repository returning success cannot establish transaction rollback behavior.",
           "scope_violation": "Introducing a new external queue requires an architecture decision and broader write scope.",
           "false_positive": "An explicitly idempotent duplicate returning the original job is correct when specified by the versioned contract.",
           "must_block": "The database schema cannot represent the accepted ownership boundary without a migration; report the dependency."}),
    _card("test_automation", "Test automation",
          "Implement the approved test design with strong assertions and trustworthy execution evidence tied to the current TASK.",
          ["task_definition", "test_design", "open_spec"],
          ["implementation_source", "coverage_matrix", "test_environment", "ui_prototype"],
          ["Map each allocated case to the design's setup, action and independently observable assertion.",
           "Implement real-boundary fixtures and limit mocks to the explicitly justified unavailable dependency.",
           "Exercise success, visible exceptions and retry paths; verify the case would detect a plausible regression.",
           "Execute the selected suite, preserve command and exit evidence, and expose skipped or blocked scenarios."],
          ["design_traceability", "assertion_discrimination", "fixture_realism", "execution_integrity"],
          ["test_changes", "test_execution_evidence"],
          ["Each new test references its design case and asserts a user or domain outcome.",
           "Execution evidence records command, exit status, collected count, failures and skipped cases."],
          ["A required fixture cannot be obtained from the declared environment.", "The implementation exposes no observable outcome for an approved assertion."],
          ["Sensitivity: realistic broken behavior fails the test.",
           "Reliability: fixture setup and cleanup isolate each case without hiding product faults.",
           "Honesty: collected, executed, skipped and failed cases are distinguishable."],
          {"pass": "Implement an import retry test that asserts one persisted job after two requests and retain the real passing run output.",
           "insufficient": "An assertion that a mock was called proves no accepted import outcome.",
           "scope_violation": "Changing production code to bypass authorization so the test can pass exceeds a test-only package.",
           "false_positive": "A deliberate permission-denial test passes when access is rejected; a non-2xx response alone is not a failing test.",
           "must_block": "The required browser is unavailable; return the environment blocker instead of fabricating a passing screenshot or run."}),
    _card("integration", "Integration preparation",
          "Reconcile the allocated producers' contracts and prepare a verified integration proposal without changing canonical state.",
          ["task_definition", "architecture_contract", "test_design"],
          ["frontend_changes", "backend_changes", "test_changes", "implementation_evidence", "dependency_results"],
          ["Read completed dependency results and match their revisions, interfaces and exact destination paths.",
           "Identify write collisions, incompatible assumptions and missing producer evidence before proposing integration order.",
           "Stage any explicitly allocated reconciliation and run the approved cross-component checks.",
           "Report the integration manifest, verification outcomes and issues requiring coordinator arbitration."],
          ["dependency_readiness", "interface_alignment", "change_manifest", "cross_component_verification"],
          ["integration_report", "integration_evidence"],
          ["The report identifies each contributing package, its output hash and its contract compatibility.",
           "Cross-component logs exercise real boundaries and name any unavailable dependency."],
          ["Two packages change the same destination incompatibly.", "A required producer is missing, stale or not ready for integration."],
          ["Consistency: all consumers and producers agree on a single contract revision.",
           "Reproducibility: integration order and exact changes are reviewable from the manifest.",
           "Separation of authority: a proposal does not claim a passed gate or completed TASK."],
          {"pass": "Reconcile a client expecting job_id with the matching backend schema and attach the executed import journey log for the staged combination.",
           "insufficient": "Two independent unit suites do not show that the client and service exchange compatible payloads.",
           "scope_violation": "Applying the proposal to canonical sources or marking TASK complete is reserved for the coordinator.",
           "false_positive": "Two packages reading the same schema have no write collision; distinguish shared input from conflicting destinations.",
           "must_block": "The backend producer returns an unresolved authorization blocker; do not relabel the combined work ready."}),
    _card("delivery_evidence", "Delivery evidence preparation",
          "Assemble a source-bound delivery evidence package that exposes coverage and outstanding risk without performing release or closure.",
          ["implementation_evidence", "test_results"],
          ["coverage_matrix", "review_results", "acceptance_criteria", "version_plan", "deployment_plan"],
          ["Inventory the current implementation, test runs and review decisions by revision and artifact hash.",
           "Map evidence to accepted stories, journeys, visible exceptions and delivery requirements.",
           "Separate verified behavior, accepted limitations and unresolved readiness questions.",
           "Prepare the release notes and coordinator checklist while leaving approval and formal closure unclaimed."],
          ["revision_consistency", "coverage_traceability", "risk_disclosure", "closure_boundary"],
          ["delivery_evidence", "release_notes"],
          ["Evidence references identify the tested implementation revision and command provenance.",
           "Release notes distinguish delivered behavior from deferred work and unresolved blockers."],
          ["Test and implementation evidence refer to different revisions.", "A mandatory journey lacks execution evidence or an explicit owner disposition."],
          ["Auditability: every readiness statement is supported by a concrete current artifact.",
           "Clarity: readers can identify remaining decisions and limitations without reconstructing the workflow.",
           "Authority: the package prepares but never substitutes for canonical closure."],
          {"pass": "Release notes cite the tested import revision, complete journey matrix and known file-size limit with its accepted disposition.",
           "insufficient": "A summary saying all tests passed without commands, revision or coverage cannot support readiness.",
           "scope_violation": "Writing the formal closure record or marking the delivery completed exceeds evidence preparation.",
           "false_positive": "An explicitly deferred export feature is not a delivery blocker for the import-only release.",
           "must_block": "The only browser evidence predates the final client changes; request current execution evidence."}),
    _card("domain_research", "Domain research",
          "Resolve an explicitly flagged domain uncertainty using bound sources and distinguish established facts from decisions needing an owner.",
          ["product_intent", "domain_sources"], ["product_blueprint", "prior_confirmations"],
          ["State the research question and the product decision it influences.",
           "Extract definitions, constraints and examples from supplied sources with date and applicability boundaries.",
           "Compare conflicting interpretations and explain their consequence for acceptance behavior.",
           "Return a cited domain brief with explicit unknowns and owner questions."],
          ["source_provenance", "applicability", "conflicting_claims", "decision_traceability"],
          ["domain_research"],
          ["Every factual claim cites a supplied source and its applicable jurisdiction, version or date.",
           "Unsupported interpretations are labelled questions rather than converted to requirements."],
          ["Sources disagree on a constraint affecting acceptance.", "The required domain source is absent from the input snapshot."],
          ["Accuracy: facts retain their source and applicability boundary.",
           "Decision utility: each finding names the product choice it informs.",
           "Restraint: uncertain interpretations remain explicit."],
          {"pass": "Explain the supplied accounting guide's decimal-rounding rule with a cited example and the affected import validation case.",
           "insufficient": "A generic statement that finance data must be accurate contains no source or applicable rule.",
           "scope_violation": "Browsing unrelated confidential repositories to settle an unanswered question expands input scope.",
           "false_positive": "A rule for archived accounts does not apply to active-account imports when the supplied guide separates them.",
           "must_block": "Two current policy documents prescribe different retention periods; request the accountable owner's interpretation."}),
    _card("data_migration", "Data migration",
          "Prepare an allocated data transition with compatibility, invariant and recovery evidence before any environment is changed.",
          ["architecture_contract", "data_model", "task_definition"], ["data_profile", "migration_history", "test_environment"],
          ["Compare source and target schemas and enumerate all transformations and irreversible information loss.",
           "Design ordered migration steps, compatibility windows, rollback or forward-repair behavior and validation queries.",
           "Implement only allocated migration artifacts and rehearse against authorized representative fixtures.",
           "Record row-count, key, nullability and ownership invariants before and after the rehearsal."],
          ["transformation_completeness", "data_invariants", "compatibility_window", "recovery_rehearsal"],
          ["migration_changes", "migration_evidence"],
          ["The rehearsal log includes input shape, transformed counts and invariant checks.",
           "Recovery instructions state any irreversible step and the coordinator decision required before use."],
          ["The migration loses data without an accepted retention decision.", "A required recovery path cannot be rehearsed with available fixtures."],
          ["Integrity: transformations preserve documented keys and ownership invariants.",
           "Operability: ordered steps and recovery are executable by an authorized owner.",
           "Evidence: representative edge cases are included in the rehearsal."],
          {"pass": "Stage a nullable job_id migration, backfill rehearsal and counts showing no orphaned imports, with a compatible rollback sequence.",
           "insufficient": "A forward SQL script without invariants or recovery evidence does not establish safe transition behavior.",
           "scope_violation": "Running the staged migration against production data requires separate operator authorization.",
           "false_positive": "A nullable transition column is intentional during a documented dual-version compatibility window.",
           "must_block": "Existing duplicate keys make the target uniqueness constraint impossible without a product data-loss decision."}),
    _card("security_engineering", "Security engineering",
          "Implement or specify allocated controls for the declared trust boundaries and provide abuse-case evidence without inventing compliance claims.",
          ["architecture_contract", "security_requirements"], ["task_definition", "open_spec", "implementation_source"],
          ["Identify actors, assets, entry points and trust transitions from the accepted architecture.",
           "Map concrete abuse cases to authorization, input validation, secret-handling and audit controls.",
           "Produce allocated control changes or specifications and verify the expected denial behavior.",
           "Document residual risk and missing control owners with evidence-backed impact."],
          ["trust_boundaries", "least_privilege", "abuse_case_controls", "sensitive_data_handling"],
          ["security_changes", "security_evidence"],
          ["Each control maps a specified threat to an observed or explicitly planned rejection outcome.",
           "Evidence redacts secrets and identifies the authorized local test scope."],
          ["The required authorization boundary has no accountable policy owner.", "A discovered credential or uncontrolled external target would require broader authorization."],
          ["Specificity: controls address an actual declared boundary and abuse case.",
           "Effectiveness: negative tests demonstrate denial without unwanted side effects.",
           "Proportion: residual risk is stated without unsupported compliance certification."],
          {"pass": "Stage an ownership check and a cross-account import test proving denial without disclosing another account's job metadata.",
           "insufficient": "A security checklist marked complete without a boundary-specific abuse case cannot support control effectiveness.",
           "scope_violation": "Probing an external production service outside the bound environment exceeds this package.",
           "false_positive": "A public health endpoint need not require login when the accepted trust model exposes no sensitive fields.",
           "must_block": "The supplied access policy assigns conflicting owners for the same import; request a policy decision."}),
    _card("performance_reliability", "Performance and reliability",
          "Establish and verify allocated workload, latency and failure-recovery behavior using explicit measurements and bounded environments.",
          ["architecture_contract", "reliability_requirements"], ["task_definition", "implementation_source", "test_environment", "workload_profile"],
          ["Translate supplied targets into workload size, concurrency, measurement window and success criteria.",
           "Identify bottlenecks and failure modes, then produce only allocated tuning or resilience changes.",
           "Run the declared benchmark or fault exercise while recording environment and baseline conditions.",
           "Compare distributions and recovery outcomes, reporting uncertainty and untested limits."],
          ["workload_definition", "measurement_validity", "failure_recovery", "resource_bounds"],
          ["reliability_changes", "reliability_evidence"],
          ["Measurements include workload, environment, revision and percentile or error-budget interpretation.",
           "Failure exercises document the injected fault and observed recovery without hidden manual repair."],
          ["A target has no measurable workload or time window.", "The assigned environment cannot safely reproduce the specified failure mode."],
          ["Validity: measurements answer the stated target under a declared workload.",
           "Resilience: recovery claims are supported by actual exercised faults.",
           "Transparency: extrapolation and environment limits are explicit."],
          {"pass": "Measure import p95 at the agreed concurrent workload and show bounded retry recovery after a local database disconnect.",
           "insufficient": "A single fast request does not establish a percentile target under concurrent load.",
           "scope_violation": "Launching a stress run against a shared production database is outside an allocated local benchmark.",
           "false_positive": "An occasional slow first request is not a p95 violation when the declared measurement window and warm-up exclude initialization.",
           "must_block": "The target says 'fast at scale' without concurrency or latency bounds; request a measurable requirement."}),
    _card("build_deployment", "Build and deployment preparation",
          "Prepare reproducible build and deployment artifacts with a verifiable rollback handoff while leaving actual publication to authorized operators.",
          ["architecture_contract", "deployment_requirements"], ["task_definition", "build_configuration", "implementation_evidence", "test_results"],
          ["Identify the runtime, dependency lock, required configuration and supported target environment.",
           "Stage allocated build or deployment configuration without embedding secrets or mutating live services.",
           "Run the declared build and local smoke checks, recording artifact identity and configuration assumptions.",
           "Prepare ordered deployment, verification and rollback instructions for the coordinator or operator."],
          ["reproducible_build", "configuration_contract", "smoke_verification", "rollback_handoff"],
          ["build_deployment_changes", "build_deployment_evidence"],
          ["Build evidence identifies source revision, dependency lock and resulting artifact digest.",
           "The handoff names required configuration keys, smoke checks and rollback target without secret values."],
          ["A build requires an unavailable secret or undocumented target configuration.", "The proposed package would publish externally or replace a live deployment."],
          ["Reproducibility: inputs and commands identify the exact built artifact.",
           "Operability: deployment verification and rollback steps have concrete outcomes.",
           "Boundary safety: staged preparation never masquerades as live deployment evidence."],
          {"pass": "Stage the container build and local smoke output, list required configuration names and provide the prior-image rollback procedure.",
           "insufficient": "A successful dependency install does not establish that the deployable artifact builds or starts.",
           "scope_violation": "Pushing the image to a public registry or replacing a live service is not preparation.",
           "false_positive": "A missing secret value is expected in a template when the required variable and authorized injection mechanism are documented.",
           "must_block": "The build can only succeed using an undocumented developer credential; request a supported configuration source."}),
]}

ROLE_IDS = tuple(_ROLE_CARDS)
CORE_ROLE_IDS = ROLE_IDS[:10]
CONDITIONAL_ROLE_IDS = ROLE_IDS[10:]
STAGES = ("product_definition", "architecture_version_planning", "open_spec_product_surface",
          "test_design", "implementation_execution", "delivery_preparation")
_STAGE_ROLES = {
    "product_definition": ["production.product_requirements"],
    "architecture_version_planning": ["production.architecture_contract"],
    "open_spec_product_surface": ["production.scenario_interaction"],
    "test_design": ["production.test_design"],
    "implementation_execution": ["production.backend", "production.test_automation", "production.integration"],
    "delivery_preparation": ["production.delivery_evidence"],
}
_STAGE_CONDITIONAL = {
    "product_definition": ["domain_research"],
    "architecture_version_planning": ["domain_research", "data_migration", "security_engineering", "performance_reliability", "build_deployment"],
    "open_spec_product_surface": ["domain_research", "security_engineering"],
    "test_design": ["security_engineering", "performance_reliability"],
    "implementation_execution": ["data_migration", "security_engineering", "performance_reliability", "build_deployment"],
    "delivery_preparation": ["security_engineering", "performance_reliability", "build_deployment"],
}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _strings(value: Any, name: str, *, empty: bool = False) -> list[str]:
    if (not isinstance(value, list) or (not value and not empty)
            or any(not _nonempty(item) for item in value)):
        raise ProductionProfileError(f"{name} must be a {'possibly empty ' if empty else 'nonempty '}string list")
    if len(set(value)) != len(value):
        raise ProductionProfileError(f"{name} contains duplicate values")
    return value


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ProductionProfileError(f"{field} requires a lowercase SHA-256 digest")
    return value


def _path(value: Any, *, write: bool = False) -> str:
    if (not _nonempty(value) or value != value.strip() or value.startswith("/")
            or any(char in value for char in "\\:*?[]#\x00")
            or any(ord(char) < 32 for char in value)
            or any(part in {"", ".", "..", ".git"} for part in value.split("/"))):
        raise ProductionProfileError("paths must name exact normalized relative files without traversal or globs")
    if write and (any(part in {".product-delivery", "canonical", ".codex", ".paseo"}
                      for part in value.split("/"))
                  or value.split("/")[-1] in {"TASK.md", "AGENTS.md", "Goal.md", "GOAL.md"}):
        raise ProductionProfileError("producer cannot write canonical or control files")
    return value


def get_production_role_card(role_id: str) -> dict[str, Any]:
    """Return an independent role card after validating its executable contract."""
    if not isinstance(role_id, str) or role_id not in _ROLE_CARDS:
        raise ProductionProfileError(f"unknown production role: {role_id}")
    card = copy.deepcopy(_ROLE_CARDS[role_id])
    for field in ("scope", "non_goals", "required_inputs", "task_steps", "must_check", "must_not_do",
                  "required_capabilities", "required_outputs", "evidence_requirements", "completion_criteria",
                  "escalation_conditions", "quality_rubric"):
        _strings(card.get(field), field)
    _strings(card.get("optional_inputs"), "optional_inputs", empty=True)
    if (card.get("role_id") != role_id or card.get("role_version") != ROLE_CATALOG_VERSION
            or not _nonempty(card.get("mission")) or not _nonempty(card.get("when_to_invoke"))
            or card.get("permissions") != _PERMISSIONS or card.get("runtime_policy") != RUNTIME_POLICY
            or card.get("output_schema") != _RESULT_SCHEMA
            or not isinstance(card.get("examples"), dict)
            or set(card["examples"]) != {"pass", "insufficient", "scope_violation", "false_positive", "must_block"}
            or any(not _nonempty(value) for value in card["examples"].values())):
        raise ProductionProfileError("production role card has an incomplete method or unsafe permissions")
    if card.get("definition_hash") != _definition_hash(card) or card.get("template_hash") != _template_hash(card):
        raise ProductionProfileError("production role definition or template hash is stale")
    return card


def get_stage_profile(stage: str, project_type: str = "non_ui") -> dict[str, Any]:
    """Return the fixed stage's mandatory responsibilities and dependency policy."""
    if not isinstance(stage, str) or stage not in STAGES or project_type not in ("ui", "non_ui"):
        raise ProductionProfileError("unknown production stage or project_type")
    roles = list(_STAGE_ROLES[stage])
    if project_type == "ui" and stage == "open_spec_product_surface":
        roles.append("production.ui_prototype")
    if project_type == "ui" and stage == "implementation_execution":
        roles.insert(0, "production.frontend")
    dependencies = {}
    if "production.ui_prototype" in roles:
        dependencies["production.ui_prototype"] = ["production.scenario_interaction"]
    if "production.integration" in roles:
        dependencies["production.integration"] = [role for role in roles if role != "production.integration"]
    index = STAGES.index(stage)
    return {"stage": stage, "profile_version": STAGE_PROFILE_VERSION, "project_type": project_type,
            "required_role_ids": roles,
            "conditional_roles": {flag: "production." + flag for flag in _STAGE_CONDITIONAL[stage]},
            "depends_on": [STAGES[index - 1]] if index else [],
            "role_dependencies": dependencies, "max_parallel": 2}


def _effective_profile(stage: str, context: dict[str, Any]) -> dict[str, Any]:
    profile = get_stage_profile(stage, context.get("project_type"))
    flags = _strings(context.get("condition_flags", []), "condition_flags", empty=True)
    known = {role.removeprefix("production.") for role in CONDITIONAL_ROLE_IDS}
    if set(flags) - known:
        raise ProductionProfileError("unknown conditional production flag")
    if stage == "implementation_execution" and "implementation_roles" in context:
        selected = _strings(context["implementation_roles"], "implementation_roles")
        permitted = {"production.frontend", "production.backend", "production.test_automation"}
        if set(selected) - permitted or not set(selected) & {"production.frontend", "production.backend"}:
            raise ProductionProfileError("implementation_roles must select frontend/backend and optional test automation")
        if context["project_type"] != "ui" and "production.frontend" in selected:
            raise ProductionProfileError("frontend implementation requires the UI project branch")
        profile["required_role_ids"] = [role for role in (
            "production.frontend", "production.backend", "production.test_automation") if role in selected]
        profile["required_role_ids"].append("production.integration")
    profile["required_role_ids"] += [role for flag, role in profile["conditional_roles"].items() if flag in flags]
    if stage == "implementation_execution":
        profile["role_dependencies"]["production.integration"] = [
            role for role in profile["required_role_ids"] if role != "production.integration"]
    return profile


def _make_task(stage: str, context: dict[str, Any], package: dict[str, Any],
               profile: dict[str, Any]) -> dict[str, Any]:
    for field in ("delivery_id", "feature_slug"):
        if not _nonempty(context.get(field)):
            raise ProductionProfileError(f"{field} is required")
    _digest(context.get("input_snapshot_hash"), "input_snapshot_hash")
    if stage == "implementation_execution" and not _nonempty(context.get("task_id")):
        raise ProductionProfileError("implementation execution requires the current task_id")
    if "task_id" in context and context["task_id"] is not None and not _nonempty(context["task_id"]):
        raise ProductionProfileError("task_id must be a nonempty string when supplied")
    if not isinstance(package, dict) or not _nonempty(package.get("work_package_id")):
        raise ProductionProfileError("work_package_id is required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", package["work_package_id"]):
        raise ProductionProfileError("work_package_id must be a safe identifier")
    roles = _strings(package.get("role_ids"), "role_ids")
    if set(roles) - set(profile["required_role_ids"]):
        raise ProductionProfileError("package contains a role not enabled by this stage")
    dependencies = _strings(package.get("depends_on", []), "depends_on", empty=True)
    paths = _strings(package.get("allowed_write_paths"), "allowed_write_paths", empty=True)
    for path in paths:
        _path(path, write=True)
    cards = [get_production_role_card(role) for role in roles]
    refs = context.get("input_refs")
    if not isinstance(refs, dict):
        raise ProductionProfileError("input_refs must map logical inputs to bound files")
    required = {key for card in cards for key in card["required_inputs"]}
    if required - set(refs):
        raise ProductionProfileError("missing required inputs: " + ", ".join(sorted(required - set(refs))))
    optional = {key for card in cards for key in card["optional_inputs"]}
    selected = {}
    for key in sorted(required | (optional & set(refs))):
        ref = refs[key]
        if not isinstance(ref, dict):
            raise ProductionProfileError(f"input ref {key} must bind a file and hash")
        _path(ref.get("ref"))
        _digest(ref.get("sha256"), "input_refs." + key + ".sha256")
        if ref.get("project_type", "shared") not in ("shared", context["project_type"]):
            raise ProductionProfileError("input reference belongs to another project branch")
        selected[key] = {"ref": ref["ref"], "sha256": ref["sha256"]}
    outputs = list(dict.fromkeys(output for card in cards for output in card["required_outputs"]))
    extra_outputs = _strings(package.get("required_outputs", []), "required_outputs", empty=True)
    outputs += [output for output in extra_outputs if output not in outputs]
    for output in outputs:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", output):
            raise ProductionProfileError("required_outputs must be artifact type identifiers")
    task = {key: copy.deepcopy(context[key]) for key in (
        "delivery_id", "feature_slug", "project_type", "input_snapshot_hash")}
    task.update({"stage": stage, "profile_version": STAGE_PROFILE_VERSION,
                 "profile_hash": stable_hash(profile), "work_package_id": package["work_package_id"],
                 "role_ids": list(roles), "role_cards": cards,
                 "role_definition_hashes": {card["role_id"]: card["definition_hash"] for card in cards},
                 "task_template_hashes": {card["role_id"]: card["template_hash"] for card in cards},
                 "must_check": list(dict.fromkeys(check for card in cards for check in card["must_check"])),
                 "required_outputs": outputs, "required_inputs": sorted(required), "input_refs": selected,
                 "depends_on": sorted(dependencies), "allowed_write_paths": list(paths),
                 "permissions": copy.deepcopy(_PERMISSIONS), "runtime_policy": copy.deepcopy(RUNTIME_POLICY),
                 "output_schema": copy.deepcopy(_RESULT_SCHEMA),
                 "condition_flags": sorted(context.get("condition_flags", []))})
    if context.get("task_id") is not None:
        task["task_id"] = context["task_id"]
    if stage == "implementation_execution" and "implementation_roles" in context:
        task["implementation_roles"] = sorted(context["implementation_roles"])
    task["task_hash"] = stable_hash(task)
    return task


def build_stage_tasks(stage: str, context: dict[str, Any],
                      work_packages: list[dict[str, Any]]) -> dict[str, Any]:
    """Bind complete stage work to concrete packages and an acyclic dependency graph."""
    if not isinstance(context, dict) or not isinstance(work_packages, list) or not work_packages:
        raise ProductionProfileError("stage context and nonempty work_packages are required")
    profile = _effective_profile(stage, context)
    tasks = [_make_task(stage, context, package, profile) for package in work_packages]
    by_id = {task["work_package_id"]: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ProductionProfileError("duplicate work_package_id")
    assigned = {role for task in tasks for role in task["role_ids"]}
    if assigned != set(profile["required_role_ids"]):
        raise ProductionProfileError("work packages must cover every required role: " +
                                     ", ".join(sorted(set(profile["required_role_ids"]) - assigned)))
    for task in tasks:
        dependencies = set(task["depends_on"])
        for role in task["role_ids"]:
            upstream = set(profile["role_dependencies"].get(role, []))
            dependencies.update(other["work_package_id"] for other in tasks
                                if other is not task and upstream & set(other["role_ids"]))
        if task["work_package_id"] in dependencies or dependencies - set(by_id):
            raise ProductionProfileError("dependency refers to itself or an unknown work package")
        task["depends_on"] = sorted(dependencies)
        task["task_hash"] = stable_hash({key: value for key, value in task.items() if key != "task_hash"})
    remaining = set(by_id)
    complete: set[str] = set()
    while remaining:
        ready = {key for key in remaining if set(by_id[key]["depends_on"]) <= complete}
        if not ready:
            raise ProductionProfileError("work package dependency graph contains a cycle")
        complete.update(ready)
        remaining -= ready
    return {"profile": profile, "tasks": tasks}


def _schema_check(value: Any, schema: dict[str, Any], name: str = "result") -> None:
    types = {"object": dict, "array": list, "string": str, "null": type(None)}
    declared = schema.get("type")
    if declared:
        names = declared if isinstance(declared, list) else [declared]
        if not any(isinstance(value, types[item]) for item in names):
            raise ProductionProfileError(f"{name} has wrong type")
    if "enum" in schema and value not in schema["enum"]:
        raise ProductionProfileError(f"{name} has unsupported value")
    if isinstance(value, str) and schema.get("minLength") and not value.strip():
        raise ProductionProfileError(f"{name} cannot be empty")
    if isinstance(value, dict):
        if set(schema.get("required", [])) - set(value):
            raise ProductionProfileError(f"{name} is missing required fields")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        if extra is False and set(value) - set(properties):
            raise ProductionProfileError(f"{name} contains fields outside the output contract")
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProductionProfileError(f"{name} requires string property names")
            if key in properties:
                _schema_check(item, properties[key], name + "." + key)
            elif isinstance(extra, dict):
                _schema_check(item, extra, name + "." + key)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ProductionProfileError(f"{name} lacks required entries")
        if "items" in schema:
            for index, item in enumerate(value):
                _schema_check(item, schema["items"], f"{name}[{index}]")


def _evidence(refs: Any, allowed: set[str], *, empty: bool = False) -> None:
    for ref in _strings(refs, "evidence_refs", empty=empty):
        if ref not in allowed and ref.partition("#")[0] not in allowed:
            raise ProductionProfileError("evidence references an unbound input or undeclared output")


def validate_production_result(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Validate claims against the authentic brief; return a detached normalized result.

    Hash syntax and manifest correspondence are checked here. The execution
    engine must verify real file bytes, staging containment, input freshness,
    producer identity and authorization before applying any change.
    """
    if not isinstance(task, dict) or not isinstance(result, dict):
        raise ProductionProfileError("a bound task and structured production result are required")
    profile = _effective_profile(task.get("stage"), task)
    expected = _make_task(task["stage"], task, task, profile)
    if expected != task:
        raise ProductionProfileError("production task content, role instructions or task hash is stale")
    _schema_check(result, _RESULT_SCHEMA)
    for field in ("task_hash", "input_snapshot_hash", "role_ids"):
        if result[field] != task[field]:
            raise ProductionProfileError(f"{field} does not match the bound production task")
    for field in ("risks", "blockers", "unresolved_questions"):
        _strings(result[field], field, empty=True)
    ready = result["status"] == "ready_for_integration"
    if ready and (result["blockers"] or result["unresolved_questions"]):
        raise ProductionProfileError("ready_for_integration cannot contain unresolved blockers or questions")
    if not ready and not (result["blockers"] or result["unresolved_questions"]):
        raise ProductionProfileError("an incomplete result must explain its blocker or unresolved question")
    artifacts: dict[str, dict[str, Any]] = {}
    outputs: dict[str, set[str]] = {}
    for row in result["artifacts"]:
        path = _path(row["path"])
        _digest(row["sha256"], "artifact.sha256")
        if path in artifacts:
            raise ProductionProfileError("duplicate artifact path")
        artifacts[path] = row
        outputs.setdefault(row["artifact_type"], set()).add(path)
    required_outputs = set(task["required_outputs"])
    if ready and required_outputs - set(outputs):
        raise ProductionProfileError("ready_for_integration is missing a required output artifact")
    changed = set()
    for change in result["changes"]:
        path = _path(change["path"], write=True)
        if path not in task["allowed_write_paths"] or path in changed:
            raise ProductionProfileError("change path is duplicated or outside the allocated exact write paths")
        changed.add(path)
        if change["operation"] == "add":
            if change["base_sha256"] is not None:
                raise ProductionProfileError("add must not claim an existing base hash")
        else:
            _digest(change["base_sha256"], "change.base_sha256")
        if change["operation"] == "delete":
            if change["result_sha256"] is not None or change["staged_path"] is not None:
                raise ProductionProfileError("delete must not provide staged content or a result hash")
        else:
            _digest(change["result_sha256"], "change.result_sha256")
            staged = _path(change["staged_path"])
            if staged not in artifacts or artifacts[staged]["sha256"] != change["result_sha256"]:
                raise ProductionProfileError("change must reference a declared staged artifact with the same hash")
    if ready and task["allowed_write_paths"] and not changed:
        raise ProductionProfileError("ready_for_integration requires changes for a write-bearing package")
    allowed = {row["ref"] for row in task["input_refs"].values()} | set(artifacts)
    required_checks = set(task["must_check"])
    seen: set[str] = set()
    for check in result["check_records"]:
        check_id = check["check_id"]
        if check_id not in required_checks or check_id in seen:
            raise ProductionProfileError("check_records contains an unknown or duplicate check")
        seen.add(check_id)
        if ready and check["outcome"] not in {"satisfied", "not_applicable"}:
            raise ProductionProfileError("ready_for_integration requires positive mandatory checks")
        _evidence(check["evidence_refs"], allowed, empty=not ready and check["outcome"] == "blocked")
    if ready and seen != required_checks:
        raise ProductionProfileError("ready_for_integration must account for every mandatory check")
    completion = result["completion_evidence"]
    if set(completion) - set(outputs) or (ready and required_outputs - set(completion)):
        raise ProductionProfileError("completion_evidence must cover the required produced artifact types")
    for kind, refs in completion.items():
        _evidence(refs, outputs[kind])
    return copy.deepcopy(result)
