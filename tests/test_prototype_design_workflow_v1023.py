import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state, write_state
from product_delivery_agent.gatekeeper import (
    GatekeeperError,
    derive_blockers,
    product_baseline_hash,
    review_input_hash,
)
from product_delivery_agent.review_gates import ReviewGateError, validate_multi_agent_review
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.conformance_fixtures import (
    PROTOTYPE_DESIGN_DIMENSIONS,
    activate_host_goal,
    bind_prototype_design_review,
    confirm_product_baseline,
    confirm_test_coverage_plan,
    prototype_design_bundle_payload,
    reconcile_host_goal,
    record_prototype_design_bundle,
    ui_conformance_review_payload,
    write_prototype_screenshot,
)
from tests.test_feature_closure import (
    browser_evidence,
    coverage_row,
    multi_agent_review,
    planned_obligation,
    ready_workflow as closure_ready_workflow,
    scenario_row,
    task_completion_artifact,
    ui_review_payload,
    valid_closure_artifact,
)


def scenario_review(workflow: ProductDeliveryWorkflow, ui_change_type: str) -> dict:
    review = multi_agent_review("scenario")
    review["ui_continuity_findings"] = []
    review["baseline_inheritance_review"] = {"ui_change_type": ui_change_type}
    if ui_change_type == "incremental_existing_surface":
        review["baseline_inheritance_review"].update(
            {
                "baseline_feature_slug": "v0-existing-classroom",
                "baseline_entry_path": (
                    "teacher opens the existing classroom dashboard"
                ),
                "inherits_existing_surface": True,
                "parallel_surface_replacement": False,
            }
        )
    return bind_prototype_design_review(workflow, review)


def start_ui_workflow(
    project_root: Path,
    *,
    ui_change_type: str = "incremental_existing_surface",
    with_bundle: bool = True,
) -> tuple[ProductDeliveryWorkflow, dict]:
    prototype = project_root / "prototype/index.html"
    prototype.parent.mkdir(parents=True, exist_ok=True)
    prototype.write_text("<html>clean product surface</html>", encoding="utf-8")
    write_prototype_screenshot(project_root)
    workflow = ProductDeliveryWorkflow(project_root)
    workflow.start(
        feature_slug="v1.0.23-prototype-design-integrity",
        multi_agent_mode="spawned_subagents_authorized",
    )
    workflow.select_project_type("ui")
    workflow.record_scenario_matrix([scenario_row()])
    review = ui_review_payload()
    review["ui_change_type"] = ui_change_type
    if ui_change_type in {"new_surface_in_existing_product", "greenfield_ui"}:
        review["new_surface_justification"] = {
            "reason": "The requested workflow requires a dedicated product surface.",
            "why_existing_surface_insufficient": (
                "The existing surface cannot represent the required workflow state."
            ),
            "navigation_impact": "The surface is reached from the existing product navigation.",
        }
    if with_bundle:
        record_prototype_design_bundle(workflow, project_root, review)
    return workflow, review


def record_reviewed_prototype(
    workflow: ProductDeliveryWorkflow,
    review: dict,
) -> dict:
    review = dict(review)
    bundle = workflow.status()["prototype_design_bundle"]
    review.update(
        {
            "prototype_design_bundle_hash": bundle["bundle_sha256"],
            "prototype_design_audit_hash": bundle["design_audit_sha256"],
            "reviewed_design_dimensions": list(PROTOTYPE_DESIGN_DIMENSIONS),
            "unmapped_design_dimensions": [],
            "global_visual_continuity_findings": [],
            "annotation_separation_findings": [],
            "global_visual_continuity": {
                "conclusion": "passed",
                "summary": "The clean prototype preserves the reviewed product context.",
                "evidence_refs": ["prototype_design_bundle.design_audit"],
            },
            "annotation_separation": {
                "conclusion": "passed",
                "summary": "Review annotations remain outside the clean product surface.",
                "evidence_refs": ["prototype_design_bundle.review_annotation_set"],
            },
        }
    )
    return workflow.record_ui_prototype_review(review)


