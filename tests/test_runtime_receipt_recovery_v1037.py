import copy
import hashlib
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import (
    ARTIFACT_ROOT,
    load_state,
    write_state,
)
from product_delivery_agent.artifact_store import ensure_delivery_layout
from product_delivery_agent.host_goal import stable_hash
from product_delivery_agent.transition_journal import _event_hash, append_transition
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


OWNER_THREAD_ID = "thread-v1037-classroom-owner"
FEATURE_SLUG = "v1.6.4-brand-delivery-material-generation-layout-optimization"
RECOVERY_MESSAGE = "用户确认恢复 1.0.36 runtime receipt 到 1.0.37"
WAYGATE_1034_RECEIPT = {
    "plugin_name": "waygate-product-delivery",
    "plugin_version": "1.0.34",
    "package_root_sha256": (
        "8632f3ab98351164a96014d42c4f7800a2a844f794ebb86c7ba7907ea22fbe12"
    ),
}
WAYGATE_1036_RECEIPT = {
    "plugin_name": "waygate-product-delivery",
    "plugin_version": "1.0.36",
    "package_root_sha256": (
        "8fbaf18d7dcc83e5363325e2b9e5661e248b3293d288cff09b3b385ae8776f72"
    ),
}
WAYGATE_1037_RECEIPT = {
    "plugin_name": "waygate-product-delivery",
    "plugin_version": "1.0.37",
    "package_root_sha256": "1" * 64,
}


