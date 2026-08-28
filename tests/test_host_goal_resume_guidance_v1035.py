import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import load_state, write_state
from product_delivery_agent.continuation import derive_continuation_status
from product_delivery_agent.hooks import (
    build_prompt_context,
    build_resume_context,
    check_final_summary_guardrail,
    check_stop_guardrail,
)
from tests.test_host_goal_continuation_v1024 import (
    activate_host_goal,
    goal_result,
    handed_off_workflow,
)


OWNER_THREAD_ID = "thread-v1035-host-goal-guidance"
STRONG_GUIDANCE = {
    "schema_version": "v1",
    "required_now": True,
    "recommended_action": "resume_current_host_goal",
    "recommended_command": "/goal resume",
    "avoid_action": "clear_current_host_goal",
    "avoid_command": "/goal clear",
    "stop_delivery_command": "$waygate-product-delivery abandon",
    "display_message": (
        "当前 Host Goal 仍为 Blocked。若要继续本次交付，请先选择 Resume（或执行 `/goal resume`）；"
        "不要选择 Clear。Clear 只会移除 Host Goal，不会终止 Waygate 交付。Goal 恢复为 Active 后将"
        "沿用当前 decision_id，已经提交的确认无需重答。若要终止交付，请执行 "
        "`$waygate-product-delivery abandon`。"
    ),
}


