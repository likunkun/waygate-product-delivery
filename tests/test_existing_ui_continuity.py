import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from product_delivery_agent.evidence_artifacts import sha256_file
from product_delivery_agent.review_gates import ReviewGateError
from product_delivery_agent.review_profiles import get_gate_profile, get_role_card
from product_delivery_agent.workflow import WorkflowError
from tests.conformance_fixtures import prototype_design_bundle_payload
from tests.test_feature_closure import scenario_row
from tests.test_prototype_design_workflow_v1023 import (
    record_reviewed_prototype,
    scenario_review,
    start_ui_workflow,
)


def write(path, document):
    path.write_text(json.dumps(document), encoding="utf-8")


def element(element_id, parent, *, role="region", dynamic=False):
    return {"id": element_id, "parent_id": parent, "kind": "control" if role == "button" else "region",
            "role": role, "name": element_id, "visible": True, "enabled": True,
            "layout": "block/static", "dynamic_text": dynamic}


class ExistingUIContinuityTests(unittest.TestCase):
    def test_historical_screenshot_alone_cannot_freeze_an_incremental_prototype(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, _ = start_ui_workflow(root, with_bundle=False)
            payload = prototype_design_bundle_payload(root)
            payload.pop("existing_ui_continuity", None)

            with self.assertRaisesRegex(WorkflowError, "real product browser baseline"):
                workflow.record_ui_prototype_design_bundle(payload)

            self.assertEqual(
                workflow.status()["prototype_design_bundle"]["status"], "missing"
            )
            with self.assertRaisesRegex(ReviewGateError, "ready prototype design bundle"):
                workflow.prepare_review_role_tasks("scenario", {})

    def v211_captures(self, root):
        workflow, review = start_ui_workflow(root, with_bundle=False)
        workflow.record_scenario_matrix([{**scenario_row(), "role": "student"}])
        contract = deepcopy(review["prototype_contract"])
        player = contract["surfaces"][0]
        player.update(surface_id="learner-player", route="/student/courses/demo", required_viewports=["desktop", "mobile"])
        entry = deepcopy(player)
        entry.update(surface_id="ordinary-entry", route="/student/courses")
        entry["critical_regions"][0]["region_id"] = "entry-region"
        for relation in entry["critical_relationships"]:
            relation.update(source_region_id="entry-region", target_region_id="entry-region")
        for interaction in entry["critical_interactions"]:
            interaction.update(interaction_id="entry-action", entry_region_id="entry-region", target_region_id="entry-region")
        contract["surfaces"] = [entry, player]
        payload = prototype_design_bundle_payload(root, contract=contract, baseline_actor_role="student")
        continuity = payload["existing_ui_continuity"]
        baseline_path = root / continuity["baseline_path"]
        candidate_path = root / continuity["prototype_capture_path"]
        baseline = json.loads(baseline_path.read_text())
        candidate = json.loads(candidate_path.read_text())
        for before, after in zip(baseline["observations"], candidate["observations"]):
            primary = before["elements"][1]["id"]
            extra = [element("learning-path", primary), element("search", primary, role="button"),
                     element("pagination", primary, role="button"), element("course-cards", primary, dynamic=True)]
            if before["surface_id"] == "learner-player":
                extra = [element("workspace", primary), element("docked-controls", primary)]
                if before["viewport"] == "mobile":
                    extra.append(element("mobile-tools", "docked-controls", role="button"))
                for row in (before, after):
                    row["entry_route"] = "/student/courses"
                    row["actions"][0]["before_route"] = row["entry_route"]
            before["elements"].extend(deepcopy(extra))
            after["elements"].extend(deepcopy(extra))
        write(baseline_path, baseline)
        candidate["baseline_sha256"] = sha256_file(baseline_path)
        write(candidate_path, candidate)
        return workflow, payload, candidate_path, candidate

    def test_v211_missing_pagination_mobile_tools_or_dock_hierarchy_fails_during_design(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, payload, candidate_path, original = self.v211_captures(Path(tmp))
            for target in ("pagination", "mobile-tools", "docked-controls"):
                with self.subTest(target=target):
                    candidate = deepcopy(original)
                    for row in candidate["observations"]:
                        if target == "docked-controls":
                            for node in row["elements"]:
                                if node["id"] == target:
                                    node["parent_id"] = "workspace"
                        else:
                            row["elements"] = [node for node in row["elements"] if node["id"] != target]
                    write(candidate_path, candidate)
                    with self.assertRaisesRegex(WorkflowError, f"undeclared existing UI difference.*{target}"):
                        workflow.record_ui_prototype_design_bundle(payload)

    def test_v211_declared_subtitle_and_real_data_variation_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, payload, candidate_path, candidate = self.v211_captures(root)
            requirements = root / "requirements.md"
            requirements.write_text("FR-V211-001 Add captions to the existing player.\n")
            changes = []
            for row in candidate["observations"]:
                if row["surface_id"] == "ordinary-entry":
                    next(node for node in row["elements"] if node["id"] == "course-cards")["name"] = "More real courses"
                    continue
                row["elements"].append(element("caption-toggle", "docked-controls", role="button"))
                changes.append({"change_id": "captions-" + row["viewport"], "kind": "elements", "target": "caption-toggle",
                                "unit": row["baseline_unit"], "requirement_ids": ["FR-V211-001"]})
            write(candidate_path, candidate)
            payload["existing_ui_continuity"].update(requirements_path="requirements.md", changes=changes)
            state = workflow.record_ui_prototype_design_bundle(payload)
            summary = state["prototype_design_bundle"]["existing_ui_continuity"]
            report = json.loads((root / summary["report_path"]).read_text())["existing_ui_continuity"]
            self.assertEqual(summary["change_ids"], ["captions-desktop", "captions-mobile"])
            self.assertEqual(report["sha256"], summary["sha256"])
            self.assertTrue(all(unit["entry_route"] == "/student/courses" for unit in report["comparisons"]))

    def test_wrong_actor_viewport_context_or_old_capture_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow, payload, candidate_path, original = self.v211_captures(Path(tmp))
            for field, value, error in (
                ("actor_role", "admin", "does not match.*role"),
                ("width", 800, "screenshot dimensions"),
                ("context_id", "draft-instead-of-published", "business state"),
            ):
                with self.subTest(field=field):
                    candidate = deepcopy(original)
                    candidate["observations"][0][field] = value
                    write(candidate_path, candidate)
                    with self.assertRaisesRegex(WorkflowError, error):
                        workflow.record_ui_prototype_design_bundle(payload)
            original["baseline_sha256"] = "0" * 64
            write(candidate_path, original)
            with self.assertRaisesRegex(WorkflowError, "stale product baseline"):
                workflow.record_ui_prototype_design_bundle(payload)

    def test_scenario_review_and_user_confirmation_revalidate_current_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, review = start_ui_workflow(root)
            record_reviewed_prototype(workflow, review)
            names = {
                name for role in get_gate_profile("scenario")
                for name in get_role_card(role)["required_inputs"] if name != "feature_slug"
            }
            source = root / "review-input.md"
            source.write_text("Frozen scenario review material.\n")
            ref = {"ref": source.name, "sha256": sha256_file(source)}
            prepared = workflow.prepare_review_role_tasks("scenario", dict.fromkeys(names, ref))
            for task in prepared["role_tasks"]:
                self.assertIn("existing_ui_continuity", task["must_check"])
                comparison = task["input_refs"]["existing_ui_comparison"]
                self.assertEqual(sha256_file(root / comparison["ref"]), comparison["sha256"])
            scenario = scenario_review(workflow, "incremental_existing_surface")
            incomplete = {key: value for key, value in scenario.items() if key != "existing_ui_continuity_review"}
            with self.assertRaisesRegex(ReviewGateError, "verify the current real product baseline"):
                workflow.record_multi_agent_review("scenario", incomplete)
            workflow.record_multi_agent_review("scenario", scenario)
            workflow.prepare_product_baseline_confirmation()

            baseline = workflow.status()["prototype_design_bundle"]["existing_ui_continuity"]["baseline_path"]
            path = root / baseline
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(WorkflowError, "stale product baseline"):
                workflow.prepare_product_baseline_confirmation()