@patch.dict(os.environ, {"CODEX_THREAD_ID": OWNER_THREAD_ID})
class RuntimeReceiptRecoveryV1037Tests(unittest.TestCase):
    @contextmanager
    def _pin_fixture_as_recovery_target(
        self, project_root: Path, *, pin_v1037_runtime: bool = True
    ):
        state_path = project_root / ARTIFACT_ROOT / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        journal = state["transition_journal"]
        with patch.multiple(
            "product_delivery_agent.workflow",
            RUNTIME_RECEIPT_RECOVERY_TARGET_DELIVERY_ID=state["delivery_id"],
            RUNTIME_RECEIPT_RECOVERY_TARGET_FEATURE_SLUG=state["feature_slug"],
            RUNTIME_RECEIPT_RECOVERY_TARGET_OWNER_THREAD_ID=(
                state["host_goal_owner"]["coordinator_thread_id"]
            ),
            RUNTIME_RECEIPT_RECOVERY_TARGET_STATE_SHA256=hashlib.sha256(
                state_path.read_bytes()
            ).hexdigest(),
            RUNTIME_RECEIPT_RECOVERY_TARGET_JOURNAL_EVENT_COUNT=len(
                journal["events"]
            ),
            RUNTIME_RECEIPT_RECOVERY_TARGET_JOURNAL_LAST_HASH=journal[
                "last_event_hash"
            ],
        ):
            if not pin_v1037_runtime:
                yield
                return
            with patch(
                "product_delivery_agent.workflow.current_runtime_provenance",
                return_value=WAYGATE_1037_RECEIPT,
            ), patch(
                "product_delivery_agent.artifact_protocol.current_runtime_provenance",
                return_value=WAYGATE_1037_RECEIPT,
            ), patch("product_delivery_agent.workflow.PLUGIN_VERSION", "1.0.37"):
                yield

    @staticmethod
    def _rehash_journal(state: dict) -> None:
        previous_hash = "0" * 64
        for sequence, event in enumerate(
            state["transition_journal"]["events"], start=1
        ):
            event["sequence"] = sequence
            event["previous_event_hash"] = previous_hash
            event.pop("event_hash", None)
            event["event_hash"] = _event_hash(event)
            previous_hash = event["event_hash"]
        state["transition_journal"]["last_event_hash"] = previous_hash

    def _write_1036_state(self, project_root: Path) -> dict:
        workflow = ProductDeliveryWorkflow(project_root)
        state = workflow.start(
            feature_slug=FEATURE_SLUG,
            multi_agent_mode="spawned_subagents_authorized",
        )
        state["transition_journal"] = {"schema_version": "v1", "events": []}
        state = append_transition(
            state,
            "current_pointer_switched",
            feature_slug=FEATURE_SLUG,
            runtime_version="1.0.34",
            metadata={"delivery_id": state["delivery_id"]},
        )
        state = append_transition(
            state,
            "delivery_activated",
            feature_slug=FEATURE_SLUG,
            runtime_version="1.0.34",
            metadata=WAYGATE_1034_RECEIPT,
        )
        state = append_transition(
            state,
            "product_contract_frozen",
            feature_slug=FEATURE_SLUG,
            runtime_version="1.0.34",
            metadata={"preserved_evidence": True},
        )
        state["runtime_provenance"] = dict(WAYGATE_1036_RECEIPT)
        state = append_transition(
            state,
            "runtime_receipt_recovered",
            feature_slug=FEATURE_SLUG,
            runtime_version="1.0.36",
            input_artifact_hashes={
                "runtime_receipt": stable_hash(WAYGATE_1034_RECEIPT)
            },
            output_artifact_hashes={
                "runtime_receipt": stable_hash(WAYGATE_1036_RECEIPT)
            },
            metadata={
                "from_plugin_version": "1.0.34",
                "to_plugin_version": "1.0.36",
            },
        )
        write_state(project_root, state)
        return load_state(project_root)

    def _write_direct_1036_activation(self, project_root: Path) -> dict:
        state = ProductDeliveryWorkflow(project_root).start(
            feature_slug=FEATURE_SLUG,
            multi_agent_mode="spawned_subagents_authorized",
        )
        state["transition_journal"] = {"schema_version": "v1", "events": []}
        state = append_transition(
            state,
            "current_pointer_switched",
            feature_slug=FEATURE_SLUG,
            runtime_version="1.0.36",
            metadata={"delivery_id": state["delivery_id"]},
        )
        state = append_transition(
            state,
            "delivery_activated",
            feature_slug=FEATURE_SLUG,
            runtime_version="1.0.36",
            metadata=WAYGATE_1036_RECEIPT,
        )
        state["runtime_provenance"] = dict(WAYGATE_1036_RECEIPT)
        write_state(project_root, state)
        return load_state(project_root)

    @staticmethod
    def _write_state_and_layout_without_lock(
        project_root: Path,
        state: dict,
    ) -> None:
        state_path = project_root / ARTIFACT_ROOT / "state.json"
        state_path.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        ensure_delivery_layout(project_root, state)

    def _assert_state_and_layout_match(
        self,
        project_root: Path,
        marker: str,
    ) -> None:
        state_path = project_root / ARTIFACT_ROOT / "state.json"
        state = load_state(project_root)
        delivery_state_path = (
            project_root
            / ARTIFACT_ROOT
            / "deliveries"
            / state["feature_slug"]
            / state["delivery_id"]
            / "state.json"
        )
        delivery_state = json.loads(delivery_state_path.read_text(encoding="utf-8"))
        current_pointer = json.loads(
            (project_root / ARTIFACT_ROOT / "current.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(state.get("concurrent_marker"), marker)
        self.assertEqual(delivery_state.get("concurrent_marker"), marker)
        self.assertEqual(state_path.read_bytes(), delivery_state_path.read_bytes())
        self.assertEqual(
            current_pointer["state_sha256"],
            hashlib.sha256(delivery_state_path.read_bytes()).hexdigest(),
        )

    def test_valid_1034_to_1036_chain_upgrades_only_receipt_and_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            before = self._write_1036_state(project_root)
            protected = copy.deepcopy(before)
            protected.pop("runtime_provenance")
            protected.pop("transition_journal")
            protected.pop("updated_at", None)
            prior_events = copy.deepcopy(before["transition_journal"]["events"])

            with self._pin_fixture_as_recovery_target(project_root):
                recovered = ProductDeliveryWorkflow(
                    project_root
                ).recover_runtime_receipt(RECOVERY_MESSAGE)

            self.assertEqual(recovered["runtime_provenance"], WAYGATE_1037_RECEIPT)
            self.assertEqual(recovered["transition_journal"]["events"][:-1], prior_events)
            event = recovered["transition_journal"]["events"][-1]
            self.assertEqual(event["transition_name"], "runtime_receipt_recovered")
            self.assertEqual(event["runtime_version"], "1.0.37")
            self.assertEqual(
                event["metadata"],
                {
                    "from_plugin_version": "1.0.36",
                    "to_plugin_version": "1.0.37",
                },
            )
            actual_protected = copy.deepcopy(recovered)
            actual_protected.pop("runtime_provenance")
            actual_protected.pop("transition_journal")
            actual_protected.pop("updated_at", None)
            self.assertEqual(actual_protected, protected)
            with self._pin_fixture_as_recovery_target(project_root):
                self.assertEqual(
                    ProductDeliveryWorkflow(project_root).status()["runtime_status"],
                    "verified_waygate",
                )

    def test_v1038_runtime_does_not_replay_the_v1037_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_1036_state(project_root)

            with self._pin_fixture_as_recovery_target(
                project_root, pin_v1037_runtime=False
            ):
                with self.assertRaisesRegex(
                    WorkflowError, "requires Waygate 1.0.37"
                ):
                    ProductDeliveryWorkflow(project_root).recover_runtime_receipt(
                        RECOVERY_MESSAGE
                    )

    def test_rejects_valid_chain_for_non_classroom_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_1036_state(project_root)

            with self.assertRaisesRegex(WorkflowError, "Classroom delivery"):
                ProductDeliveryWorkflow(project_root).recover_runtime_receipt(
                    RECOVERY_MESSAGE
                )

    def test_concurrent_state_change_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_1036_state(project_root)
            workflow = ProductDeliveryWorkflow(project_root)
            original_exchange = ProductDeliveryWorkflow._atomic_exchange
            exchange_count = 0

            def exchange_after_concurrent_change(left: Path, right: Path) -> None:
                nonlocal exchange_count
                exchange_count += 1
                if exchange_count == 1:
                    concurrent = load_state(project_root)
                    concurrent["concurrent_marker"] = "must-survive"
                    self._write_state_and_layout_without_lock(
                        project_root, concurrent
                    )
                original_exchange(left, right)

            with self._pin_fixture_as_recovery_target(project_root):
                with patch.object(
                    ProductDeliveryWorkflow,
                    "_atomic_exchange",
                    side_effect=exchange_after_concurrent_change,
                ):
                    with self.assertRaisesRegex(
                        WorkflowError, "changed during commit"
                    ):
                        workflow.recover_runtime_receipt(RECOVERY_MESSAGE)

            self._assert_state_and_layout_match(project_root, "must-survive")

    def test_concurrent_state_change_during_layout_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            stale_state = self._write_1036_state(project_root)
            stale_state["concurrent_marker"] = "late-writer-must-survive"

            def replace_state_during_layout(root: Path, candidate: dict) -> dict:
                self._write_state_and_layout_without_lock(root, stale_state)
                return load_state(root)

            with self._pin_fixture_as_recovery_target(project_root):
                with patch(
                    "product_delivery_agent.artifact_store.ensure_delivery_layout",
                    side_effect=replace_state_during_layout,
                ):
                    with self.assertRaisesRegex(
                        WorkflowError, "changed during commit"
                    ):
                        ProductDeliveryWorkflow(
                            project_root
                        ).recover_runtime_receipt(RECOVERY_MESSAGE)

            self.assertEqual(
                load_state(project_root)["runtime_provenance"],
                WAYGATE_1036_RECEIPT,
            )
            self._assert_state_and_layout_match(
                project_root, "late-writer-must-survive"
            )

    def test_layout_refresh_failure_rolls_back_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_1036_state(project_root)
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            before_bytes = state_path.read_bytes()

            with self._pin_fixture_as_recovery_target(project_root):
                with patch(
                    "product_delivery_agent.artifact_store.ensure_delivery_layout",
                    side_effect=OSError("injected layout failure"),
                ):
                    with self.assertRaisesRegex(WorkflowError, "persistence failed"):
                        ProductDeliveryWorkflow(
                            project_root
                        ).recover_runtime_receipt(RECOVERY_MESSAGE)

            self.assertEqual(state_path.read_bytes(), before_bytes)

    def test_rejects_direct_1036_activation_without_1034_recovery_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_direct_1036_activation(project_root)

            with self._pin_fixture_as_recovery_target(project_root):
                with self.assertRaisesRegex(
                    WorkflowError, "1.0.34 activation.*1.0.36 recovery"
                ):
                    ProductDeliveryWorkflow(project_root).recover_runtime_receipt(
                        RECOVERY_MESSAGE
                    )

    def test_rejects_tampered_journal_without_writing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = self._write_1036_state(project_root)
            state["transition_journal"]["events"][-1]["metadata"][
                "to_plugin_version"
            ] = "tampered"
            state_path = project_root / ARTIFACT_ROOT / "state.json"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            original_bytes = state_path.read_bytes()

            with self._pin_fixture_as_recovery_target(project_root):
                with self.assertRaisesRegex(WorkflowError, "intact journal"):
                    ProductDeliveryWorkflow(project_root).recover_runtime_receipt(
                        RECOVERY_MESSAGE
                    )

            self.assertEqual(state_path.read_bytes(), original_bytes)

    def test_rejects_hash_valid_chain_bound_to_another_delivery_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = self._write_1036_state(project_root)
            pointer_event = next(
                event
                for event in state["transition_journal"]["events"]
                if event["transition_name"] == "current_pointer_switched"
            )
            pointer_event["metadata"]["delivery_id"] = "foreign-delivery"
            self._rehash_journal(state)
            write_state(project_root, state)

            with self._pin_fixture_as_recovery_target(project_root):
                with self.assertRaisesRegex(WorkflowError, "delivery pointer"):
                    ProductDeliveryWorkflow(project_root).recover_runtime_receipt(
                        RECOVERY_MESSAGE
                    )

    def test_rejects_foreign_owner_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_1036_state(project_root)

            with self._pin_fixture_as_recovery_target(project_root):
                with patch.dict(os.environ, {"CODEX_THREAD_ID": "foreign-thread"}):
                    with self.assertRaisesRegex(WorkflowError, "coordinator thread"):
                        ProductDeliveryWorkflow(project_root).recover_runtime_receipt(
                            RECOVERY_MESSAGE
                        )

    def test_rejects_policy_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = self._write_1036_state(project_root)
            state["multi_agent_policy"]["authorization_delivery_id"] = "foreign"
            write_state(project_root, state)

            with self._pin_fixture_as_recovery_target(project_root):
                with self.assertRaisesRegex(
                    WorkflowError, "multi-agent authorization"
                ):
                    ProductDeliveryWorkflow(project_root).recover_runtime_receipt(
                        RECOVERY_MESSAGE
                    )

    def test_rejects_unknown_1036_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state = self._write_1036_state(project_root)
            state["runtime_provenance"]["package_root_sha256"] = "f" * 64
            write_state(project_root, state)

            with self._pin_fixture_as_recovery_target(project_root):
                with self.assertRaisesRegex(
                    WorkflowError, "unsupported.*1.0.36 receipt"
                ):
                    ProductDeliveryWorkflow(project_root).recover_runtime_receipt(
                        RECOVERY_MESSAGE
                    )

    def test_rejects_inactive_or_terminal_delivery(self):
        for case in ("inactive", "terminal"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                project_root = Path(tmp)
                state = self._write_1036_state(project_root)
                if case == "inactive":
                    state["active"] = False
                else:
                    state["delivery_lifecycle"]["status"] = "closed"
                write_state(project_root, state)

                with self._pin_fixture_as_recovery_target(project_root):
                    with self.assertRaisesRegex(
                        WorkflowError, "active nonterminal"
                    ):
                        ProductDeliveryWorkflow(
                            project_root
                        ).recover_runtime_receipt(RECOVERY_MESSAGE)

    def test_rejects_replay_and_non_exact_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_1036_state(project_root)
            workflow = ProductDeliveryWorkflow(project_root)

            with self.assertRaisesRegex(WorkflowError, "explicit user authorization"):
                workflow.recover_runtime_receipt("继续")

            with self._pin_fixture_as_recovery_target(project_root):
                workflow.recover_runtime_receipt(RECOVERY_MESSAGE)
            with self._pin_fixture_as_recovery_target(project_root):
                with self.assertRaisesRegex(WorkflowError, "active invalid_runtime"):
                    workflow.recover_runtime_receipt(RECOVERY_MESSAGE)


if __name__ == "__main__":
    unittest.main()
