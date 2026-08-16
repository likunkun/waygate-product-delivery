import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from product_delivery_agent.coverage_audit import CoverageAuditError
from product_delivery_agent.journey_slice_tasks import (
    JourneySliceTaskError,
    derive_journey_slice_tasks,
    ensure_journey_slice_task_policy,
    journey_slice_tasks_required,
    refine_journey_slice_tasks,
    rewrite_coverage_task_column,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError

from tests.conformance_fixtures import (
    activate_host_goal,
    confirm_product_baseline,
    confirm_test_coverage_plan,
    reconcile_host_goal,
    record_bundled_ui_prototype_review,
    record_passing_task_prototype_conformance,
    record_passing_task_slice_evidence,
    slice_browser_evidence,
    task_prototype_conformance_payload,
    write_prototype_screenshot,
)
from tests.test_codex_goal_handoff import (
    authorize_launch,
    coverage_row,
    multi_agent_review,
    planned_obligation,
    ready_workflow,
    scenario_row,
    ui_review_payload,
)
from tests.test_feature_closure import task_completion_artifact


def _obligation(**overrides):
    row = planned_obligation()
    row.update(overrides)
    row.setdefault("surface_ids", ["primary-surface"])
    return row


def _assertion(item_id: str) -> dict:
    return {
        "item_id": item_id,
        "action_entry": f"use {item_id}",
        "expected_real_surface": f"{item_id} surface",
        "assertion_target": f"{item_id} result is visible",
        "semantic_depth": "real_surface",
    }


class JourneySliceDerivationTests(unittest.TestCase):
    def test_same_journey_becomes_one_task(self):
        first = _obligation()
        second = _obligation(
            obligation_id="OBL-002",
            test_id="TC-V008-002",
            path_kind="visible_exception",
            coverage_items=["classroom-duplicate"],
            action_assertions=[_assertion("classroom-duplicate")],
        )
        state = {
            "project_type": "ui",
            "planned_e2e_obligations": {"obligations": [first, second]},
        }

        tasks = derive_journey_slice_tasks(state)

        self.assertEqual([task["task_id"] for task in tasks], ["TASK-001"])
        self.assertEqual(tasks[0]["obligation_ids"], ["OBL-001", "OBL-002"])
        self.assertTrue(tasks[0]["includes_minimum_shell"])
        self.assertEqual(tasks[0]["ui_impact"], "prototype_bound")
        self.assertEqual(
            [binding["surface_id"] for binding in tasks[0]["prototype_bindings"]],
            ["primary-surface"],
        )
        self.assertNotIn("none", [task.get("ui_impact") for task in tasks])

    def test_overloaded_journey_is_split(self):
        obligations = []
        for index in range(1, 4):
            item_id = f"item-{index:03d}"
            obligations.append(
                _obligation(
                    obligation_id=f"OBL-{index:03d}",
                    test_id=f"TC-V008-{index:03d}",
                    path_kind="primary_happy_path",
                    coverage_items=[item_id],
                    action_assertions=[_assertion(item_id)],
                    required_actor_roles=["teacher"],
                )
            )
        state = {
            "project_type": "ui",
            "planned_e2e_obligations": {"obligations": obligations},
        }

        tasks = derive_journey_slice_tasks(state)

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["obligation_ids"], ["OBL-001", "OBL-002"])
        self.assertEqual(tasks[1]["obligation_ids"], ["OBL-003"])
        self.assertTrue(tasks[0]["includes_minimum_shell"])
        self.assertFalse(tasks[1]["includes_minimum_shell"])

    def test_collection_items_over_three_are_rejected(self):
        obligation = _obligation(
            coverage_items=["a", "b", "c", "d"],
            action_assertions=[_assertion(item) for item in ("a", "b", "c", "d")],
        )

        with self.assertRaisesRegex(JourneySliceTaskError, "collection items"):
            derive_journey_slice_tasks(
                {
                    "project_type": "ui",
                    "planned_e2e_obligations": {"obligations": [obligation]},
                }
            )

    def test_ui_obligation_requires_surface_ids(self):
        obligation = planned_obligation()
        obligation.pop("surface_ids", None)

        with self.assertRaisesRegex(JourneySliceTaskError, "surface_ids"):
            derive_journey_slice_tasks(
                {
                    "project_type": "ui",
                    "planned_e2e_obligations": {"obligations": [obligation]},
                }
            )

    def test_first_task_absorbs_shell_units_later_tasks_do_not(self):
        baseline = {
            "status": "ready",
            "units": [
                {
                    "surface_id": "global-shell",
                    "state_id": "ready",
                    "viewport_class": "desktop",
                    "region_ids": ["global-shell"],
                    "interaction_ids": ["open-app"],
                },
                {
                    "surface_id": "primary-surface",
                    "state_id": "ready",
                    "viewport_class": "desktop",
                    "region_ids": ["primary-region"],
                    "interaction_ids": ["primary-action"],
                },
                {
                    "surface_id": "settings-surface",
                    "state_id": "ready",
                    "viewport_class": "desktop",
                    "region_ids": ["settings-region"],
                    "interaction_ids": ["save-settings"],
                },
            ],
        }
        first = _obligation(surface_ids=["primary-surface"])
        second = _obligation(
            obligation_id="OBL-002",
            test_id="TC-V008-002",
            journey="Teacher updates settings",
            path_kind="primary_happy_path",
            surface_ids=["settings-surface"],
            coverage_items=["settings-save"],
            action_assertions=[_assertion("settings-save")],
        )
        tasks = derive_journey_slice_tasks(
            {
                "project_type": "ui",
                "implementation_baseline": baseline,
                "planned_e2e_obligations": {"obligations": [first, second]},
            }
        )

        first_surfaces = {item["surface_id"] for item in tasks[0]["prototype_bindings"]}
        second_surfaces = {item["surface_id"] for item in tasks[1]["prototype_bindings"]}
        self.assertEqual(first_surfaces, {"global-shell", "primary-surface"})
        self.assertEqual(second_surfaces, {"settings-surface"})

    def test_non_ui_slices_are_behavior_tasks(self):
        obligation = _obligation()
        obligation["test_layer"] = "api_e2e"
        tasks = derive_journey_slice_tasks(
            {
                "project_type": "non_ui",
                "planned_e2e_obligations": {"obligations": [obligation]},
            }
        )
        self.assertEqual(tasks[0]["ui_impact"], "none")
        self.assertEqual(tasks[0]["ui_impact_reason"], "non-UI behavior slice")
        self.assertEqual(tasks[0]["prototype_bindings"], [])

    def test_refinement_can_narrow_but_not_merge_or_move_e2e(self):
        derived = derive_journey_slice_tasks(
            {
                "project_type": "ui",
                "planned_e2e_obligations": {
                    "obligations": [
                        _obligation(),
                        _obligation(
                            obligation_id="OBL-002",
                            test_id="TC-V008-002",
                            journey="Teacher updates settings",
                            surface_ids=["primary-surface"],
                            coverage_items=["settings-save"],
                            action_assertions=[_assertion("settings-save")],
                        ),
                    ]
                },
            }
        )
        narrowed = deepcopy(derived)
        narrowed[0]["title"] = "Build classroom create slice"
        narrowed[0]["prototype_bindings"][0]["region_ids"] = ["primary-surface-region"]
        refined = refine_journey_slice_tasks(derived, narrowed)
        self.assertEqual(refined[0]["title"], "Build classroom create slice")

        merged = [deepcopy(derived[0])]
        with self.assertRaisesRegex(JourneySliceTaskError, "keep derived task ids"):
            refine_journey_slice_tasks(derived, merged)

        moved = deepcopy(derived)
        moved[-1]["obligation_ids"] = list(derived[0]["obligation_ids"]) + list(
            derived[-1]["obligation_ids"]
        )
        with self.assertRaisesRegex(JourneySliceTaskError, "cannot move"):
            refine_journey_slice_tasks(derived, moved)

        leftover = deepcopy(derived)
        leftover[-1]["title"] = "Do remaining full-suite E2E"
        with self.assertRaisesRegex(JourneySliceTaskError, "leftover|full-suite"):
            refine_journey_slice_tasks(derived, leftover)

    def test_coverage_rows_are_rewritten_to_derived_task_ids(self):
        tasks = derive_journey_slice_tasks(
            {
                "project_type": "ui",
                "planned_e2e_obligations": {"obligations": [_obligation()]},
            }
        )
        rows = rewrite_coverage_task_column(
            [{"obligation_ref": "OBL-001", "journey": planned_obligation()["journey"], "task": "TASK-009"}],
            tasks,
        )
        self.assertEqual(rows[0]["task"], "TASK-001")

    def test_confirmed_old_delivery_is_grandfathered(self):
        state = {
            "confirmation_readiness": {"test_coverage_plan": "confirmed"},
            "user_confirmations": {"test_coverage_plan": {"decision": "approved"}},
        }
        policy = ensure_journey_slice_task_policy(state)
        self.assertEqual(policy["status"], "grandfathered")
        self.assertFalse(journey_slice_tasks_required(state))


