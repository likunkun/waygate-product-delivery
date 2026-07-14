import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, write_state
from product_delivery_agent.continuation import derive_continuation_status
from product_delivery_agent.hooks import (
    check_final_summary_guardrail,
    check_stop_guardrail,
)


def active_state(**overrides):
    state = {
        "active": True,
        "stage": "scenario_matrix_draft_ready",
        "project_type": "ui",
        "next_gate": "multi_agent_scenario_review",
        "blocked_until": [],
        "pending_confirmations": {},
        "confirmation_points": {
            "product_brief": {"confirmed": True},
            "version_scope": {"confirmed": True},
            "ui_prototype_review": {"confirmed": True},
        },
        "artifact_paths": {
            "product_brief": "artifacts/product-brief.md",
            "version_scope": "artifacts/version-scope.md",
            "ui_prototype_review": "artifacts/ui-prototype-review.md",
        },
        "closure_validation": {"status": "not_run", "errors": []},
    }
    state.update(overrides)
    return state


def write_required_artifacts(project_root):
    artifacts_dir = project_root / ARTIFACT_ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for filename in (
        "product-brief.md",
        "version-scope.md",
        "ui-prototype-review.md",
    ):
        (artifacts_dir / filename).write_text("# ok\n", encoding="utf-8")


class ContinuationGuardTests(unittest.TestCase):
    def test_pending_multi_agent_authorization_waits_for_user_immediately(self):
        result = derive_continuation_status(
            active_state(
                next_gate="multi_agent_mode_selection",
                multi_agent_policy={
                    "mode": "authorization_pending",
                    "execution_authorization": "pending",
                },
                pending_user_decisions={
                    "multi_agent_mode": {"status": "pending"},
                },
            )
        )

        self.assertEqual(result["status"], "wait_for_user")
        self.assertTrue(result["can_stop"])
        self.assertEqual(result["next_action"], "multi_agent_mode_selection")

    def test_invalidated_multi_agent_authorization_waits_for_user_when_active(self):
        result = derive_continuation_status(
            active_state(
                multi_agent_policy={"execution_authorization": "invalidated"},
            )
        )

        self.assertEqual(result["status"], "wait_for_user")
        self.assertEqual(result["next_action"], "multi_agent_mode_selection")
        self.assertIn("pending_user_decision:multi_agent_mode", result["blockers"])

    def test_active_next_gate_without_user_wait_must_continue(self):
        result = derive_continuation_status(active_state())

        self.assertEqual(result["status"], "must_continue")
        self.assertFalse(result["can_stop"])
        self.assertEqual(result["next_action"], "multi_agent_scenario_review")

    def test_pending_confirmation_allows_waiting_for_user(self):
        result = derive_continuation_status(
            active_state(
                next_gate="ui_prototype_review_confirmation",
                pending_confirmations={"ui_prototype": {"nonce": "abc"}},
            )
        )

        self.assertEqual(result["status"], "wait_for_user")
        self.assertTrue(result["can_stop"])
        self.assertIn("pending_confirmation:ui_prototype", result["blockers"])

    def test_internal_pending_confirmation_must_continue(self):
        result = derive_continuation_status(
            active_state(
                next_gate="codex_goal_handoff",
                pending_confirmations={
                    "implementation_launch_authorization": {"nonce": "abc"},
                    "handoff": {"artifact_path": "artifacts/handoff.md"},
                    "test_coverage_audit": {"artifact_path": "artifacts/test-coverage-audit.md"},
                },
            )
        )

        self.assertEqual(result["status"], "must_continue")
        self.assertFalse(result["can_stop"])
        self.assertEqual(result["next_action"], "codex_goal_handoff")
        self.assertNotIn(
            "pending_confirmation:implementation_launch_authorization",
            result["blockers"],
        )

    def test_stale_review_blocker_must_continue_to_review_gate(self):
        result = derive_continuation_status(
            active_state(
                next_gate="codex_goal_handoff",
                blocked_until=["stale_multi_agent_test_coverage_review"],
            )
        )

        self.assertEqual(result["status"], "must_continue")
        self.assertFalse(result["can_stop"])
        self.assertEqual(result["next_action"], "multi_agent_test_coverage_review")
        self.assertIn("stale_multi_agent_test_coverage_review", result["blockers"])

    def test_stale_requirements_e2e_confirmation_returns_to_combined_confirmation(self):
        result = derive_continuation_status(
            active_state(
                next_gate="codex_goal_handoff",
                blocked_until=["stale_requirements_e2e_confirmation"],
            )
        )

        self.assertEqual(result["status"], "must_continue")
        self.assertFalse(result["can_stop"])
        self.assertEqual(result["next_action"], "requirements_e2e_user_confirmation")
        self.assertIn("stale_requirements_e2e_confirmation", result["blockers"])

    def test_closure_plugin_version_mismatch_blocks_continuation(self):
        result = derive_continuation_status(
            active_state(
                status="closure_failed",
                stage="closure_failed",
                next_gate="feature_closure_after_implementation",
                closure_validation={
                    "status": "closure_failed",
                    "errors": ["canonical_closure_plugin_version"],
                },
            )
        )

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["can_stop"])
        self.assertIn("canonical_closure_plugin_version", result["blockers"])

    def test_stop_guard_blocks_active_main_flow_with_next_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_required_artifacts(project_root)
            write_state(project_root, active_state())

            result = check_stop_guardrail(project_root)

            self.assertFalse(result.passed)
            self.assertEqual(result.message, "continuation_guard=must_continue")
            self.assertIn("next_gate:multi_agent_scenario_review", result.missing_items)

    def test_final_summary_guard_uses_same_continuation_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_required_artifacts(project_root)
            write_state(project_root, active_state())

            result = check_final_summary_guardrail(project_root)

            self.assertFalse(result.passed)
            self.assertEqual(result.message, "continuation_guard=must_continue")

    def test_stop_guard_allows_pending_user_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_required_artifacts(project_root)
            write_state(
                project_root,
                active_state(
                    next_gate="ui_prototype_review_confirmation",
                    pending_confirmations={"ui_prototype": {"nonce": "abc"}},
                ),
            )

            result = check_stop_guardrail(project_root)

            self.assertTrue(result.passed)
            self.assertEqual(result.message, "continuation_guard=wait_for_user")


if __name__ == "__main__":
    unittest.main()
