import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.evidence_artifacts import sha256_file
from product_delivery_agent.prototype_design import (
    PrototypeDesignError,
    build_prototype_design_bundle,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError
from tests.test_prototype_design_integrity_v1023 import (
    prepare_project,
    semantic_prototype_contract,
    valid_payload,
    write_json,
)
from tests.test_prototype_design_workflow_v1023 import (
    start_ui_workflow,
)


SCAN_VERSION = "prototype-acceptance-content-scan-v1"


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _finding(
    finding_id: str,
    *,
    rule_id: str,
    classification: str,
    source: str,
    location: str,
    text: str,
    region_id: str = "course-grid",
) -> dict:
    return {
        "finding_id": finding_id,
        "rule_id": rule_id,
        "classification": classification,
        "source": source,
        "location": location,
        "region_id": region_id,
        "text_excerpt": text,
        "text_sha256": _text_hash(text),
    }


def _write_scan_report(root: Path, payload: dict, findings: list[dict]) -> str:
    prototype_path = root / payload["clean_surface"]["prototype_path"]
    semantic_path = root / payload["clean_surface"]["semantic_snapshot_path"]
    observations = []
    for viewport in ("desktop", "mobile"):
        observations.append(
            {
                "surface_id": "course-catalog",
                "state_id": "catalog-ready",
                "viewport": viewport,
                "findings": copy.deepcopy(findings),
            }
        )
    report = {
        "schema_version": SCAN_VERSION,
        "prototype_path": payload["clean_surface"]["prototype_path"],
        "prototype_sha256": sha256_file(prototype_path),
        "semantic_snapshot_sha256": sha256_file(semantic_path),
        "observations": observations,
    }
    path = root / ".product-delivery/artifacts/review-only/acceptance-content-scan.json"
    write_json(path, report)
    return str(path.relative_to(root))


def v2_payload(
    root: Path,
    *,
    findings: list[dict] | None = None,
    mappings: list[dict] | None = None,
) -> dict:
    payload = valid_payload(root)
    payload["bundle_version"] = "v2"
    payload["acceptance_content_separation"] = {
        "declared_absent": True,
        "scan_report_path": _write_scan_report(root, payload, findings or []),
        "product_content_mappings": mappings or [],
    }
    return payload


class AcceptanceContentSeparationV1034Tests(unittest.TestCase):
    def test_v2_requires_positive_declaration_and_bound_scan_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            payload = v2_payload(root)

            result = build_prototype_design_bundle(
                root, payload, prototype_contract=semantic_prototype_contract()
            )

            self.assertEqual(result["bundle_version"], "v2")
            self.assertTrue(
                result["acceptance_content_separation"]["declared_absent"]
            )
            self.assertEqual(
                result["artifact_metadata"]["acceptance_content_scan_report"][
                    "schema_version"
                ],
                SCAN_VERSION,
            )
            self.assertTrue(
                result["design_audit"]["deterministic_checks"][
                    "acceptance_content_separated"
                ]
            )

            missing = copy.deepcopy(payload)
            missing.pop("acceptance_content_separation")
            with self.assertRaisesRegex(
                PrototypeDesignError, "requires acceptance_content_separation"
            ):
                build_prototype_design_bundle(
                    root, missing, prototype_contract=semantic_prototype_contract()
                )

            denied = copy.deepcopy(payload)
            denied["acceptance_content_separation"]["declared_absent"] = False
            with self.assertRaisesRegex(PrototypeDesignError, "declared_absent"):
                build_prototype_design_bundle(
                    root, denied, prototype_contract=semantic_prototype_contract()
                )

    def test_static_acceptance_and_development_copy_is_hard_blocking(self):
        forbidden_copy = (
            "验收标准：课程可打开",
            "测试步骤：点击课程",
            "预期结果：进入详情",
            "AC-001",
            "TC-023",
            "SC-004",
            "证据路径：artifacts/result.png",
            "评审意见：需要确认",
            "评审结论：待验收",
            "测试覆盖：主流程",
            "开发说明：使用 mock fixture test-only 数据",
        )
        for text in forbidden_copy:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                prepare_project(root)
                prototype = root / "docs/prototypes/course-catalog.html"
                prototype.write_text(
                    f'<html><body><main id="course-grid">{text}</main></body></html>',
                    encoding="utf-8",
                )
                payload = v2_payload(root)
                with self.assertRaisesRegex(
                    PrototypeDesignError,
                    r"acceptance content.*course-catalog/catalog-ready.*course-grid",
                ):
                    build_prototype_design_bundle(
                        root,
                        payload,
                        prototype_contract=semantic_prototype_contract(),
                    )

    def test_runtime_hard_finding_and_hidden_review_dom_are_hard_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            hidden = root / "docs/prototypes/course-catalog.html"
            hidden.write_text(
                '<html><body><div hidden data-acceptance-note="AC-001">'
                "验收标准</div></body></html>",
                encoding="utf-8",
            )
            payload = v2_payload(root)
            with self.assertRaisesRegex(PrototypeDesignError, "acceptance content"):
                build_prototype_design_bundle(
                    root, payload, prototype_contract=semantic_prototype_contract()
                )

    def test_semantic_snapshot_acceptance_copy_is_hard_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            payload = valid_payload(root)
            contract = semantic_prototype_contract()
            text = "验收标准：课程列表可见"
            contract["surfaces"][0]["critical_regions"][2][
                "accessible_name_match"
            ]["value"] = text
            snapshot_path = root / payload["clean_surface"]["semantic_snapshot_path"]
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            for state in snapshot["states"]:
                state["regions"][2]["accessible_name"] = text
            write_json(snapshot_path, snapshot)
            preflight_path = root / payload["clean_surface"][
                "browser_preflight_probe_path"
            ]
            preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
            preflight["semantic_snapshot_sha256"] = sha256_file(snapshot_path)
            for observation, state in zip(
                preflight["observations"], snapshot["states"]
            ):
                from product_delivery_agent.evidence_artifacts import stable_json_hash

                observation["semantic_state_sha256"] = stable_json_hash(state)
            write_json(preflight_path, preflight)
            payload["bundle_version"] = "v2"
            payload["acceptance_content_separation"] = {
                "declared_absent": True,
                "scan_report_path": _write_scan_report(root, payload, []),
                "product_content_mappings": [],
            }

            with self.assertRaisesRegex(
                PrototypeDesignError,
                r"acceptance content.*semantic_snapshot.*course-grid",
            ):
                build_prototype_design_bundle(
                    root, payload, prototype_contract=contract
                )

    def test_acceptance_resource_reference_is_hard_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            prototype = root / "docs/prototypes/course-catalog.html"
            prototype.write_text(
                '<html><body><main id="course-grid">'
                '<a href="/acceptance/evidence.html">Details</a>'
                "</main></body></html>",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PrototypeDesignError, r"course-grid.*acceptance-only-resource"
            ):
                build_prototype_design_bundle(
                    root,
                    v2_payload(root),
                    prototype_contract=semantic_prototype_contract(),
                )

    def test_acceptance_copy_in_accessibility_attribute_is_hard_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            prototype = root / "docs/prototypes/course-catalog.html"
            prototype.write_text(
                '<html><body><main id="course-grid" '
                'aria-label="验收标准：课程列表可见">Catalog</main></body></html>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PrototypeDesignError, r"attribute.*acceptance-standard"
            ):
                build_prototype_design_bundle(
                    root,
                    v2_payload(root),
                    prototype_contract=semantic_prototype_contract(),
                )

    def test_scan_report_must_be_review_only_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            payload = v2_payload(root)
            original_path = root / payload["acceptance_content_separation"][
                "scan_report_path"
            ]
            wrong_path = root / ".product-delivery/artifacts/prototype-design/scan.json"
            write_json(
                wrong_path,
                json.loads(original_path.read_text(encoding="utf-8")),
            )
            payload["acceptance_content_separation"]["scan_report_path"] = str(
                wrong_path.relative_to(root)
            )
            with self.assertRaisesRegex(PrototypeDesignError, "review-only"):
                build_prototype_design_bundle(
                    root, payload, prototype_contract=semantic_prototype_contract()
                )

            payload = v2_payload(root)
            report_path = root / payload["acceptance_content_separation"][
                "scan_report_path"
            ]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["prototype_sha256"] = "0" * 64
            write_json(report_path, report)
            with self.assertRaisesRegex(PrototypeDesignError, "prototype_sha256"):
                build_prototype_design_bundle(
                    root, payload, prototype_contract=semantic_prototype_contract()
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            finding = _finding(
                "runtime-acceptance-1",
                rule_id="acceptance-standard",
                classification="hard_blocking",
                source="rendered_dom",
                location="#course-grid > .generated-note",
                text="验收标准：运行时生成",
            )
            payload = v2_payload(root, findings=[finding])
            with self.assertRaisesRegex(
                PrototypeDesignError,
                r"runtime-acceptance-1.*rendered_dom.*course-catalog/catalog-ready",
            ):
                build_prototype_design_bundle(
                    root, payload, prototype_contract=semantic_prototype_contract()
                )

    def test_ambiguous_product_copy_requires_matching_callout_mapping(self):
        cases = ("测试连接", "审核通过", "状态：不通过")
        for text in cases:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                prepare_project(root)
                finding = _finding(
                    "product-copy-1",
                    rule_id="ambiguous-product-status",
                    classification="product_content_candidate",
                    source="rendered_dom",
                    location="#course-grid .status",
                    text=text,
                )
                payload = v2_payload(root, findings=[finding])
                with self.assertRaisesRegex(
                    PrototypeDesignError, "product-copy-1.*product_content_mappings"
                ):
                    build_prototype_design_bundle(
                        root, payload, prototype_contract=semantic_prototype_contract()
                    )

                payload["acceptance_content_separation"][
                    "product_content_mappings"
                ] = [
                    {
                        "finding_id": "product-copy-1",
                        "callout_id": "catalog-empty-state",
                    }
                ]
                result = build_prototype_design_bundle(
                    root, payload, prototype_contract=semantic_prototype_contract()
                )
                self.assertEqual(
                    result["acceptance_content_separation"][
                        "product_content_mappings"
                    ],
                    [
                        {
                            "finding_id": "product-copy-1",
                            "callout_id": "catalog-empty-state",
                        }
                    ],
                )

    def test_mapping_must_be_unique_and_match_callout_state_and_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            finding = _finding(
                "candidate-1",
                rule_id="ambiguous-product-status",
                classification="product_content_candidate",
                source="rendered_dom",
                location="#catalog-navigation .status",
                text="审核通过",
                region_id="catalog-navigation",
            )
            mapping = {"finding_id": "candidate-1", "callout_id": "catalog-empty-state"}
            payload = v2_payload(root, findings=[finding], mappings=[mapping])
            with self.assertRaisesRegex(PrototypeDesignError, "state and region"):
                build_prototype_design_bundle(
                    root, payload, prototype_contract=semantic_prototype_contract()
                )

            duplicate = v2_payload(
                root,
                findings=[finding],
                mappings=[mapping, copy.deepcopy(mapping)],
            )
            with self.assertRaisesRegex(PrototypeDesignError, "duplicate.*finding_id"):
                build_prototype_design_bundle(
                    root, duplicate, prototype_contract=semantic_prototype_contract()
                )

            unknown = v2_payload(
                root,
                findings=[],
                mappings=[{"finding_id": "missing", "callout_id": "catalog-empty-state"}],
            )
            with self.assertRaisesRegex(PrototypeDesignError, "unknown finding"):
                build_prototype_design_bundle(
                    root, unknown, prototype_contract=semantic_prototype_contract()
                )

    def test_data_testid_and_normal_product_help_are_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            prototype = root / "docs/prototypes/course-catalog.html"
            prototype.write_text(
                '<html><body><main id="course-grid" data-testid="course-grid">'
                "请选择课程后继续；连接失败，请重试。"
                "</main></body></html>",
                encoding="utf-8",
            )
            result = build_prototype_design_bundle(
                root,
                v2_payload(root),
                prototype_contract=semantic_prototype_contract(),
            )
            self.assertEqual(result["status"], "ready")

    def test_scan_evidence_and_mapping_are_outside_product_domain_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            finding = _finding(
                "candidate-1",
                rule_id="ambiguous-product-status",
                classification="product_content_candidate",
                source="rendered_dom",
                location="#course-grid .status",
                text="审核通过",
            )
            first_payload = v2_payload(
                root,
                findings=[finding],
                mappings=[
                    {
                        "finding_id": "candidate-1",
                        "callout_id": "catalog-empty-state",
                    }
                ],
            )
            first = build_prototype_design_bundle(
                root, first_payload, prototype_contract=semantic_prototype_contract()
            )

            changed = copy.deepcopy(first_payload)
            scan_path = root / changed["acceptance_content_separation"]["scan_report_path"]
            scan = json.loads(scan_path.read_text(encoding="utf-8"))
            for observation in scan["observations"]:
                observation["findings"][0]["location"] = "#course-grid .renamed-status"
            write_json(scan_path, scan)
            second = build_prototype_design_bundle(
                root, changed, prototype_contract=semantic_prototype_contract()
            )

            self.assertEqual(
                first["product_domain_sha256"], second["product_domain_sha256"]
            )
            self.assertNotEqual(
                first["review_domain_sha256"], second["review_domain_sha256"]
            )

    def test_historical_v1_bundle_remains_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            result = build_prototype_design_bundle(
                root,
                valid_payload(root),
                prototype_contract=semantic_prototype_contract(),
            )
            self.assertEqual(result["bundle_version"], "v1")
            self.assertNotIn("acceptance_content_separation", result)
            self.assertEqual(
                result["product_domain_sha256"],
                "51960893648b54dc7d1e88642c4e61809d3ecf8c176ab1bf91f7c357da4f84c2",
            )
            self.assertEqual(
                result["review_domain_sha256"],
                "ed124d91c8c69af8db8708c26c206fb652c6ebeda582b8d9809252cfb198e0c8",
            )
            self.assertEqual(
                result["bundle_sha256"],
                "b1e04486548b867900747a075bbaad4c43b11e1070d114d73b903e99d8274073",
            )

    def test_workflow_requires_v2_for_new_or_reopened_bundle_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow, _ = start_ui_workflow(root, with_bundle=False)
            prepare_project(root)
            payload = valid_payload(root)
            payload["clean_surface"]["prototype_contract"] = semantic_prototype_contract()

            with self.assertRaisesRegex(WorkflowError, "bundle_version must be v2"):
                workflow.record_ui_prototype_design_bundle(payload)

            upgraded = v2_payload(root)
            upgraded["clean_surface"]["prototype_contract"] = (
                semantic_prototype_contract()
            )
            state = workflow.record_ui_prototype_design_bundle(upgraded)
            self.assertEqual(state["prototype_design_bundle"]["bundle_version"], "v2")


if __name__ == "__main__":
    unittest.main()
