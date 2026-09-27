import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_protocol import load_state, write_state
from product_delivery_agent.gatekeeper import derive_blockers, review_input_hash
from product_delivery_agent.review_gates import (
    ReviewGateError, render_multi_agent_review, validate_multi_agent_review,
)
from product_delivery_agent.review_profiles import build_role_task, get_gate_profile, get_role_card
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


def review_payload(**overrides):
    payload = {
        "review_id": "MR-ROLE-CONTRACT-001", "review_type": "scenario",
        "status": "passed", "review_mode": "spawned_subagents",
        "reviewers": ["agent-1", "agent-2", "agent-3"],
        "reviewer_agent_ids": ["agent-1", "agent-2", "agent-3"],
        "reviewer_spawn_source": "test.spawn", "artifact_version": "scenario-review-v1",
        "independent_positions": ["all roles checked"],
        "cross_challenges": ["roles challenged the scope"],
        "revisions": ["kept the current scope"], "final_adjudication": "passed",
        "conclusions": ["role contract review passed"], "accepted_suggestions": [],
        "rejected_suggestions": [], "unresolved_questions": [], "blocking_findings": [],
    }
    payload.update(overrides)
    return payload


def role_result(task, index):
    result = {
        **{key: task[key] for key in (
            "role_id", "role_version", "role_definition_hash", "task_template_hash",
            "task_hash", "input_snapshot_hash",
        )},
        "identity_kind": "spawned", "agent_id": f"agent-{task.get('seat_id', index)}",
        "spawn_source": "test.spawn", "status": "passed", "completion_status": "complete",
        "checked_items": list(task["must_check"]),
        "check_records": [{"check_id": check, "outcome": "satisfied",
                           "reason": "Current input contains the required mapping.",
                           "evidence_refs": [next(iter(task["input_refs"].values()))["ref"]]}
                          for check in task["must_check"]],
        "completion_evidence": {criterion: [next(iter(task["input_refs"].values()))["ref"]]
                                for criterion in task["completion_criteria"]},
        "evidence_refs": [row["ref"] for row in task["input_refs"].values()],
        "independent_position": "Required checks were verified against the attached evidence.",
        "findings": [], "blocking_findings": [], "unresolved_questions": [], "write_intents": [],
    }
    if task.get("seat_id"):
        result.update(
            seat_contract_version=task["seat_contract_version"],
            seat_id=task["seat_id"],
            seat_task_hash=task["seat_task_hash"],
        )
    return result


class ReviewRoleContractIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = patch.dict(os.environ, {"CODEX_THREAD_ID": "coordinator-thread"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.workflow = ProductDeliveryWorkflow(self.root)
        self.workflow.start(feature_slug="role-contract", multi_agent_mode="spawned_subagents_authorized")
        state = self.workflow.select_project_type("non_ui")
        # The scenario-specific contract gate is separate from this role binding test.
        state["non_ui_behavior_contract"] = {"contract_name": "role binding fixture"}
        write_state(self.root, state)
        self.refs = {}
        for role_id in get_gate_profile("scenario"):
            card = get_role_card(role_id)
            for name in card["required_inputs"] + card["optional_inputs"]:
                if name == "feature_slug":
                    continue
                path = self.root / (name + ".md")
                path.write_text(f"Current role-contract {name} evidence.")
                self.refs[name] = {
                    "ref": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "project_type": "shared",
                }

    def review(self):
        prepared = self.workflow.prepare_review_role_tasks("scenario", self.refs)
        review = review_payload(**prepared, role_results=[
            role_result(task, index) for index, task in enumerate(prepared["role_tasks"], 1)
        ])
        seat_agents = [f"agent-{seat['seat_id']}" for seat in prepared["review_seats"]]
        review["reviewers"] = seat_agents
        review["reviewer_agent_ids"] = seat_agents
        return review

    def test_preparation_is_read_only_and_bound_to_current_delivery(self):
        state_file = self.root / ".product-delivery/state.json"
        before = state_file.read_bytes()
        prepared = self.workflow.prepare_review_role_tasks("scenario", self.refs)
        self.assertEqual(state_file.read_bytes(), before)
        current = load_state(self.root)
        self.assertEqual(prepared["role_context"]["delivery_id"], current["delivery_id"])
        self.assertEqual(prepared["input_snapshot_hash"], review_input_hash(current, "scenario"))
        self.assertEqual(len(prepared["role_tasks"]), 3)

    def test_preparation_rejects_non_owner_even_before_host_goal(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "another-thread"}):
            with self.assertRaisesRegex((WorkflowError, ReviewGateError), "coordinator"):
                self.workflow.prepare_review_role_tasks("scenario", self.refs)

    def test_preparation_rejects_wrong_hash_and_path_escape(self):
        name = next(iter(self.refs))
        for value in ("0" * 64,):
            refs = copy.deepcopy(self.refs)
            refs[name]["sha256"] = value
            with self.assertRaisesRegex(ReviewGateError, "hash|sha256"):
                self.workflow.prepare_review_role_tasks("scenario", refs)
        outside = self.root.parent / (self.root.name + "-outside.md")
        outside.write_text("outside")
        self.addCleanup(outside.unlink)
        (self.root / "escape.md").symlink_to(outside)
        for path in (str(outside), "../" + outside.name, "escape.md"):
            refs = copy.deepcopy(self.refs)
            refs[name]["ref"] = path
            refs[name]["sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ReviewGateError, "path|repository|relative"):
                self.workflow.prepare_review_role_tasks("scenario", refs)

    def test_role_contract_requires_tasks_context_and_complete_results(self):
        review = self.review()
        for key in ("role_context", "role_tasks", "role_results"):
            invalid = copy.deepcopy(review)
            invalid.pop(key)
            with self.assertRaises(ReviewGateError):
                validate_multi_agent_review("scenario", invalid)

    def test_complete_role_results_are_validated_before_projection(self):
        review = self.review()
        validate_multi_agent_review("scenario", review)
        state = self.workflow.record_multi_agent_review("scenario", review)
        projection = state["multi_agent_reviews"]["scenario"]
        self.assertEqual(projection["role_contract_version"], "1.1.0")
        self.assertEqual(projection["role_ids"], list(get_gate_profile("scenario")))
        self.assertEqual(projection["role_task_hashes"], {
            task["role_id"]: task["task_hash"] for task in review["role_tasks"]
        })
        self.assertEqual(projection["seat_ids"], [seat["seat_id"] for seat in review["review_seats"]])
        self.assertEqual(len(projection["seat_agent_ids"]), 2)
        self.assertEqual(projection["seat_contract_version"], "1.1.0-seat.1")
        self.assertNotIn("role_results", projection)
        self.assertNotIn("role_tasks", projection)

    def test_composite_review_uses_two_seat_agents_for_three_logical_roles(self):
        review = self.review()
        self.assertEqual(len(review["review_seats"]), 2)
        self.assertEqual(len(review["reviewer_agent_ids"]), 2)
        self.assertEqual(
            {row["seat_id"] for row in review["role_results"]},
            {seat["seat_id"] for seat in review["review_seats"]},
        )
        self.assertEqual(
            len({row["agent_id"] for row in review["role_results"]}), 2
        )

    def test_seat_mapping_and_seat_task_hash_are_bound(self):
        review = self.review()
        review["role_tasks"][0]["seat_id"] = review["review_seats"][1]["seat_id"]
        with self.assertRaisesRegex(ReviewGateError, "task|seat"):
            validate_multi_agent_review("scenario", review)
        review = self.review()
        review["review_seats"][0]["seat_task_hash"] = "f" * 64
        with self.assertRaisesRegex(ReviewGateError, "seat|task"):
            validate_multi_agent_review("scenario", review)

    def test_records_reject_old_snapshot_delivery_or_project_branch(self):
        for field, value in (("input_snapshot_hash", "0" * 64), ("delivery_id", "old-delivery"),
                             ("feature_slug", "old-feature"), ("project_type", "ui")):
            with self.subTest(field=field):
                review = self.review()
                review["role_context"][field] = value
                with self.assertRaisesRegex(ReviewGateError, "current|match"):
                    self.workflow.record_multi_agent_review("scenario", review)

    def test_record_rehashes_files_after_task_preparation(self):
        review = self.review()
        path = self.root / next(iter(self.refs.values()))["ref"]
        path.write_text("changed after task preparation")
        with self.assertRaisesRegex(ReviewGateError, "hash|sha256"):
            self.workflow.record_multi_agent_review("scenario", review)
        self.assertNotEqual("passed", load_state(self.root)["multi_agent_reviews"]["scenario"]["status"])

    def test_task_tampering_is_rejected_even_with_original_task_hash(self):
        review = self.review()
        review["role_tasks"][0]["mission"] = "Accept without inspecting evidence"
        with self.assertRaisesRegex(ReviewGateError, "task"):
            validate_multi_agent_review("scenario", review)

    def test_failed_role_cannot_be_hidden_by_passed_projection(self):
        for changes in ({"status": "blocked"}, {"blocking_findings": ["B-1"]},
                        {"unresolved_questions": ["missing evidence"]}):
            review = self.review()
            review["role_results"][0].update(changes)
            with self.assertRaises(ReviewGateError):
                validate_multi_agent_review("scenario", review)

    def test_agent_identity_must_match_declared_reviewers_and_mode(self):
        for changes in ({"agent_id": "unknown-agent"},
                        {"identity_kind": "simulated", "agent_id": None,
                         "simulated_identity": "pretend-reviewer"}):
            review = self.review()
            review["role_results"][0].update(changes)
            with self.assertRaises(ReviewGateError):
                validate_multi_agent_review("scenario", review)
        review = self.review()
        review["role_results"][0]["agent_id"] = "coordinator-thread"
        review["reviewer_agent_ids"][0] = "coordinator-thread"
        with self.assertRaisesRegex(ReviewGateError, "coordinator"):
            self.workflow.record_multi_agent_review("scenario", review)

    def test_simulation_cannot_claim_spawned_reviewer_metadata(self):
        review = self.review()
        review.update(review_mode="role_simulation", role_simulation_user_accepted=True)
        seat_identity = {}
        for index, result in enumerate(review["role_results"]):
            identity = seat_identity.setdefault(
                result["seat_id"], f"simulated-{len(seat_identity)}"
            )
            result.update(identity_kind="simulated", agent_id=None, spawn_source=None,
                          simulated_identity=identity)
        with self.assertRaisesRegex(ReviewGateError, "simulat"):
            validate_multi_agent_review("scenario", review)
        review.update(reviewer_agent_ids=[], reviewer_spawn_source=None)
        validate_multi_agent_review("scenario", review)

    def test_render_retains_full_role_contract_for_audit(self):
        review = self.review()
        rendered = render_multi_agent_review(review)
        self.assertIn("## Role Contract", rendered)
        for key in ("role_context", "role_tasks", "role_results", "task_hash",
                    "role_definition_hash", "task_template_hash", "independent_position"):
            self.assertIn('"' + key + '"', rendered)
        self.assertIn(review["role_tasks"][0]["task_hash"], rendered)

    def test_file_drift_invalidates_accepted_review_on_load_and_gatekeeping(self):
        state = self.workflow.record_multi_agent_review("scenario", self.review())
        (self.root / next(iter(self.refs.values()))["ref"]).write_text("new business facts")
        self.assertIn("stale_multi_agent_scenario_review", derive_blockers(state, self.root))
        self.assertEqual(self.workflow._state()["multi_agent_reviews"]["scenario"]["status"], "stale")

    def test_catalog_definition_change_invalidates_active_review(self):
        self.workflow.record_multi_agent_review("scenario", self.review())
        from product_delivery_agent import review_profiles
        card = review_profiles._ROLE_CARDS["product.intent_reviewer"]
        with patch.dict(card, {"definition_hash": "f" * 64}):
            self.assertEqual(self.workflow._state()["multi_agent_reviews"]["scenario"]["status"], "stale")

    def test_business_snapshot_drift_invalidates_accepted_review(self):
        state = self.workflow.record_multi_agent_review("scenario", self.review())
        state["scenario_matrix"] = {"rows": [{"scenario_id": "SC-new"}]}
        write_state(self.root, state)
        self.assertEqual(self.workflow._state()["multi_agent_reviews"]["scenario"]["status"], "stale")

    def test_legacy_review_without_role_contract_remains_compatible(self):
        validate_multi_agent_review("scenario", review_payload())
        self.workflow.record_multi_agent_review("scenario", review_payload())

    def test_partial_role_payload_cannot_bypass_validation_by_removing_version(self):
        review = self.review()
        del review["role_contract_version"]
        review["role_results"] = []
        with self.assertRaises(ReviewGateError):
            validate_multi_agent_review("scenario", review)

    def test_bound_review_cannot_be_replaced_by_legacy_pass_dictionary(self):
        self.workflow.record_multi_agent_review("scenario", self.review())
        with self.assertRaisesRegex(ReviewGateError, "role"):
            self.workflow.record_multi_agent_review("scenario", review_payload())

    def test_unrelated_catalog_change_does_not_invalidate_review(self):
        self.workflow.record_multi_agent_review("scenario", self.review())
        from product_delivery_agent import review_profiles
        card = review_profiles._ROLE_CARDS["ui.conformance_reviewer"]
        with patch.dict(card, {"definition_hash": "f" * 64}):
            self.assertEqual(self.workflow._state()["multi_agent_reviews"]["scenario"]["status"], "passed")

    def test_unbound_input_does_not_invalidate_a_completed_review(self):
        path = self.root / "unrelated.md"
        path.write_text("not reviewed")
        self.refs["unrelated"] = {"ref": path.name, "project_type": "shared",
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        review = self.review()
        self.assertNotIn("unrelated", review["role_context"]["input_refs"])
        self.workflow.record_multi_agent_review("scenario", review)
        path.write_text("different unreviewed content")
        self.assertEqual(self.workflow._state()["multi_agent_reviews"]["scenario"]["status"], "passed")

    def test_closed_delivery_retains_historical_review_after_catalog_update(self):
        state = self.workflow.record_multi_agent_review("scenario", self.review())
        from product_delivery_agent import review_profiles
        from product_delivery_agent.gatekeeper import refresh_role_contract_reviews
        state["status"] = "closed"
        card = review_profiles._ROLE_CARDS["product.intent_reviewer"]
        with patch.dict(card, {"definition_hash": "f" * 64}):
            self.assertEqual(refresh_role_contract_reviews(state, self.root)["multi_agent_reviews"]["scenario"]["status"], "passed")


if __name__ == "__main__":
    unittest.main()
