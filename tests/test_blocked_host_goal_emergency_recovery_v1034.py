import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import (
    ARTIFACT_ROOT,
    lifecycle_state_hash,
    load_state,
    runtime_status,
    write_state,
)
from product_delivery_agent.transition_journal import (
    append_transition,
    journal_integrity_errors,
)
from tests.test_host_goal_continuation_v1024 import (
    activate_host_goal,
    handed_off_workflow,
)


OWNER_THREAD_ID = "thread-v1034-emergency-owner"
RECOVERY_MESSAGE = "恢复被阻塞的 Host Goal 并继续当前交付"
TARGET_DELIVERY_ID = "26a6049314fe48caa1e7d4dcdb45c171"
TARGET_FEATURE_SLUG = "v0-7-response-evidence"
TARGET_BINDING_NONCE = "e987454240574c8dbf468f815a7f1d21"
TARGET_OBJECTIVE_SHA256 = (
    "7c0cab9d70d7c4586e9220f9d0274bad7c520d67fb932e7f503433463ffcf2db"
)
TARGET_LAUNCH_PACKAGE_HASH = (
    "aa1cc78edc37f1532865adf108dd688be208cedd6bae269cdd0cdf241a590528"
)
TARGET_OBJECTIVE = (
    "Complete Waygate Product Delivery for delivery "
    f"{TARGET_DELIVERY_ID}, feature {TARGET_FEATURE_SLUG}, launch package "
    f"{TARGET_LAUNCH_PACKAGE_HASH}, binding {TARGET_BINDING_NONCE}. Execute "
    "every planned TASK, record required evidence and reviews, and reach "
    "canonical closure. Pause without canonical delivery mutations for "
    "unresolved human decisions. Stop further delivery work after an explicit "
    "user stop."
)
RECOVERY_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "recover-blocked-host-goal-v1034.py"
)


def blocked_delivery(project_root: Path) -> dict:
    with patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}):
        workflow = handed_off_workflow(project_root)
        state = activate_host_goal(workflow)

    state["delivery_id"] = TARGET_DELIVERY_ID
    state["feature_slug"] = TARGET_FEATURE_SLUG
    state["host_goal_owner"].update(
        {
            "delivery_id": TARGET_DELIVERY_ID,
            "feature_slug": TARGET_FEATURE_SLUG,
        }
    )
    state["delivery_goal"].update(
        {
            "feature_slug": TARGET_FEATURE_SLUG,
            "launch_package_hash": TARGET_LAUNCH_PACKAGE_HASH,
        }
    )
    state["implementation_launch_authorization"].update(
        {
            "feature_slug": TARGET_FEATURE_SLUG,
            "launch_package_hash": TARGET_LAUNCH_PACKAGE_HASH,
        }
    )
    binding = copy.deepcopy(state["host_goal_binding"])
    binding.update(
        {
            "delivery_id": TARGET_DELIVERY_ID,
            "feature_slug": TARGET_FEATURE_SLUG,
            "binding_nonce": TARGET_BINDING_NONCE,
            "launch_package_hash": TARGET_LAUNCH_PACKAGE_HASH,
            "objective": TARGET_OBJECTIVE,
            "objective_sha256": TARGET_OBJECTIVE_SHA256,
            "status": "blocked",
            "human_wait": None,
            "pending_checkpoint": None,
            "authorized_transition": None,
            "last_observed_status": "blocked",
        }
    )
    state["host_goal_binding"] = binding
    state["status"] = "implementation_tasks_complete"
    state["stage"] = "executed_browser_evidence_passed"
    state["next_gate"] = "host_goal_resume_required"
    completed_tasks = [
        task["task_id"] for task in state["delivery_goal"]["planned_tasks"]
    ]
    state["implementation"] = {
        "current_task": "TASKS_COMPLETE",
        "completed_tasks": completed_tasks,
    }
    state["executed_browser_evidence"] = {
        "status": "passed",
        "records": [{"test_id": "TC-V008-001"}],
    }
    state["prototype_production_conformance"] = {
        "status": "missing",
        "records": [],
    }
    state["multi_agent_reviews"]["test_implementation"] = {
        "status": "missing",
        "artifact": None,
    }
    state["multi_agent_reviews"]["ui_conformance"] = {
        "status": "missing",
        "artifact": None,
    }
    state["closure_validation"] = {"status": "not_run"}
    state["delivery_goal"].update(
        {
            "status": "implementation_tasks_complete",
            "completed_tasks": completed_tasks,
            "current_task_cursor": None,
            "next_action": "record_executed_evidence_and_closure",
        }
    )
    state = append_transition(
        state,
        "task_completed",
        feature_slug=state["feature_slug"],
        runtime_version="1.0.34",
        metadata={"task_ids": completed_tasks},
    )
    return write_state(project_root, state)


