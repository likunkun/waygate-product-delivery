import struct
import json
import os
import zlib
from copy import deepcopy
from pathlib import Path

from product_delivery_agent.evidence_artifacts import sha256_file, stable_json_hash


os.environ.setdefault("CODEX_THREAD_ID", "test-host-goal-thread")


DEFAULT_PROTOTYPE_SCREENSHOT = (
    ".product-delivery/artifacts/prototype/default-desktop.png"
)
PROTOTYPE_DESIGN_DIMENSIONS = (
    "global_shell",
    "navigation",
    "visual_language",
    "information_density",
    "component_system",
    "responsive_behavior",
)
PROTOTYPE_STYLE_PROBES = {
    "global_shell": "layout_structure",
    "navigation": "entry_path",
    "visual_language": "color_tokens",
    "information_density": "density_scale",
    "component_system": "component_variant",
    "responsive_behavior": "breakpoint_behavior",
}


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prototype_contract(
    screenshot_path: str = DEFAULT_PROTOTYPE_SCREENSHOT,
) -> dict:
    return {
        "contract_version": "v1",
        "prototype_screenshot_paths": [screenshot_path],
        "surfaces": [
            {
                "surface_id": "primary-surface",
                "route": "/customer/course-production",
                "state_id": "ready",
                "required_viewports": ["desktop"],
                "critical_regions": [
                    {
                        "region_id": "primary-region",
                        "semantic_role": "main",
                        "accessible_name_match": {
                            "mode": "contains",
                            "value": "primary",
                        },
                        "visibility": "visible",
                    }
                ],
                "critical_relationships": [
                    {
                        "source_region_id": "primary-region",
                        "relation": "contains",
                        "target_region_id": "primary-region",
                    }
                ],
                "critical_interactions": [
                    {
                        "interaction_id": "primary-action",
                        "entry_region_id": "primary-region",
                        "action": "use primary action",
                        "expected_relation": "updates",
                        "target_region_id": "primary-region",
                    }
                ],
            }
        ],
    }


def write_prototype_screenshot(
    project_root: Path,
    screenshot_path: str = DEFAULT_PROTOTYPE_SCREENSHOT,
    *,
    width: int = 1280,
    height: int = 720,
) -> None:
    path = project_root / screenshot_path
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


