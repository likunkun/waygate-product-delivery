import copy
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from product_delivery_agent.prototype_design import (
    PrototypeDesignError,
    build_prototype_design_bundle,
)
from product_delivery_agent.evidence_artifacts import sha256_file, stable_json_hash


PRODUCT_CONTEXT_DIMENSIONS = (
    "global_shell",
    "navigation",
    "visual_language",
    "information_density",
    "component_system",
    "responsive_behavior",
)

SEMANTIC_SCHEMA_VERSION = "prototype-semantic-snapshot-v1"
PREFLIGHT_SCHEMA_VERSION = "prototype-browser-preflight-v1"
DESIGN_EVIDENCE_SCHEMA_VERSION = "prototype-design-evidence-v1"


def write_png(path: Path, width: int = 1280, height: int = 720) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + (b"\xff\xff\xff\xff" * width)
    image = b"\x89PNG\r\n\x1a\n"
    image += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    image += chunk(b"IDAT", zlib.compress(row * height))
    image += chunk(b"IEND", b"")
    path.write_bytes(image)


def prototype_contract() -> dict:
    return {
        "contract_version": "v1",
        "surfaces": [
            {
                "surface_id": "course-catalog",
                "state_id": "catalog-ready",
                "required_viewports": ["desktop", "mobile"],
                "critical_regions": [
                    {"region_id": "global-shell"},
                    {"region_id": "catalog-navigation"},
                    {"region_id": "course-grid"},
                ],
            }
        ],
    }


def semantic_prototype_contract() -> dict:
    contract = prototype_contract()
    contract["prototype_screenshot_paths"] = [
        ".product-delivery/artifacts/prototype-design/catalog-desktop.png"
    ]
    surface = contract["surfaces"][0]
    surface["route"] = "/customer/course-catalog"
    for index, (region, role, accessible_name) in enumerate(zip(
        surface["critical_regions"],
        ("banner", "navigation", "main"),
        ("Course catalog shell", "Catalog navigation", "Course grid"),
    ), start=1):
        region["semantic_role"] = role
        region["accessible_name_match"] = {
            "mode": "exact",
            "value": accessible_name,
        }
        region["visibility"] = "visible"
        region["display_order"] = index
    surface["critical_relationships"] = [
        {
            "source_region_id": "catalog-navigation",
            "relation": "precedes",
            "target_region_id": "course-grid",
        }
    ]
    surface["critical_interactions"] = [
        {
            "interaction_id": "open-course",
            "entry_region_id": "course-grid",
            "action": "open the selected course",
            "expected_relation": "navigates_to",
            "target_region_id": "course-grid",
        }
    ]
    canonical = {
        "contract_version": contract["contract_version"],
        "surfaces": contract["surfaces"],
        "prototype_screenshot_paths": contract["prototype_screenshot_paths"],
    }
    contract["contract_sha256"] = stable_json_hash(canonical)
    return contract


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def semantic_state(
    viewport: str,
    *,
    width: int,
    height: int,
) -> dict:
    return {
        "surface_id": "course-catalog",
        "state_id": "catalog-ready",
        "viewport": viewport,
        "regions": [
            {
                "region_id": "global-shell",
                "semantic_role": "banner",
                "accessible_name": "Course catalog shell",
                "visibility": "visible",
                "display_order": 1,
                "bounds": {"x": 0, "y": 0, "width": width, "height": 72},
                "controls": ["account-menu"],
                "interaction_state": "ready",
            },
            {
                "region_id": "catalog-navigation",
                "semantic_role": "navigation",
                "accessible_name": "Catalog navigation",
                "visibility": "visible",
                "display_order": 2,
                "bounds": {"x": 0, "y": 72, "width": width, "height": 56},
                "controls": ["catalog-filter"],
                "interaction_state": "ready",
            },
            {
                "region_id": "course-grid",
                "semantic_role": "main",
                "accessible_name": "Course grid",
                "visibility": "visible",
                "display_order": 3,
                "bounds": {
                    "x": 0,
                    "y": 128,
                    "width": width,
                    "height": height - 128,
                },
                "controls": ["open-course"],
                "interaction_state": "catalog-ready",
            },
        ],
    }


def semantic_snapshot() -> dict:
    return {
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        "states": [
            semantic_state("desktop", width=1280, height=720),
            semantic_state("mobile", width=390, height=844),
        ],
    }