def confirm_test_plan(workflow: ProductDeliveryWorkflow) -> dict:
    workflow.record_planned_e2e_obligations([planned_obligation()])
    workflow.record_test_coverage_audit(
        [coverage_row()],
        negative_guard_records=["student billing is absent"],
    )
    workflow.record_multi_agent_review(
        "test_coverage", multi_agent_review("test_coverage")
    )
    workflow.record_multi_agent_review("test", multi_agent_review("test"))
    return confirm_test_coverage_plan(workflow)


def confirmed_workflow(project_root: Path) -> ProductDeliveryWorkflow:
    workflow, review = start_ui_workflow(project_root)
    record_reviewed_prototype(workflow, review)
    confirm_product_baseline(
        workflow,
        scenario_review(workflow, "incremental_existing_surface"),
    )
    confirm_test_plan(workflow)
    return workflow


def handoff_workflow(project_root: Path) -> ProductDeliveryWorkflow:
    workflow = confirmed_workflow(project_root)
    launch_args = {
        "scope": "Implement the confirmed classroom surface",
        "verification_commands": ["pytest"],
        "prohibited_work": ["Do not revise the confirmed product baseline"],
    }
    workflow.record_implementation_launch_authorization(**launch_args)
    workflow.generate_codex_goal_handoff(**launch_args)
    return workflow


def mutate_text_artifact(project_root: Path, artifact_path: str) -> None:
    path = project_root / artifact_path
    path.write_bytes(path.read_bytes() + b"\nchanged on disk\n")


def write_raw_state(project_root: Path, state: dict) -> None:
    workspace = project_root / ARTIFACT_ROOT
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "state.json").write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def prototype_review_validation_fixture(
    project_root: Path,
) -> tuple[ProductDeliveryWorkflow, dict, dict, dict]:
    prototype = project_root / "prototype/index.html"
    prototype.parent.mkdir(parents=True, exist_ok=True)
    prototype.write_text("<html>clean product surface</html>", encoding="utf-8")
    workflow = ProductDeliveryWorkflow(project_root)
    workflow.start(
        feature_slug="v1.0.23-prototype-review-validation",
        multi_agent_mode="spawned_subagents_authorized",
    )
    workflow.select_project_type("ui")
    review = ui_review_payload()
    bundle_state = {
        "status": "ready",
        "bundle_sha256": "b" * 64,
        "design_audit_sha256": "a" * 64,
    }
    state = workflow.status()
    state["prototype_design_bundle"] = bundle_state
    write_state(project_root, state)
    rebuilt_bundle = {
        "bundle_sha256": bundle_state["bundle_sha256"],
        "product_domain_sha256": "c" * 64,
        "review_domain_sha256": "d" * 64,
        "ui_change_type": review["ui_change_type"],
        "clean_surface": {"prototype_path": review["prototype_path"]},
        "artifact_metadata": {"clean_prototype": {"sha256": "e" * 64}},
    }
    contract = copy.deepcopy(review["prototype_contract"])
    contract["contract_sha256"] = "f" * 64
    contract["prototype_screenshot_set_sha256"] = "1" * 64
    return workflow, review, rebuilt_bundle, contract