class HostGoalResumeGuidanceV1035Tests(unittest.TestCase):
    def _active_waiting_workflow(self, project_root: Path):
        workflow = handed_off_workflow(project_root)
        active = activate_host_goal(workflow)
        state = workflow.status()
        state["blocked_until"] = ["requirements_clarification"]
        write_state(project_root, state)
        return workflow, active

    def _block_after_three_turns(self, workflow, active):
        objective = active["host_goal_binding"]["objective"]
        decision_id = None
        for index in range(1, 4):
            request = workflow.prepare_host_goal_reconciliation(
                "turn_start",
                target_gate=active["next_gate"],
                host_turn_id=f"goal-turn-v1035-{index}",
            )
            decision_id = decision_id or request["decision_id"]
            workflow.record_host_goal_observation(
                request["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(objective),
                },
            )
        block = workflow.prepare_host_goal_reconciliation(
            "block_goal",
            target_gate=active["next_gate"],
            host_turn_id="goal-turn-v1035-3",
        )
        blocked = workflow.record_host_goal_observation(
            block["checkpoint_id"],
            {
                "observation_source": "codex_goal_tool",
                "tool": "update_goal",
                "result": goal_result(objective, status="blocked"),
            },
        )
        return decision_id, objective, blocked

    def test_first_human_prompt_previews_guidance_once(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}
        ):
            workflow, active = self._active_waiting_workflow(Path(tmp))
            objective = active["host_goal_binding"]["objective"]

            first = workflow.prepare_host_goal_reconciliation(
                "turn_start",
                target_gate=active["next_gate"],
                host_turn_id="goal-turn-v1035-preview-1",
            )
            guidance = first["host_goal_user_guidance"]
            self.assertFalse(guidance["required_now"])
            self.assertEqual(guidance["recommended_command"], "/goal resume")
            self.assertEqual(guidance["avoid_command"], "/goal clear")
            self.assertEqual(
                guidance["stop_delivery_command"],
                "$waygate-product-delivery abandon",
            )
            for command in (
                "/goal resume",
                "/goal clear",
                "$waygate-product-delivery abandon",
            ):
                self.assertIn(command, guidance["display_message"])
            workflow.record_host_goal_observation(
                first["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(objective),
                },
            )

            repeated = workflow.prepare_host_goal_reconciliation(
                "turn_start",
                target_gate=active["next_gate"],
                host_turn_id="goal-turn-v1035-preview-2",
            )
            self.assertFalse(repeated["should_prompt"])
            self.assertNotIn("host_goal_user_guidance", repeated)

    def test_blocked_continuation_and_observation_return_strong_guidance(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}
        ):
            project_root = Path(tmp)
            workflow, active = self._active_waiting_workflow(project_root)

            _, _, blocked = self._block_after_three_turns(workflow, active)

            self.assertEqual(blocked["host_goal_user_guidance"], STRONG_GUIDANCE)
            continuation = derive_continuation_status(load_state(project_root))
            self.assertEqual(continuation["status"], "wait_for_user")
            self.assertEqual(
                continuation["host_goal_user_guidance"], STRONG_GUIDANCE
            )
            self.assertNotIn(
                "host_goal_user_guidance", load_state(project_root)
            )

    def test_blocked_resume_keeps_wait_and_active_resume_reuses_decision(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}
        ):
            project_root = Path(tmp)
            workflow, active = self._active_waiting_workflow(project_root)
            decision_id, objective, _ = self._block_after_three_turns(
                workflow, active
            )

            first_resume = workflow.prepare_host_goal_reconciliation(
                "user_resume",
                decision_id=decision_id,
                user_message="按已提交的确认继续",
            )
            self.assertEqual(first_resume["decision_id"], decision_id)
            still_blocked = workflow.record_host_goal_observation(
                first_resume["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(objective, status="blocked"),
                },
            )
            self.assertEqual(still_blocked["host_goal_user_guidance"], STRONG_GUIDANCE)
            self.assertEqual(
                still_blocked["host_goal_binding"]["human_wait"]["status"],
                "pending",
            )
            self.assertEqual(
                still_blocked["host_goal_binding"]["human_wait"]["decision_id"],
                decision_id,
            )
            self.assertIsNone(
                still_blocked["host_goal_binding"].get("authorized_transition")
            )
            self.assertIn("requirements_clarification", still_blocked["blocked_until"])

            second_resume = workflow.prepare_host_goal_reconciliation(
                "user_resume",
                decision_id=decision_id,
                user_message="Host Goal 已恢复，继续原确认",
            )
            self.assertEqual(second_resume["decision_id"], decision_id)
            resumed = workflow.record_host_goal_observation(
                second_resume["checkpoint_id"],
                {
                    "observation_source": "codex_goal_tool",
                    "tool": "get_goal",
                    "result": goal_result(objective),
                },
            )
            self.assertNotIn("host_goal_user_guidance", resumed)
            self.assertEqual(resumed["host_goal_binding"]["status"], "active")
            self.assertEqual(
                resumed["host_goal_binding"]["human_wait"]["status"],
                "resolved",
            )
            self.assertEqual(
                resumed["host_goal_binding"]["human_wait"]["decision_id"],
                decision_id,
            )
            self.assertNotIn("requirements_clarification", resumed["blocked_until"])
            self.assertEqual(
                resumed["host_goal_binding"]["authorized_transition"]["target_gate"],
                active["next_gate"],
            )

    def test_hooks_restore_guidance_only_while_host_goal_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}
        ):
            project_root = Path(tmp)
            workflow, active = self._active_waiting_workflow(project_root)
            for hook_result in (
                build_resume_context(project_root),
                build_prompt_context(project_root),
                check_stop_guardrail(project_root),
                check_final_summary_guardrail(project_root),
            ):
                self.assertIsNone(hook_result.host_goal_user_guidance)

            self._block_after_three_turns(workflow, active)

            for hook_result in (
                build_resume_context(project_root),
                build_prompt_context(project_root),
                check_stop_guardrail(project_root),
                check_final_summary_guardrail(project_root),
            ):
                self.assertEqual(
                    hook_result.host_goal_user_guidance,
                    STRONG_GUIDANCE,
                )

    def test_blocked_guidance_survives_higher_priority_decisions(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}
        ):
            project_root = Path(tmp)
            workflow, active = self._active_waiting_workflow(project_root)
            self._block_after_three_turns(workflow, active)

            visual_state = load_state(project_root)
            visual_state["pending_user_decisions"] = {
                "task_visual_conformance:TASK-001": {"status": "pending"}
            }
            write_state(project_root, visual_state)
            visual_decision = derive_continuation_status(load_state(project_root))
            self.assertEqual(
                visual_decision["next_action"],
                "task_visual_conformance_adjudication",
            )
            self.assertEqual(
                visual_decision["host_goal_user_guidance"], STRONG_GUIDANCE
            )

            invalid_state = load_state(project_root)
            invalid_state["pending_user_decisions"] = {}
            invalid_state["protocol_errors"] = ["invalid_runtime_fixture"]
            write_state(project_root, invalid_state)
            for hook_result in (
                build_resume_context(project_root),
                build_prompt_context(project_root),
                check_stop_guardrail(project_root),
                check_final_summary_guardrail(project_root),
            ):
                self.assertFalse(hook_result.passed)
                self.assertEqual(
                    hook_result.host_goal_user_guidance,
                    STRONG_GUIDANCE,
                )

            owner_state = load_state(project_root)
            owner_state["protocol_errors"] = []
            write_state(project_root, owner_state)
            with patch.dict(
                os.environ,
                {"CODEX_THREAD_ID": "thread-v1035-foreign-owner"},
            ):
                owner_decision = derive_continuation_status(
                    load_state(project_root)
                )
            self.assertEqual(owner_decision["next_action"], "host_goal_owner_recovery")
            self.assertEqual(
                owner_decision["host_goal_user_guidance"], STRONG_GUIDANCE
            )


if __name__ == "__main__":
    unittest.main()
