#!/usr/bin/env python3
"""One-shot recovery for the V2.1 completed-handoff implementation mirror."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = PLUGIN_ROOT / "runtime"
if not RUNTIME.is_dir():
    RUNTIME = PLUGIN_ROOT / "plugins/waygate-product-delivery/runtime"
sys.path.insert(0, str(RUNTIME))

from product_delivery_agent.artifact_protocol import current_runtime_provenance, runtime_status
from product_delivery_agent.host_goal import stable_hash as host_goal_stable_hash
from product_delivery_agent.transition_journal import append_transition, journal_integrity_errors
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


AUTHORIZATION = (
    "授权发起 CR008：修复 Waygate completed handoff mirror，并按修复版 runtime 的受支持迁移入口恢复当前 delivery。"
)
DELIVERY_ID = "06ebce38bc2d49458e0c61ab5c40e75a"
FEATURE_SLUG = "v2.1-classroom-quiz-ai-analysis"
OWNER_THREAD = "01a1a461-56c5-77f2-a73e-766207705271"
BINDING_NONCE = "3da96a3d41334b92ae6a9b5b0c293148"
OBJECTIVE_SHA256 = "509b53495ea8a476a7acdf581070e47a786307547b5e1564bdb7a7a44cb30393"
SOURCE_RECEIPT = {
    "plugin_name": "waygate-product-delivery",
    "plugin_version": "1.1.0",
    "package_root_sha256": "5f767aa96ada0f1bbd29748dd660b1aaf261c5ab26a286235fa04278613d1eed",
}


def require(value: object, reason: str) -> None:
    if not value:
        raise WorkflowError(reason)


def main() -> int:
    request = json.load(sys.stdin)
    allowed = {
        "schema_version", "authorization_message", "project_root", "expected_state_sha256",
        "expected_journal_event_count", "expected_journal_last_hash", "goal_observation", "dry_run",
    }
    require(isinstance(request, dict) and set(request) == allowed, "recovery request fields mismatch")
    require(request["schema_version"] == "v1", "recovery schema mismatch")
    require(request["authorization_message"] == AUTHORIZATION, "exact CR008 authorization is required")
    root = Path(request["project_root"]).resolve()
    state_path = root / ".product-delivery/state.json"
    before = state_path.read_bytes()
    before_sha = hashlib.sha256(before).hexdigest()
    require(before_sha == request["expected_state_sha256"], "recovery state SHA mismatch")
    state = json.loads(before)
    require(state.get("runtime_provenance") == SOURCE_RECEIPT, "recovery source receipt mismatch")
    require(runtime_status(state, state) == "invalid_runtime", "recovery requires invalid_runtime source")
    require(not journal_integrity_errors(state), "recovery journal integrity failed")
    journal = state["transition_journal"]
    require(len(journal["events"]) == request["expected_journal_event_count"], "recovery journal count mismatch")
    require(journal["last_event_hash"] == request["expected_journal_last_hash"], "recovery journal anchor mismatch")
    binding = state.get("host_goal_binding") or {}
    owner = state.get("host_goal_owner") or {}
    require(state.get("delivery_id") == DELIVERY_ID and state.get("feature_slug") == FEATURE_SLUG,
            "recovery delivery identity mismatch")
    require(owner.get("coordinator_thread_id") == OWNER_THREAD and binding.get("owner_thread_id") == OWNER_THREAD,
            "recovery owner mismatch")
    require(binding.get("binding_nonce") == BINDING_NONCE and binding.get("objective_sha256") == OBJECTIVE_SHA256,
            "recovery binding mismatch")
    require(not binding.get("human_wait") and not binding.get("pending_checkpoint") and not binding.get("authorized_transition"),
            "recovery requires no pending Host Goal transition")
    observed = request["goal_observation"].get("goal") or {}
    require(observed.get("threadId") == OWNER_THREAD and observed.get("status") == "active",
            "recovery requires fresh active Host Goal observation")
    require(host_goal_stable_hash(observed.get("objective")) == OBJECTIVE_SHA256,
            "recovery Host Goal objective mismatch")
    require(state.get("stage") == "multi_agent_test_implementation_review_passed"
            and state.get("next_gate") == "prototype_production_conformance",
            "recovery delivery stage mismatch")
    goal = state.get("delivery_goal") or {}
    implementation = state.get("implementation") or {}
    expected_tasks = [f"TASK-{index:03d}" for index in range(1, 45)]
    require(goal.get("status") == "implementation_tasks_complete"
            and goal.get("current_task_cursor") is None
            and goal.get("completed_tasks") == expected_tasks,
            "recovery TASK completion mismatch")
    require(implementation.get("current_task") is None
            and implementation.get("completed_tasks") == expected_tasks,
            "recovery mirror is not the exact completed-handoff defect")
    require((state.get("executed_browser_evidence") or {}).get("status") == "passed"
            and (state.get("multi_agent_reviews") or {}).get("test_implementation", {}).get("status") == "passed",
            "recovery closure prerequisites mismatch")
    target_receipt = current_runtime_provenance()
    require(target_receipt != SOURCE_RECEIPT and target_receipt.get("plugin_version") == "1.1.0",
            "recovery requires the distinct fixed Waygate 1.1.0 runtime")
    if request["dry_run"]:
        require(state_path.read_bytes() == before, "dry run changed state")
        print(json.dumps({"result": "dry_run_passed", "state_sha256": before_sha,
                          "source_runtime_provenance": SOURCE_RECEIPT,
                          "target_runtime_provenance": target_receipt}, sort_keys=True))
        return 0
    state["runtime_provenance"] = target_receipt
    state["implementation"] = {**implementation, "current_task": "TASKS_COMPLETE"}
    state = append_transition(
        state, "runtime_receipt_recovered", feature_slug=FEATURE_SLUG,
        runtime_version="1.1.0",
        input_artifact_hashes={"runtime_receipt": host_goal_stable_hash(SOURCE_RECEIPT)},
        output_artifact_hashes={"runtime_receipt": host_goal_stable_hash(target_receipt)},
        metadata={"recovery_scope": "completed_handoff_mirror_v111",
                  "authorization_sha256": host_goal_stable_hash(AUTHORIZATION)},
    )
    workflow = ProductDeliveryWorkflow(root)
    persisted = workflow._commit_pinned_runtime_receipt_recovery(
        state_path, state, expected_state_sha256=before_sha,
        candidate_filename="state.json.completed-handoff-mirror-v111-candidate.tmp",
    )
    print(json.dumps({"result": "recovered", "state_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest(),
                      "implementation_current_task": persisted["implementation"]["current_task"],
                      "runtime_provenance": persisted["runtime_provenance"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (WorkflowError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        print(f"completed-handoff recovery blocked: {error}", file=sys.stderr)
        raise SystemExit(1)