class PrototypeDesignWorkflowV1023Tests(unittest.TestCase):
    def test_ui_prototype_review_binds_complete_positive_design_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, review, rebuilt_bundle, contract = (
                prototype_review_validation_fixture(Path(tmp))
            )
            bundle = workflow.status()["prototype_design_bundle"]
            review = dict(review)
            review.update(
                {
                    "prototype_design_bundle_hash": bundle["bundle_sha256"],
                    "prototype_design_audit_hash": bundle["design_audit_sha256"],
                    "reviewed_design_dimensions": list(PROTOTYPE_DESIGN_DIMENSIONS),
                    "unmapped_design_dimensions": [],
                    "global_visual_continuity_findings": [],
                    "annotation_separation_findings": [],
                    "global_visual_continuity": {
                        "conclusion": "passed",
                        "summary": "The global product context is preserved.",
                        "evidence_refs": ["prototype_design_bundle.design_audit"],
                    },
                    "annotation_separation": {
                        "conclusion": "passed",
                        "summary": "Annotations are isolated from the clean surface.",
                        "evidence_refs": [
                            "prototype_design_bundle.review_annotation_set"
                        ],
                    },
                }
            )

            with patch.object(
                workflow,
                "_rebuild_current_prototype_design_bundle",
                return_value=(rebuilt_bundle, contract),
            ):
                state = workflow.record_ui_prototype_review(review)

            recorded = state["ui_prototype_review"]
            self.assertEqual(
                recorded["prototype_design_bundle_hash"], bundle["bundle_sha256"]
            )
            self.assertEqual(
                recorded["prototype_design_audit_hash"],
                bundle["design_audit_sha256"],
            )
            self.assertEqual(
                recorded["reviewed_design_dimensions"],
                list(PROTOTYPE_DESIGN_DIMENSIONS),
            )
            self.assertEqual(recorded["unmapped_design_dimensions"], [])
            self.assertEqual(
                recorded["global_visual_continuity_findings"], []
            )
            self.assertEqual(recorded["annotation_separation_findings"], [])
            self.assertEqual(
                recorded["global_visual_continuity"]["conclusion"], "passed"
            )
            self.assertEqual(
                recorded["annotation_separation"]["conclusion"], "passed"
            )

    def test_ui_prototype_review_requires_current_design_audit_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, review, rebuilt_bundle, contract = (
                prototype_review_validation_fixture(Path(tmp))
            )
            bundle = workflow.status()["prototype_design_bundle"]
            review = dict(review)
            review.update(
                {
                    "prototype_design_bundle_hash": bundle["bundle_sha256"],
                    "prototype_design_audit_hash": "0" * 64,
                    "reviewed_design_dimensions": list(PROTOTYPE_DESIGN_DIMENSIONS),
                    "unmapped_design_dimensions": [],
                    "global_visual_continuity": {
                        "conclusion": "passed",
                        "summary": "The global product context is preserved.",
                        "evidence_refs": ["prototype_design_bundle.design_audit"],
                    },
                    "annotation_separation": {
                        "conclusion": "passed",
                        "summary": "Annotations are isolated from the clean surface.",
                        "evidence_refs": [
                            "prototype_design_bundle.review_annotation_set"
                        ],
                    },
                }
            )

            with patch.object(
                workflow,
                "_rebuild_current_prototype_design_bundle",
                return_value=(rebuilt_bundle, contract),
            ):
                with self.assertRaisesRegex(WorkflowError, "design_audit_hash"):
                    workflow.record_ui_prototype_review(review)

    def test_ui_prototype_review_requires_complete_positive_design_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, review, rebuilt_bundle, contract = (
                prototype_review_validation_fixture(Path(tmp))
            )
            bundle = workflow.status()["prototype_design_bundle"]
            review = dict(review)
            review.update(
                {
                    "prototype_design_bundle_hash": bundle["bundle_sha256"],
                    "prototype_design_audit_hash": bundle["design_audit_sha256"],
                    "reviewed_design_dimensions": list(
                        PROTOTYPE_DESIGN_DIMENSIONS[:-1]
                    ),
                    "unmapped_design_dimensions": [
                        PROTOTYPE_DESIGN_DIMENSIONS[-1]
                    ],
                    "global_visual_continuity_findings": [],
                    "annotation_separation_findings": [],
                }
            )

            with patch.object(
                workflow,
                "_rebuild_current_prototype_design_bundle",
                return_value=(rebuilt_bundle, contract),
            ):
                with self.assertRaisesRegex(
                    WorkflowError,
                    "reviewed_design_dimensions|unmapped_design_dimensions|global_visual_continuity",
                ):
                    workflow.record_ui_prototype_review(review)

    def test_unconfirmed_ui_cannot_review_scenario_without_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, review = start_ui_workflow(Path(tmp), with_bundle=False)

            self.assertEqual(
                workflow.status()["prototype_design_bundle"]["status"], "missing"
            )
            with self.assertRaisesRegex(WorkflowError, "prototype design bundle"):
                workflow.record_ui_prototype_review(review)
            with self.assertRaisesRegex(ReviewGateError, "prototype design bundle"):
                workflow.record_multi_agent_review(
                    "scenario", multi_agent_review("scenario")
                )
            self.assertIn(
                "prototype_design_integrity",
                derive_blockers(workflow.status(), Path(tmp)),
            )

    def test_valid_bundle_modes_can_proceed_to_scenario_review(self):
        for ui_change_type in (
            "incremental_existing_surface",
            "new_surface_in_existing_product",
            "greenfield_ui",
        ):
            with self.subTest(ui_change_type=ui_change_type):
                with tempfile.TemporaryDirectory() as tmp:
                    workflow, review = start_ui_workflow(
                        Path(tmp), ui_change_type=ui_change_type
                    )
                    record_reviewed_prototype(workflow, review)

                    state = workflow.record_multi_agent_review(
                        "scenario", scenario_review(workflow, ui_change_type)
                    )

                    self.assertEqual(
                        state["multi_agent_reviews"]["scenario"]["status"], "passed"
                    )
                    self.assertEqual(
                        state["next_gate"], "product_baseline_confirmation_preparation"
                    )

    def test_missing_design_dimension_fails_before_scenario_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow, review = start_ui_workflow(project_root, with_bundle=False)
            payload = prototype_design_bundle_payload(
                project_root,
                prototype_path=review["prototype_path"],
                contract=review["prototype_contract"],
            )
            payload["product_context_contract"]["coverage_rows"].pop()

            with self.assertRaisesRegex(WorkflowError, "product context coverage"):
                workflow.record_ui_prototype_design_bundle(payload)
            with self.assertRaisesRegex(ReviewGateError, "prototype design bundle"):
                workflow.record_multi_agent_review(
                    "scenario", multi_agent_review("scenario")
                )

    def test_empty_findings_without_positive_design_binding_fail_scenario_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, review = start_ui_workflow(Path(tmp))
            record_reviewed_prototype(workflow, review)
            incomplete = multi_agent_review("scenario")
            incomplete.update(
                {
                    "ui_continuity_findings": [],
                    "baseline_inheritance_review": {
                        "ui_change_type": "incremental_existing_surface",
                        "baseline_feature_slug": "v0-existing-classroom",
                        "baseline_entry_path": "existing dashboard",
                        "inherits_existing_surface": True,
                        "parallel_surface_replacement": False,
                    },
                    "global_visual_continuity_findings": [],
                    "annotation_separation_findings": [],
                }
            )

            with self.assertRaisesRegex(
                ReviewGateError, "prototype_design_bundle_hash|reviewed_design_dimensions"
            ):
                workflow.record_multi_agent_review("scenario", incomplete)

    def test_annotation_only_revision_stales_scenario_and_restores_resume_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow, review = start_ui_workflow(project_root)
            record_reviewed_prototype(workflow, review)
            confirm_product_baseline(
                workflow,
                scenario_review(workflow, "incremental_existing_surface"),
            )
            confirm_test_plan(workflow)
            state = workflow.status()
            state["prototype_production_conformance"] = {
                "status": "passed",
                "marker": "preserve-conformance",
            }
            state["implementation_launch_authorization"] = {
                "status": "authorized",
                "marker": "preserve-launch",
            }
            state["next_gate"] = "codex_goal_handoff"
            state = write_state(project_root, state)
            original_product_hash = product_baseline_hash(state)
            original_review_hash = review_input_hash(state, "scenario")
            original_confirmations = copy.deepcopy(state["user_confirmations"])
            original_planned = copy.deepcopy(state["planned_e2e_obligations"])

            changed_payload = prototype_design_bundle_payload(
                project_root,
                prototype_path=review["prototype_path"],
                contract=review["prototype_contract"],
                annotation_text="Review the inherited density and shell continuity.",
            )
            state = workflow.record_ui_prototype_design_bundle(changed_payload)

            self.assertEqual(product_baseline_hash(state), original_product_hash)
            self.assertNotEqual(review_input_hash(state, "scenario"), original_review_hash)
            self.assertEqual(state["user_confirmations"], original_confirmations)
            self.assertEqual(state["planned_e2e_obligations"], original_planned)
            self.assertEqual(
                state["prototype_production_conformance"]["marker"],
                "preserve-conformance",
            )
            self.assertEqual(
                state["implementation_launch_authorization"]["marker"],
                "preserve-launch",
            )
            self.assertEqual(
                state["multi_agent_reviews"]["scenario"]["status"], "stale"
            )
            for review_type in ("test", "test_coverage"):
                self.assertEqual(
                    state["multi_agent_reviews"][review_type]["status"], "passed"
                )
            self.assertEqual(state["next_gate"], "multi_agent_scenario_review")
            self.assertEqual(
                state["annotation_review_resume_gate"], "codex_goal_handoff"
            )

            state = workflow.record_multi_agent_review(
                "scenario",
                scenario_review(workflow, "incremental_existing_surface"),
            )

            self.assertEqual(state["next_gate"], "codex_goal_handoff")
            self.assertNotIn("annotation_review_resume_gate", state)
            self.assertEqual(state["user_confirmations"], original_confirmations)

    def test_disk_current_integrity_blocks_launch_handoff_and_task_progression(self):
        launch_args = {
            "scope": "Implement the confirmed classroom surface",
            "verification_commands": ["pytest"],
            "prohibited_work": ["Do not revise the confirmed product baseline"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = confirmed_workflow(project_root)
            mutate_text_artifact(project_root, "prototype/index.html")

            self.assertIn(
                "stale_prototype_design_integrity",
                derive_blockers(workflow.status(), project_root),
            )
            with self.assertRaisesRegex(
                WorkflowError, "stale_prototype_design_integrity"
            ):
                workflow.record_implementation_launch_authorization(**launch_args)

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = confirmed_workflow(project_root)
            mutate_text_artifact(
                project_root,
                ".product-delivery/artifacts/prototype-design-bundle.json",
            )

            self.assertIn(
                "stale_prototype_design_integrity",
                derive_blockers(workflow.status(), project_root),
            )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = confirmed_workflow(project_root)
            workflow.record_implementation_launch_authorization(**launch_args)
            mutate_text_artifact(
                project_root,
                ".product-delivery/artifacts/prototype-design/semantic-snapshot.json",
            )

            with self.assertRaisesRegex(
                GatekeeperError, "stale_prototype_design_integrity"
            ):
                workflow.generate_codex_goal_handoff(**launch_args)

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handoff_workflow(project_root)
            activate_host_goal(workflow)
            reconcile_host_goal(workflow)
            state = workflow.status()
            bundle_path = project_root / ".product-delivery/artifacts/prototype-design-bundle.json"
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            screenshot_path = bundle["clean_surface"]["runtime_checks"][0][
                "clean_screenshot_path"
            ]
            write_prototype_screenshot(project_root, screenshot_path, width=900)

            with self.assertRaisesRegex(
                WorkflowError, "prototype design bundle"
            ):
                workflow.record_task_completion(
                    "TASK-001",
                    artifact=task_completion_artifact(state, "TASK-001"),
                )
            self.assertEqual(
                workflow.status()["delivery_goal"]["completed_tasks"], []
            )

    def test_disk_current_integrity_blocks_evidence_conformance_and_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handoff_workflow(project_root)
            activate_host_goal(workflow)
            reconcile_host_goal(workflow)
            workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(workflow.status(), "TASK-001"),
            )
            reconcile_host_goal(workflow)
            mutate_text_artifact(
                project_root,
                ".product-delivery/artifacts/prototype-design/baseline-surface.png",
            )

            with self.assertRaisesRegex(
                WorkflowError, "prototype design bundle"
            ):
                workflow.record_executed_browser_evidence(
                    [browser_evidence(project_root)]
                )
            self.assertEqual(
                workflow.status()["executed_browser_evidence"]["status"], "missing"
            )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handoff_workflow(project_root)
            activate_host_goal(workflow)
            reconcile_host_goal(workflow)
            workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(workflow.status(), "TASK-001"),
            )
            reconcile_host_goal(workflow)
            workflow.record_executed_browser_evidence([browser_evidence(project_root)])
            reconcile_host_goal(workflow)
            mutate_text_artifact(
                project_root,
                ".product-delivery/artifacts/prototype-design/semantic-snapshot.json",
            )

            with self.assertRaisesRegex(
                WorkflowError, "prototype design bundle"
            ):
                workflow.record_prototype_production_conformance({})
            self.assertEqual(
                workflow.status()["prototype_production_conformance"]["status"],
                "missing",
            )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = closure_ready_workflow(project_root)
            mutate_text_artifact(
                project_root,
                ".product-delivery/artifacts/review-only/prototype-review.html",
            )

            with self.assertRaisesRegex(
                WorkflowError, "prototype design bundle"
            ):
                workflow.record_feature_closure(
                    valid_closure_artifact(workflow.status())
                )
            self.assertNotIn("feature_closure", workflow.status())

    def test_annotation_review_pending_blocks_progression_until_current_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = handoff_workflow(project_root)
            original_state = workflow.status()
            original_authorization = copy.deepcopy(
                original_state["implementation_launch_authorization"]
            )
            original_confirmations = copy.deepcopy(
                original_state["user_confirmations"]
            )
            changed_payload = prototype_design_bundle_payload(
                project_root,
                prototype_path=original_state["ui_prototype"]["prototype_path"],
                contract=original_state["prototype_contract"],
                annotation_text="Re-review the annotation-only continuity guidance.",
            )

            activate_host_goal(workflow)
            reconcile_host_goal(workflow)
            pending = workflow.record_ui_prototype_design_bundle(changed_payload)

            self.assertEqual(pending["next_gate"], "multi_agent_scenario_review")
            self.assertEqual(
                pending["annotation_review_resume_gate"], "TASK-001"
            )
            self.assertEqual(
                pending["implementation_launch_authorization"],
                original_authorization,
            )
            self.assertEqual(pending["user_confirmations"], original_confirmations)
            reconcile_host_goal(workflow)
            with self.assertRaisesRegex(WorkflowError, "annotation review is pending"):
                workflow.record_task_completion(
                    "TASK-001",
                    artifact=task_completion_artifact(pending, "TASK-001"),
                )
            reconcile_host_goal(workflow)
            with self.assertRaisesRegex(WorkflowError, "annotation review is pending"):
                workflow.record_executed_browser_evidence(
                    [browser_evidence(project_root)]
                )
            reconcile_host_goal(workflow)
            with self.assertRaisesRegex(WorkflowError, "annotation review is pending"):
                workflow.record_multi_agent_review(
                    "test_implementation",
                    multi_agent_review("test_implementation"),
                )

            reconcile_host_goal(workflow)
            reviewed = workflow.record_multi_agent_review(
                "scenario",
                scenario_review(workflow, "incremental_existing_surface"),
            )

            self.assertEqual(reviewed["next_gate"], "TASK-001")
            self.assertNotIn("annotation_review_resume_gate", reviewed)
            reconcile_host_goal(workflow)
            progressed = workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(reviewed, "TASK-001"),
            )
            self.assertEqual(
                progressed["delivery_goal"]["completed_tasks"], ["TASK-001"]
            )

    def test_product_domain_change_retains_full_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow, review = start_ui_workflow(project_root)
            record_reviewed_prototype(workflow, review)
            workflow.record_multi_agent_review(
                "scenario", scenario_review(workflow, "incremental_existing_surface")
            )
            state = workflow.status()
            for review_type in (
                "test",
                "test_coverage",
                "test_implementation",
                "ui_conformance",
            ):
                state["multi_agent_reviews"][review_type] = {
                    "status": "passed",
                    "input_snapshot_hash": "fixture-current",
                }
            state["user_confirmations"]["test_coverage_plan"] = {
                "user_semantics_hash": "fixture-confirmation"
            }
            state["prototype_production_conformance"] = {"status": "passed"}
            state["implementation_launch_authorization"] = {"status": "authorized"}
            write_state(project_root, state)
            changed = prototype_design_bundle_payload(
                project_root,
                prototype_path=review["prototype_path"],
                contract=review["prototype_contract"],
            )
            changed["intended_product_ui_callouts"][0]["trigger"] = (
                "the product enters a changed ready state"
            )

            state = workflow.record_ui_prototype_design_bundle(changed)

            for review_type in (
                "scenario",
                "test",
                "test_coverage",
                "test_implementation",
                "ui_conformance",
            ):
                self.assertEqual(
                    state["multi_agent_reviews"][review_type]["status"], "stale"
                )
            self.assertEqual(
                state["prototype_production_conformance"]["status"], "stale"
            )
            self.assertEqual(
                state["implementation_launch_authorization"]["status"], "stale"
            )
            self.assertNotIn("test_coverage_plan", state["user_confirmations"])

    def test_product_confirmation_uses_clean_surface_not_review_companion(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow, review = start_ui_workflow(project_root)
            record_reviewed_prototype(workflow, review)
            workflow.record_multi_agent_review(
                "scenario", scenario_review(workflow, "incremental_existing_surface")
            )

            state = workflow.prepare_product_baseline_confirmation()
            pending = state["pending_confirmations"]["product_baseline"]
            self.assertEqual(pending["artifact_path"], "prototype/index.html")
            self.assertEqual(
                pending["prototype_design_product_hash"],
                state["prototype_design_bundle"]["product_domain_sha256"],
            )
            self.assertNotIn("prototype_design_review_hash", pending)
            self.assertNotIn("prototype_design_bundle_hash", pending)

            state = workflow.confirm_product_baseline(
                "确认产品基线和干净原型", pending["nonce"]
            )
            confirmation = state["user_confirmations"]["ui_prototype"]
            self.assertEqual(confirmation["artifact_path"], "prototype/index.html")
            self.assertNotIn("review-only", confirmation["artifact_path"])

    def test_legacy_confirmed_ui_is_grandfathered_until_product_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            legacy = {
                "delivery_id": "legacy-v1022-confirmed",
                "active": True,
                "status": "active",
                "feature_slug": "legacy-confirmed-ui",
                "project_type": "ui",
                "runtime_version": "1.0.22+codex.20260714180655",
                "open_spec_draft_ready": True,
                "scenario_matrix_draft_ready": True,
                "scenario_matrix": {"draft_ready": True, "rows": [scenario_row()]},
                "open_spec_freeze": {"approved_by_user": True},
                "ui_prototype": {
                    "generated": True,
                    "reviewed_by_agent": True,
                    "confirmed_by_user": True,
                    "prototype_path": "prototype/index.html",
                },
                "user_confirmations": {
                    "ui_prototype": {"artifact_path": "prototype/index.html"}
                },
                "multi_agent_reviews": {"scenario": {"status": "missing"}},
                "multi_agent_policy": {
                    "mode": "spawned_subagents_required",
                    "execution_authorization": "authorized",
                    "authorization_scope": "current_delivery",
                    "authorization_source": "legacy",
                    "authorization_delivery_id": "legacy-v1022-confirmed",
                    "authorization_feature_slug": "legacy-confirmed-ui",
                    "authorized_review_types": ["scenario"],
                },
            }
            write_raw_state(project_root, legacy)

            state = load_state(project_root)

            self.assertEqual(
                state["prototype_design_bundle"]["status"], "legacy_grandfathered"
            )
            self.assertEqual(
                state["prototype_design_bundle"]["enforcement"],
                "on_next_prototype_revision",
            )
            self.assertNotIn(
                "prototype_design_integrity", derive_blockers(state, project_root)
            )

            state = ProductDeliveryWorkflow(project_root).record_user_requested_change(
                targets=["product_baseline"],
                user_message="Revise the confirmed product surface",
            )
            self.assertEqual(
                state["prototype_design_bundle"]["status"], "missing"
            )

    def test_only_v1022_confirmed_active_ui_is_grandfathered(self):
        for provenance in (None, "1.0.21", "1.0.23"):
            with self.subTest(provenance=provenance):
                with tempfile.TemporaryDirectory() as tmp:
                    project_root = Path(tmp)
                    legacy = {
                        "delivery_id": "legacy-confirmed",
                        "active": True,
                        "status": "active",
                        "feature_slug": "legacy-confirmed-ui",
                        "project_type": "ui",
                        "open_spec_freeze": {"approved_by_user": True},
                        "ui_prototype": {
                            "generated": True,
                            "reviewed_by_agent": True,
                            "confirmed_by_user": True,
                            "prototype_path": "prototype/index.html",
                        },
                        "user_confirmations": {
                            "ui_prototype": {
                                "artifact_path": "prototype/index.html"
                            }
                        },
                    }
                    if provenance is not None:
                        legacy["plugin_version"] = provenance
                    write_raw_state(project_root, legacy)

                    state = load_state(project_root)

                    self.assertEqual(
                        state["prototype_design_bundle"]["status"], "missing"
                    )
                    self.assertIn(
                        "prototype_design_integrity",
                        derive_blockers(state, project_root),
                    )

    def test_v1022_plugin_version_provenance_is_grandfathered(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            legacy = {
                "delivery_id": "legacy-v1022-plugin-version",
                "active": True,
                "status": "active",
                "feature_slug": "legacy-confirmed-ui",
                "project_type": "ui",
                "plugin_version": "1.0.22",
                "open_spec_freeze": {"approved_by_user": True},
                "ui_prototype": {
                    "generated": True,
                    "reviewed_by_agent": True,
                    "confirmed_by_user": True,
                    "prototype_path": "prototype/index.html",
                },
                "user_confirmations": {
                    "ui_prototype": {"artifact_path": "prototype/index.html"}
                },
            }
            write_raw_state(project_root, legacy)

            state = load_state(project_root)

            self.assertEqual(
                state["prototype_design_bundle"]["status"],
                "legacy_grandfathered",
            )

    def test_legacy_unconfirmed_ui_is_fail_closed_and_terminal_state_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            unconfirmed = {
                "delivery_id": "legacy-v1022-unconfirmed",
                "active": True,
                "status": "active",
                "feature_slug": "legacy-unconfirmed-ui",
                "project_type": "ui",
                "ui_prototype": {
                    "generated": True,
                    "reviewed_by_agent": True,
                    "confirmed_by_user": False,
                },
            }
            write_raw_state(project_root, unconfirmed)
            state = load_state(project_root)
            self.assertEqual(state["prototype_design_bundle"]["status"], "missing")
            self.assertIn(
                "prototype_design_integrity", derive_blockers(state, project_root)
            )

            terminal_root = project_root / "terminal"
            terminal = {
                "status": "closed",
                "active": False,
                "project_type": "ui",
                "artifact_marker": "preserve",
            }
            write_raw_state(terminal_root, terminal)
            loaded_terminal = load_state(terminal_root)
            self.assertNotIn("prototype_design_bundle", loaded_terminal)
            self.assertEqual(loaded_terminal["artifact_marker"], "preserve")

    def test_ui_conformance_requires_positive_design_dimension_coverage(self):
        state = {"prototype_contract": ui_review_payload()["prototype_contract"]}
        review = ui_conformance_review_payload(state)
        review.pop("reviewed_design_dimensions")

        with self.assertRaisesRegex(ReviewGateError, "reviewed_design_dimensions"):
            validate_multi_agent_review(
                "ui_conformance",
                review,
                prototype_contract=state["prototype_contract"],
            )

        review["reviewed_design_dimensions"] = list(PROTOTYPE_DESIGN_DIMENSIONS)
        validate_multi_agent_review(
            "ui_conformance",
            review,
            prototype_contract=state["prototype_contract"],
        )

    def test_non_ui_workflow_is_unaffected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            state = workflow.start(
                feature_slug="v1.0.23-non-ui",
                multi_agent_mode="spawned_subagents_authorized",
            )
            self.assertEqual(
                state["prototype_design_bundle"]["status"], "missing"
            )
            state = workflow.select_project_type("non_ui")
            self.assertNotIn(
                "prototype_design_integrity", derive_blockers(state, project_root)
            )
            with self.assertRaisesRegex(WorkflowError, "only available for UI"):
                workflow.record_ui_prototype_design_bundle({})


if __name__ == "__main__":
    unittest.main()
