import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent import review_profiles as profiles
from product_delivery_agent.review_profiles import (
    ROLE_IDS, SEAT_PROFILE_VERSION, RoleProfileError, build_gate_tasks,
    build_role_task, get_gate_profile, get_gate_seat_profile, get_role_card,
    validate_role_result, validate_role_results,
)


def context_for(review_type, role_id):
    card = get_role_card(role_id)
    keys = set(card["required_inputs"] + card["optional_inputs"]) - {"feature_slug"}
    if review_type == "test_implementation":
        keys.update(("test_source", "execution_evidence"))
    return {
        "feature_slug": "imports", "delivery_id": "delivery-1",
        "project_type": "ui" if review_type == "ui_conformance" else "non_ui",
        "input_snapshot_hash": "a" * 64,
        "input_refs": {
            key: {"ref": f"docs/{key}.md", "sha256": "b" * 64,
                  "project_type": "shared"} for key in keys
        },
        "coordinator_conclusion": "Everything passes",
        "peer_results": [{"status": "passed"}],
    }


def completed_result(task, agent_id="worker-1"):
    evidence = [row["ref"] for row in task["input_refs"].values()]
    result = {
        "role_id": task["role_id"], "role_version": task["role_version"],
        "role_definition_hash": task["role_definition_hash"],
        "task_template_hash": task["task_template_hash"],
        "task_hash": task["task_hash"],
        "input_snapshot_hash": task["input_snapshot_hash"],
        "identity_kind": "spawned", "agent_id": agent_id,
        "spawn_source": "host.spawn", "status": "passed",
        "completion_status": "complete", "checked_items": list(task["must_check"]),
        "check_records": [{"check_id": check, "outcome": "satisfied",
                           "reason": "Current input contains the required mapping.",
                           "evidence_refs": [evidence[0]]} for check in task["must_check"]],
        "completion_evidence": {criterion: [evidence[0]]
                                for criterion in task["completion_criteria"]},
        "independent_position": "All declared obligations were inspected against current evidence.",
        "evidence_refs": evidence, "findings": [], "blocking_findings": [],
        "unresolved_questions": [], "write_intents": [],
    }
    if task.get("seat_id"):
        result.update(
            seat_contract_version=task["seat_contract_version"],
            seat_id=task["seat_id"],
            seat_task_hash=task["seat_task_hash"],
        )
    return result


