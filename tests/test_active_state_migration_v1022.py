import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state, write_state
from product_delivery_agent.gatekeeper import derive_blockers
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


FEATURE_SLUG = "v1.4.5-student-standard-course-learning"
DELIVERY_ID = "legacy-5e1f4a9c039ff88f"


def write_raw_state(project_root: Path, state: dict) -> None:
    workspace = project_root / ARTIFACT_ROOT
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "state.json").write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def classroom_active_state() -> dict:
    return {
        "delivery_id": DELIVERY_ID,
        "active": True,
        "status": "active",
        "stage": "ui_prototype_review_ready",
        "next_gate": "multi_agent_scenario_review",
        "feature_slug": FEATURE_SLUG,
        "project_type": "ui",
        "updated_at": "2026-07-14T16:26:25+00:00",
        "multi_agent_policy": {
            "mode": "spawned_subagents_required",
            "evidence_requirement": "spawned_subagents",
            "execution_authorization": "authorized",
            "authorization_scope": "current_delivery",
            "authorization_source": "startup_command",
            "authorization_delivery_id": DELIVERY_ID,
            "authorization_feature_slug": FEATURE_SLUG,
            "authorized_review_types": [
                "scenario",
                "test",
                "test_coverage",
                "test_implementation",
                "ui_conformance",
            ],
        },
        "execution_model_policy": {
            "mode": "automatic",
            "authorization_status": "authorized",
            "execution_verification_status": "host_model_control_unavailable",
            "pending_switch": {
                "mode": "full_speed",
                "authorization_status": "authorized",
            },
        },
        "pending_user_decisions": {
            "main_thread_model": {"status": "pending"},
            "execution_mode": {"status": "pending"},
            "requirements_clarification": {"status": "pending"},
        },
        "blocked_until": [
            "planning_files_ready",
            "planned_e2e_user_confirmation",
            "user_confirmed_freeze",
            "multi_agent_scenario_review",
            "product_baseline_user_confirmation",
            "ui_prototype_user_confirmation",
            "host_model_control_unavailable",
            "pending_stage_agent_spawn",
        ],
        "blocking_gates": {
            "host_model_control_unavailable": True,
            "stage_agent_model_mismatch": True,
            "planning_files_ready": True,
        },
        "pending_confirmations": {},
        "confirmation_readiness": {
            "product_baseline": "blocked_on_scenario_review",
            "test_coverage_plan": "blocked_on_product_baseline",
        },
        "multi_agent_reviews": {
            "scenario": {"status": "missing", "artifact": None},
        },
        "ui_prototype": {
            "generated": True,
            "reviewed_by_agent": True,
            "confirmed_by_user": False,
            "confirmation_status": "pending_user_confirmation",
            "pending_confirmation_nonce": "legacy-ui-nonce",
            "prototype_path": (
                "docs/prototypes/"
                "v1.4.5-student-standard-course-learning-prototype.html"
            ),
        },
        "artifact_marker": {"preserve": True},
    }


class ActiveStateMigrationV1022Tests(unittest.TestCase):
    def test_legacy_model_policy_requires_archive_and_fresh_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            original = classroom_active_state()
            write_raw_state(project_root, original)
            workflow = ProductDeliveryWorkflow(project_root)

            self.assertEqual(workflow.status()["runtime_status"], "legacy_unverified")
            with self.assertRaisesRegex(WorkflowError, "recover_legacy_active_delivery"):
                workflow.retire_model_execution_policy()
            state = workflow.recover_legacy_active_delivery()

            self.assertNotEqual(state["delivery_id"], DELIVERY_ID)
            self.assertEqual(state["feature_slug"], FEATURE_SLUG)
            self.assertTrue(state["active"])
            self.assertEqual(state["next_gate"], "multi_agent_mode_selection")
            self.assertNotIn("execution_model_policy", state)
            snapshot = project_root / state["previous_delivery"]["state_snapshot_path"]
            self.assertEqual(
                json.loads(snapshot.read_text(encoding="utf-8")), original
            )

    def test_model_policy_retirement_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            state = workflow.start(
                feature_slug=FEATURE_SLUG,
                multi_agent_mode="spawned_subagents_authorized",
            )
            state["execution_model_policy"] = classroom_active_state()[
                "execution_model_policy"
            ]
            write_state(project_root, state)

            first = workflow.retire_model_execution_policy()
            second = workflow.retire_model_execution_policy()

            self.assertEqual(
                len(first["retired_model_execution_policies"]), 1
            )
            self.assertEqual(
                second["retired_model_execution_policies"],
                first["retired_model_execution_policies"],
            )
            self.assertEqual(second["updated_at"], first["updated_at"])

    def test_empty_current_runtime_model_policy_is_removed_and_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(project_root)
            state = workflow.start(
                feature_slug=FEATURE_SLUG,
                multi_agent_mode="spawned_subagents_authorized",
            )
            state["execution_model_policy"] = {}
            state["pending_user_decisions"] = {}
            state["blocked_until"] = ["multi_agent_scenario_review"]
            state["blocking_gates"] = {}
            write_state(project_root, state)

            workflow.retire_model_execution_policy()
            persisted = json.loads(
                (project_root / ARTIFACT_ROOT / "state.json").read_text("utf-8")
            )

            self.assertNotIn("execution_model_policy", persisted)
            self.assertEqual(
                persisted["retired_model_execution_policies"][0]["policy"], {}
            )

    def test_legacy_model_apis_fail_with_retirement_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))

            with self.assertRaisesRegex(
                WorkflowError, "model orchestration has been retired to the Codex host"
            ):
                workflow.start(execution_mode="automatic")

            for method_name, args in (
                ("authorize_execution_mode", ("automatic", "user message")),
                ("request_execution_mode_switch", ("automatic", "user message")),
                ("begin_execution_stage", ("product_design",)),
                ("bind_execution_stage_agent", ("assignment-id",)),
                ("record_host_model_capabilities", ({},)),
                ("save_model_profiles", ()),
            ):
                with self.subTest(method=method_name):
                    with self.assertRaisesRegex(
                        WorkflowError,
                        "model orchestration has been retired to the Codex host",
                    ):
                        getattr(workflow, method_name)(*args)

    def test_new_event_timestamps_do_not_reuse_state_updated_at(self):
        old_timestamp = "2026-01-01T00:00:00+00:00"

        created_at = ProductDeliveryWorkflow._timestamp_from_state(
            {"updated_at": old_timestamp}
        )

        self.assertNotEqual(created_at, old_timestamp)
        parsed = datetime.fromisoformat(created_at)
        self.assertLess(
            abs((datetime.now(timezone.utc) - parsed).total_seconds()), 5
        )

    def test_load_state_retires_legacy_ui_pending_confirmation_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = classroom_active_state()
            state["pending_confirmations"] = {
                "ui_prototype": {"nonce": "legacy-ui-nonce"}
            }
            write_raw_state(project_root, state)

            migrated = load_state(project_root)

            self.assertNotIn("ui_prototype", migrated["pending_confirmations"])
            self.assertEqual(
                migrated["ui_prototype"]["confirmation_status"],
                "superseded_by_product_baseline",
            )
            self.assertNotIn(
                "pending_confirmation_nonce", migrated["ui_prototype"]
            )
            self.assertNotIn(
                "ui_prototype_user_confirmation", migrated["blocked_until"]
            )


if __name__ == "__main__":
    unittest.main()