def recovery_request(state: dict, *, dry_run: bool) -> dict:
    binding = state["host_goal_binding"]
    return {
        "schema_version": "v1",
        "action": "recover_blocked_host_goal",
        "delivery_id": state["delivery_id"],
        "feature_slug": state["feature_slug"],
        "binding_nonce": binding["binding_nonce"],
        "expected_objective_sha256": binding["objective_sha256"],
        "authorization_message": RECOVERY_MESSAGE,
        "host_turn_id": "goal-turn-v1034-recovery",
        "goal_observation": {
            "observation_source": "codex_goal_tool",
            "tool": "get_goal",
            "result": {
                "goal": {
                    "threadId": OWNER_THREAD_ID,
                    "objective": binding["objective"],
                    "status": "active",
                }
            },
        },
        "dry_run": dry_run,
    }


def run_recovery(
    project_root: Path,
    request: dict | str,
    *,
    thread_id: str = OWNER_THREAD_ID,
    override_runtime_hash: bool = True,
    override_state_hash: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CODEX_THREAD_ID"] = thread_id
    if override_runtime_hash:
        state_override = (
            "m.TARGET_STATE_FILE_SHA256=hashlib.sha256((Path(sys.argv[3])/"
            "m.ARTIFACT_ROOT/'state.json').read_bytes()).hexdigest();"
            if override_state_hash
            else ""
        )
        bootstrap = (
            "import hashlib,importlib.util,os,sys;"
            "from pathlib import Path;"
            "p=sys.argv[1];"
            "s=importlib.util.spec_from_file_location('recovery_under_test',p);"
            "m=importlib.util.module_from_spec(s);"
            "s.loader.exec_module(m);"
            "m.TARGET_RUNTIME_SHA256=m.current_runtime_provenance()"
            "['package_root_sha256'];"
            "m.TARGET_OWNER_THREAD_ID=os.environ['CODEX_THREAD_ID'];"
            + state_override
            +
            "raise SystemExit(m.main(sys.argv[2:]))"
        )
        command = [
            sys.executable,
            "-c",
            bootstrap,
            str(RECOVERY_SCRIPT),
            "--project-root",
            str(project_root),
        ]
    else:
        command = [
            sys.executable,
            str(RECOVERY_SCRIPT),
            "--project-root",
            str(project_root),
        ]
    return subprocess.run(
        command,
        input=request if isinstance(request, str) else json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def load_recovery_module(project_root: Path):
    spec = importlib.util.spec_from_file_location(
        "recovery_failure_injection", RECOVERY_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    state_path = project_root / ARTIFACT_ROOT / "state.json"
    module.TARGET_RUNTIME_SHA256 = module.current_runtime_provenance()[
        "package_root_sha256"
    ]
    module.TARGET_OWNER_THREAD_ID = OWNER_THREAD_ID
    module.TARGET_STATE_FILE_SHA256 = hashlib.sha256(
        state_path.read_bytes()
    ).hexdigest()
    return module


def workspace_file_snapshot(project_root: Path) -> dict[str, tuple[str, bytes | str]]:
    workspace = project_root / ARTIFACT_ROOT
    snapshot = {}
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink():
            snapshot[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            snapshot[relative] = ("file", path.read_bytes())
    return snapshot


class BlockedHostGoalEmergencyRecoveryV1034Tests(unittest.TestCase):
    def assert_rejected_without_state_change(
        self,
        project_root: Path,
        request: dict,
        expected_error: str,
        *,
        thread_id: str = OWNER_THREAD_ID,
        override_runtime_hash: bool = True,
        override_state_hash: bool = True,
    ) -> None:
        state_path = project_root / ARTIFACT_ROOT / "state.json"
        before_bytes = state_path.read_bytes()

        result = run_recovery(
            project_root,
            request,
            thread_id=thread_id,
            override_runtime_hash=override_runtime_hash,
            override_state_hash=override_state_hash,
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(expected_error, result.stderr)
        self.assertEqual(state_path.read_bytes(), before_bytes)

    def test_dry_run_then_recovery_preserves_delivery_and_runtime_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            before = blocked_delivery(project_root)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            before_bytes = state_path.read_bytes()
            protected = {
                "delivery_id": before["delivery_id"],
                "feature_slug": before["feature_slug"],
                "runtime_provenance": copy.deepcopy(before["runtime_provenance"]),
                "user_confirmations": copy.deepcopy(before["user_confirmations"]),
                "implementation": copy.deepcopy(before["implementation"]),
                "executed_browser_evidence": copy.deepcopy(
                    before["executed_browser_evidence"]
                ),
                "delivery_goal": copy.deepcopy(before["delivery_goal"]),
            }

            dry_run = run_recovery(
                project_root, recovery_request(before, dry_run=True)
            )

            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            dry_response = json.loads(dry_run.stdout)
            self.assertEqual(dry_response["result"], "dry_run")
            self.assertEqual(
                dry_response["next_gate"],
                "multi_agent_test_implementation_review",
            )
            self.assertEqual(
                dry_response["validation_results"],
                {
                    "binding_recoverable": True,
                    "goal_active_and_matching": True,
                    "journal_integrity": "passed",
                    "runtime_identity": "verified_waygate",
                    "state_write": "not_performed",
                },
            )
            self.assertEqual(state_path.read_bytes(), before_bytes)

            recovery = run_recovery(
                project_root, recovery_request(before, dry_run=False)
            )

            self.assertEqual(recovery.returncode, 0, recovery.stderr)
            response = json.loads(recovery.stdout)
            after = load_state(project_root)
            self.assertEqual(response["result"], "recovered")
            self.assertEqual(after["host_goal_binding"]["status"], "active")
            self.assertEqual(
                after["next_gate"], "multi_agent_test_implementation_review"
            )
            self.assertEqual(response["state_hash_after"], lifecycle_state_hash(after))
            self.assertEqual(runtime_status(after, after), "verified_waygate")
            self.assertEqual(journal_integrity_errors(after), [])
            self.assertEqual(
                after["transition_journal"]["events"][-1]["transition_name"],
                "host_goal_blocked_binding_recovered",
            )
            self.assertEqual(
                after["host_goal_binding_history"][-1]["reason"],
                "blocked_host_goal_emergency_recovery_v1034",
            )
            self.assertEqual(
                after["host_goal_binding_history"][-1]["binding"],
                before["host_goal_binding"],
            )
            allowed_state_changes = {
                "updated_at",
                "host_goal_binding",
                "host_goal_binding_history",
                "transition_journal",
                "next_gate",
            }
            self.assertEqual(
                {
                    key: value
                    for key, value in after.items()
                    if key not in allowed_state_changes
                },
                {
                    key: value
                    for key, value in before.items()
                    if key not in allowed_state_changes
                },
            )
            for key, expected in protected.items():
                self.assertEqual(after[key], expected, key)

    def test_rejects_unknown_request_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            request = recovery_request(state, dry_run=True)
            request["unexpected"] = True

            self.assert_rejected_without_state_change(
                project_root, request, "unknown fields"
            )

    def test_rejects_duplicate_json_keys_before_dry_run_can_be_overridden(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            before_bytes = state_path.read_bytes()
            raw_request = json.dumps(recovery_request(state, dry_run=True)).replace(
                '"dry_run": true',
                '"dry_run": true, "dry_run": false',
            )

            result = run_recovery(project_root, raw_request)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("duplicate JSON key: dry_run", result.stderr)
            self.assertEqual(state_path.read_bytes(), before_bytes)

    def test_rejects_non_standard_json_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            before_bytes = state_path.read_bytes()
            raw_request = json.dumps(recovery_request(state, dry_run=True)).replace(
                '"host_turn_id": "goal-turn-v1034-recovery"',
                '"host_turn_id": NaN',
            )

            result = run_recovery(project_root, raw_request)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("non-standard JSON constant: NaN", result.stderr)
            self.assertEqual(state_path.read_bytes(), before_bytes)

    def test_rejects_foreign_owner_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)

            self.assert_rejected_without_state_change(
                project_root,
                recovery_request(state, dry_run=True),
                "current CODEX_THREAD_ID",
                thread_id="thread-v1034-foreign",
            )

    def test_rejects_non_active_goal_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            request = recovery_request(state, dry_run=True)
            request["goal_observation"]["result"]["goal"]["status"] = "blocked"

            self.assert_rejected_without_state_change(
                project_root, request, "Host Goal must be active"
            )

    def test_rejects_objective_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            request = recovery_request(state, dry_run=True)
            request["goal_observation"]["result"]["goal"]["objective"] += " changed"

            self.assert_rejected_without_state_change(
                project_root, request, "objective mismatch"
            )

    def test_rejects_delivery_feature_and_binding_identity_mismatches(self):
        cases = {
            "delivery_id": "other-delivery",
            "feature_slug": "other-feature",
            "binding_nonce": "other-binding",
            "expected_objective_sha256": "0" * 64,
        }
        for field, invalid_value in cases.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                project_root = Path(tmp)
                state = blocked_delivery(project_root)
                request = recovery_request(state, dry_run=True)
                request[field] = invalid_value

                self.assert_rejected_without_state_change(
                    project_root, request, f"{field} mismatch"
                )

    def test_rejects_a_self_consistent_non_target_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            state["delivery_id"] = "other-delivery"
            state["host_goal_binding"]["delivery_id"] = "other-delivery"
            state["host_goal_owner"]["delivery_id"] = "other-delivery"
            state = write_state(project_root, state)

            self.assert_rejected_without_state_change(
                project_root,
                recovery_request(state, dry_run=True),
                "recovery is restricted to delivery",
            )

    def test_rejects_binding_with_human_wait(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            state["host_goal_binding"]["human_wait"] = {
                "decision_id": "decision-existing",
                "status": "pending",
            }
            state = write_state(project_root, state)

            self.assert_rejected_without_state_change(
                project_root,
                recovery_request(state, dry_run=True),
                "human_wait must be absent",
            )

    def test_rejects_binding_with_pending_checkpoint_or_authorized_transition(self):
        cases = {
            "pending_checkpoint": {"checkpoint_id": "checkpoint-existing"},
            "authorized_transition": {"checkpoint_id": "transition-existing"},
        }
        for field, value in cases.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                project_root = Path(tmp)
                state = blocked_delivery(project_root)
                state["host_goal_binding"][field] = value
                state = write_state(project_root, state)

                self.assert_rejected_without_state_change(
                    project_root,
                    recovery_request(state, dry_run=True),
                    field.replace("_", " "),
                )

    def test_rejects_wrong_delivery_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            state["stage"] = "implementation_in_progress"
            state = write_state(project_root, state)

            self.assert_rejected_without_state_change(
                project_root,
                recovery_request(state, dry_run=True),
                "stage must be executed_browser_evidence_passed",
            )

    def test_rejects_runtime_provenance_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            state["runtime_provenance"]["package_root_sha256"] = "0" * 64
            state = write_state(project_root, state)

            self.assert_rejected_without_state_change(
                project_root,
                recovery_request(state, dry_run=True),
                "runtime must remain verified_waygate",
            )

    def test_rejects_non_original_runtime_even_when_receipt_matches_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)

            self.assert_rejected_without_state_change(
                project_root,
                recovery_request(state, dry_run=True),
                "original runtime package hash mismatch",
                thread_id=OWNER_THREAD_ID,
                override_runtime_hash=False,
            )

    def test_rejects_incomplete_planned_task_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            extra_task = copy.deepcopy(state["delivery_goal"]["planned_tasks"][0])
            extra_task["task_id"] = "TASK-002"
            state["delivery_goal"]["planned_tasks"].append(extra_task)
            state = write_state(project_root, state)

            self.assert_rejected_without_state_change(
                project_root,
                recovery_request(state, dry_run=True),
                "all planned TASKs must be complete",
            )

    def test_target_runtime_hash_is_the_frozen_zhaobiao_receipt(self):
        source = RECOVERY_SCRIPT.read_text(encoding="utf-8")
        expected = (
            "c7ee45f75750e5563e288c64b2b18f3093b6501d2fdc38470c5789ccd53f9234"
        )
        self.assertIn(f'TARGET_RUNTIME_SHA256 = "{expected}"', source)

    def test_target_state_and_owner_are_frozen_to_zhaobiao(self):
        source = RECOVERY_SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            'TARGET_OWNER_THREAD_ID = "01a02a39-b3f6-7062-8a4b-e8a3cb399bbc"',
            source,
        )
        self.assertIn(
            'TARGET_STATE_FILE_SHA256 = "44e1447e328e660eca8054ae9e39dc0b28295069fb526df3dc6dc8ac55e4b702"',
            source,
        )

    def test_rejects_any_frozen_state_snapshot_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)

            self.assert_rejected_without_state_change(
                project_root,
                recovery_request(state, dry_run=True),
                "frozen recovery state snapshot mismatch",
                override_state_hash=False,
            )

    def test_persistence_failure_rolls_back_all_delivery_layout_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            module = load_recovery_module(project_root)
            before = workspace_file_snapshot(project_root)
            original_ensure_layout = module.ensure_delivery_layout

            def layout_then_fail(root, next_state):
                original_ensure_layout(root, next_state)
                raise RuntimeError("injected post-layout failure")

            with patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}), patch.object(
                module, "ensure_delivery_layout", side_effect=layout_then_fail
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "injected post-layout failure"
                ):
                    module.recover(
                        project_root,
                        recovery_request(state, dry_run=False),
                    )

            self.assertEqual(workspace_file_snapshot(project_root), before)

    def test_candidate_fsync_failure_removes_partial_file_and_allows_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            module = load_recovery_module(project_root)
            before = workspace_file_snapshot(project_root)
            candidate_path = (
                project_root
                / ARTIFACT_ROOT
                / "state.json.recovery-candidate.tmp"
            )

            with patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}), patch.object(
                module.os, "fsync", side_effect=OSError("injected candidate fsync failure")
            ):
                with self.assertRaisesRegex(
                    OSError, "injected candidate fsync failure"
                ):
                    module.recover(
                        project_root,
                        recovery_request(state, dry_run=False),
                    )

            self.assertEqual(workspace_file_snapshot(project_root), before)
            self.assertFalse(candidate_path.exists())

            with patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}):
                response = module.recover(
                    project_root,
                    recovery_request(state, dry_run=False),
                )

            self.assertEqual(response["result"], "recovered")
            self.assertFalse(candidate_path.exists())

    def test_candidate_cleanup_failure_rolls_back_commit_and_allows_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            module = load_recovery_module(project_root)
            before = workspace_file_snapshot(project_root)
            candidate_path = (
                project_root
                / ARTIFACT_ROOT
                / "state.json.recovery-candidate.tmp"
            )
            original_unlink = Path.unlink
            cleanup_failed = False

            def fail_first_candidate_cleanup(path, *args, **kwargs):
                nonlocal cleanup_failed
                if path == candidate_path and not cleanup_failed:
                    cleanup_failed = True
                    raise OSError("injected candidate cleanup failure")
                return original_unlink(path, *args, **kwargs)

            with patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}), patch.object(
                Path, "unlink", new=fail_first_candidate_cleanup
            ):
                with self.assertRaisesRegex(
                    OSError, "injected candidate cleanup failure"
                ):
                    module.recover(
                        project_root,
                        recovery_request(state, dry_run=False),
                    )

            self.assertTrue(cleanup_failed)
            self.assertEqual(workspace_file_snapshot(project_root), before)
            self.assertFalse(candidate_path.exists())

            with patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}):
                response = module.recover(
                    project_root,
                    recovery_request(state, dry_run=False),
                )

            self.assertEqual(response["result"], "recovered")
            self.assertFalse(candidate_path.exists())

    def test_compare_and_swap_rejects_change_after_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            module = load_recovery_module(project_root)
            original_exchange = module._atomic_exchange
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            injected = False

            def change_then_exchange(left, right):
                nonlocal injected
                if not injected:
                    injected = True
                    current = json.loads(state_path.read_text(encoding="utf-8"))
                    current["concurrent_writer_marker"] = True
                    state_path.write_text(
                        json.dumps(current, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                return original_exchange(left, right)

            with patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID}), patch.object(
                module, "_atomic_exchange", side_effect=change_then_exchange
            ):
                with self.assertRaisesRegex(
                    module.RecoveryError,
                    "frozen recovery state changed during commit",
                ):
                    module.recover(
                        project_root,
                        recovery_request(state, dry_run=False),
                    )

            after = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertTrue(after["concurrent_writer_marker"])
            self.assertEqual(after["host_goal_binding"]["status"], "blocked")

    def test_rejects_repeated_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = blocked_delivery(project_root)
            request = recovery_request(state, dry_run=False)
            first = run_recovery(project_root, request)
            self.assertEqual(first.returncode, 0, first.stderr)

            self.assert_rejected_without_state_change(
                project_root,
                request,
                "binding status must be blocked",
            )


if __name__ == "__main__":
    unittest.main()
