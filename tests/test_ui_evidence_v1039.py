import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import shutil
import tempfile
import threading
import unittest
from unittest import mock

from product_delivery_agent.ui_evidence import (
    UIEvidenceError,
    append_performance_event,
    browser_records_from_capture_runs,
    build_capture_plan,
    build_closure_manifest,
    ingest_capture_run,
    inspect_capture_run,
    load_capture_run,
    performance_report,
    resolve_evidence_profile,
    run_capture_adapter,
    stable_hash,
    unit_records_from_capture_runs,
)
from product_delivery_agent.artifact_protocol import load_state, write_state
from product_delivery_agent.workflow import ProductDeliveryWorkflow
from product_delivery_agent.coverage_audit import build_executed_browser_evidence
from tests.conformance_fixtures import PROTOTYPE_DESIGN_DIMENSIONS
from tests.test_full_stack_browser_evidence_v1013 import (
    full_stack_record,
    planned_obligation,
    review_payload,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UIEvidenceV1039Tests(unittest.TestCase):
    @staticmethod
    def _ui_conformance_review(*, reviewed_regions=None) -> dict:
        return {
            "review_id": "REV-V1039-UI-CONFORMANCE",
            "review_type": "ui_conformance",
            "status": "passed",
            "review_mode": "spawned_subagents",
            "reviewers": ["ui reviewer", "accessibility reviewer"],
            "reviewer_agent_ids": ["agent-ui", "agent-a11y"],
            "reviewer_spawn_source": "codex.multi_agent_v1.spawn_agent",
            "artifact_version": "ui-conformance-v1",
            "independent_positions": ["UI passed", "Accessibility passed"],
            "cross_challenges": ["challenged region coverage"],
            "revisions": ["reviewed every region"],
            "final_adjudication": "passed",
            "conclusions": ["UI conformance passed"],
            "accepted_suggestions": [],
            "rejected_suggestions": [],
            "unresolved_questions": [],
            "blocking_findings": [],
            "reviewed_surface_ids": ["dashboard"],
            "reviewed_state_ids": ["default"],
            "reviewed_region_ids": list(reviewed_regions or ["main-region"]),
            "structural_findings": [],
            "visual_findings": [],
            "interaction_findings": [],
            "legacy_reuse_findings": [],
            "unmapped_regions": [],
            "reviewed_design_dimensions": list(PROTOTYPE_DESIGN_DIMENSIONS),
            "global_visual_continuity_findings": [],
            "annotation_separation_findings": [],
            "accepted_visual_deviations": [],
        }
    def _staging_manifest(self, root: Path, plan: dict, **overrides) -> Path:
        staging = root / ".product-delivery" / "staging" / plan["plan_id"]
        staging.mkdir(parents=True)
        screenshot = staging / "screen.png"
        semantic = staging / "semantic.json"
        trace = staging / "trace.zip"
        evidence = staging / "evidence.json"
        probe = staging / "probe.json"
        screenshot.write_bytes(b"png-evidence")
        semantic.write_text('{"regions": []}', encoding="utf-8")
        trace.write_bytes(b"trace-evidence")
        evidence.write_text('{"result": "observed"}', encoding="utf-8")
        actor_response = {
            "role": "teacher",
            "user_id": "teacher-1",
            "session_id": "session-1",
        }
        actor_hash = hashlib.sha256(
            json.dumps(
                actor_response,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        probe.write_text(
            json.dumps(
                {
                    "capture_run_ref": plan["plan_id"],
                    "acceptance_url": "https://app.example.test/dashboard",
                    "api_health_url": "https://api.example.test/health",
                    "api_health_identity": "api-v1",
                    "health_response_status": 200,
                    "health_response_content_type": "application/json",
                    "health_response_body_sample": '{"service":"api-v1"}',
                    "actor_identity_response": actor_response,
                    "business_api_requests": [
                        {
                            "method": "GET",
                            "url": "https://api.example.test/items",
                            "status": 200,
                            "source": "network",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        def artifact(path: Path) -> dict:
            return {
                "path": str(path.relative_to(root)),
                "sha256": _sha256(path),
            }

        segment_metadata = staging / "segment-metadata.json"
        segment_metadata.write_text(
            json.dumps(
                {
                    "schema_version": "ui-journey-segment-metadata-v1",
                    "capture_run_ref": plan["plan_id"],
                    "execution_segment_id": "teacher-dashboard",
                    "actor_identity_sha256": stable_hash({
                        "role": "teacher",
                        "user_id": "teacher-1",
                        "session_id": "session-1",
                        "backend_identity_sha256": actor_hash,
                    }),
                    "screenshot_sha256": _sha256(screenshot),
                    "trace_sha256": _sha256(trace),
                    "evidence_sha256": _sha256(evidence),
                    "probe_sha256": _sha256(probe),
                }
            ),
            encoding="utf-8",
        )

        manifest = {
            "schema_version": "capture-run-v1",
            "plan_id": plan["plan_id"],
            "capture_run_ref": plan["plan_id"],
            "purpose": plan["purpose"],
            "profile": plan["resolved_profile"],
            "closure_valid": plan["closure_valid"],
            "source_identity": {
                "tree_sha256": "1" * 64,
                "commit_sha": "commit-123",
            },
            "build_identity": {"build_digest": "build-123"},
            "deployment_identity": {
                "deployment_id": "deploy-123",
                "origin": "https://app.example.test",
                "api_origin": "https://api.example.test",
            },
            "environment_identity": {
                "environment_id": "acceptance",
                "feature_flags_sha256": "2" * 64,
                "locale": "en-US",
                "timezone": "UTC",
                "reduced_motion": False,
            },
            "collector_identity": {
                "name": "fixture-adapter",
                "version": "1.0",
                "browser_name": "chromium",
                "browser_version": "123",
                "validator_version": "1.0.39",
            },
            "actor_identity": {
                "role": "teacher",
                "user_id": "teacher-1",
                "session_id": "session-1",
                "backend_identity_sha256": actor_hash,
            },
            "data_state_identity": {"seed_id": "seed-1", "version": "1"},
            "units": [
                {
                    "surface_id": "dashboard",
                    "state_id": "default",
                    "viewport_class": "desktop",
                    "dpr": 1,
                    "route": "/dashboard",
                    "origin": "https://app.example.test",
                    "execution_segment_id": "teacher-dashboard",
                    "screenshot": artifact(screenshot),
                    "task_semantic_snapshot": artifact(semantic),
                    "production_semantic_snapshot": artifact(semantic),
                    "computed_style": {"comparisons": []},
                    "geometry": {"observations": []},
                    "console_errors": [],
                    "network_errors": [],
                }
            ],
            "journey_segments": [
                {
                    "obligation_id": "OBL-001",
                    "test_id": "TC-001",
                    "scenario_id": "SC-001",
                    "user_story": "US-001",
                    "journey": "teacher opens dashboard",
                    "command": "npx playwright test dashboard.spec.ts",
                    "exit_code": 0,
                    "trace": artifact(trace),
                    "screenshot": artifact(screenshot),
                    "evidence": artifact(evidence),
                    "probe": artifact(probe),
                    "segment_metadata": artifact(segment_metadata),
                    "semantic_assertions": ["dashboard is visible"],
                    "evidence_strength": "full_stack_browser_e2e",
                    "acceptance_url": "https://app.example.test/dashboard",
                    "api_health_url": "https://api.example.test/health",
                    "api_health_identity": "api-v1",
                    "mocked_routes": [],
                    "executed_actor_roles": ["teacher"],
                    "primary_actor_role": "teacher",
                    "actor_identity_evidence": {
                        "role": "teacher",
                        "user_id": "teacher-1",
                        "session_id": "session-1",
                        "backend_identity_sha256": actor_hash,
                    },
                    "ordinary_path_observed": True,
                    "execution_segment_id": "teacher-dashboard",
                    "test_title_or_step": "teacher opens dashboard",
                }
            ],
        }
        manifest.update(overrides)
        path = staging / "capture-manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def _plan(self, *, purpose="closure", requested_profile="auto", risk_facts=None):
        return build_capture_plan(
            delivery_id="delivery-1",
            feature_slug="v1-ui",
            purpose=purpose,
            requested_profile=requested_profile,
            risk_facts=risk_facts or {"impact_known": True, "risk_tags": []},
            units=[
                {
                    "surface_id": "dashboard",
                    "state_id": "default",
                    "viewport_class": "desktop",
                }
            ],
            journeys=[{"obligation_id": "OBL-001", "test_id": "TC-001"}],
        )

    @staticmethod
    def _refresh_segment_metadata(
        root: Path,
        manifest: dict,
        index: int = 0,
    ) -> None:
        segment = manifest["journey_segments"][index]
        metadata_path = root / segment["segment_metadata"]["path"]
        metadata_path.write_text(
            json.dumps({
                "schema_version": "ui-journey-segment-metadata-v1",
                "capture_run_ref": manifest["capture_run_ref"],
                "execution_segment_id": segment["execution_segment_id"],
                "actor_identity_sha256": stable_hash(
                    segment["actor_identity_evidence"]
                ),
                "screenshot_sha256": segment["screenshot"]["sha256"],
                "trace_sha256": segment["trace"]["sha256"],
                "evidence_sha256": segment["evidence"]["sha256"],
                "probe_sha256": segment["probe"]["sha256"],
            }),
            encoding="utf-8",
        )
        segment["segment_metadata"]["sha256"] = _sha256(metadata_path)

    def test_profile_resolution_is_fail_closed_and_iteration_is_noncanonical(self):
        iteration = resolve_evidence_profile(
            purpose="iteration",
            requested_profile="auto",
            risk_facts={"impact_known": False, "risk_tags": []},
        )
        self.assertEqual(iteration["profile"], "iteration")
        self.assertFalse(iteration["closure_valid"])

        unknown = resolve_evidence_profile(
            purpose="closure",
            requested_profile="auto",
            risk_facts={"impact_known": False, "risk_tags": []},
        )
        self.assertEqual(unknown["profile"], "strict")
        high_risk = resolve_evidence_profile(
            purpose="closure",
            requested_profile="auto",
            risk_facts={"impact_known": True, "risk_tags": ["authorization"]},
        )
        self.assertEqual(high_risk["profile"], "strict")
        standard = resolve_evidence_profile(
            purpose="closure",
            requested_profile="auto",
            risk_facts={"impact_known": True, "risk_tags": []},
        )
        self.assertEqual(standard["profile"], "standard")
        forced = resolve_evidence_profile(
            purpose="closure",
            requested_profile="strict",
            risk_facts={"impact_known": True, "risk_tags": []},
        )
        self.assertEqual(forced["profile"], "strict")
        with self.assertRaises(UIEvidenceError):
            resolve_evidence_profile(
                purpose="closure",
                requested_profile="standard",
                risk_facts={"impact_known": True, "risk_tags": []},
            )

    def test_workflow_changed_path_analysis_escalates_global_ui_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Waygate Test"],
                cwd=root,
                check=True,
            )
            source = root / "src" / "features" / "dashboard" / "widget.tsx"
            source.parent.mkdir(parents=True)
            source.write_text("export const widget = 1;\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "src/features/dashboard/widget.tsx"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-qm", "fixture"], cwd=root, check=True
            )
            source.write_text("export const widget = 2;\n", encoding="utf-8")
            state = {
                "prototype_contract": {
                    "surfaces": [{
                        "surface_id": "dashboard",
                        "state_id": "default",
                        "required_viewports": ["desktop"],
                    }]
                },
                "delivery_goal": {
                    "planned_tasks": [{
                        "ui_impact": "prototype_bound",
                        "prototype_bindings": [{
                            "surface_id": "dashboard",
                            "state_id": "default",
                            "viewport_classes": ["desktop"],
                        }],
                    }]
                },
            }
            workflow = ProductDeliveryWorkflow(root)
            low_risk = workflow._derive_ui_evidence_risk_facts(state)
            self.assertTrue(low_risk["dependency_proof_complete"])
            self.assertEqual(
                resolve_evidence_profile(purpose="closure", risk_facts=low_risk)[
                    "profile"
                ],
                "standard",
            )

            stylesheet = root / "src" / "global.css"
            stylesheet.write_text(":root { --space: 8px; }\n", encoding="utf-8")
            high_risk = workflow._derive_ui_evidence_risk_facts(state)
            self.assertIn("design_tokens", high_risk["risk_tags"])
            self.assertEqual(
                resolve_evidence_profile(purpose="closure", risk_facts=high_risk)[
                    "profile"
                ],
                "strict",
            )

            stylesheet.unlink()
            shared_button = root / "src" / "components" / "Button.tsx"
            shared_button.parent.mkdir(parents=True)
            shared_button.write_text("export const Button = 1;\n", encoding="utf-8")
            shared_risk = workflow._derive_ui_evidence_risk_facts(state)
            self.assertIn("design_tokens", shared_risk["risk_tags"])
            self.assertFalse(shared_risk["dependency_proof_complete"])

            shared_button.unlink()
            theme = root / "src" / "theme.ts"
            theme.write_text("export const colors = {};\n", encoding="utf-8")
            theme_risk = workflow._derive_ui_evidence_risk_facts(state)
            self.assertIn("design_tokens", theme_risk["risk_tags"])
            self.assertEqual(
                resolve_evidence_profile(purpose="closure", risk_facts=theme_risk)[
                    "profile"
                ],
                "strict",
            )

            theme.unlink()
            new_route = root / "src" / "app" / "dashboard" / "page.tsx"
            new_route.parent.mkdir(parents=True)
            new_route.write_text("export default function Page() {}\n", encoding="utf-8")
            route_risk = workflow._derive_ui_evidence_risk_facts(state)
            self.assertIn("new_route", route_risk["risk_tags"])
            self.assertEqual(
                resolve_evidence_profile(purpose="closure", risk_facts=route_risk)[
                    "profile"
                ],
                "strict",
            )

            new_route.unlink()
            auth_file = root / "src" / "features" / "dashboard" / "auth.ts"
            auth_file.write_text("export const auth = true;\n", encoding="utf-8")
            auth_risk = workflow._derive_ui_evidence_risk_facts(state)
            self.assertIn("auth", auth_risk["risk_tags"])

    def test_standard_plan_focuses_affected_units_and_keeps_full_requirement(self):
        units = [
            {"surface_id": "dashboard", "state_id": "default", "viewport_class": "desktop"},
            {"surface_id": "settings", "state_id": "default", "viewport_class": "desktop"},
        ]
        plan = build_capture_plan(
            delivery_id="delivery-1",
            feature_slug="v1-ui",
            purpose="closure",
            requested_profile="auto",
            risk_facts={
                "impact_known": True,
                "risk_tags": [],
                "affected_units": [units[0]],
                "canary_units": [],
                "reusable_units": [units[1]],
            },
            units=units,
            journeys=[{"obligation_id": "OBL-001", "test_id": "TC-001"}],
        )
        self.assertEqual(plan["resolved_profile"], "standard")
        self.assertEqual(plan["units"], [units[0]])
        self.assertEqual(plan["required_units"], units)

    def test_capture_registry_is_content_addressed_append_only_and_projects_browser_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan()
            path = self._staging_manifest(root, plan)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            first = ingest_capture_run(root, delivery_root, plan, path)
            second = ingest_capture_run(root, delivery_root, plan, path)
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(first["capture_id"], second["capture_id"])
            stored = load_capture_run(delivery_root, first["capture_id"])
            self.assertNotIn("passed", stored)
            records = browser_records_from_capture_runs(delivery_root, [first["capture_id"]])
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["capture_id"], first["capture_id"])
            self.assertEqual(records[0]["network_probe_summary"]["business_api_request_count"], 1)
            self.assertEqual(
                records[0]["actor_identity_evidence"]["backend_identity_sha256"],
                "3b784a967d1743120817a6b190d9e10558765aebb4751d00b29ee7ad86f8330e",
            )
            validated = build_executed_browser_evidence(root, records)
            self.assertEqual(validated["status"], "passed")

    def test_iteration_capture_cannot_enter_canonical_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(purpose="iteration")
            path = self._staging_manifest(root, plan)
            with self.assertRaises(UIEvidenceError) as caught:
                ingest_capture_run(
                    root,
                    root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1",
                    plan,
                    path,
                )
            self.assertIn("noncanonical", str(caught.exception))

    def test_capture_rejects_verdicts_path_escape_and_cross_build_plan_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan()
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            verdict_path = self._staging_manifest(root, plan, status="passed")
            with self.assertRaises(UIEvidenceError):
                ingest_capture_run(root, delivery_root, plan, verdict_path)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan()
            path = self._staging_manifest(root, plan)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["units"][0]["screenshot"]["path"] = "../outside.png"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(UIEvidenceError):
                ingest_capture_run(
                    root,
                    root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1",
                    plan,
                    path,
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan()
            plan["required_build_digest"] = "expected-build"
            path = self._staging_manifest(root, plan)
            with self.assertRaises(UIEvidenceError):
                ingest_capture_run(
                    root,
                    root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1",
                    plan,
                    path,
                )

    def test_capture_registry_rejects_canonical_artifact_or_history_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan()
            path = self._staging_manifest(root, plan)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            result = ingest_capture_run(root, delivery_root, plan, path)
            stored = load_capture_run(delivery_root, result["capture_id"])
            canonical_screenshot = delivery_root / stored["units"][0]["screenshot"]["path"]
            canonical_screenshot.write_bytes(b"tampered")
            with self.assertRaises(UIEvidenceError):
                ingest_capture_run(root, delivery_root, plan, path)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan()
            path = self._staging_manifest(root, plan)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            result = ingest_capture_run(root, delivery_root, plan, path)
            manifest_path = (
                delivery_root
                / "evidence"
                / "captures"
                / result["capture_id"]
                / "manifest.json"
            )
            stored = json.loads(manifest_path.read_text(encoding="utf-8"))
            stored["build_identity"]["build_digest"] = "tampered-build"
            manifest_path.write_text(json.dumps(stored), encoding="utf-8")
            with self.assertRaises(UIEvidenceError) as caught:
                load_capture_run(delivery_root, result["capture_id"])
            self.assertIn("manifest changed", str(caught.exception))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan()
            path = self._staging_manifest(root, plan)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            ingest_capture_run(root, delivery_root, plan, path)
            registry_path = delivery_root / "evidence" / "capture-registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["captures"] = []
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaises(UIEvidenceError):
                ingest_capture_run(root, delivery_root, plan, path)

    def test_capture_projection_rejects_origin_lookalike(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan()
            path = self._staging_manifest(root, plan)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["journey_segments"][0]["acceptance_url"] = (
                "https://app.example.test.evil/dashboard"
            )
            probe_path = root / payload["journey_segments"][0]["probe"]["path"]
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            probe["acceptance_url"] = "https://app.example.test.evil/dashboard"
            probe_path.write_text(json.dumps(probe), encoding="utf-8")
            payload["journey_segments"][0]["probe"]["sha256"] = _sha256(probe_path)
            self._refresh_segment_metadata(root, payload)
            path.write_text(json.dumps(payload), encoding="utf-8")
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            result = ingest_capture_run(root, delivery_root, plan, path)
            with self.assertRaises(UIEvidenceError) as caught:
                browser_records_from_capture_runs(delivery_root, [result["capture_id"]])
            self.assertIn("production origin", str(caught.exception))

    def test_closure_manifest_rejects_cross_build_capture_union(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan()
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            first_path = self._staging_manifest(root, plan)
            first = ingest_capture_run(root, delivery_root, plan, first_path)
            payload = json.loads(first_path.read_text(encoding="utf-8"))
            payload["build_identity"]["build_digest"] = "build-456"
            payload["capture_run_ref"] = "capture-run-second"
            probe_path = root / payload["journey_segments"][0]["probe"]["path"]
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            probe["capture_run_ref"] = "capture-run-second"
            probe_path.write_text(json.dumps(probe), encoding="utf-8")
            payload["journey_segments"][0]["probe"]["sha256"] = _sha256(probe_path)
            self._refresh_segment_metadata(root, payload)
            first_path.write_text(json.dumps(payload), encoding="utf-8")
            second = ingest_capture_run(root, delivery_root, plan, first_path)

            with self.assertRaises(UIEvidenceError) as caught:
                build_closure_manifest(
                    delivery_root,
                    capture_run_ids=[first["capture_id"], second["capture_id"]],
                    required_units=plan["required_units"],
                    required_journeys=plan["journeys"],
                    profile="standard",
                    registry_root_sha256=second["registry_root_sha256"],
                )
            self.assertIn("different builds", str(caught.exception))

    def test_closure_manifest_rejects_profile_elevation_and_accepts_matching_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery_root = (
                root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            )
            standard_plan = self._plan()
            standard_path = self._staging_manifest(root, standard_plan)
            standard = ingest_capture_run(
                root, delivery_root, standard_plan, standard_path
            )

            with self.assertRaises(UIEvidenceError) as caught:
                build_closure_manifest(
                    delivery_root,
                    capture_run_ids=[standard["capture_id"]],
                    required_units=standard_plan["required_units"],
                    required_journeys=standard_plan["journeys"],
                    profile="strict",
                    registry_root_sha256=standard["registry_root_sha256"],
                )
            self.assertIn("profile", str(caught.exception))

            strict_plan = self._plan(requested_profile="strict")
            strict_path = self._staging_manifest(root, strict_plan)
            strict = ingest_capture_run(root, delivery_root, strict_plan, strict_path)
            manifest = build_closure_manifest(
                delivery_root,
                capture_run_ids=[strict["capture_id"]],
                required_units=strict_plan["required_units"],
                required_journeys=strict_plan["journeys"],
                profile="strict",
                registry_root_sha256=strict["registry_root_sha256"],
            )
            self.assertEqual(manifest["profile"], "strict")
            self.assertTrue(manifest["closure_valid"])

    def test_formal_capture_rejects_prototype_origin_as_production_unit_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = build_capture_plan(
                delivery_id="delivery-1",
                feature_slug="v1-ui",
                purpose="closure",
                requested_profile="auto",
                risk_facts={"impact_known": True, "risk_tags": []},
                units=[
                    {
                        "surface_id": "dashboard",
                        "state_id": "default",
                        "viewport_class": "desktop",
                    }
                ],
                journeys=[{"obligation_id": "OBL-001", "test_id": "TC-001"}],
                prototype_origin="https://prototype.example.test",
            )
            manifest_path = self._staging_manifest(root, plan)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["units"][0]["origin"] = "https://prototype.example.test"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(UIEvidenceError) as caught:
                ingest_capture_run(
                    root,
                    root
                    / ".product-delivery"
                    / "deliveries"
                    / "v1-ui"
                    / "delivery-1",
                    plan,
                    manifest_path,
                )
            self.assertIn("production origin", str(caught.exception))

    def test_capture_rejects_cross_capture_segment_borrowing_and_accepts_same_origin_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            plan = self._plan()
            manifest_path = self._staging_manifest(root, plan)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["deployment_identity"]["api_origin"] = "https://app.example.test"
            manifest["journey_segments"][0]["api_health_url"] = (
                "https://app.example.test/api/health"
            )
            probe_path = root / manifest["journey_segments"][0]["probe"]["path"]
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            probe["api_health_url"] = "https://app.example.test/api/health"
            probe["business_api_requests"][0]["url"] = (
                "https://app.example.test/api/items"
            )
            probe_path.write_text(json.dumps(probe), encoding="utf-8")
            manifest["journey_segments"][0]["probe"]["sha256"] = _sha256(probe_path)
            self._refresh_segment_metadata(root, manifest)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            accepted = ingest_capture_run(root, delivery_root, plan, manifest_path)
            self.assertTrue(accepted["capture_id"].startswith("capture-"))

            other_plan = {**plan, "plan_id": plan["plan_id"] + "-other"}
            other_manifest_path = self._staging_manifest(root, other_plan)
            other_manifest = json.loads(other_manifest_path.read_text(encoding="utf-8"))
            other_manifest["units"][0]["execution_segment_id"] = "borrowed-segment"
            other_manifest_path.write_text(json.dumps(other_manifest), encoding="utf-8")
            with self.assertRaises(UIEvidenceError) as caught:
                ingest_capture_run(root, delivery_root, other_plan, other_manifest_path)
            self.assertIn("same capture", str(caught.exception))

    def test_one_capture_can_project_two_backend_verified_actor_journeys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = build_capture_plan(
                delivery_id="delivery-1",
                feature_slug="v1-ui",
                purpose="closure",
                requested_profile="strict",
                risk_facts={"impact_known": False, "risk_tags": ["authorization"]},
                units=[{
                    "surface_id": "dashboard",
                    "state_id": "default",
                    "viewport_class": "desktop",
                }],
                journeys=[
                    {"obligation_id": "OBL-001", "test_id": "TC-001"},
                    {"obligation_id": "OBL-002", "test_id": "TC-002"},
                ],
            )
            manifest_path = self._staging_manifest(root, plan)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            teacher = manifest.pop("actor_identity")
            admin_response = {
                "role": "admin",
                "user_id": "admin-1",
                "session_id": "session-admin",
            }
            admin = {
                **admin_response,
                "backend_identity_sha256": hashlib.sha256(
                    json.dumps(
                        admin_response,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ).encode("utf-8")
                ).hexdigest(),
            }
            manifest["actor_identities"] = [teacher, admin]
            staging = manifest_path.parent
            admin_probe_path = staging / "probe-admin.json"
            teacher_probe = json.loads((staging / "probe.json").read_text(encoding="utf-8"))
            teacher_probe["actor_identity_response"] = admin_response
            admin_probe_path.write_text(json.dumps(teacher_probe), encoding="utf-8")
            admin_screenshot = staging / "screen-admin.png"
            admin_screenshot.write_bytes(b"admin-png-evidence")
            admin_trace = staging / "trace-admin.zip"
            admin_trace.write_bytes(b"admin-trace-evidence")
            admin_evidence = staging / "evidence-admin.json"
            admin_evidence.write_text('{"result":"admin observed"}', encoding="utf-8")
            admin_metadata = staging / "segment-metadata-admin.json"
            admin_metadata.write_text(
                json.dumps({
                    "schema_version": "ui-journey-segment-metadata-v1",
                    "capture_run_ref": plan["plan_id"],
                    "execution_segment_id": "admin-dashboard",
                    "actor_identity_sha256": stable_hash(admin),
                    "screenshot_sha256": _sha256(admin_screenshot),
                    "trace_sha256": _sha256(admin_trace),
                    "evidence_sha256": _sha256(admin_evidence),
                    "probe_sha256": _sha256(admin_probe_path),
                }),
                encoding="utf-8",
            )
            second = json.loads(json.dumps(manifest["journey_segments"][0]))
            second.update({
                "obligation_id": "OBL-002",
                "test_id": "TC-002",
                "scenario_id": "SC-002",
                "user_story": "US-002",
                "journey": "admin opens dashboard",
                "primary_actor_role": "admin",
                "executed_actor_roles": ["admin"],
                "actor_identity_evidence": admin,
                "execution_segment_id": "admin-dashboard",
                "test_title_or_step": "admin opens dashboard",
                "probe": {
                    "path": str(admin_probe_path.relative_to(root)),
                    "sha256": _sha256(admin_probe_path),
                },
                "screenshot": {
                    "path": str(admin_screenshot.relative_to(root)),
                    "sha256": _sha256(admin_screenshot),
                },
                "trace": {
                    "path": str(admin_trace.relative_to(root)),
                    "sha256": _sha256(admin_trace),
                },
                "evidence": {
                    "path": str(admin_evidence.relative_to(root)),
                    "sha256": _sha256(admin_evidence),
                },
                "segment_metadata": {
                    "path": str(admin_metadata.relative_to(root)),
                    "sha256": _sha256(admin_metadata),
                },
            })
            manifest["journey_segments"].append(second)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            ingested = ingest_capture_run(root, delivery_root, plan, manifest_path)
            records = browser_records_from_capture_runs(
                delivery_root, [ingested["capture_id"]]
            )
            self.assertEqual(
                {record["primary_actor_role"] for record in records},
                {"teacher", "admin"},
            )

    def test_unregistered_and_malformed_capture_ids_fail_before_manifest_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            plan = self._plan()
            manifest_path = self._staging_manifest(root, plan)
            result = ingest_capture_run(root, delivery_root, plan, manifest_path)
            outside = root / "outside" / "manifest.json"
            outside.parent.mkdir()
            outside.write_text("{}", encoding="utf-8")
            with self.assertRaises(UIEvidenceError) as caught:
                load_capture_run(delivery_root, "../../../../outside")
            self.assertIn("content-addressed", str(caught.exception))

            registry_path = delivery_root / "evidence" / "capture-registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["captures"] = []
            body = {
                "schema_version": registry["schema_version"],
                "captures": [],
            }
            registry["registry_root_sha256"] = hashlib.sha256(
                json.dumps(
                    body,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ).encode("utf-8")
            ).hexdigest()
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaises(UIEvidenceError):
                load_capture_run(delivery_root, result["capture_id"])

    def test_canonical_evidence_symlink_escape_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            outside = Path(outside_tmp)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            delivery_root.mkdir(parents=True)
            (delivery_root / "evidence").symlink_to(outside, target_is_directory=True)
            plan = self._plan()
            manifest_path = self._staging_manifest(root, plan)
            with self.assertRaises(UIEvidenceError) as caught:
                ingest_capture_run(root, delivery_root, plan, manifest_path)
            self.assertIn("symlink", str(caught.exception))
            self.assertEqual(list(outside.iterdir()), [])

    def test_telemetry_symlink_cannot_append_to_external_file(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            delivery_root = Path(tmp) / "delivery"
            evidence = delivery_root / "evidence"
            evidence.mkdir(parents=True)
            victim = Path(outside_tmp) / "victim.log"
            victim.write_text("original\n", encoding="utf-8")
            (evidence / "performance-telemetry.jsonl").symlink_to(victim)
            with self.assertRaises(UIEvidenceError) as caught:
                append_performance_event(
                    delivery_root,
                    {"operation": "capture_ingest", "wall_ms": 1},
                )
            self.assertIn("symlink", str(caught.exception))
            self.assertEqual(victim.read_text(encoding="utf-8"), "original\n")

    def test_probe_schema_rejects_fake_full_stack_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            plan = self._plan()
            manifest_path = self._staging_manifest(root, plan)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            probe_path = root / manifest["journey_segments"][0]["probe"]["path"]
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            probe["business_api_requests"] = [None]
            probe_path.write_text(json.dumps(probe), encoding="utf-8")
            manifest["journey_segments"][0]["probe"]["sha256"] = _sha256(probe_path)
            self._refresh_segment_metadata(root, manifest)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = ingest_capture_run(root, delivery_root, plan, manifest_path)
            with self.assertRaises(UIEvidenceError) as caught:
                browser_records_from_capture_runs(delivery_root, [result["capture_id"]])
            self.assertIn("business API request", str(caught.exception))

    def test_canonical_exemptions_are_typed_object_and_scope_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            plan = self._plan()
            manifest_path = self._staging_manifest(root, plan)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            error = {"message": "known third-party warning", "source": "vendor.js"}
            error_hash = stable_hash(error)
            manifest["units"][0]["console_errors"] = [error]
            manifest["units"][0]["error_exemptions"] = [{
                "field": "console_errors",
                "error_sha256": error_hash,
                "exemption_ref": "EX-UI-001",
                "reason": "Known third-party warning outside the product bundle",
            }]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = ingest_capture_run(root, delivery_root, plan, manifest_path)
            capture_ids = [result["capture_id"]]
            with self.assertRaises(UIEvidenceError):
                unit_records_from_capture_runs(delivery_root, capture_ids)

            canonical = {
                "EX-UI-001": {
                    "exemption_id": "EX-UI-001",
                    "exemption_type": "console_errors",
                    "object_id": f"console_errors:{error_hash}",
                    "valid_scope": "console_errors",
                    "allows_closure": True,
                }
            }
            self.assertEqual(
                len(unit_records_from_capture_runs(
                    delivery_root,
                    capture_ids,
                    authorized_exemptions=canonical,
                )),
                1,
            )
            closure = build_closure_manifest(
                delivery_root,
                capture_run_ids=capture_ids,
                required_units=plan["required_units"],
                required_journeys=plan["journeys"],
                profile="standard",
                registry_root_sha256=result["registry_root_sha256"],
                authorized_exemptions=canonical,
            )
            self.assertTrue(closure["closure_valid"])
            wrong_scope = json.loads(json.dumps(canonical))
            wrong_scope["EX-UI-001"]["valid_scope"] = "non_ui_behavior"
            with self.assertRaises(UIEvidenceError):
                unit_records_from_capture_runs(
                    delivery_root,
                    capture_ids,
                    authorized_exemptions=wrong_scope,
                )
            generic_cross_field = {
                "EX-UI-001": {
                    "exemption_id": "EX-UI-001",
                    "exemption_type": "ui_evidence_error",
                    "object_id": error_hash,
                    "valid_scope": "ui_evidence",
                    "allows_closure": True,
                }
            }
            with self.assertRaises(UIEvidenceError):
                unit_records_from_capture_runs(
                    delivery_root,
                    capture_ids,
                    authorized_exemptions=generic_cross_field,
                )

    def test_business_mock_exemption_cannot_cross_route_or_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            plan = self._plan()
            manifest_path = self._staging_manifest(root, plan)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            route = {
                "mechanism": "playwright.page.route",
                "pattern": "**/api/vendor-status",
                "classification": "business_api",
                "is_business_api": True,
                "exemption_ref": "EX-MOCK-001",
            }
            manifest["journey_segments"][0]["mocked_routes"] = [route]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = ingest_capture_run(root, delivery_root, plan, manifest_path)
            capture_ids = [result["capture_id"]]
            valid = {
                "EX-MOCK-001": {
                    "exemption_id": "EX-MOCK-001",
                    "exemption_type": "business_api_mock",
                    "object_id": "mocked_route:" + stable_hash({
                        field_name: route[field_name]
                        for field_name in (
                            "mechanism",
                            "pattern",
                            "classification",
                            "is_business_api",
                        )
                    }),
                    "valid_scope": ["business_api_mock"],
                    "allows_closure": True,
                }
            }
            records = browser_records_from_capture_runs(
                delivery_root,
                capture_ids,
                authorized_exemptions=valid,
            )
            self.assertTrue(
                records[0]["mocked_routes"][0][
                    "canonical_exemption_ref_verified"
                ]
            )
            invalid = json.loads(json.dumps(valid))
            invalid["EX-MOCK-001"]["object_id"] = "mocked_route:" + ("0" * 64)
            with self.assertRaises(UIEvidenceError):
                browser_records_from_capture_runs(
                    delivery_root,
                    capture_ids,
                    authorized_exemptions=invalid,
                )
            pattern_only = json.loads(json.dumps(valid))
            pattern_only["EX-MOCK-001"]["object_id"] = route["pattern"]
            with self.assertRaises(UIEvidenceError):
                browser_records_from_capture_runs(
                    delivery_root,
                    capture_ids,
                    authorized_exemptions=pattern_only,
                )

    def test_frozen_execution_identity_mismatch_has_no_registry_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery_root = root / ".product-delivery" / "deliveries" / "v1-ui" / "delivery-1"
            plan = self._plan()
            first_path = self._staging_manifest(root, plan)
            first = ingest_capture_run(root, delivery_root, plan, first_path)
            registry_path = delivery_root / "evidence" / "capture-registry.json"
            before_registry = registry_path.read_bytes()
            before_directories = sorted(
                item.name
                for item in (delivery_root / "evidence" / "captures").iterdir()
            )

            second_plan = {**plan, "plan_id": plan["plan_id"] + "-identity"}
            second_path = self._staging_manifest(root, second_plan)
            second_manifest = json.loads(second_path.read_text(encoding="utf-8"))
            second_manifest["environment_identity"]["feature_flags_sha256"] = "f" * 64
            second_path.write_text(json.dumps(second_manifest), encoding="utf-8")
            with self.assertRaises(UIEvidenceError) as caught:
                ingest_capture_run(
                    root,
                    delivery_root,
                    second_plan,
                    second_path,
                    expected_registry_sha256=first["registry_sha256"],
                    expected_registry_root_sha256=first["registry_root_sha256"],
                    expected_execution_identity=first["execution_identity"],
                )
            self.assertIn("execution identity", str(caught.exception))
            self.assertEqual(registry_path.read_bytes(), before_registry)
            self.assertEqual(
                sorted(
                    item.name
                    for item in (delivery_root / "evidence" / "captures").iterdir()
                ),
                before_directories,
            )

    def test_adapter_is_invoked_once_with_exact_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(purpose="iteration")
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            manifest_fixture = self._staging_manifest(root, plan)
            output = manifest_fixture.parent
            script = root / "adapter.py"
            counter = root / "counter.txt"
            script.write_text(
                "#!/usr/bin/env python3\n"
                "import hashlib, json, os, pathlib, sys\n"
                "counter = pathlib.Path(sys.argv[1])\n"
                "counter.write_text(counter.read_text() + 'x' if counter.exists() else 'x')\n"
                "out = pathlib.Path(os.environ['WAYGATE_CAPTURE_OUTPUT_DIR'])\n"
                "out.mkdir(parents=True, exist_ok=True)\n"
                "(out / 'argv.json').write_text(json.dumps(sys.argv[2:]))\n"
                "manifest_path = out / 'capture-manifest.json'\n"
                "manifest = json.loads(manifest_path.read_text())\n"
                "run_id = os.environ['WAYGATE_CAPTURE_RUN_ID']\n"
                "manifest['capture_run_ref'] = run_id\n"
                "probe_ref = manifest['journey_segments'][0]['probe']\n"
                "probe_path = pathlib.Path.cwd() / probe_ref['path']\n"
                "probe = json.loads(probe_path.read_text())\n"
                "probe['capture_run_ref'] = run_id\n"
                "probe_path.write_text(json.dumps(probe))\n"
                "probe_ref['sha256'] = hashlib.sha256(probe_path.read_bytes()).hexdigest()\n"
                "manifest_path.write_text(json.dumps(manifest))\n",
                encoding="utf-8",
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
            manifest = run_capture_adapter(
                project_root=root,
                plan_path=plan_path,
                adapter_executable=str(script),
                adapter_args=[str(counter), "argument with spaces", "literal;$HOME"],
                output_dir=output,
            )
            self.assertEqual(counter.read_text(), "x")
            self.assertEqual(
                json.loads((output / "argv.json").read_text()),
                ["argument with spaces", "literal;$HOME"],
            )
            self.assertEqual(manifest, output / "capture-manifest.json")
            metrics = json.loads(
                (output / "capture-run-telemetry.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metrics["browser_launches"], 1)
            self.assertGreaterEqual(metrics["wall_ms"], 0)

    def test_performance_telemetry_is_aggregated_without_gate_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            delivery_root = Path(tmp)
            append_performance_event(
                delivery_root,
                {
                    "operation": "capture",
                    "wall_ms": 120,
                    "browser_launches": 1,
                    "capture_units": 2,
                    "reused_artifacts": 6,
                    "total_artifacts": 8,
                },
            )
            append_performance_event(
                delivery_root,
                {
                    "operation": "projection",
                    "wall_ms": 30,
                    "browser_launches": 0,
                    "capture_units": 0,
                    "reused_artifacts": 2,
                    "total_artifacts": 2,
                },
            )
            report = performance_report(delivery_root)
            self.assertEqual(report["event_count"], 2)
            self.assertEqual(report["wall_ms"], 150)
            self.assertEqual(report["browser_launches"], 1)
            self.assertEqual(report["artifact_reuse_ratio"], 0.8)
            self.assertIn("gate_wall_clock_ms", report)
            self.assertIn("duplicate_capture_ratio", report)
            self.assertIn("raw_artifacts", report)
            self.assertIn("unique_artifacts", report)
            self.assertIn("validator_wall_ms", report)
            self.assertIn("projection_reuse_count", report)
            self.assertNotIn("passed", report)

    def test_workflow_prepares_and_records_capture_without_advancing_a_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_thread = os.environ.get("CODEX_THREAD_ID")
            os.environ["CODEX_THREAD_ID"] = "thread-v1039-capture"
            try:
                workflow = ProductDeliveryWorkflow(root)
                started = workflow.start(
                    feature_slug="v1039-ui-capture",
                    multi_agent_mode="spawned_subagents_authorized",
                )
                workflow.select_project_type("ui")
                state = load_state(root)
                state["prototype_contract"] = {
                    "surfaces": [
                        {
                            "surface_id": "dashboard",
                            "state_id": "default",
                            "required_viewports": ["desktop"],
                        }
                    ]
                }
                state["planned_e2e_obligations"] = {
                    "obligations": [
                        {"obligation_id": "OBL-001", "test_id": "TC-001"}
                    ]
                }
                state["ui_evidence_risk_facts"] = {
                    "impact_known": True,
                    "risk_tags": [],
                }
                write_state(root, state)

                plan = workflow.prepare_ui_evidence_run("closure")
                self.assertEqual(plan["resolved_profile"], "strict")
                self.assertTrue(plan["artifact_path"].endswith(".json"))
                manifest_path = self._staging_manifest(root, plan)
                result = workflow.record_ui_evidence_run(
                    plan["plan_id"], str(manifest_path)
                )
                current = load_state(root)
                self.assertTrue(result["closure_valid"])
                self.assertEqual(
                    current["ui_capture_registry"]["capture_run_ids"],
                    [result["capture_id"]],
                )
                self.assertEqual(current["stage"], "ui_prototype_confirmation")
                self.assertEqual(workflow.performance_report()["event_count"], 1)
                self.assertEqual(started["feature_slug"], "v1039-ui-capture")
            finally:
                if previous_thread is None:
                    os.environ.pop("CODEX_THREAD_ID", None)
                else:
                    os.environ["CODEX_THREAD_ID"] = previous_thread

    def test_workflow_rejects_superseded_plan_and_preserves_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_thread = os.environ.get("CODEX_THREAD_ID")
            os.environ["CODEX_THREAD_ID"] = "thread-v1039-stale-plan"
            try:
                workflow = ProductDeliveryWorkflow(root)
                workflow.start(
                    feature_slug="v1039-stale-plan",
                    multi_agent_mode="spawned_subagents_authorized",
                )
                workflow.select_project_type("ui")
                state = load_state(root)
                state["prototype_contract"] = {
                    "surfaces": [{
                        "surface_id": "dashboard",
                        "state_id": "default",
                        "required_viewports": ["desktop"],
                    }]
                }
                state["planned_e2e_obligations"] = {
                    "obligations": [{"obligation_id": "OBL-001", "test_id": "TC-001"}]
                }
                write_state(root, state)
                old = workflow.prepare_ui_evidence_run("closure")
                old_manifest = self._staging_manifest(root, old)
                changed = load_state(root)
                changed["ui_evidence_risk_facts"] = {
                    "impact_known": False,
                    "risk_tags": ["security"],
                }
                write_state(root, changed)
                strict = workflow.prepare_ui_evidence_run("closure", "strict")
                self.assertEqual(strict["resolved_profile"], "strict")
                registry = (
                    root / ".product-delivery" / "deliveries" / "v1039-stale-plan"
                    / state["delivery_id"] / "evidence" / "capture-registry.json"
                )
                with self.assertRaises(Exception) as caught:
                    workflow.record_ui_evidence_run(old["plan_id"], str(old_manifest))
                self.assertIn("current", str(caught.exception))
                self.assertFalse(registry.exists())
            finally:
                if previous_thread is None:
                    os.environ.pop("CODEX_THREAD_ID", None)
                else:
                    os.environ["CODEX_THREAD_ID"] = previous_thread

    def test_workflow_rolls_back_capture_registry_when_state_commit_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_thread = os.environ.get("CODEX_THREAD_ID")
            os.environ["CODEX_THREAD_ID"] = "thread-v1039-rollback"
            try:
                workflow = ProductDeliveryWorkflow(root)
                workflow.start(
                    feature_slug="v1039-rollback",
                    multi_agent_mode="spawned_subagents_authorized",
                )
                workflow.select_project_type("ui")
                state = load_state(root)
                state["prototype_contract"] = {
                    "surfaces": [{
                        "surface_id": "dashboard",
                        "state_id": "default",
                        "required_viewports": ["desktop"],
                    }]
                }
                state["planned_e2e_obligations"] = {
                    "obligations": [{"obligation_id": "OBL-001", "test_id": "TC-001"}]
                }
                write_state(root, state)
                plan = workflow.prepare_ui_evidence_run("closure", "strict")
                manifest = self._staging_manifest(root, plan)
                delivery_root = (
                    root / ".product-delivery" / "deliveries"
                    / state["feature_slug"] / state["delivery_id"]
                )
                with mock.patch(
                    "product_delivery_agent.workflow._write_state_locked",
                    side_effect=OSError("injected state failure"),
                ):
                    with self.assertRaises(Exception) as caught:
                        workflow.record_ui_evidence_run(
                            plan["plan_id"], str(manifest)
                        )
                self.assertIn("rolled back", str(caught.exception))
                self.assertFalse(
                    (delivery_root / "evidence" / "capture-registry.json").exists()
                )
                captures_root = delivery_root / "evidence" / "captures"
                self.assertFalse(captures_root.exists() and any(captures_root.iterdir()))
            finally:
                if previous_thread is None:
                    os.environ.pop("CODEX_THREAD_ID", None)
                else:
                    os.environ["CODEX_THREAD_ID"] = previous_thread

    def test_pending_capture_transaction_recovers_after_process_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_thread = os.environ.get("CODEX_THREAD_ID")
            os.environ["CODEX_THREAD_ID"] = "thread-v1039-crash-recovery"
            try:
                workflow = ProductDeliveryWorkflow(root)
                workflow.start(
                    feature_slug="v1039-crash-recovery",
                    multi_agent_mode="spawned_subagents_authorized",
                )
                workflow.select_project_type("ui")
                state = load_state(root)
                state["prototype_contract"] = {
                    "surfaces": [{
                        "surface_id": "dashboard",
                        "state_id": "default",
                        "required_viewports": ["desktop"],
                    }]
                }
                state["planned_e2e_obligations"] = {
                    "obligations": [{"obligation_id": "OBL-001", "test_id": "TC-001"}]
                }
                write_state(root, state)
                plan = workflow.prepare_ui_evidence_run("closure", "strict")
                manifest = self._staging_manifest(root, plan)
                state = load_state(root)
                delivery_root = workflow._current_delivery_root(state)
                registry_path = delivery_root / "evidence" / "capture-registry.json"
                inspected = inspect_capture_run(
                    root,
                    delivery_root,
                    (state["ui_capture_plans"] or {})[plan["plan_id"]],
                    manifest,
                )
                transaction = workflow._begin_ui_capture_transaction(
                    state,
                    root=delivery_root,
                    plan_id=plan["plan_id"],
                    registry_path=registry_path,
                    capture_id=inspected["capture_id"],
                    capture_created=True,
                    manifest_path=manifest,
                    manifest_sha256=inspected["manifest_sha256"],
                )
                result = ingest_capture_run(
                    root,
                    delivery_root,
                    (state["ui_capture_plans"] or {})[plan["plan_id"]],
                    manifest,
                )
                transaction.update({
                    "status": "registry_committed",
                    "capture_id": result["capture_id"],
                    "capture_created": True,
                    "registry_after_sha256": result["registry_sha256"],
                    "registry_root_after_sha256": result["registry_root_sha256"],
                })
                workflow._write_ui_capture_transaction(transaction)

                shutil.rmtree(manifest.parent)
                workflow.performance_report()
                self.assertFalse(registry_path.exists())
                self.assertFalse(
                    (delivery_root / "evidence" / "captures" / result["capture_id"]).exists()
                )
                receipt_path = (
                    delivery_root / "evidence" / "transactions"
                    / f"{transaction['transaction_id']}.json"
                )
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                self.assertEqual(receipt["status"], "rolled_back")
            finally:
                if previous_thread is None:
                    os.environ.pop("CODEX_THREAD_ID", None)
                else:
                    os.environ["CODEX_THREAD_ID"] = previous_thread

    def test_post_state_replace_failure_preserves_capture_and_retry_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_thread = os.environ.get("CODEX_THREAD_ID")
            os.environ["CODEX_THREAD_ID"] = "thread-v1039-post-replace"
            try:
                workflow = ProductDeliveryWorkflow(root)
                workflow.start(
                    feature_slug="v1039-post-replace",
                    multi_agent_mode="spawned_subagents_authorized",
                )
                workflow.select_project_type("ui")
                state = load_state(root)
                state["prototype_contract"] = {
                    "surfaces": [{
                        "surface_id": "dashboard",
                        "state_id": "default",
                        "required_viewports": ["desktop"],
                    }]
                }
                state["planned_e2e_obligations"] = {
                    "obligations": [{"obligation_id": "OBL-001", "test_id": "TC-001"}]
                }
                write_state(root, state)
                plan = workflow.prepare_ui_evidence_run("closure", "strict")
                manifest = self._staging_manifest(root, plan)
                with mock.patch(
                    "product_delivery_agent.artifact_store.ensure_delivery_layout",
                    side_effect=OSError("injected mirror refresh failure"),
                ):
                    with self.assertRaises(Exception) as caught:
                        workflow.record_ui_evidence_run(plan["plan_id"], str(manifest))
                self.assertIn("state committed", str(caught.exception))
                committed = load_state(root)
                capture_id = committed["ui_evidence_policy"]["current_capture_id"]
                delivery_root = workflow._current_delivery_root(committed)
                self.assertTrue(
                    (delivery_root / "evidence" / "capture-registry.json").is_file()
                )
                self.assertTrue(
                    (delivery_root / "evidence" / "captures" / capture_id).is_dir()
                )
                recovered = workflow.record_ui_evidence_run(
                    plan["plan_id"], str(manifest)
                )
                self.assertEqual(recovered["capture_id"], capture_id)
                self.assertTrue(recovered["recovered"])
            finally:
                if previous_thread is None:
                    os.environ.pop("CODEX_THREAD_ID", None)
                else:
                    os.environ["CODEX_THREAD_ID"] = previous_thread

    def test_tampered_transaction_receipt_cannot_cross_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_thread = os.environ.get("CODEX_THREAD_ID")
            os.environ["CODEX_THREAD_ID"] = "thread-v1039-receipt-tamper"
            try:
                workflow = ProductDeliveryWorkflow(root)
                workflow.start(
                    feature_slug="v1039-receipt-tamper",
                    multi_agent_mode="spawned_subagents_authorized",
                )
                workflow.select_project_type("ui")
                state = load_state(root)
                delivery_root = workflow._current_delivery_root(state)
                transactions = delivery_root / "evidence" / "transactions"
                transactions.mkdir(parents=True)
                transaction_id = "ui-capture-tx-" + ("a" * 32)
                forged = {
                    "schema_version": "ui-capture-transaction-v1",
                    "transaction_id": transaction_id,
                    "status": "pending",
                    "delivery_id": state["delivery_id"],
                    "feature_slug": state["feature_slug"],
                    "plan_id": "capture-plan-" + ("b" * 24),
                    "capture_id": "capture-" + ("c" * 64),
                    "capture_created": True,
                    "delivery_root": ".product-delivery/deliveries/victim/other",
                    "registry_path": "evidence/capture-registry.json",
                    "registry_before_exists": False,
                    "registry_before_sha256": None,
                    "registry_before_base64": "",
                    "state_before_sha256": "d" * 64,
                }
                path = transactions / f"{transaction_id}.json"
                path.write_text(json.dumps(forged), encoding="utf-8")
                with self.assertRaises(Exception) as caught:
                    workflow._recover_pending_ui_capture_transactions(state)
                self.assertIn("delivery root", str(caught.exception))
                self.assertTrue(path.is_file())
            finally:
                if previous_thread is None:
                    os.environ.pop("CODEX_THREAD_ID", None)
                else:
                    os.environ["CODEX_THREAD_ID"] = previous_thread

    def test_capture_transaction_serializes_concurrent_idempotent_writers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_thread = os.environ.get("CODEX_THREAD_ID")
            os.environ["CODEX_THREAD_ID"] = "thread-v1039-concurrent"
            try:
                workflow = ProductDeliveryWorkflow(root)
                workflow.start(
                    feature_slug="v1039-concurrent",
                    multi_agent_mode="spawned_subagents_authorized",
                )
                workflow.select_project_type("ui")
                state = load_state(root)
                state["prototype_contract"] = {
                    "surfaces": [{
                        "surface_id": "dashboard",
                        "state_id": "default",
                        "required_viewports": ["desktop"],
                    }]
                }
                state["planned_e2e_obligations"] = {
                    "obligations": [{"obligation_id": "OBL-001", "test_id": "TC-001"}]
                }
                write_state(root, state)
                plan = workflow.prepare_ui_evidence_run("closure", "strict")
                manifest = self._staging_manifest(root, plan)
                results = []
                errors = []

                def record():
                    try:
                        results.append(
                            ProductDeliveryWorkflow(root).record_ui_evidence_run(
                                plan["plan_id"], str(manifest)
                            )
                        )
                    except Exception as cause:
                        errors.append(cause)

                threads = [threading.Thread(target=record) for _ in range(2)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=10)
                self.assertFalse(errors)
                self.assertEqual(len(results), 2)
                self.assertEqual({row["capture_id"] for row in results}, {
                    results[0]["capture_id"]
                })
                current = load_state(root)
                self.assertEqual(
                    current["ui_capture_registry"]["capture_run_ids"],
                    [results[0]["capture_id"]],
                )
                self.assertEqual(
                    sum(
                        1
                        for event in current["transition_journal"]["events"]
                        if event["transition_name"] == "ui_capture_run_ingested"
                    ),
                    1,
                )
            finally:
                if previous_thread is None:
                    os.environ.pop("CODEX_THREAD_ID", None)
                else:
                    os.environ["CODEX_THREAD_ID"] = previous_thread

    def test_ingested_plan_replay_rejects_new_capture_without_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_thread = os.environ.get("CODEX_THREAD_ID")
            os.environ["CODEX_THREAD_ID"] = "thread-v1039-replay"
            try:
                workflow = ProductDeliveryWorkflow(root)
                workflow.start(
                    feature_slug="v1039-replay",
                    multi_agent_mode="spawned_subagents_authorized",
                )
                workflow.select_project_type("ui")
                state = load_state(root)
                state["prototype_contract"] = {
                    "surfaces": [{
                        "surface_id": "dashboard",
                        "state_id": "default",
                        "required_viewports": ["desktop"],
                    }]
                }
                state["planned_e2e_obligations"] = {
                    "obligations": [{"obligation_id": "OBL-001", "test_id": "TC-001"}]
                }
                write_state(root, state)
                plan = workflow.prepare_ui_evidence_run("closure", "strict")
                manifest_path = self._staging_manifest(root, plan)
                first = workflow.record_ui_evidence_run(
                    plan["plan_id"], str(manifest_path)
                )
                current = load_state(root)
                delivery_root = workflow._current_delivery_root(current)
                registry_path = delivery_root / "evidence" / "capture-registry.json"
                registry_before = registry_path.read_bytes()
                captures_before = sorted(
                    item.name
                    for item in (delivery_root / "evidence" / "captures").iterdir()
                )
                state_before = (root / ".product-delivery" / "state.json").read_bytes()
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["data_state_identity"]["version"] = "2"
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(Exception) as caught:
                    workflow.record_ui_evidence_run(
                        plan["plan_id"], str(manifest_path)
                    )
                self.assertIn("identity changed", str(caught.exception))
                self.assertEqual(registry_path.read_bytes(), registry_before)
                self.assertEqual(
                    sorted(
                        item.name
                        for item in (delivery_root / "evidence" / "captures").iterdir()
                    ),
                    captures_before,
                )
                self.assertEqual(
                    (root / ".product-delivery" / "state.json").read_bytes(),
                    state_before,
                )
                self.assertEqual(first["capture_id"], captures_before[0])
            finally:
                if previous_thread is None:
                    os.environ.pop("CODEX_THREAD_ID", None)
                else:
                    os.environ["CODEX_THREAD_ID"] = previous_thread

    def test_post_implementation_review_batch_is_atomic_and_typed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_thread = os.environ.get("CODEX_THREAD_ID")
            os.environ["CODEX_THREAD_ID"] = "thread-v1039-review"
            try:
                workflow = ProductDeliveryWorkflow(root)
                workflow.start(
                    feature_slug="v1039-review-batch",
                    multi_agent_mode="spawned_subagents_authorized",
                )
                workflow.select_project_type("ui")
                state = load_state(root)
                obligation = planned_obligation()
                state["planned_e2e_obligations"] = {
                    "accepted": True,
                    "accepted_by_user": True,
                    "obligations": [obligation],
                    "exemptions": [],
                }
                state["executed_browser_evidence"] = {
                    "status": "passed",
                    "records": [
                        {
                            **full_stack_record(),
                            "scenario_id": obligation["scenario_id"],
                            "user_story": obligation["user_story"],
                            "journey": obligation["journey"],
                        }
                    ],
                }
                state["prototype_contract"] = {
                    "surfaces": [
                        {
                            "surface_id": "dashboard",
                            "state_id": "default",
                            "critical_regions": [{"region_id": "main-region"}],
                        }
                    ]
                }
                state["prototype_production_conformance"] = {
                    "status": "passed",
                    "covered_surface_ids": ["dashboard"],
                    "covered_state_ids": ["default"],
                    "covered_region_ids": ["main-region"],
                }
                write_state(root, state)
                batch = workflow.prepare_post_implementation_review_batch()
                qa_review = review_payload(
                    reviewer_agent_ids=["agent-qa", "agent-e2e"],
                    reviewer_spawn_source="codex.multi_agent_v1.spawn_agent",
                )
                with self.assertRaises(Exception):
                    workflow.record_post_implementation_review_batch(
                        {
                            "batch_id": batch["batch_id"],
                            "closure_review_snapshot_sha256": batch[
                                "closure_review_snapshot_sha256"
                            ],
                            "test_implementation_review": qa_review,
                            "ui_conformance_review": self._ui_conformance_review(
                                reviewed_regions=["wrong-region"]
                            ),
                        }
                    )
                failed_state = load_state(root)
                self.assertNotEqual(
                    failed_state.get("multi_agent_reviews", {})
                    .get("test_implementation", {})
                    .get("status"),
                    "passed",
                )

                passed = workflow.record_post_implementation_review_batch(
                    {
                        "batch_id": batch["batch_id"],
                        "closure_review_snapshot_sha256": batch[
                            "closure_review_snapshot_sha256"
                        ],
                        "test_implementation_review": qa_review,
                        "ui_conformance_review": self._ui_conformance_review(),
                    }
                )
                self.assertEqual(
                    passed["post_implementation_review_batch"]["status"], "passed"
                )
                self.assertEqual(
                    {
                        key: passed["multi_agent_reviews"][key]["status"]
                        for key in ("test_implementation", "ui_conformance")
                    },
                    {"test_implementation": "passed", "ui_conformance": "passed"},
                )
            finally:
                if previous_thread is None:
                    os.environ.pop("CODEX_THREAD_ID", None)
                else:
                    os.environ["CODEX_THREAD_ID"] = previous_thread

    def test_review_batch_rejects_changed_evidence_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_thread = os.environ.get("CODEX_THREAD_ID")
            os.environ["CODEX_THREAD_ID"] = "thread-v1039-stale-review"
            try:
                workflow = ProductDeliveryWorkflow(root)
                workflow.start(
                    feature_slug="v1039-stale-review",
                    multi_agent_mode="spawned_subagents_authorized",
                )
                workflow.select_project_type("ui")
                state = load_state(root)
                obligation = planned_obligation()
                state["planned_e2e_obligations"] = {
                    "accepted": True,
                    "accepted_by_user": True,
                    "obligations": [obligation],
                    "exemptions": [],
                }
                state["executed_browser_evidence"] = {
                    "status": "passed",
                    "records": [{
                        **full_stack_record(),
                        "scenario_id": obligation["scenario_id"],
                        "user_story": obligation["user_story"],
                        "journey": obligation["journey"],
                    }],
                }
                state["prototype_contract"] = {
                    "surfaces": [{
                        "surface_id": "dashboard",
                        "state_id": "default",
                        "critical_regions": [{"region_id": "main-region"}],
                    }]
                }
                state["prototype_production_conformance"] = {
                    "status": "passed",
                    "covered_surface_ids": ["dashboard"],
                    "covered_state_ids": ["default"],
                    "covered_region_ids": ["main-region"],
                }
                write_state(root, state)
                batch = workflow.prepare_post_implementation_review_batch()
                changed = load_state(root)
                changed["executed_browser_evidence"]["records"][0][
                    "test_title_or_step"
                ] = "changed after review snapshot"
                write_state(root, changed)
                with self.assertRaises(Exception) as caught:
                    workflow.record_post_implementation_review_batch({
                        "batch_id": batch["batch_id"],
                        "closure_review_snapshot_sha256": batch[
                            "closure_review_snapshot_sha256"
                        ],
                        "test_implementation_review": review_payload(
                            reviewer_agent_ids=["agent-qa", "agent-e2e"],
                            reviewer_spawn_source="codex.multi_agent_v1.spawn_agent",
                        ),
                        "ui_conformance_review": self._ui_conformance_review(),
                    })
                self.assertIn("snapshot", str(caught.exception))
            finally:
                if previous_thread is None:
                    os.environ.pop("CODEX_THREAD_ID", None)
                else:
                    os.environ["CODEX_THREAD_ID"] = previous_thread


if __name__ == "__main__":
    unittest.main()
