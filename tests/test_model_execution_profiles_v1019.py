import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state
from product_delivery_agent.continuation import derive_continuation_status
from product_delivery_agent.model_profiles import (
    ModelProfileError,
    resolve_model_profiles,
    select_model_for_stage,
)
from product_delivery_agent.review_gates import ReviewGateError
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


class ModelExecutionProfilesV1019Tests(unittest.TestCase):
    def test_profile_precedence_is_delivery_project_user_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            codex_home = root / "codex"
            user_path = codex_home / "waygate-product-delivery" / "model-profiles.json"
            project_path = (
                project_root
                / ARTIFACT_ROOT
                / "config"
                / "model-profiles.json"
            )
            user_path.parent.mkdir(parents=True)
            project_path.parent.mkdir(parents=True)
            user_path.write_text(
                json.dumps(
                    {
                        "schema_version": "v1",
                        "profiles": {
                            "full_speed": {
                                "reasoning_effort": "high",
                            },
                            "automatic": {
                                "stages": {
                                    "implementation": {
                                        "model": "gpt-5.4",
                                        "reasoning_effort": "medium",
                                    }
                                }
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            project_path.write_text(
                json.dumps(
                    {
                        "schema_version": "v1",
                        "profiles": {
                            "automatic": {
                                "stages": {
                                    "implementation": {
                                        "reasoning_effort": "high",
                                    },
                                    "browser_evidence": {
                                        "model": "gpt-5.6-luna",
                                        "reasoning_effort": "high",
                                    },
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            resolved = resolve_model_profiles(
                project_root,
                codex_home=codex_home,
                delivery_overrides={
                    "automatic": {
                        "stages": {
                            "implementation": {
                                "model": "gpt-5.6-terra",
                            }
                        }
                    }
                },
            )

            self.assertEqual(resolved["profiles"]["full_speed"]["model"], "gpt-5.6-sol")
            self.assertEqual(resolved["profiles"]["full_speed"]["reasoning_effort"], "high")
            implementation = resolved["profiles"]["automatic"]["stages"]["implementation"]
            self.assertEqual(implementation["model"], "gpt-5.6-terra")
            self.assertEqual(implementation["reasoning_effort"], "high")
            self.assertEqual(
                resolved["profiles"]["automatic"]["stages"]["browser_evidence"]["model"],
                "gpt-5.6-luna",
            )
            self.assertEqual(
                resolved["sources"],
                ["builtin", "user", "project", "delivery"],
            )

    def test_unknown_model_requires_explicit_unverified_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ModelProfileError):
                resolve_model_profiles(
                    root,
                    delivery_overrides={
                        "full_speed": {
                            "model": "custom-frontier",
                            "reasoning_effort": "high",
                        }
                    },
                )

            resolved = resolve_model_profiles(
                root,
                delivery_overrides={
                    "full_speed": {
                        "model": "custom-frontier",
                        "reasoning_effort": "high",
                        "allow_unverified_model": True,
                    }
                },
            )
            self.assertEqual(
                resolved["profiles"]["full_speed"]["model"],
                "custom-frontier",
            )

    def test_plain_start_waits_for_both_startup_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp), codex_home=Path(tmp) / "codex")

            state = workflow.start()

            self.assertEqual(state["next_gate"], "startup_mode_selection")
            self.assertIn("multi_agent_mode", state["pending_user_decisions"])
            self.assertIn("execution_mode", state["pending_user_decisions"])
            self.assertEqual(
                state["execution_model_policy"]["authorization_status"],
                "pending",
            )
            continuation = derive_continuation_status(state)
            self.assertEqual(continuation["status"], "wait_for_user")
            self.assertEqual(continuation["next_action"], "startup_mode_selection")
            self.assertEqual(
                continuation["blockers"],
                [
                    "pending_user_decision:multi_agent_mode",
                    "pending_user_decision:execution_mode",
                ],
            )

    def test_combined_startup_configuration_authorizes_both_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp), codex_home=Path(tmp) / "codex")
            workflow.start()

            state = workflow.configure_startup_modes(
                "automatic",
                "spawned_subagents_authorized",
                "启动交付，自动模式，多 Agent 模式",
            )

            self.assertEqual(
                state["multi_agent_policy"]["execution_authorization"],
                "authorized",
            )
            self.assertEqual(state["execution_model_policy"]["mode"], "automatic")
            self.assertEqual(
                state["execution_model_policy"]["authorization_status"],
                "authorized",
            )
            self.assertEqual(state["pending_user_decisions"], {})
            self.assertEqual(state["next_gate"], "product_blueprint")
            review_stage = workflow.begin_execution_stage(
                "review",
                agent_id="skeptic-1",
                risk_flags=["skeptic_adjudication"],
            )
            self.assertEqual(review_stage["assignment"]["model"], "gpt-5.6-sol")
            self.assertEqual(
                review_stage["state"]["execution_model_policy"]["stage_agent_assignments"][0]["agent_id"],
                "skeptic-1",
            )
            self.assertEqual(
                review_stage["assignment"]["state_owner"],
                "main_coordinator",
            )

    def test_legacy_review_startup_still_waits_for_execution_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp), codex_home=Path(tmp) / "codex")

            state = workflow.start(
                multi_agent_mode="spawned_subagents_authorized",
            )

            self.assertNotIn("multi_agent_mode", state["pending_user_decisions"])
            self.assertIn("execution_mode", state["pending_user_decisions"])
            self.assertEqual(state["next_gate"], "startup_mode_selection")
            with self.assertRaises(WorkflowError):
                workflow.select_project_type("ui")
            with self.assertRaises(ReviewGateError):
                workflow.record_multi_agent_review("scenario", {})

    def test_full_speed_requires_matching_main_thread_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp), codex_home=Path(tmp) / "codex")
            workflow.start()
            state = workflow.configure_startup_modes(
                "full_speed",
                "spawned_subagents_authorized",
                "启动交付，全速模式，多 Agent 模式",
            )

            self.assertIn("main_thread_model", state["pending_user_decisions"])
            mismatch = workflow.record_main_thread_model_observation(
                model="gpt-5.6-terra",
                reasoning_effort="high",
                source="host_context",
            )
            self.assertEqual(
                mismatch["execution_model_policy"]["main_thread_observation"]["status"],
                "mismatch",
            )
            self.assertIn("main_thread_model", mismatch["pending_user_decisions"])

            matched = workflow.record_main_thread_model_observation(
                model="gpt-5.6-sol",
                reasoning_effort="xhigh",
                source="host_context",
            )
            self.assertEqual(
                matched["execution_model_policy"]["main_thread_observation"]["status"],
                "matched",
            )
            self.assertNotIn("main_thread_model", matched["pending_user_decisions"])
            self.assertEqual(matched["next_gate"], "product_blueprint")

    def test_automatic_stage_selection_and_escalation(self):
        with tempfile.TemporaryDirectory() as tmp:
            resolved = resolve_model_profiles(Path(tmp))
            profile = resolved["profiles"]["automatic"]

            routine = select_model_for_stage(profile, "implementation")
            escalated = select_model_for_stage(
                profile,
                "implementation",
                consecutive_failures=2,
            )
            closure = select_model_for_stage(profile, "closure")

            self.assertEqual(routine["model"], "gpt-5.6-terra")
            self.assertEqual(routine["reasoning_effort"], "high")
            self.assertEqual(escalated["model"], "gpt-5.6-sol")
            self.assertEqual(escalated["reasoning_effort"], "xhigh")
            self.assertEqual(escalated["selection_reason"], "consecutive_failures")
            self.assertEqual(closure["model"], "gpt-5.6-sol")
            self.assertFalse(closure["fork_context"])
            self.assertFalse(closure["canonical_state_writes"])

    def test_full_speed_custom_profile_is_used_for_every_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            resolved = resolve_model_profiles(
                Path(tmp),
                delivery_overrides={
                    "full_speed": {
                        "model": "gpt-5.5",
                        "reasoning_effort": "xhigh",
                    }
                },
            )
            profile = resolved["profiles"]["full_speed"]

            for stage in (
                "discovery",
                "product_design",
                "implementation",
                "browser_evidence",
                "review",
                "closure",
            ):
                assignment = select_model_for_stage(profile, stage, full_speed=True)
                self.assertEqual(assignment["model"], "gpt-5.5")
                self.assertEqual(assignment["reasoning_effort"], "xhigh")

    def test_mode_switch_is_frozen_until_next_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp), codex_home=Path(tmp) / "codex")
            workflow.start(
                execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized",
            )
            original_hash = workflow.status()["execution_model_policy"]["profile_hash"]

            requested = workflow.request_execution_mode_switch(
                "full_speed",
                "切换交付执行模式：全速模式",
                model_profile_overrides={
                    "full_speed": {
                        "model": "gpt-5.5",
                        "reasoning_effort": "xhigh",
                    }
                },
            )

            self.assertEqual(requested["execution_model_policy"]["mode"], "automatic")
            self.assertEqual(
                requested["execution_model_policy"]["profile_hash"],
                original_hash,
            )
            self.assertEqual(
                requested["execution_model_policy"]["pending_switch"]["mode"],
                "full_speed",
            )

            workflow.record_main_thread_model_observation(
                model="gpt-5.5",
                reasoning_effort="xhigh",
                source="host_context",
            )

            stage = workflow.begin_execution_stage("implementation")
            self.assertEqual(stage["state"]["execution_model_policy"]["mode"], "full_speed")
            self.assertEqual(stage["assignment"]["model"], "gpt-5.5")

    def test_config_changes_do_not_mutate_active_snapshot_without_explicit_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ProductDeliveryWorkflow(
                root / "project",
                codex_home=root / "codex",
            )
            workflow.start(
                execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized",
            )
            original_hash = workflow.status()["execution_model_policy"]["profile_hash"]
            workflow.save_model_profiles(
                scope="project",
                profiles={
                    "automatic": {
                        "stages": {
                            "implementation": {
                                "model": "gpt-5.4",
                                "reasoning_effort": "high",
                            }
                        }
                    }
                },
            )

            unchanged = workflow.status()
            self.assertEqual(
                unchanged["execution_model_policy"]["profile_hash"],
                original_hash,
            )
            requested = workflow.request_execution_mode_switch(
                "automatic",
                "切换交付执行模式：自动模式",
            )
            pending = requested["execution_model_policy"]["pending_switch"]
            self.assertNotEqual(pending["profile_hash"], original_hash)
            self.assertEqual(
                pending["selected_profile"]["stages"]["implementation"]["model"],
                "gpt-5.4",
            )

    def test_save_profiles_supports_user_and_project_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ProductDeliveryWorkflow(
                root / "project",
                codex_home=root / "codex",
            )
            profiles = {
                "full_speed": {
                    "model": "gpt-5.5",
                    "reasoning_effort": "xhigh",
                }
            }

            user_result = workflow.save_model_profiles(scope="user", profiles=profiles)
            project_result = workflow.save_model_profiles(scope="project", profiles=profiles)

            self.assertTrue(Path(user_result["path"]).is_file())
            self.assertTrue(Path(project_result["path"]).is_file())
            self.assertEqual(
                json.loads(Path(project_result["path"]).read_text(encoding="utf-8"))["schema_version"],
                "v1",
            )

    def test_active_v1018_state_requires_execution_mode_but_terminal_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "active": True,
                        "stage": "implementation_in_progress",
                        "multi_agent_policy": {
                            "mode": "spawned_subagents_required",
                            "execution_authorization": "authorized",
                        },
                    }
                ),
                encoding="utf-8",
            )

            active = load_state(project_root)
            self.assertEqual(
                active["execution_model_policy"]["authorization_status"],
                "legacy_unverified",
            )
            self.assertIn("execution_mode", active["pending_user_decisions"])
            self.assertEqual(active["next_gate"], "startup_mode_selection")

            state_path.write_text(
                json.dumps(
                    {
                        "active": False,
                        "status": "closed",
                        "stage": "feature_closure_passed",
                    }
                ),
                encoding="utf-8",
            )
            terminal = load_state(project_root)
            self.assertNotIn("execution_model_policy", terminal)
            self.assertNotIn("execution_mode", terminal["pending_user_decisions"])

    def test_legacy_execution_mode_migration_recovers_at_stage_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "active": True,
                        "stage": "implementation_in_progress",
                        "multi_agent_policy": {
                            "mode": "spawned_subagents_required",
                            "execution_authorization": "authorized",
                            "authorization_scope": "current_delivery",
                            "authorization_source": "startup_command",
                            "authorized_review_types": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            workflow = ProductDeliveryWorkflow(
                project_root,
                codex_home=project_root / "codex",
            )

            migrated = load_state(project_root)
            self.assertEqual(
                migrated["execution_model_policy"]["authorization_status"],
                "legacy_unverified",
            )
            self.assertIn("execution_mode", migrated["pending_user_decisions"])

            workflow.request_execution_mode_switch(
                "automatic",
                "切换交付执行模式：自动模式",
            )
            recovered = workflow.begin_execution_stage("product_design")["state"]

            self.assertEqual(
                recovered["execution_model_policy"]["authorization_status"],
                "authorized",
            )
            self.assertEqual(recovered["execution_model_policy"]["mode"], "automatic")
            self.assertNotIn("execution_mode", recovered["pending_user_decisions"])
            workflow.select_project_type("ui")

    def test_authorized_stage_clears_only_stale_execution_mode_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            workflow = ProductDeliveryWorkflow(
                project_root,
                codex_home=project_root / "codex",
            )
            state = workflow.start(
                execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized",
            )
            state["pending_user_decisions"] = {
                "execution_mode": {"status": "pending"},
                "main_thread_model": {"status": "pending"},
            }
            state["execution_model_policy"]["pending_switch"] = None
            (project_root / ARTIFACT_ROOT / "state.json").write_text(
                json.dumps(state),
                encoding="utf-8",
            )

            recovered = workflow.begin_execution_stage("product_design")["state"]

            self.assertEqual(
                recovered["execution_model_policy"]["authorization_status"],
                "authorized",
            )
            self.assertNotIn("execution_mode", recovered["pending_user_decisions"])
            self.assertIn("main_thread_model", recovered["pending_user_decisions"])


if __name__ == "__main__":
    unittest.main()