def design_evidence(
    ui_change_type: str,
    dimension: str,
) -> dict:
    context_mapping: dict = {}
    if ui_change_type == "incremental_existing_surface":
        if dimension == "global_shell":
            context_mapping["baseline_shell_region_ids"] = ["global-shell"]
        elif dimension == "navigation":
            context_mapping.update(
                {
                    "ordinary_entry_path": "course operations -> course catalog",
                    "navigation_mapping": "Retains the existing catalog navigation slot.",
                }
            )
        elif dimension == "information_density":
            context_mapping["density_inheritance_mapping"] = (
                "Retains the baseline compact catalog density."
            )
        elif dimension == "component_system":
            context_mapping["component_inheritance_mapping"] = (
                "Reuses the existing catalog cards and controls."
            )
    elif ui_change_type == "new_surface_in_existing_product":
        if dimension == "global_shell":
            context_mapping["existing_shell_region_ids"] = ["global-shell"]
        elif dimension == "navigation":
            context_mapping.update(
                {
                    "ordinary_entry_path": "course operations -> new catalog surface",
                    "navigation_integration": "Adds one destination to existing navigation.",
                }
            )
        elif dimension == "component_system":
            context_mapping["design_system_integration"] = (
                "Uses the existing product token and component contracts."
            )
    elif ui_change_type == "greenfield_ui" and dimension == "component_system":
        context_mapping["cross_page_state_consistency"] = [
            {
                "surface_id": "course-catalog",
                "state_id": "catalog-ready",
                "token_set_sha256": "a" * 64,
            },
            {
                "surface_id": "course-detail",
                "state_id": "detail-ready",
                "token_set_sha256": "a" * 64,
            },
        ]
    return {
        "schema_version": DESIGN_EVIDENCE_SCHEMA_VERSION,
        "evidence_id": f"{ui_change_type}-{dimension}",
        "ui_change_type": ui_change_type,
        "surface_id": "course-catalog",
        "state_id": "catalog-ready",
        "dimension": dimension,
        "region_ids": ["global-shell", "catalog-navigation", "course-grid"],
        "claims": [f"Deterministic {dimension} evidence is present."],
        "style_probes": [
            {
                "probe": {
                    "global_shell": "layout_structure",
                    "navigation": "entry_path",
                    "visual_language": "color_tokens",
                    "information_density": "density_scale",
                    "component_system": "component_variant",
                    "responsive_behavior": "breakpoint_behavior",
                }[dimension],
                "expected": f"{dimension}-contract-v1",
                "observed": f"{dimension}-contract-v1",
            }
        ],
        "context_mapping": context_mapping,
    }


def write_design_evidence(root: Path, ui_change_type: str) -> dict[str, dict]:
    refs = {}
    for dimension in PRODUCT_CONTEXT_DIMENSIONS:
        path = (
            root
            / ".product-delivery/artifacts/prototype-design/evidence"
            / f"{ui_change_type}-{dimension}.json"
        )
        write_json(path, design_evidence(ui_change_type, dimension))
        refs[dimension] = {
            "artifact_path": str(path.relative_to(root)),
            "artifact_sha256": sha256_file(path),
        }
    return refs


def prepare_project(root: Path) -> None:
    prototype = root / "docs/prototypes/course-catalog.html"
    prototype.parent.mkdir(parents=True, exist_ok=True)
    prototype.write_text(
        """<html><body><header id="global-shell">Catalog</header>
<nav id="catalog-navigation">Browse</nav>
<main id="course-grid"><button>Open course</button></main></body></html>""",
        encoding="utf-8",
    )

    snapshot = root / ".product-delivery/artifacts/prototype-design/semantic.json"
    write_json(snapshot, semantic_snapshot())

    write_png(
        root / ".product-delivery/artifacts/prototype-design/catalog-desktop.png",
        1280,
        720,
    )
    write_png(
        root / ".product-delivery/artifacts/prototype-design/catalog-mobile.png",
        390,
        844,
    )
    write_png(
        root / ".product-delivery/artifacts/prototype-design/baseline-catalog.png",
        1280,
        720,
    )

    snapshot_value = semantic_snapshot()
    snapshot_hash = sha256_file(snapshot)
    observations = []
    for state, screenshot_name in zip(
        snapshot_value["states"],
        ("catalog-desktop.png", "catalog-mobile.png"),
    ):
        screenshot = (
            root
            / ".product-delivery/artifacts/prototype-design"
            / screenshot_name
        )
        observations.append(
            {
                "surface_id": state["surface_id"],
                "state_id": state["state_id"],
                "viewport": state["viewport"],
                "semantic_state_sha256": stable_json_hash(state),
                "clean_screenshot_path": str(screenshot.relative_to(root)),
                "clean_screenshot_sha256": sha256_file(screenshot),
                "observed_region_ids": [
                    region["region_id"] for region in state["regions"]
                ],
                "document_ready": True,
                "console_errors": [],
                "network_errors": [],
                "annotation_nodes_present": False,
                "review_assets_loaded": False,
                "review_mode_available": False,
            }
        )
    write_json(
        root / ".product-delivery/artifacts/prototype-design/browser-preflight.json",
        {
            "schema_version": PREFLIGHT_SCHEMA_VERSION,
            "prototype_path": "docs/prototypes/course-catalog.html",
            "semantic_snapshot_sha256": snapshot_hash,
            "observations": observations,
        },
    )

    review = root / ".product-delivery/artifacts/review-only/catalog-review.html"
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_text(
        """<html><body><a data-annotation-id="review-navigation-density"
data-clean-region-id="catalog-navigation"
data-clean-surface-reference="docs/prototypes/course-catalog.html"
href="docs/prototypes/course-catalog.html#catalog-navigation">Review navigation</a>
</body></html>""",
        encoding="utf-8",
    )

    design_system = root / "docs/design-system.json"
    write_json(
        design_system,
        {
            "schema_version": "prototype-design-system-v1",
            "name": "Waygate UI",
            "token_sets": ["color", "type", "spacing", "components"],
        },
    )


