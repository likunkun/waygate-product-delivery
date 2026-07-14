import struct
import json
import zlib
from pathlib import Path


DEFAULT_PROTOTYPE_SCREENSHOT = (
    ".product-delivery/artifacts/prototype/default-desktop.png"
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
    workflow.record_multi_agent_review("scenario", review)
    state = workflow.prepare_product_baseline_confirmation()
    pending = state["pending_confirmations"]["product_baseline"]
    return workflow.confirm_product_baseline(message, pending["nonce"])


def confirm_test_coverage_plan(
    workflow, message: str = "确认 planned E2E 和测试覆盖计划"
):
    state = workflow.prepare_test_coverage_confirmation()
    pending = state["pending_confirmations"]["test_coverage_plan"]
    return workflow.confirm_test_coverage_plan(message, pending["nonce"])


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
    state = workflow.record_prototype_production_conformance(payload)
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
    }