def prototype_design_bundle_payload(
    project_root: Path,
    *,
    prototype_path: str = "prototype/index.html",
    contract: dict | None = None,
    ui_change_type: str = "incremental_existing_surface",
    include_review_companion: bool = True,
    annotation_text: str = "Confirm the inherited product context.",
) -> dict:
    contract = deepcopy(contract or prototype_contract())
    prototype = project_root / prototype_path
    prototype.parent.mkdir(parents=True, exist_ok=True)
    if not prototype.exists():
        region_id = contract["surfaces"][0]["critical_regions"][0]["region_id"]
        prototype.write_text(
            f'<html><body><main id="{region_id}">Clean prototype</main></body></html>',
            encoding="utf-8",
        )

    for screenshot_path in contract["prototype_screenshot_paths"]:
        if not (project_root / screenshot_path).exists():
            write_prototype_screenshot(project_root, screenshot_path)

    semantic_snapshot_path = (
        ".product-delivery/artifacts/prototype-design/semantic-snapshot.json"
    )
    semantic_snapshot = project_root / semantic_snapshot_path
    semantic_states = []
    runtime_checks = []
    preflight_observations = []
    for surface in contract["surfaces"]:
        region_ids = [
            region["region_id"] for region in surface["critical_regions"]
        ]
        for viewport in surface["required_viewports"]:
            screenshot_path = (
                ".product-delivery/artifacts/prototype-design/"
                f"{surface['surface_id']}-{surface['state_id']}-{viewport}.png"
            )
            width, height = (390, 844) if viewport == "mobile" else (1280, 720)
            write_prototype_screenshot(
                project_root,
                screenshot_path,
                width=width,
                height=height,
            )
            semantic_state = {
                "surface_id": surface["surface_id"],
                "state_id": surface["state_id"],
                "viewport": viewport,
                "regions": [
                    {
                        "region_id": region["region_id"],
                        "semantic_role": region.get("semantic_role") or "region",
                        "accessible_name": (
                            region.get("accessible_name_match", {}).get("value")
                            or region["region_id"]
                        ),
                        "visibility": "visible",
                        "display_order": index,
                        "bounds": {
                            "x": 0,
                            "y": (index - 1) * 40,
                            "width": width,
                            "height": max(40, height // len(region_ids)),
                        },
                        "controls": ["primary-action"],
                        "interaction_state": surface["state_id"],
                    }
                    for index, region in enumerate(
                        surface["critical_regions"], start=1
                    )
                ],
            }
            semantic_states.append(semantic_state)
            runtime_checks.append(
                {
                    "surface_id": surface["surface_id"],
                    "state_id": surface["state_id"],
                    "viewport": viewport,
                    "status": "passed",
                    "clean_screenshot_path": screenshot_path,
                    "observed_region_ids": region_ids,
                    "annotation_nodes_present": False,
                    "review_assets_loaded": False,
                    "review_mode_available": False,
                }
            )

    _write_json(
        semantic_snapshot,
        {
            "schema_version": "prototype-semantic-snapshot-v1",
            "states": semantic_states,
        },
    )
    semantic_snapshot_sha256 = sha256_file(semantic_snapshot)
    for semantic_state, runtime_check in zip(semantic_states, runtime_checks):
        screenshot = project_root / runtime_check["clean_screenshot_path"]
        preflight_observations.append(
            {
                "surface_id": semantic_state["surface_id"],
                "state_id": semantic_state["state_id"],
                "viewport": semantic_state["viewport"],
                "semantic_state_sha256": stable_json_hash(semantic_state),
                "clean_screenshot_path": runtime_check["clean_screenshot_path"],
                "clean_screenshot_sha256": sha256_file(screenshot),
                "observed_region_ids": [
                    region["region_id"] for region in semantic_state["regions"]
                ],
                "document_ready": True,
                "console_errors": [],
                "network_errors": [],
                "annotation_nodes_present": False,
                "review_assets_loaded": False,
                "review_mode_available": False,
            }
        )
    browser_preflight_path = (
        ".product-delivery/artifacts/prototype-design/browser-preflight.json"
    )
    _write_json(
        project_root / browser_preflight_path,
        {
            "schema_version": "prototype-browser-preflight-v1",
            "prototype_path": prototype_path,
            "semantic_snapshot_sha256": semantic_snapshot_sha256,
            "observations": preflight_observations,
        },
    )

    coverage_rows = []
    for surface in contract["surfaces"]:
        covered_region_ids = [
            region["region_id"] for region in surface["critical_regions"]
        ]
        for dimension in PROTOTYPE_DESIGN_DIMENSIONS:
            context_mapping = {}
            if ui_change_type == "incremental_existing_surface":
                if dimension == "global_shell":
                    context_mapping["baseline_shell_region_ids"] = covered_region_ids
                elif dimension == "navigation":
                    context_mapping.update(
                        {
                            "ordinary_entry_path": "product shell -> primary surface",
                            "navigation_mapping": "Retains the existing primary navigation entry.",
                        }
                    )
                elif dimension == "information_density":
                    context_mapping["density_inheritance_mapping"] = (
                        "Retains the existing compact surface density."
                    )
                elif dimension == "component_system":
                    context_mapping["component_inheritance_mapping"] = (
                        "Reuses the existing primary controls."
                    )
            elif ui_change_type == "new_surface_in_existing_product":
                if dimension == "global_shell":
                    context_mapping["existing_shell_region_ids"] = covered_region_ids
                elif dimension == "navigation":
                    context_mapping.update(
                        {
                            "ordinary_entry_path": "product shell -> new primary surface",
                            "navigation_integration": "Adds the surface to existing navigation.",
                        }
                    )
                elif dimension == "component_system":
                    context_mapping["design_system_integration"] = (
                        "Uses the existing product component contracts."
                    )
            elif ui_change_type == "greenfield_ui" and dimension == "component_system":
                context_mapping["cross_page_state_consistency"] = [
                    {
                        "surface_id": surface["surface_id"],
                        "state_id": surface["state_id"],
                        "token_set_sha256": "a" * 64,
                    },
                    {
                        "surface_id": f"{surface['surface_id']}-secondary",
                        "state_id": "ready",
                        "token_set_sha256": "a" * 64,
                    },
                ]
            evidence_path = (
                ".product-delivery/artifacts/prototype-design/evidence/"
                f"{surface['surface_id']}-{surface['state_id']}-{dimension}.json"
            )
            _write_json(
                project_root / evidence_path,
                {
                    "schema_version": "prototype-design-evidence-v1",
                    "evidence_id": (
                        f"{surface['surface_id']}-{surface['state_id']}-{dimension}"
                    ),
                    "ui_change_type": ui_change_type,
                    "surface_id": surface["surface_id"],
                    "state_id": surface["state_id"],
                    "dimension": dimension,
                    "region_ids": covered_region_ids,
                    "claims": [f"Fixture {dimension} evidence is present."],
                    "style_probes": [
                        {
                            "probe": PROTOTYPE_STYLE_PROBES[dimension],
                            "expected": f"{dimension}-fixture-v1",
                            "observed": f"{dimension}-fixture-v1",
                        }
                    ],
                    "context_mapping": context_mapping,
                },
            )
            coverage_rows.append(
                {
                    "surface_id": surface["surface_id"],
                    "state_id": surface["state_id"],
                    "dimension": dimension,
                    "status": "passed",
                    "evidence_refs": [
                        {
                            "artifact_path": evidence_path,
                            "artifact_sha256": sha256_file(
                                project_root / evidence_path
                            ),
                        }
                    ],
                    "covered_region_ids": covered_region_ids,
                }
            )
    product_context_contract = {"coverage_rows": coverage_rows}
    if ui_change_type == "greenfield_ui":
        design_system_path = "docs/prototype-design-system.json"
        design_system = project_root / design_system_path
        design_system.parent.mkdir(parents=True, exist_ok=True)
        _write_json(
            design_system,
            {
                "schema_version": "prototype-design-system-v1",
                "name": "Fixture Design System",
                "token_sets": ["color", "type", "spacing", "components"],
            },
        )
        product_context_contract["design_system_artifact_path"] = design_system_path
    else:
        baseline_path = (
            ".product-delivery/artifacts/prototype-design/baseline-surface.png"
        )
        write_prototype_screenshot(project_root, baseline_path)
        product_context_contract["baseline_identity"] = {
            "canonical_baseline_id": "fixture-baseline-v1",
            "baseline_feature_slug": "fixture-existing-product",
            "baseline_surface_paths": ["/customer/course-production"],
            "baseline_snapshot_paths": [baseline_path],
        }
        if ui_change_type == "new_surface_in_existing_product":
            design_system_path = "docs/prototype-design-system.json"
            _write_json(
                project_root / design_system_path,
                {
                    "schema_version": "prototype-design-system-v1",
                    "name": "Fixture Design System",
                    "token_sets": ["color", "type", "spacing", "components"],
                },
            )
            product_context_contract.update(
                {
                    "design_system_artifact_path": design_system_path,
                    "new_surface_justification": {
                        "reason": "The workflow needs a distinct product surface.",
                        "why_existing_surface_insufficient": (
                            "The existing surface cannot represent the new lifecycle."
                        ),
                        "navigation_impact": (
                            "Adds one destination to the existing product navigation."
                        ),
                    },
                }
            )

    first_surface = contract["surfaces"][0]
    first_region = first_surface["critical_regions"][0]
    payload = {
        "bundle_version": "v1",
        "ui_change_type": ui_change_type,
        "clean_surface": {
            "prototype_path": prototype_path,
            "prototype_contract": contract,
            "semantic_snapshot_path": semantic_snapshot_path,
            "browser_preflight_probe_path": browser_preflight_path,
            "runtime_checks": runtime_checks,
        },
        "product_context_contract": product_context_contract,
        "intended_product_ui_callouts": [
            {
                "callout_id": "fixture-primary-callout",
                "requirement_ids": ["FR-001"],
                "scenario_ids": ["SC-001"],
                "actor_roles": ["teacher"],
                "trigger": "the primary workflow enters its ready state",
                "lifecycle": "visible while the ready state remains active",
                "dismissal_or_persistence": "persists until the state changes",
                "state_id": first_surface["state_id"],
                "region_id": first_region["region_id"],
            }
        ],
        "review_annotation_set": None,
    }
    if include_review_companion:
        review_path = (
            ".product-delivery/artifacts/review-only/prototype-review.html"
        )
        review_artifact = project_root / review_path
        review_artifact.parent.mkdir(parents=True, exist_ok=True)
        review_artifact.write_text(
            (
                '<html><body><a data-annotation-id="fixture-context-note" '
                f'data-clean-region-id="{first_region["region_id"]}" '
                f'data-clean-surface-reference="{prototype_path}" '
                f'href="{prototype_path}#{first_region["region_id"]}">'
                f"{annotation_text}</a></body></html>"
            ),
            encoding="utf-8",
        )
        payload["review_annotation_set"] = {
            "artifact_path": review_path,
            "clean_surface_reference": prototype_path,
            "annotations": [
                {
                    "annotation_id": "fixture-context-note",
                    "target_region_id": first_region["region_id"],
                    "text": annotation_text,
                }
            ],
        }
    return payload


def record_prototype_design_bundle(
    workflow,
    project_root: Path,
    review_payload: dict | None = None,
    **payload_options,
) -> dict:
    review_payload = review_payload if review_payload is not None else {}
    payload = prototype_design_bundle_payload(
        project_root,
        prototype_path=review_payload.get("prototype_path", "prototype/index.html"),
        contract=review_payload.get("prototype_contract") or prototype_contract(),
        ui_change_type=review_payload.get(
            "ui_change_type", "incremental_existing_surface"
        ),
        **payload_options,
    )
    state = workflow.record_ui_prototype_design_bundle(payload)
    if review_payload is not None:
        review_payload.update(bind_prototype_design_review(workflow, review_payload))
    return state


def bind_prototype_design_review(workflow, review: dict) -> dict:
    bound = dict(review)
    bundle = workflow.status()["prototype_design_bundle"]
    bound["prototype_design_bundle_hash"] = bundle["bundle_sha256"]
    bound["prototype_design_audit_hash"] = bundle["design_audit_sha256"]
    bound.setdefault(
        "reviewed_design_dimensions", list(PROTOTYPE_DESIGN_DIMENSIONS)
    )
    bound.setdefault("unmapped_design_dimensions", [])
    bound.setdefault("global_visual_continuity_findings", [])
    bound.setdefault("annotation_separation_findings", [])
    bound.setdefault(
        "global_visual_continuity",
        {
            "conclusion": "passed",
            "summary": "All six product-context dimensions are positively covered.",
            "evidence_refs": [
                f"prototype-design-audit:{bundle['design_audit_sha256']}"
            ],
        },
    )
    bound.setdefault(
        "annotation_separation",
        {
            "conclusion": "passed",
            "summary": "The clean prototype is separated from review annotations.",
            "evidence_refs": [
                f"prototype-design-bundle:{bundle['bundle_sha256']}"
            ],
        },
    )
    return bound


def record_bundled_ui_prototype_review(
    workflow,
    project_root: Path,
    review: dict,
) -> dict:
    record_prototype_design_bundle(workflow, project_root, review)
    return workflow.record_ui_prototype_review(
        bind_prototype_design_review(workflow, review)
    )


def record_scenario_review(workflow, review: dict) -> dict:
    state = workflow.status()
    bundle = state.get("prototype_design_bundle") or {}
    if state.get("project_type") == "ui" and bundle.get("status") == "ready":
        review = bind_prototype_design_review(workflow, review)
    return workflow.record_multi_agent_review("scenario", review)


def confirm_product_baseline(workflow, review: dict, message: str = "确认产品基线"):
    review = dict(review)
    reviewers = list(review.get("reviewers") or [])
    review.setdefault(
        "reviewer_agent_ids",
        [f"fixture-agent-{index}" for index, _ in enumerate(reviewers, start=1)],
    )
    review.setdefault(
        "reviewer_spawn_source",
        "codex.multi_agent_v1.spawn_agent",
    )
    state = workflow.status()
    if state.get("project_type") == "ui":
        ui_review = state.get("ui_prototype_review") or {}
        change_type = ui_review.get("ui_change_type")
        review.setdefault("ui_continuity_findings", [])
        if change_type == "incremental_existing_surface":
            review.setdefault(
                "baseline_inheritance_review",
                {
                    "ui_change_type": change_type,
                    "baseline_feature_slug": ui_review.get(
                        "baseline_feature_slug"
                    ),
                    "baseline_entry_path": ui_review.get(
                        "baseline_user_journey"
                    ),
                    "inherits_existing_surface": True,
                    "parallel_surface_replacement": False,
                },
            )
        review = bind_prototype_design_review(workflow, review)
    record_scenario_review(workflow, review)
    state = workflow.prepare_product_baseline_confirmation()
    pending = state["pending_confirmations"]["product_baseline"]
    return workflow.confirm_product_baseline(message, pending["nonce"])


def confirm_test_coverage_plan(
    workflow, message: str = "确认 planned E2E 和测试覆盖计划"
):
    state = workflow.prepare_test_coverage_confirmation()
    pending = state["pending_confirmations"]["test_coverage_plan"]
    return workflow.confirm_test_coverage_plan(message, pending["nonce"])


def host_goal_result(objective: str, status: str = "active") -> dict:
    return {
        "goal": {
            "threadId": os.environ["CODEX_THREAD_ID"],
            "objective": objective,
            "status": status,
        }
    }


def activate_host_goal(workflow) -> dict:
    inspection = workflow.prepare_host_goal_activation()
    workflow.record_host_goal_observation(
        inspection["checkpoint_id"],
        {
            "observation_source": "codex_goal_tool",
            "tool": "get_goal",
            "result": {"goal": None},
        },
    )
    creation = workflow.prepare_host_goal_activation()
    objective = creation["objective"]
    workflow.record_host_goal_observation(
        creation["checkpoint_id"],
        {
            "observation_source": "codex_goal_tool",
            "tool": "create_goal",
            "result": host_goal_result(objective),
        },
    )
    verification = workflow.prepare_host_goal_activation()
    return workflow.record_host_goal_observation(
        verification["checkpoint_id"],
        {
            "observation_source": "codex_goal_tool",
            "tool": "get_goal",
            "result": host_goal_result(objective),
        },
    )


def reconcile_host_goal(workflow, operation: str = "stage_transition") -> dict:
    state = workflow.status()
    checkpoint = workflow.prepare_host_goal_reconciliation(
        operation,
        target_gate=state["next_gate"],
    )
    return workflow.record_host_goal_observation(
        checkpoint["checkpoint_id"],
        {
            "observation_source": "codex_goal_tool",
            "tool": checkpoint["required_tool"],
            "result": host_goal_result(
                state["host_goal_binding"]["objective"]
            ),
        },
    )


def complete_host_goal(workflow) -> dict:
    state = workflow.status()
    objective = state["host_goal_binding"]["objective"]
    pre_complete = workflow.prepare_host_goal_reconciliation(
        "pre_complete",
        target_gate=state["next_gate"],
    )
    workflow.record_host_goal_observation(
        pre_complete["checkpoint_id"],
        {
            "observation_source": "codex_goal_tool",
            "tool": "get_goal",
            "result": host_goal_result(objective),
        },
    )
    completion = workflow.prepare_host_goal_reconciliation(
        "complete_goal",
        target_gate=workflow.status()["next_gate"],
    )
    workflow.record_host_goal_observation(
        completion["checkpoint_id"],
        {
            "observation_source": "codex_goal_tool",
            "tool": "update_goal",
            "result": host_goal_result(objective, status="complete"),
        },
    )
    verification = workflow.prepare_host_goal_reconciliation(
        "verify_completion",
        target_gate=workflow.status()["next_gate"],
    )
    return workflow.record_host_goal_observation(
        verification["checkpoint_id"],
        {
            "observation_source": "codex_goal_tool",
            "tool": "get_goal",
            "result": host_goal_result(objective, status="complete"),
        },
    )


def record_ui_conformance(workflow, project_root: Path) -> dict:
    state = workflow.status()
    executed = state["executed_browser_evidence"]["records"][0]
    production_screenshot = (
        ".product-delivery/artifacts/conformance/default-production.png"
    )
    write_prototype_screenshot(project_root, production_screenshot)
    snapshot_path = (
        project_root
        / ".product-delivery/artifacts/conformance/default-semantic.json"
    )
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "schema_version": "ui-semantic-surface-v1",
                "acceptance_url": executed["acceptance_url"],
                "execution_segment_id": executed["execution_segment_id"],
                "production_route": "/customer/course-production",
                "viewport": {"class": "desktop", "width": 1280, "height": 720},
                "regions": [
                    {
                        "region_id": "primary-region",
                        "matched_count": 1,
                        "visible": True,
                        "role": "main",
                        "accessible_name": "primary surface",
                        "parent_region_id": None,
                        "display_order": 1,
                        "bounding_box": {
                            "x": 0,
                            "y": 0,
                            "width": 1280,
                            "height": 720,
                        },
                        "key_controls": ["primary action"],
                        "interaction_state": "ready",
                    }
                ],
                "relationships": [
                    {
                        "source_region_id": "primary-region",
                        "relation": "contains",
                        "target_region_id": "primary-region",
                        "observed": True,
                    }
                ],
                "interactions": [
                    {
                        "interaction_id": "primary-action",
                        "observed": True,
                        "result": "primary-region updated",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    component = project_root / "src" / "primary_surface.tsx"
    component.parent.mkdir(parents=True, exist_ok=True)
    component.write_text("export const PrimarySurface = true;\n", encoding="utf-8")
    payload = {
        "prototype_revision": state["ui_prototype"]["prototype_revision"],
        "prototype_contract_hash": state["prototype_contract"]["contract_sha256"],
        "records": [
            {
                "surface_id": "primary-surface",
                "state_id": "ready",
                "viewport_class": "desktop",
                "acceptance_url": executed["acceptance_url"],
                "execution_segment_id": executed["execution_segment_id"],
                "production_route": "/customer/course-production",
                "production_screenshot_path": production_screenshot,
                "semantic_snapshot_path": str(snapshot_path.relative_to(project_root)),
                "region_results": [
                    {"region_id": "primary-region", "observed": True}
                ],
                "relationship_results": [
                    {
                        "source_region_id": "primary-region",
                        "relation": "contains",
                        "target_region_id": "primary-region",
                        "observed": True,
                    }
                ],
                "interaction_results": [
                    {"interaction_id": "primary-action", "observed": True}
                ],
                "production_component_refs": [
                    {
                        "path": "src/primary_surface.tsx",
                        "kind": "dedicated_surface",
                        "note": "test fixture surface",
                    }
                ],
            }
        ],
    }
    reconcile_host_goal(workflow)
    state = workflow.record_prototype_production_conformance(payload)
    reconcile_host_goal(workflow)
    workflow.record_multi_agent_review(
        "ui_conformance",
        ui_conformance_review_payload(state),
    )
    return workflow.status()


def ui_conformance_review_payload(state: dict) -> dict:
    contract = state["prototype_contract"]
    surfaces = contract["surfaces"]
    return {
        "review_id": "REV-UI-CONFORMANCE-FIXTURE",
        "review_type": "ui_conformance",
        "status": "passed",
        "review_mode": "spawned_subagents",
        "reviewers": ["prototype reviewer", "production reviewer"],
        "reviewer_agent_ids": ["agent-prototype", "agent-production"],
        "reviewer_spawn_source": "codex.multi_agent_v1.spawn_agent",
        "artifact_version": "ui-conformance-v1",
        "independent_positions": ["all frozen regions were compared"],
        "cross_challenges": ["reviewed semantic and viewport evidence"],
        "revisions": ["kept complete region coverage"],
        "final_adjudication": "passed",
        "conclusions": ["UI conformance passed"],
        "accepted_suggestions": [],
        "rejected_suggestions": [],
        "unresolved_questions": [],
        "blocking_findings": [],
        "reviewed_surface_ids": [surface["surface_id"] for surface in surfaces],
        "reviewed_state_ids": [surface["state_id"] for surface in surfaces],
        "reviewed_region_ids": [
            region["region_id"]
            for surface in surfaces
            for region in surface["critical_regions"]
        ],
        "structural_findings": [],
        "visual_findings": [],
        "interaction_findings": [],
        "legacy_reuse_findings": [],
        "unmapped_regions": [],
        "reviewed_design_dimensions": list(PROTOTYPE_DESIGN_DIMENSIONS),
        "global_visual_continuity_findings": [],
        "annotation_separation_findings": [],
    }