def valid_payload(
    root: Path,
    *,
    ui_change_type: str = "incremental_existing_surface",
) -> dict:
    region_ids = ["global-shell", "catalog-navigation", "course-grid"]
    evidence_refs = write_design_evidence(root, ui_change_type)
    product_context = {
        "coverage_rows": [
            {
                "surface_id": "course-catalog",
                "state_id": "catalog-ready",
                "dimension": dimension,
                "status": "passed",
                "evidence_refs": [evidence_refs[dimension]],
                "covered_region_ids": region_ids,
            }
            for dimension in PRODUCT_CONTEXT_DIMENSIONS
        ],
    }
    if ui_change_type == "greenfield_ui":
        product_context["design_system_artifact_path"] = "docs/design-system.json"
    else:
        product_context["baseline_identity"] = {
            "canonical_baseline_id": "baseline-v1.0.22",
            "baseline_feature_slug": "course-catalog",
            "baseline_surface_paths": ["/customer/course-catalog"],
            "baseline_snapshot_paths": [
                ".product-delivery/artifacts/prototype-design/baseline-catalog.png"
            ],
        }
        if ui_change_type == "new_surface_in_existing_product":
            product_context.update(
                {
                    "design_system_artifact_path": "docs/design-system.json",
                    "new_surface_justification": {
                        "reason": "A distinct catalog workflow is required.",
                        "why_existing_surface_insufficient": (
                            "The existing surface cannot represent catalog lifecycle states."
                        ),
                        "navigation_impact": (
                            "Adds one destination to the existing course operations navigation."
                        ),
                    },
                }
            )
    return {
        "bundle_version": "v1",
        "ui_change_type": ui_change_type,
        "clean_surface": {
            "prototype_path": "docs/prototypes/course-catalog.html",
            "semantic_snapshot_path": (
                ".product-delivery/artifacts/prototype-design/semantic.json"
            ),
            "browser_preflight_probe_path": (
                ".product-delivery/artifacts/prototype-design/browser-preflight.json"
            ),
            "runtime_checks": [
                {
                    "surface_id": "course-catalog",
                    "state_id": "catalog-ready",
                    "viewport": "desktop",
                    "status": "passed",
                    "clean_screenshot_path": (
                        ".product-delivery/artifacts/prototype-design/catalog-desktop.png"
                    ),
                    "observed_region_ids": region_ids,
                    "annotation_nodes_present": False,
                    "review_assets_loaded": False,
                    "review_mode_available": False,
                },
                {
                    "surface_id": "course-catalog",
                    "state_id": "catalog-ready",
                    "viewport": "mobile",
                    "status": "passed",
                    "clean_screenshot_path": (
                        ".product-delivery/artifacts/prototype-design/catalog-mobile.png"
                    ),
                    "observed_region_ids": region_ids,
                    "annotation_nodes_present": False,
                    "review_assets_loaded": False,
                    "review_mode_available": False,
                },
            ],
        },
        "product_context_contract": product_context,
        "intended_product_ui_callouts": [
            {
                "callout_id": "catalog-empty-state",
                "requirement_ids": ["FR-023"],
                "scenario_ids": ["SCN-023"],
                "actor_roles": ["catalog-manager"],
                "trigger": "the catalog has no courses",
                "lifecycle": "shown after the empty response resolves",
                "dismissal_or_persistence": "persists until a course is added",
                "state_id": "catalog-ready",
                "region_id": "course-grid",
            }
        ],
        "review_annotation_set": {
            "artifact_path": (
                ".product-delivery/artifacts/review-only/catalog-review.html"
            ),
            "clean_surface_reference": "docs/prototypes/course-catalog.html",
            "annotations": [
                {
                    "annotation_id": "review-navigation-density",
                    "target_region_id": "catalog-navigation",
                    "text": "Confirm the inherited navigation density.",
                }
            ],
        },
    }


def mutate_design_evidence(
    root: Path,
    payload: dict,
    dimension: str,
    mutate,
) -> None:
    row = next(
        item
        for item in payload["product_context_contract"]["coverage_rows"]
        if item["dimension"] == dimension
    )
    ref = row["evidence_refs"][0]
    path = root / ref["artifact_path"]
    artifact = json.loads(path.read_text(encoding="utf-8"))
    mutate(artifact)
    write_json(path, artifact)
    ref["artifact_sha256"] = sha256_file(path)