class ReviewProfileTests(unittest.TestCase):
    def task(self, role_id, review_type=None):
        gate = review_type or next(g for g in profiles.GATE_PROFILES
                                   if role_id in get_gate_profile(g))
        return gate, build_role_task(gate, role_id, context_for(gate, role_id))

    def validate(self, gate, task, result):
        validate_role_result(gate, result,
                             expected_snapshot_hash=task["input_snapshot_hash"],
                             expected_task=task)

    def gate_context(self, gate, branch=None):
        roles = get_gate_profile(gate)
        context = context_for(gate, roles[0])
        for role in roles:
            context["input_refs"].update(context_for(gate, role)["input_refs"])
        if branch is not None:
            context["project_type"] = branch
            for ref in context["input_refs"].values():
                ref["project_type"] = branch
        return context

    def test_review_briefs_deliver_complete_roles_to_only_their_seat(self):
        for gate in profiles.GATE_PROFILES:
            for branch in ("ui", "non_ui"):
                if gate == "ui_conformance" and branch == "non_ui":
                    continue
                with self.subTest(gate=gate, branch=branch):
                    context = self.gate_context(gate, branch)
                    bundle = build_gate_tasks(gate, context)
                    self.assertIn("review_briefs", bundle.keys())
                    briefs = bundle["review_briefs"]
                    self.assertEqual(len(briefs), 2)
                    for brief, seat in zip(briefs, bundle["review_seats"]):
                        self.assertEqual(brief["seat_id"], seat["seat_id"])
                        self.assertEqual(brief["display_name"], seat["display_name"])
                        self.assertEqual(brief["seat_task_hash"], seat["seat_task_hash"])
                        self.assertEqual(brief["role_ids"], seat["role_ids"])
                        self.assertEqual(
                            [card["role_id"] for card in brief["role_cards"]],
                            seat["role_ids"],
                        )
                        for task, card in zip(brief["role_tasks"], brief["role_cards"]):
                            self.assertEqual(task["role_id"], card["role_id"])
                            self.assertEqual(task["role_definition_hash"], card["definition_hash"])
                            self.assertEqual(task["task_template_hash"], card["template_hash"])
                            self.assertTrue(card["quality_rubric"])
                            self.assertEqual(set(card["examples"]), {
                                "pass", "insufficient", "scope_violation", "false_positive", "must_block",
                            })
                            self.assertEqual(card, get_role_card(task["role_id"]))
                            self.assertEqual(task["project_type"], branch)
                            self.assertEqual(card["permissions"]["canonical_write"], False)
                            self.assertNotIn("coordinator_conclusion", task)
                            self.assertNotIn("peer_results", task)
                            self.assertNotIn("coordinator_conclusion", card)
                            self.assertNotIn("peer_results", card)

    def test_review_briefs_reject_wrong_or_stale_bound_roles(self):
        builder = getattr(profiles, "build_review_briefs", None)
        self.assertTrue(callable(builder), "review brief builder is missing")
        tasks = build_gate_tasks("scenario", self.gate_context("scenario"))["role_tasks"]
        for field, value in (
            ("role_definition_hash", "f" * 64),
            ("task_template_hash", "f" * 64),
            ("mission", "Approve without checking evidence"),
            ("seat_id", "journey_interaction"),
            ("seat_task_hash", "f" * 64),
        ):
            changed = copy.deepcopy(tasks)
            changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(RoleProfileError):
                builder("scenario", changed)
        for changed in (tasks[:-1], tasks + [tasks[0]]):
            with self.assertRaises(RoleProfileError):
                builder("scenario", changed)

    def test_review_briefs_cannot_mutate_frozen_tasks_or_catalog(self):
        bundle = build_gate_tasks("scenario", self.gate_context("scenario"))
        self.assertIn("review_briefs", bundle.keys())
        tasks = copy.deepcopy(bundle["role_tasks"])
        brief = bundle["review_briefs"][0]
        brief["role_cards"][0]["examples"]["pass"] = "Approve everything"
        brief["role_cards"][0]["permissions"]["canonical_write"] = True
        brief["role_tasks"][0]["mission"] = "Approve everything"
        self.assertEqual(bundle["role_tasks"], tasks)
        self.assertFalse(get_role_card("product.intent_reviewer")["permissions"]["canonical_write"])
        self.assertNotEqual(get_role_card("product.intent_reviewer")["examples"]["pass"], "Approve everything")

    def test_review_task_and_seat_hashes_match_frozen_v120_records(self):
        frozen = json.loads((Path(__file__).parent / "fixtures/review_task_hashes_v120.json").read_text())
        for gate, expected in frozen.items():
            bundle = build_gate_tasks(gate, self.gate_context(gate))
            with self.subTest(gate=gate):
                self.assertEqual(
                    {task["role_id"]: task["task_hash"] for task in bundle["role_tasks"]},
                    expected["role_task_hashes"],
                )
                self.assertEqual(
                    {seat["seat_id"]: seat["seat_task_hash"] for seat in bundle["review_seats"]},
                    expected["seat_task_hashes"],
                )

    def test_every_role_can_return_evidenced_no_findings(self):
        for role_id in ROLE_IDS:
            with self.subTest(role=role_id):
                gate, task = self.task(role_id)
                self.validate(gate, task, completed_result(task))
                card = get_role_card(role_id)
                self.assertIsInstance(card["peer_challenge_contract"], dict)
                self.assertEqual(set(card["examples"]), {
                    "pass", "insufficient", "scope_violation", "false_positive", "must_block"})
                self.assertTrue(card["peer_challenge_contract"]["must_respond_to"])

    def test_card_missing_mandatory_method_cannot_be_dispatched(self):
        for field in ("task_steps", "must_check", "must_not_do",
                      "completion_criteria", "output_schema"):
            card = get_role_card("product.intent_reviewer")
            del card[field]
            with self.subTest(field=field), patch.dict(profiles._ROLE_CARDS, {card["role_id"]: card}):
                with self.assertRaises(RoleProfileError):
                    build_role_task("scenario", card["role_id"], context_for("scenario", card["role_id"]))

    def test_wrong_gate_and_unknown_role_cannot_be_dispatched(self):
        with self.assertRaises(RoleProfileError):
            get_role_card("unknown")
        with self.assertRaises(RoleProfileError):
            build_role_task("scenario", "coverage.assertion_reviewer", {})

    def test_missing_input_wrong_branch_or_implementation_source_blocks_dispatch(self):
        cases = [("scenario", "product.intent_reviewer", "open_spec"),
                 ("test_implementation", "coverage.assertion_reviewer", "test_source"),
                 ("test_implementation", "coverage.assertion_reviewer", "execution_evidence")]
        for gate, role, key in cases:
            context = context_for(gate, role)
            del context["input_refs"][key]
            with self.subTest(key=key), self.assertRaises(RoleProfileError):
                build_role_task(gate, role, context)
        context = context_for("scenario", "scenario.journey_reviewer")
        context["input_refs"]["prototype_or_behavior_contract"]["project_type"] = "ui"
        with self.assertRaises(RoleProfileError):
            build_role_task("scenario", "scenario.journey_reviewer", context)
        context = context_for("ui_conformance", "ui.conformance_reviewer")
        context["project_type"] = "non_ui"
        with self.assertRaises(RoleProfileError):
            build_role_task("ui_conformance", "ui.conformance_reviewer", context)

    def test_task_filters_unrelated_inputs_and_coordinator_or_peer_conclusions(self):
        context = context_for("scenario", "product.intent_reviewer")
        context["input_refs"]["unrelated"] = {"ref": "secret.txt", "sha256": "c"*64, "project_type": "shared"}
        task = build_role_task("scenario", "product.intent_reviewer", context)
        self.assertNotIn("unrelated", task["input_refs"])
        self.assertNotIn("coordinator_conclusion", task)
        self.assertNotIn("peer_results", task)
        self.assertTrue(task["task_hash"])
        self.assertEqual(task["delivery_id"], "delivery-1")
        self.assertEqual(task["permissions"]["canonical_write"], False)

    def test_task_hash_binds_input_content_delivery_and_instructions(self):
        context = context_for("scenario", "product.intent_reviewer")
        task = build_role_task("scenario", "product.intent_reviewer", context)
        for field, value in (("delivery_id", "delivery-2"), ("feature_slug", "other"),
                             ("input_snapshot_hash", "d"*64)):
            changed = copy.deepcopy(context)
            changed[field] = value
            self.assertNotEqual(task["task_hash"], build_role_task("scenario", task["role_id"], changed)["task_hash"])
        changed = copy.deepcopy(context)
        changed["input_refs"]["open_spec"]["sha256"] = "e"*64
        self.assertNotEqual(task["task_hash"], build_role_task("scenario", task["role_id"], changed)["task_hash"])
        tampered = copy.deepcopy(task)
        tampered["must_not_do"] = []
        with self.assertRaises(RoleProfileError):
            self.validate("scenario", tampered, completed_result(task))

    def test_each_role_insufficient_evidence_cannot_pass(self):
        for role in ROLE_IDS:
            gate, task = self.task(role)
            for field, value in (("check_records", []), ("completion_evidence", {}),
                                 ("evidence_refs", []), ("checked_items", [])):
                result = completed_result(task)
                result[field] = value
                with self.subTest(role=role, field=field), self.assertRaises(RoleProfileError):
                    self.validate(gate, task, result)

    def test_each_role_scope_task_code_test_goal_and_closure_writes_rejected(self):
        for role in ROLE_IDS:
            gate, task = self.task(role)
            for action in ("change_scope", "edit_TASK", "write_code", "edit_tests", "update_Goal", "close_delivery"):
                result = completed_result(task)
                result["write_intents"] = [action]
                with self.subTest(role=role, action=action), self.assertRaises(RoleProfileError):
                    self.validate(gate, task, result)

    def finding(self, task, kind="blocking_finding", disposition="open"):
        return {"finding_id": "F-1", "kind": kind, "check_id": task["must_check"][0],
                "subject_ref": next(iter(task["input_refs"].values()))["ref"],
                "evidence_refs": [next(iter(task["input_refs"].values()))["ref"]],
                "impact": "Required result is missing", "recommendation": "Owner must resolve the missing result",
                "disposition": disposition, "rationale": "Linked current evidence supports this classification"}

    def test_each_role_blocking_findings_cannot_be_hidden_in_passed_result(self):
        for role in ROLE_IDS:
            gate, task = self.task(role)
            result = completed_result(task)
            result["findings"] = [self.finding(task)]
            with self.subTest(role=role), self.assertRaises(RoleProfileError):
                self.validate(gate, task, result)
            result["blocking_findings"] = ["F-1"]
            result["status"] = "needs_remediation"
            result["check_records"][0]["outcome"] = "finding"
            self.validate(gate, task, result)

    def test_each_role_false_positive_requires_evidence_and_reason_to_reject(self):
        for role in ROLE_IDS:
            gate, task = self.task(role)
            result = completed_result(task)
            finding = self.finding(task, disposition="rejected")
            finding["rationale"] = "Current accepted scope excludes this behavior; evidence anchors the exclusion."
            result["findings"] = [finding]
            with self.subTest(role=role):
                self.validate(gate, task, result)
                finding["rationale"] = ""
                with self.assertRaises(RoleProfileError):
                    self.validate(gate, task, result)

    def test_open_unresolved_question_cannot_be_hidden_inside_findings(self):
        gate, task = self.task("product.intent_reviewer")
        result = completed_result(task)
        result["findings"] = [self.finding(task, kind="unresolved_question")]
        with self.assertRaises(RoleProfileError):
            self.validate(gate, task, result)

    def test_unknown_evidence_or_unstructured_finding_is_rejected(self):
        gate, task = self.task("coverage.assertion_reviewer")
        for field, value in (("evidence_refs", ["old/version.md"]), ("findings", ["looks bad"]),
                             ("task_hash", "f"*64), ("role_definition_hash", "f"*64),
                             ("task_template_hash", "f"*64), ("input_snapshot_hash", "f"*64)):
            result = completed_result(task)
            result[field] = value
            with self.subTest(field=field), self.assertRaises(RoleProfileError):
                self.validate(gate, task, result)

    def test_incomplete_blocked_result_is_recordable_but_cannot_claim_pass(self):
        gate, task = self.task("test.implementation_reviewer")
        result = completed_result(task)
        result.update(status="blocked", completion_status="incomplete", checked_items=[],
                      check_records=[], completion_evidence={}, findings=[], evidence_refs=[],
                      unresolved_questions=["Execution log cannot be read"])
        self.validate(gate, task, result)
        result["status"] = "passed"
        with self.assertRaises(RoleProfileError):
            self.validate(gate, task, result)

    def test_simulation_cannot_claim_spawn_and_requires_explicit_identity(self):
        gate, task = self.task("product.intent_reviewer")
        result = completed_result(task)
        result["identity_kind"] = "simulated"
        with self.assertRaises(RoleProfileError):
            self.validate(gate, task, result)
        result.update(agent_id=None, spawn_source=None, simulated_identity="sim-product")
        self.validate(gate, task, result)
        result.update(agent_id="", spawn_source="")
        with self.assertRaises(RoleProfileError):
            self.validate(gate, task, result)

    def test_unsupported_role_version_is_rejected_before_dispatch(self):
        card = get_role_card("product.intent_reviewer")
        context = context_for("scenario", card["role_id"])
        card["role_version"] = "9.9.9"
        card["definition_hash"] = profiles._definition_hash(card)
        card["template_hash"] = profiles._template_hash(card)
        with patch.dict(profiles._ROLE_CARDS, {card["role_id"]: card}):
            with self.assertRaises(RoleProfileError):
                build_role_task("scenario", card["role_id"], context)

    def test_fixed_profiles_cannot_pass_missing_duplicate_or_wrong_seats(self):
        expected = {
            "scenario": ("product.intent_reviewer", "scenario.journey_reviewer", "negative.boundary_reviewer"),
            "test": ("test.strategy_reviewer", "coverage.assertion_reviewer"),
            "test_coverage": ("coverage.traceability_reviewer", "coverage.assertion_reviewer", "negative.boundary_reviewer"),
            "test_implementation": ("test.implementation_reviewer", "coverage.assertion_reviewer"),
            "ui_conformance": ("ui.conformance_reviewer", "scenario.journey_reviewer"),
        }
        for gate, roles in expected.items():
            tasks = [self.task(role, gate)[1] for role in roles]
            results = [completed_result(task, f"agent-{i}") for i, task in enumerate(tasks)]
            validate_role_results(gate, results, expected_snapshot_hash="a"*64, expected_tasks=tasks)
            for bad in (results[:-1], results + [results[0]], [results[0]]*len(results)):
                with self.subTest(gate=gate), self.assertRaises(RoleProfileError):
                    validate_role_results(gate, bad, expected_snapshot_hash="a"*64, expected_tasks=tasks)

    def test_fixed_gate_seats_cover_all_roles_with_two_dispatch_units(self):
        for gate in profiles.GATE_PROFILES:
            context = context_for(gate, profiles.GATE_PROFILES[gate][0])
            for role_id in get_gate_profile(gate):
                card = get_role_card(role_id)
                for key in card["required_inputs"] + card["optional_inputs"]:
                    if key != "feature_slug":
                        context["input_refs"].setdefault(
                            key,
                            {"ref": f"docs/{key}.md", "sha256": "b" * 64,
                             "project_type": "shared"},
                        )
            bundle = build_gate_tasks(gate, context)
            seats = get_gate_seat_profile(gate)
            self.assertEqual(len(seats), 2)
            self.assertEqual(bundle["seat_contract_version"], SEAT_PROFILE_VERSION)
            self.assertEqual(
                {role for seat in seats for role in seat["role_ids"]},
                set(get_gate_profile(gate)),
            )
            tasks = bundle["role_tasks"]
            results = [
                completed_result(task, f"agent-{task['seat_id']}")
                for task in tasks
            ]
            validate_role_results(
                gate,
                results,
                expected_snapshot_hash="a" * 64,
                expected_tasks=tasks,
            )
            first_seat = seats[0]["seat_id"]
            same_seat = [result for result in results if result["seat_id"] == first_seat]
            if len(same_seat) > 1:
                same_seat[1]["agent_id"] = "agent-other"
                with self.assertRaises(RoleProfileError):
                    validate_role_results(
                        gate, results, expected_snapshot_hash="a" * 64,
                        expected_tasks=tasks,
                    )
            results = [
                completed_result(task, "agent-shared") for task in tasks
            ]
            with self.assertRaises(RoleProfileError):
                validate_role_results(
                    gate, results, expected_snapshot_hash="a" * 64,
                    expected_tasks=tasks,
                )

    def test_all_profiles_support_ui_and_applicable_non_ui_branches(self):
        for gate, roles in profiles.GATE_PROFILES.items():
            for branch in ("ui", "non_ui"):
                if gate == "ui_conformance" and branch == "non_ui":
                    continue
                for role in roles:
                    context = context_for(gate, role)
                    context["project_type"] = branch
                    for ref in context["input_refs"].values():
                        ref["project_type"] = branch
                    with self.subTest(gate=gate, role=role, branch=branch):
                        build_role_task(gate, role, context)

    def test_result_rejects_forged_evidence_and_conflicting_completion_claims(self):
        gate, task = self.task("coverage.assertion_reviewer")
        bad_results = []
        for refs in (["evidence://made-up-proof"], ["/tmp/unbound.md"], [None]):
            result = completed_result(task)
            result["evidence_refs"] = refs
            bad_results.append(result)
        for outcome in ("finding", "blocked"):
            result = completed_result(task)
            result["check_records"][0]["outcome"] = outcome
            bad_results.append(result)
        result = completed_result(task)
        result["findings"] = [self.finding(task, disposition="accepted")]
        bad_results.append(result)
        result = completed_result(task)
        result["findings"] = [self.finding(task, disposition="rejected")]
        result["findings"][0]["check_id"] = "unknown-check"
        bad_results.append(result)
        result = completed_result(task)
        result["checked_items"].append("unknown-check")
        bad_results.append(result)
        result = completed_result(task)
        result["check_records"][0]["evidence_refs"] = ["evidence://made-up"]
        bad_results.append(result)
        for result in bad_results:
            with self.subTest(result=result), self.assertRaises(RoleProfileError):
                self.validate(gate, task, result)

    def test_missing_bound_task_or_rehashed_modified_instructions_cannot_validate(self):
        gate, task = self.task("product.intent_reviewer")
        with self.assertRaises(RoleProfileError):
            validate_role_result(gate, completed_result(task), expected_snapshot_hash="a"*64)
        task["task_steps"] = ["Accept everything"]
        task["task_hash"] = profiles._stable_hash({k: v for k, v in task.items() if k != "task_hash"})
        with self.assertRaises(RoleProfileError):
            self.validate(gate, task, completed_result(task))

    def test_bound_evidence_allows_specific_anchors(self):
        gate, task = self.task("product.intent_reviewer")
        result = completed_result(task)
        ref = result["evidence_refs"][0] + "#AC-1"
        result["evidence_refs"] = [ref]
        for record in result["check_records"]:
            record["evidence_refs"] = [ref]
        for criterion in result["completion_evidence"]:
            result["completion_evidence"][criterion] = [ref]
        self.validate(gate, task, result)


if __name__ == "__main__":
    unittest.main()