class JourneySliceWorkflowV1029Tests(unittest.TestCase):
    def test_missing_surface_ids_block_planned_e2e_for_new_ui_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ready_workflow(Path(tmp))
            workflow.record_user_requested_change(
                targets=["test_coverage_plan"],
                user_message="补 surface 绑定",
            )
            obligation = planned_obligation()
            obligation.pop("surface_ids", None)
            with self.assertRaisesRegex((WorkflowError, CoverageAuditError, JourneySliceTaskError), "surface_ids"):
                workflow.record_planned_e2e_obligations([obligation])

    def test_handoff_rejects_merged_or_expanded_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            authorize_launch(workflow)
            derived = workflow.status()["journey_slice_task_queue"]["tasks"]
            extra = deepcopy(derived[0])
            extra["task_id"] = "TASK-999"
            with self.assertRaisesRegex(WorkflowError, "keep derived task ids"):
                workflow.generate_codex_goal_handoff(
                    scope="Implement classroom dashboard",
                    verification_commands=["pytest"],
                    planned_tasks=derived + [extra],
                )

    def test_task_cannot_complete_without_slice_e2e(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            authorize_launch(workflow)
            workflow.generate_codex_goal_handoff(
                scope="Implement classroom dashboard",
                verification_commands=["pytest"],
            )
            activate_host_goal(workflow)
            reconcile_host_goal(workflow)
            workflow.record_task_prototype_conformance(
                "TASK-001",
                task_prototype_conformance_payload(root, workflow.status(), "TASK-001"),
            )
            reconcile_host_goal(workflow)
            with self.assertRaisesRegex(WorkflowError, "slice"):
                workflow.record_task_completion(
                    "TASK-001",
                    artifact=task_completion_artifact(workflow.status(), "TASK-001"),
                )

    def test_slice_e2e_lets_current_task_finish_without_other_journeys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            authorize_launch(workflow)
            workflow.generate_codex_goal_handoff(
                scope="Implement classroom dashboard",
                verification_commands=["pytest"],
            )
            activate_host_goal(workflow)
            record_passing_task_prototype_conformance(workflow, root, "TASK-001")
            reconcile_host_goal(workflow)
            record_passing_task_slice_evidence(workflow, root, "TASK-001")
            reconcile_host_goal(workflow)
            completed = workflow.record_task_completion(
                "TASK-001",
                artifact=task_completion_artifact(workflow.status(), "TASK-001"),
            )
            self.assertEqual(completed["delivery_goal"]["completed_tasks"], ["TASK-001"])
            self.assertIsNone(completed["delivery_goal"]["current_task_cursor"])

    def test_full_evidence_requires_recorded_slice_union(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            authorize_launch(workflow)
            workflow.generate_codex_goal_handoff(
                scope="Implement classroom dashboard",
                verification_commands=["pytest"],
            )
            activate_host_goal(workflow)
            reconcile_host_goal(workflow)
            obligation = workflow.status()["planned_e2e_obligations"]["obligations"][0]
            with self.assertRaisesRegex(WorkflowError, "slice"):
                workflow.record_executed_browser_evidence(
                    [slice_browser_evidence(root, obligation, segment_id="full-only")]
                )

    def test_reopened_coverage_rebuilds_new_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ready_workflow(root)
            first_hash = workflow.status()["journey_slice_task_queue"]["task_queue_hash"]
            workflow.record_user_requested_change(
                targets=["test_coverage_plan"],
                user_message="拆开 settings journey 覆盖",
            )
            extra = _obligation(
                obligation_id="OBL-002",
                test_id="TC-V008-002",
                journey="Teacher updates settings",
                coverage_items=["settings-save"],
                action_assertions=[_assertion("settings-save")],
            )
            workflow.record_planned_e2e_obligations(
                [_obligation(), extra]
            )
            rebuilt = workflow.status()["journey_slice_task_queue"]
            self.assertNotEqual(rebuilt["task_queue_hash"], first_hash)
            self.assertEqual(len(rebuilt["tasks"]), 2)