class PrototypeDesignIntegrityV1023Tests(unittest.TestCase):
    def test_complete_prototype_contract_identity_is_bound_to_product_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            contract = semantic_prototype_contract()
            base = build_prototype_design_bundle(
                root,
                valid_payload(root),
                prototype_contract=contract,
            )

            mutations = {
                "route": lambda value: value["surfaces"][0].__setitem__(
                    "route", "/customer/changed-catalog"
                ),
                "semantic_role": lambda value: value["surfaces"][0][
                    "critical_regions"
                ][2].__setitem__("semantic_role", "complementary"),
                "relationship": lambda value: value["surfaces"][0][
                    "critical_relationships"
                ][0].__setitem__("relation", "adjacent_to"),
                "interaction": lambda value: value["surfaces"][0][
                    "critical_interactions"
                ][0].__setitem__("action", "preview the selected course"),
            }
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    prepare_project(root)
                    payload = valid_payload(root)
                    changed_contract = copy.deepcopy(contract)
                    mutate(changed_contract)
                    if name == "semantic_role":
                        snapshot_path = root / payload["clean_surface"][
                            "semantic_snapshot_path"
                        ]
                        snapshot = json.loads(
                            snapshot_path.read_text(encoding="utf-8")
                        )
                        for state in snapshot["states"]:
                            state["regions"][2]["semantic_role"] = "complementary"
                        write_json(snapshot_path, snapshot)
                        probe_path = root / payload["clean_surface"][
                            "browser_preflight_probe_path"
                        ]
                        probe = json.loads(probe_path.read_text(encoding="utf-8"))
                        probe["semantic_snapshot_sha256"] = sha256_file(snapshot_path)
                        states_by_key = {
                            (
                                state["surface_id"],
                                state["state_id"],
                                state["viewport"],
                            ): state
                            for state in snapshot["states"]
                        }
                        for observation in probe["observations"]:
                            key = (
                                observation["surface_id"],
                                observation["state_id"],
                                observation["viewport"],
                            )
                            observation["semantic_state_sha256"] = stable_json_hash(
                                states_by_key[key]
                            )
                        write_json(probe_path, probe)
                    changed = build_prototype_design_bundle(
                        root,
                        payload,
                        prototype_contract=changed_contract,
                    )

                    self.assertNotEqual(
                        base["product_domain_sha256"],
                        changed["product_domain_sha256"],
                    )
                    self.assertNotEqual(
                        base["bundle_sha256"],
                        changed["bundle_sha256"],
                    )
                    self.assertEqual(
                        changed["prototype_contract_identity"]["contract_sha256"],
                        contract["contract_sha256"],
                    )
                    self.assertNotEqual(
                        changed["prototype_contract_identity"][
                            "runtime_computed_contract_sha256"
                        ],
                        contract["contract_sha256"],
                    )
                    self.assertFalse(
                        changed["prototype_contract_identity"][
                            "contract_sha256_verified"
                        ]
                    )

    def test_builds_canonical_bundle_with_runtime_artifacts_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            payload = valid_payload(root)
            original = copy.deepcopy(payload)

            result = build_prototype_design_bundle(
                root,
                payload,
                prototype_contract=prototype_contract(),
            )

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["normalized_payload"], original)
            self.assertEqual(payload, original)
            self.assertRegex(result["product_domain_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(result["review_domain_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(result["bundle_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(
                result["artifact_metadata"]["clean_prototype"]["sha256"],
                r"^[0-9a-f]{64}$",
            )
            self.assertRegex(
                result["artifact_metadata"]["semantic_snapshot"]["sha256"],
                r"^[0-9a-f]{64}$",
            )
            self.assertRegex(
                result["artifact_metadata"]["browser_preflight_probe"]["sha256"],
                r"^[0-9a-f]{64}$",
            )
            self.assertEqual(
                len(result["artifact_metadata"]["design_evidence_artifacts"]),
                6,
            )
            screenshots = result["artifact_metadata"]["clean_screenshots"]
            self.assertEqual([item["viewport"] for item in screenshots], ["desktop", "mobile"])
            self.assertEqual(screenshots[0]["artifact"]["width"], 1280)
            matrix = result["required_coverage_matrix"]
            self.assertEqual(len(matrix["runtime_checks"]), 2)
            self.assertEqual(len(matrix["product_context"]), 6)
            self.assertEqual(result["design_audit"]["status"], "passed")
            self.assertEqual(result["design_audit"]["accepted_exemption_count"], 0)
            self.assertTrue(
                all(result["design_audit"]["deterministic_checks"].values())
            )

            rebuilt = build_prototype_design_bundle(
                root,
                copy.deepcopy(payload),
                prototype_contract=copy.deepcopy(prototype_contract()),
            )
            self.assertEqual(rebuilt, result)

    def test_returned_output_views_do_not_share_mutable_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)

            with self.subTest(direction="top-level-to-normalized"):
                result = build_prototype_design_bundle(
                    root,
                    valid_payload(root),
                    prototype_contract=prototype_contract(),
                )
                result["clean_surface"]["runtime_checks"][0][
                    "observed_region_ids"
                ].append("top-level-mutation")
                self.assertNotIn(
                    "top-level-mutation",
                    result["normalized_payload"]["clean_surface"][
                        "runtime_checks"
                    ][0]["observed_region_ids"],
                )

            with self.subTest(direction="normalized-to-top-level"):
                result = build_prototype_design_bundle(
                    root,
                    valid_payload(root),
                    prototype_contract=prototype_contract(),
                )
                result["normalized_payload"]["product_context_contract"][
                    "coverage_rows"
                ][0]["evidence_refs"].append("normalized-mutation")
                self.assertNotIn(
                    "normalized-mutation",
                    result["product_context_contract"]["coverage_rows"][0][
                        "evidence_refs"
                    ],
                )

            with self.subTest(direction="matrix-to-normalized"):
                result = build_prototype_design_bundle(
                    root,
                    valid_payload(root),
                    prototype_contract=prototype_contract(),
                )
                result["required_coverage_matrix"]["runtime_checks"][0][
                    "observed_region_ids"
                ].append("matrix-mutation")
                self.assertNotIn(
                    "matrix-mutation",
                    result["normalized_payload"]["clean_surface"][
                        "runtime_checks"
                    ][0]["observed_region_ids"],
                )

    def test_annotation_changes_only_change_review_and_bundle_domains(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            first_payload = valid_payload(root)
            second_payload = copy.deepcopy(first_payload)
            second_payload["review_annotation_set"]["annotations"][0]["text"] = (
                "Use the compact inherited navigation spacing."
            )

            first = build_prototype_design_bundle(
                root,
                first_payload,
                prototype_contract=prototype_contract(),
            )
            second = build_prototype_design_bundle(
                root,
                second_payload,
                prototype_contract=prototype_contract(),
            )

            self.assertEqual(
                first["product_domain_sha256"], second["product_domain_sha256"]
            )
            self.assertNotEqual(
                first["review_domain_sha256"], second["review_domain_sha256"]
            )
            self.assertNotEqual(first["bundle_sha256"], second["bundle_sha256"])

    def test_rejects_invalid_bundle_version_and_ui_change_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)

            for field, value, message in (
                ("bundle_version", "v2", "bundle_version"),
                ("ui_change_type", "non_ui", "ui_change_type"),
            ):
                with self.subTest(field=field):
                    payload = valid_payload(root)
                    payload[field] = value
                    with self.assertRaisesRegex(PrototypeDesignError, message):
                        build_prototype_design_bundle(
                            root,
                            payload,
                            prototype_contract=prototype_contract(),
                        )

    def test_semantic_snapshot_requires_fixed_complete_region_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            snapshot_path = (
                root / ".product-delivery/artifacts/prototype-design/semantic.json"
            )

            invalid_snapshots = {
                "empty": ({}, "schema_version"),
                "unexpected_field": (
                    {**semantic_snapshot(), "status": "passed"},
                    "unexpected fields",
                ),
                "missing_viewport": (
                    {
                        "schema_version": SEMANTIC_SCHEMA_VERSION,
                        "states": semantic_snapshot()["states"][:1],
                    },
                    "coverage",
                ),
                "empty_regions": (
                    {
                        "schema_version": SEMANTIC_SCHEMA_VERSION,
                        "states": [
                            {
                                **semantic_snapshot()["states"][0],
                                "regions": [],
                            },
                            semantic_snapshot()["states"][1],
                        ],
                    },
                    "regions",
                ),
            }
            for name, (snapshot, message) in invalid_snapshots.items():
                with self.subTest(name=name):
                    write_json(snapshot_path, snapshot)
                    with self.assertRaisesRegex(PrototypeDesignError, message):
                        build_prototype_design_bundle(
                            root,
                            valid_payload(root),
                            prototype_contract=prototype_contract(),
                        )

            required_region_fields = (
                "semantic_role",
                "accessible_name",
                "visibility",
                "display_order",
                "bounds",
                "controls",
                "interaction_state",
            )
            for field_name in required_region_fields:
                with self.subTest(missing_region_field=field_name):
                    snapshot = semantic_snapshot()
                    snapshot["states"][0]["regions"][0].pop(field_name)
                    write_json(snapshot_path, snapshot)
                    with self.assertRaisesRegex(
                        PrototypeDesignError,
                        field_name,
                    ):
                        build_prototype_design_bundle(
                            root,
                            valid_payload(root),
                            prototype_contract=prototype_contract(),
                        )

            invalid_bounds = semantic_snapshot()
            invalid_bounds["states"][0]["regions"][0]["bounds"]["width"] = 0
            write_json(snapshot_path, invalid_bounds)
            with self.assertRaisesRegex(PrototypeDesignError, "bounds"):
                build_prototype_design_bundle(
                    root,
                    valid_payload(root),
                    prototype_contract=prototype_contract(),
                )

    def test_semantic_snapshot_matches_frozen_region_contract(self):
        mutations = {
            "semantic_role": lambda regions: regions[2].__setitem__(
                "semantic_role", "complementary"
            ),
            "accessible_name": lambda regions: regions[2].__setitem__(
                "accessible_name", "Different surface"
            ),
            "visibility": lambda regions: regions[0].__setitem__(
                "visibility", "hidden"
            ),
            "relationship_order": lambda regions: (
                regions[1].__setitem__("display_order", 3),
                regions[2].__setitem__("display_order", 2),
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    prepare_project(root)
                    payload = valid_payload(root)
                    snapshot_path = root / payload["clean_surface"][
                        "semantic_snapshot_path"
                    ]
                    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                    mutate(snapshot["states"][0]["regions"])
                    write_json(snapshot_path, snapshot)

                    with self.assertRaisesRegex(
                        PrototypeDesignError,
                        "prototype contract|accessible name|visibility|relationship",
                    ):
                        build_prototype_design_bundle(
                            root,
                            payload,
                            prototype_contract=semantic_prototype_contract(),
                        )

    def test_browser_preflight_is_artifact_bound_and_payload_flags_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            payload = valid_payload(root)
            probe_path = root / payload["clean_surface"][
                "browser_preflight_probe_path"
            ]

            missing_probe = copy.deepcopy(payload)
            missing_probe["clean_surface"].pop("browser_preflight_probe_path")
            with self.assertRaisesRegex(PrototypeDesignError, "preflight probe"):
                build_prototype_design_bundle(
                    root,
                    missing_probe,
                    prototype_contract=prototype_contract(),
                )

            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            probe["observations"][0]["document_ready"] = False
            write_json(probe_path, probe)
            payload["clean_surface"]["runtime_checks"][0]["status"] = "passed"
            payload["clean_surface"]["runtime_checks"][0][
                "annotation_nodes_present"
            ] = False
            with self.assertRaisesRegex(PrototypeDesignError, "document_ready"):
                build_prototype_design_bundle(
                    root,
                    payload,
                    prototype_contract=prototype_contract(),
                )

            prepare_project(root)
            payload = valid_payload(root)
            probe_path = root / payload["clean_surface"][
                "browser_preflight_probe_path"
            ]
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            probe["observations"].pop()
            write_json(probe_path, probe)
            with self.assertRaisesRegex(PrototypeDesignError, "coverage"):
                build_prototype_design_bundle(
                    root,
                    payload,
                    prototype_contract=prototype_contract(),
                )

            prepare_project(root)
            payload = valid_payload(root)
            probe_path = root / payload["clean_surface"][
                "browser_preflight_probe_path"
            ]
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            probe["observations"][0]["semantic_state_sha256"] = "0" * 64
            write_json(probe_path, probe)
            with self.assertRaisesRegex(PrototypeDesignError, "semantic snapshot identity"):
                build_prototype_design_bundle(
                    root,
                    payload,
                    prototype_contract=prototype_contract(),
                )

            prepare_project(root)
            payload = valid_payload(root)
            probe_path = root / payload["clean_surface"][
                "browser_preflight_probe_path"
            ]
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            probe["observations"][0]["status"] = "passed"
            write_json(probe_path, probe)
            with self.assertRaisesRegex(PrototypeDesignError, "unexpected fields"):
                build_prototype_design_bundle(
                    root,
                    payload,
                    prototype_contract=prototype_contract(),
                )

    def test_clean_html_rejects_overlay_import_and_query_mode_markers(self):
        contaminated_html = {
            "overlay": '<div id="prototype-annotation-overlay">review</div>',
            "review_import": (
                '<iframe src="../../.product-delivery/artifacts/review-only/'
                'catalog-review.html"></iframe>'
            ),
            "query_mode": '<script src="catalog.js?mode=prototype_review"></script>',
        }
        for name, marker in contaminated_html.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    prepare_project(root)
                    prototype = root / "docs/prototypes/course-catalog.html"
                    prototype.write_text(
                        f"<html><body>{marker}</body></html>",
                        encoding="utf-8",
                    )
                    payload = valid_payload(root)
                    for check in payload["clean_surface"]["runtime_checks"]:
                        check["annotation_nodes_present"] = False
                        check["review_assets_loaded"] = False
                        check["review_mode_available"] = False

                    with self.assertRaisesRegex(
                        PrototypeDesignError,
                        "clean prototype.*review|forbidden",
                    ):
                        build_prototype_design_bundle(
                            root,
                            payload,
                            prototype_contract=prototype_contract(),
                        )

    def test_clean_html_allows_product_content_review_features(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            prototype = root / "docs/prototypes/course-catalog.html"
            prototype.write_text(
                """<html><body><main id="course-grid" data-review-status="ready">
<a href="?mode=review">Open content review mode</a></main></body></html>""",
                encoding="utf-8",
            )

            result = build_prototype_design_bundle(
                root,
                valid_payload(root),
                prototype_contract=prototype_contract(),
            )

            self.assertEqual(result["status"], "ready")

    def test_review_artifact_requires_external_clean_region_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            review_path = (
                root / ".product-delivery/artifacts/review-only/catalog-review.html"
            )

            review_path.write_text(
                "<html><body>annotation text only</body></html>",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PrototypeDesignError, "external anchor"):
                build_prototype_design_bundle(
                    root,
                    valid_payload(root),
                    prototype_contract=prototype_contract(),
                )

            review_path.write_text(
                """<html><body><a data-annotation-id="review-navigation-density"
data-clean-region-id="unknown-region"
data-clean-surface-reference="docs/prototypes/course-catalog.html"
href="docs/prototypes/course-catalog.html#unknown-region">Review</a></body></html>""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PrototypeDesignError, "clean region"):
                build_prototype_design_bundle(
                    root,
                    valid_payload(root),
                    prototype_contract=prototype_contract(),
                )

    def test_design_dimension_refs_are_structured_hashed_and_mode_specific(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)

            arbitrary = valid_payload(root)
            arbitrary["product_context_contract"]["coverage_rows"][0][
                "evidence_refs"
            ] = ["evidence:global_shell"]
            with self.assertRaisesRegex(PrototypeDesignError, "structured evidence"):
                build_prototype_design_bundle(
                    root,
                    arbitrary,
                    prototype_contract=prototype_contract(),
                )

            wrong_hash = valid_payload(root)
            wrong_hash["product_context_contract"]["coverage_rows"][0][
                "evidence_refs"
            ][0]["artifact_sha256"] = "0" * 64
            with self.assertRaisesRegex(PrototypeDesignError, "artifact_sha256"):
                build_prototype_design_bundle(
                    root,
                    wrong_hash,
                    prototype_contract=prototype_contract(),
                )

            malformed = valid_payload(root)
            ref = malformed["product_context_contract"]["coverage_rows"][0][
                "evidence_refs"
            ][0]
            evidence_path = root / ref["artifact_path"]
            write_json(evidence_path, {})
            ref["artifact_sha256"] = sha256_file(evidence_path)
            with self.assertRaisesRegex(PrototypeDesignError, "schema_version"):
                build_prototype_design_bundle(
                    root,
                    malformed,
                    prototype_contract=prototype_contract(),
                )

            unexpected_evidence = valid_payload(root)
            mutate_design_evidence(
                root,
                unexpected_evidence,
                "global_shell",
                lambda artifact: artifact.__setitem__("status", "passed"),
            )
            with self.assertRaisesRegex(PrototypeDesignError, "unexpected fields"):
                build_prototype_design_bundle(
                    root,
                    unexpected_evidence,
                    prototype_contract=prototype_contract(),
                )

            style_mismatch = valid_payload(root)
            mutate_design_evidence(
                root,
                style_mismatch,
                "visual_language",
                lambda artifact: artifact["style_probes"][0].__setitem__(
                    "observed", "different-token-contract"
                ),
            )
            with self.assertRaisesRegex(PrototypeDesignError, "style probe"):
                build_prototype_design_bundle(
                    root,
                    style_mismatch,
                    prototype_contract=prototype_contract(),
                )

            incremental_requirements = (
                ("global_shell", "baseline_shell_region_ids"),
                ("navigation", "ordinary_entry_path"),
                ("navigation", "navigation_mapping"),
                ("information_density", "density_inheritance_mapping"),
                ("component_system", "component_inheritance_mapping"),
            )
            for dimension, field_name in incremental_requirements:
                with self.subTest(
                    ui_change_type="incremental_existing_surface",
                    field_name=field_name,
                ):
                    incremental = valid_payload(root)
                    mutate_design_evidence(
                        root,
                        incremental,
                        dimension,
                        lambda artifact, field_name=field_name: artifact[
                            "context_mapping"
                        ].pop(field_name),
                    )
                    with self.assertRaisesRegex(
                        PrototypeDesignError,
                        field_name,
                    ):
                        build_prototype_design_bundle(
                            root,
                            incremental,
                            prototype_contract=prototype_contract(),
                        )

            new_surface = valid_payload(
                root,
                ui_change_type="new_surface_in_existing_product",
            )
            new_surface["product_context_contract"].pop(
                "new_surface_justification"
            )
            with self.assertRaisesRegex(PrototypeDesignError, "new_surface_justification"):
                build_prototype_design_bundle(
                    root,
                    new_surface,
                    prototype_contract=prototype_contract(),
                )

            new_surface_requirements = (
                ("global_shell", "existing_shell_region_ids"),
                ("navigation", "ordinary_entry_path"),
                ("navigation", "navigation_integration"),
                ("component_system", "design_system_integration"),
            )
            for dimension, field_name in new_surface_requirements:
                with self.subTest(
                    ui_change_type="new_surface_in_existing_product",
                    field_name=field_name,
                ):
                    new_surface = valid_payload(
                        root,
                        ui_change_type="new_surface_in_existing_product",
                    )
                    mutate_design_evidence(
                        root,
                        new_surface,
                        dimension,
                        lambda artifact, field_name=field_name: artifact[
                            "context_mapping"
                        ].pop(field_name),
                    )
                    with self.assertRaisesRegex(
                        PrototypeDesignError,
                        field_name,
                    ):
                        build_prototype_design_bundle(
                            root,
                            new_surface,
                            prototype_contract=prototype_contract(),
                        )

            greenfield = valid_payload(root, ui_change_type="greenfield_ui")
            mutate_design_evidence(
                root,
                greenfield,
                "component_system",
                lambda artifact: artifact["context_mapping"][
                    "cross_page_state_consistency"
                ].pop(),
            )
            with self.assertRaisesRegex(PrototypeDesignError, "cross-page/state"):
                build_prototype_design_bundle(
                    root,
                    greenfield,
                    prototype_contract=prototype_contract(),
                )

    def test_rejects_incomplete_or_non_clean_runtime_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)

            missing = valid_payload(root)
            missing["clean_surface"]["runtime_checks"].pop()
            with self.assertRaisesRegex(PrototypeDesignError, "missing runtime coverage"):
                build_prototype_design_bundle(
                    root,
                    missing,
                    prototype_contract=prototype_contract(),
                )

            unexpected = valid_payload(root)
            unexpected["clean_surface"]["runtime_checks"][0]["viewport"] = "tablet"
            with self.assertRaisesRegex(PrototypeDesignError, "not in prototype contract"):
                build_prototype_design_bundle(
                    root,
                    unexpected,
                    prototype_contract=prototype_contract(),
                )

            annotated = valid_payload(root)
            probe_path = (
                root
                / annotated["clean_surface"]["browser_preflight_probe_path"]
            )
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            probe["observations"][0]["annotation_nodes_present"] = True
            write_json(probe_path, probe)
            with self.assertRaisesRegex(PrototypeDesignError, "annotation_nodes_present"):
                build_prototype_design_bundle(
                    root,
                    annotated,
                    prototype_contract=prototype_contract(),
                )

            invalid_png = root / ".product-delivery/artifacts/prototype-design/fake.png"
            invalid_png.write_bytes(b"not a png")
            invalid = valid_payload(root)
            invalid["clean_surface"]["runtime_checks"][0][
                "clean_screenshot_path"
            ] = str(invalid_png.relative_to(root))
            with self.assertRaisesRegex(PrototypeDesignError, "valid PNG"):
                build_prototype_design_bundle(
                    root,
                    invalid,
                    prototype_contract=prototype_contract(),
                )

    def test_runtime_payload_cannot_invent_noncritical_observed_regions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            payload = valid_payload(root)
            payload["clean_surface"]["runtime_checks"][0][
                "observed_region_ids"
            ] = [
                *payload["clean_surface"]["runtime_checks"][0][
                    "observed_region_ids"
                ],
                "noncritical-footer",
            ]

            result = build_prototype_design_bundle(
                root,
                payload,
                prototype_contract=prototype_contract(),
            )

            observed = result["clean_surface"]["runtime_checks"][0][
                "observed_region_ids"
            ]
            self.assertNotIn("noncritical-footer", observed)
            self.assertEqual(
                result["required_coverage_matrix"]["runtime_checks"][0][
                    "required_region_ids"
                ],
                ["global-shell", "catalog-navigation", "course-grid"],
            )

    def test_requires_complete_product_context_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)

            missing = valid_payload(root)
            missing["product_context_contract"]["coverage_rows"].pop()
            with self.assertRaisesRegex(PrototypeDesignError, "missing product context coverage"):
                build_prototype_design_bundle(
                    root,
                    missing,
                    prototype_contract=prototype_contract(),
                )

            unknown_region = valid_payload(root)
            unknown_region["product_context_contract"]["coverage_rows"][0][
                "covered_region_ids"
            ] = ["not-in-contract"]
            with self.assertRaisesRegex(PrototypeDesignError, "unknown contract region"):
                build_prototype_design_bundle(
                    root,
                    unknown_region,
                    prototype_contract=prototype_contract(),
                )

    def test_accepts_only_complete_accepted_context_exemptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)
            payload = valid_payload(root)
            replacement_refs = copy.deepcopy(
                payload["product_context_contract"]["coverage_rows"][0][
                    "evidence_refs"
                ]
            )
            payload["product_context_contract"]["coverage_rows"][0] = {
                "surface_id": "course-catalog",
                "state_id": "catalog-ready",
                "dimension": "global_shell",
                "status": "exempted",
                "exception": {
                    "requirement_ids": ["FR-023"],
                    "scenario_ids": ["SCN-023"],
                    "rationale": "The host shell is rendered by the existing product frame.",
                    "replacement_evidence_refs": replacement_refs,
                    "review_disposition": "accepted",
                },
            }

            result = build_prototype_design_bundle(
                root,
                payload,
                prototype_contract=prototype_contract(),
            )
            self.assertEqual(result["design_audit"]["accepted_exemption_count"], 1)

            payload["product_context_contract"]["coverage_rows"][0]["exception"][
                "review_disposition"
            ] = "pending"
            with self.assertRaisesRegex(PrototypeDesignError, "review_disposition"):
                build_prototype_design_bundle(
                    root,
                    payload,
                    prototype_contract=prototype_contract(),
                )

    def test_enforces_mode_specific_baseline_or_design_system_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)

            incremental = valid_payload(root)
            del incremental["product_context_contract"]["baseline_identity"]
            with self.assertRaisesRegex(PrototypeDesignError, "baseline_identity"):
                build_prototype_design_bundle(
                    root,
                    incremental,
                    prototype_contract=prototype_contract(),
                )

            new_surface = valid_payload(
                root,
                ui_change_type="new_surface_in_existing_product",
            )
            new_surface_result = build_prototype_design_bundle(
                root,
                new_surface,
                prototype_contract=prototype_contract(),
            )
            self.assertEqual(
                new_surface_result["ui_change_type"],
                "new_surface_in_existing_product",
            )
            missing_new_surface_design_system = valid_payload(
                root,
                ui_change_type="new_surface_in_existing_product",
            )
            missing_new_surface_design_system["product_context_contract"].pop(
                "design_system_artifact_path"
            )
            with self.assertRaisesRegex(
                PrototypeDesignError,
                "design_system_artifact_path",
            ):
                build_prototype_design_bundle(
                    root,
                    missing_new_surface_design_system,
                    prototype_contract=prototype_contract(),
                )

            greenfield = valid_payload(root, ui_change_type="greenfield_ui")

            result = build_prototype_design_bundle(
                root,
                greenfield,
                prototype_contract=prototype_contract(),
            )
            self.assertEqual(
                result["artifact_metadata"]["design_system_artifact"]["path"],
                "docs/design-system.json",
            )

            greenfield["product_context_contract"]["baseline_identity"] = {
                "canonical_baseline_id": "forbidden",
            }
            with self.assertRaisesRegex(PrototypeDesignError, "instead of baseline_identity"):
                build_prototype_design_bundle(
                    root,
                    greenfield,
                    prototype_contract=prototype_contract(),
                )

    def test_validates_callouts_and_review_only_annotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)

            duplicate_callout = valid_payload(root)
            duplicate_callout["intended_product_ui_callouts"].append(
                copy.deepcopy(duplicate_callout["intended_product_ui_callouts"][0])
            )
            with self.assertRaisesRegex(PrototypeDesignError, "duplicate callout_id"):
                build_prototype_design_bundle(
                    root,
                    duplicate_callout,
                    prototype_contract=prototype_contract(),
                )

            bad_target = valid_payload(root)
            bad_target["review_annotation_set"]["annotations"][0][
                "target_region_id"
            ] = "unknown-region"
            with self.assertRaisesRegex(PrototypeDesignError, "target_region_id"):
                build_prototype_design_bundle(
                    root,
                    bad_target,
                    prototype_contract=prototype_contract(),
                )

            wrong_location = valid_payload(root)
            wrong_location["review_annotation_set"]["artifact_path"] = (
                "docs/prototypes/course-catalog.html"
            )
            with self.assertRaisesRegex(PrototypeDesignError, "review-only"):
                build_prototype_design_bundle(
                    root,
                    wrong_location,
                    prototype_contract=prototype_contract(),
                )

    def test_malformed_artifact_paths_raise_prototype_design_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_project(root)

            def malformed_prototype(payload: dict) -> None:
                payload["clean_surface"]["prototype_path"] = "bad\x00prototype.html"

            def malformed_semantic_snapshot(payload: dict) -> None:
                payload["clean_surface"]["semantic_snapshot_path"] = (
                    ".product-delivery/artifacts/prototype-design/bad\x00semantic.json"
                )

            def malformed_clean_screenshot(payload: dict) -> None:
                payload["clean_surface"]["runtime_checks"][0][
                    "clean_screenshot_path"
                ] = ".product-delivery/artifacts/prototype-design/bad\x00capture.png"

            def malformed_baseline_snapshot(payload: dict) -> None:
                payload["product_context_contract"]["baseline_identity"][
                    "baseline_snapshot_paths"
                ] = [
                    ".product-delivery/artifacts/prototype-design/bad\x00baseline.png"
                ]

            def malformed_design_system(payload: dict) -> None:
                payload["ui_change_type"] = "greenfield_ui"
                del payload["product_context_contract"]["baseline_identity"]
                payload["product_context_contract"][
                    "design_system_artifact_path"
                ] = "docs/bad\x00design-system.json"

            def malformed_review_artifact(payload: dict) -> None:
                payload["review_annotation_set"]["artifact_path"] = (
                    ".product-delivery/artifacts/review-only/bad\x00review.html"
                )

            cases = {
                "prototype": malformed_prototype,
                "semantic_snapshot": malformed_semantic_snapshot,
                "clean_screenshot": malformed_clean_screenshot,
                "baseline_snapshot": malformed_baseline_snapshot,
                "design_system": malformed_design_system,
                "review_artifact": malformed_review_artifact,
            }
            for name, mutate in cases.items():
                with self.subTest(name=name):
                    payload = valid_payload(root)
                    mutate(payload)
                    with self.assertRaises(PrototypeDesignError):
                        build_prototype_design_bundle(
                            root,
                            payload,
                            prototype_contract=prototype_contract(),
                        )


if __name__ == "__main__":
    unittest.main()
