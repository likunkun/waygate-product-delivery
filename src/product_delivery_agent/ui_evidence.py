"""Trusted, reusable UI capture evidence for Waygate Product Delivery."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
import uuid
from urllib.parse import urlsplit


CAPTURE_PLAN_VERSION = "capture-plan-v1"
CAPTURE_RUN_VERSION = "capture-run-v1"
EVIDENCE_POLICY_VERSION = "v1"
REGISTRY_VERSION = "ui-capture-registry-v1"
TELEMETRY_VERSION = "ui-performance-telemetry-v1"

STRICT_RISK_TAGS = frozenset(
    {
        "auth",
        "authentication",
        "authorization",
        "privacy",
        "security",
        "payment",
        "destructive",
        "global_shell",
        "navigation",
        "design_tokens",
        "responsive_infrastructure",
        "new_surface",
        "new_route",
        "api_schema",
        "migration",
        "cross_role_critical_journey",
    }
)

_TOP_LEVEL_VERDICT_FIELDS = frozenset(
    {
        "status",
        "passed",
        "gate_status",
        "closure_status",
        "authoritative_verdict",
    }
)
_IDENTITY_FIELDS = {
    "source_identity": ("tree_sha256", "commit_sha"),
    "build_identity": ("build_digest",),
    "deployment_identity": ("deployment_id", "origin", "api_origin"),
    "environment_identity": (
        "environment_id",
        "feature_flags_sha256",
        "locale",
        "timezone",
        "reduced_motion",
    ),
    "collector_identity": (
        "name",
        "version",
        "browser_name",
        "browser_version",
        "validator_version",
    ),
    "data_state_identity": ("seed_id", "version"),
}
_ARTIFACT_REF_FIELDS = (
    "screenshot",
    "semantic_snapshot",
    "task_semantic_snapshot",
    "production_semantic_snapshot",
    "trace",
    "evidence",
    "probe",
    "segment_metadata",
    "acceptance_scan",
)


class UIEvidenceError(RuntimeError):
    """Raised when UI capture evidence is incomplete, stale, or unsafe."""


def stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_evidence_profile(
    *,
    purpose: str,
    requested_profile: str = "auto",
    risk_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a non-downgradable UI evidence profile."""
    if purpose not in {"iteration", "closure"}:
        raise UIEvidenceError("purpose must be iteration or closure")
    if requested_profile not in {"auto", "strict"}:
        raise UIEvidenceError(
            "requested_profile must be auto or strict; formal evidence cannot be downgraded"
        )
    facts = risk_facts if isinstance(risk_facts, dict) else {}
    tags = sorted(
        {
            str(tag).strip().lower()
            for tag in facts.get("risk_tags", [])
            if isinstance(tag, str) and tag.strip()
        }
    )
    reasons: list[str] = []
    if purpose == "iteration":
        return {
            "policy_version": EVIDENCE_POLICY_VERSION,
            "profile": "iteration",
            "closure_valid": False,
            "reasons": ["developer_iteration_only"],
            "risk_tags": tags,
        }
    if requested_profile == "strict":
        reasons.append("user_upgraded_to_strict")
    if facts.get("impact_known") is not True:
        reasons.append("impact_unknown")
    strict_tags = sorted(set(tags).intersection(STRICT_RISK_TAGS))
    reasons.extend(f"strict_risk:{tag}" for tag in strict_tags)
    profile = "strict" if reasons else "standard"
    return {
        "policy_version": EVIDENCE_POLICY_VERSION,
        "profile": profile,
        "closure_valid": True,
        "reasons": reasons or ["complete_low_risk_impact"],
        "risk_tags": tags,
    }


def build_capture_plan(
    *,
    delivery_id: str,
    feature_slug: str,
    purpose: str,
    requested_profile: str = "auto",
    risk_facts: dict[str, Any] | None = None,
    units: list[dict[str, Any]] | None = None,
    journeys: list[dict[str, Any]] | None = None,
    required_build_digest: str | None = None,
    prototype_origin: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic capture plan with a fail-closed profile."""
    for label, value in (("delivery_id", delivery_id), ("feature_slug", feature_slug)):
        _require_text(value, label)
    profile = resolve_evidence_profile(
        purpose=purpose,
        requested_profile=requested_profile,
        risk_facts=risk_facts,
    )
    normalized_units = _normalize_plan_units(units or [])
    required_units = list(normalized_units)
    if profile["profile"] in {"iteration", "standard"}:
        selected_keys = {
            (
                str(item.get("surface_id") or ""),
                str(item.get("state_id") or ""),
                str(item.get("viewport_class") or ""),
            )
            for field_name in ("affected_units", "canary_units")
            for item in (risk_facts or {}).get(field_name, [])
            if isinstance(item, dict)
        }
        if selected_keys:
            reusable_keys = {
                (
                    str(item.get("surface_id") or ""),
                    str(item.get("state_id") or ""),
                    str(item.get("viewport_class") or ""),
                )
                for item in (risk_facts or {}).get("reusable_units", [])
                if isinstance(item, dict)
            }
            normalized_units = [
                item
                for item in normalized_units
                if (
                    item["surface_id"],
                    item["state_id"],
                    item["viewport_class"],
                )
                in selected_keys
                or (
                    item["surface_id"],
                    item["state_id"],
                    item["viewport_class"],
                )
                not in reusable_keys
            ]
    normalized_journeys = _normalize_plan_journeys(journeys or [])
    if purpose == "closure" and (not normalized_units or not normalized_journeys):
        raise UIEvidenceError("formal capture plan requires UI units and journeys")
    plan_body = {
        "schema_version": CAPTURE_PLAN_VERSION,
        "delivery_id": delivery_id,
        "feature_slug": feature_slug,
        "purpose": purpose,
        "requested_profile": requested_profile,
        "resolved_profile": profile["profile"],
        "closure_valid": profile["closure_valid"],
        "profile_reasons": profile["reasons"],
        "risk_facts": deepcopy(risk_facts or {}),
        "required_units": required_units,
        "units": normalized_units,
        "journeys": normalized_journeys,
        "required_build_digest": required_build_digest,
        "prototype_origin": prototype_origin,
        "reusable_capture_run_ids": sorted(
            {
                str(item)
                for item in (risk_facts or {}).get(
                    "reusable_capture_run_ids", []
                )
                if isinstance(item, str) and item
            }
        ),
        "adapter_protocol": {
            "manifest_schema_version": CAPTURE_RUN_VERSION,
            "environment": [
                "WAYGATE_CAPTURE_PLAN",
                "WAYGATE_CAPTURE_RUN_ID",
                "WAYGATE_CAPTURE_OUTPUT_DIR",
            ],
            "manifest_name": "capture-manifest.json",
            "single_invocation": True,
        },
    }
    return {**plan_body, "plan_id": "capture-plan-" + stable_hash(plan_body)[:24]}


def run_capture_adapter(
    *,
    project_root: str | Path,
    plan_path: str | Path,
    adapter_executable: str,
    adapter_args: list[str] | None = None,
    output_dir: str | Path,
) -> Path:
    """Invoke one target-project adapter directly, never through a shell."""
    root = Path(project_root).resolve()
    plan_file = Path(plan_path).resolve()
    output = Path(output_dir).resolve()
    _require_under(root, plan_file, "capture plan")
    _require_under(root, output, "capture output")
    try:
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as cause:
        raise UIEvidenceError("capture plan must be valid JSON") from cause
    if not isinstance(plan, dict) or plan.get("schema_version") != CAPTURE_PLAN_VERSION:
        raise UIEvidenceError("capture plan schema is invalid")
    _require_text(plan.get("plan_id"), "capture plan plan_id")
    _require_text(adapter_executable, "adapter_executable")
    output.mkdir(parents=True, exist_ok=True)
    run_id = "capture-run-" + uuid.uuid4().hex
    environment = dict(os.environ)
    environment.update(
        {
            "WAYGATE_CAPTURE_PLAN": str(plan_file),
            "WAYGATE_CAPTURE_RUN_ID": run_id,
            "WAYGATE_CAPTURE_OUTPUT_DIR": str(output),
        }
    )
    command = [adapter_executable, *[str(item) for item in (adapter_args or [])]]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            check=False,
            shell=False,
        )
    except OSError as cause:
        raise UIEvidenceError(f"capture adapter failed to start: {cause}") from cause
    if completed.returncode != 0:
        raise UIEvidenceError(
            f"capture adapter failed with exit code {completed.returncode}"
        )
    wall_ms = round((time.perf_counter() - started) * 1000, 3)
    manifest_path = output / "capture-manifest.json"
    if not manifest_path.is_file():
        raise UIEvidenceError("capture adapter did not write capture-manifest.json")
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as cause:
        raise UIEvidenceError("capture adapter manifest is invalid JSON") from cause
    if not isinstance(value, dict):
        raise UIEvidenceError("capture adapter manifest must be an object")
    if value.get("capture_run_ref") != run_id:
        raise UIEvidenceError(
            "capture adapter manifest capture_run_ref must match WAYGATE_CAPTURE_RUN_ID"
        )
    _validate_manifest_identity(plan, value)
    _validate_manifest_structure(plan, value)
    _validate_artifact_refs(root, output, value)
    (output / "capture-run-telemetry.json").write_text(
        json.dumps(
            {
                "schema_version": TELEMETRY_VERSION,
                "plan_id": plan["plan_id"],
                "operation": "capture_adapter",
                "wall_ms": wall_ms,
                "browser_launches": 1,
                "capture_units": len(plan.get("units") or []),
                "retries": 0,
                "reused_artifacts": 0,
                "total_artifacts": sum(
                    1
                    for collection in ("units", "journey_segments")
                    for row in value.get(collection, [])
                    if isinstance(row, dict)
                    for field_name in _ARTIFACT_REF_FIELDS
                    if row.get(field_name) is not None
                ),
                "raw_artifacts": sum(
                    1
                    for collection in ("units", "journey_segments")
                    for row in value.get(collection, [])
                    if isinstance(row, dict)
                    for field_name in _ARTIFACT_REF_FIELDS
                    if row.get(field_name) is not None
                ),
                "unique_artifacts": len(
                    {
                        row[field_name]["sha256"]
                        for collection in ("units", "journey_segments")
                        for row in value.get(collection, [])
                        if isinstance(row, dict)
                        for field_name in _ARTIFACT_REF_FIELDS
                        if isinstance(row.get(field_name), dict)
                        and row[field_name].get("sha256")
                    }
                ),
                "validator_wall_ms": 0,
                "projection_reuse_count": 0,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def ingest_capture_run(
    project_root: str | Path,
    delivery_root: str | Path,
    plan: dict[str, Any],
    manifest_path: str | Path,
    *,
    expected_registry_sha256: str | None = None,
    expected_registry_root_sha256: str | None = None,
    expected_execution_identity: dict[str, Any] | None = None,
    transaction_id: str | None = None,
    expected_capture_id: str | None = None,
    expected_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate and immutably ingest an untrusted staging capture manifest."""
    root = Path(project_root).resolve()
    if plan.get("closure_valid") is not True:
        raise UIEvidenceError(
            "iteration capture remains noncanonical staging evidence and cannot be ingested"
        )
    delivery = Path(delivery_root).resolve()
    _require_under(root, delivery, "delivery root")
    validate_delivery_evidence_root(delivery)
    path = Path(manifest_path).resolve()
    _require_under(root, path, "capture manifest")
    try:
        manifest_bytes = path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as cause:
        raise UIEvidenceError("capture manifest must be valid JSON") from cause
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if expected_manifest_sha256 and manifest_sha256 != expected_manifest_sha256:
        raise UIEvidenceError("capture transaction staging manifest changed")
    if not isinstance(manifest, dict):
        raise UIEvidenceError("capture manifest must be an object")
    forbidden = _forbidden_verdict_paths(manifest)
    if forbidden:
        raise UIEvidenceError(
            "raw capture manifest cannot contain authoritative verdicts: "
            + ", ".join(forbidden)
        )
    _validate_manifest_identity(plan, manifest)
    _validate_manifest_structure(plan, manifest)
    execution_identity = _execution_identity(manifest)
    if expected_execution_identity is not None and execution_identity != expected_execution_identity:
        raise UIEvidenceError(
            "capture execution identity does not match the frozen final build environment"
        )

    artifact_sources = _validate_artifact_refs(root, path.parent, manifest)
    performance_event = _load_staging_performance_event(path.parent, plan)
    _validate_existing_registry_identity(
        delivery,
        expected_registry_sha256=expected_registry_sha256,
        expected_registry_root_sha256=expected_registry_root_sha256,
    )
    identity_manifest = deepcopy(manifest)
    identity_manifest.pop("capture_id", None)
    _canonicalize_artifact_identity(identity_manifest)
    capture_id = "capture-" + stable_hash(identity_manifest)
    if expected_capture_id and capture_id != expected_capture_id:
        raise UIEvidenceError("capture transaction identity changed before ingest")
    if manifest.get("capture_id") not in {None, capture_id}:
        raise UIEvidenceError("declared capture_id does not match normalized capture facts")

    capture_root = delivery / "evidence" / "captures" / capture_id
    manifest_target = capture_root / "manifest.json"
    canonical = deepcopy(identity_manifest)
    canonical["capture_id"] = capture_id
    canonical["ingested_schema_version"] = CAPTURE_RUN_VERSION
    artifact_directory = capture_root / "artifacts"
    rewritten: dict[tuple[str, str], dict[str, str]] = {}
    for owner, field_name, reference, source in artifact_sources:
        suffix = source.suffix.lower()
        target_name = reference["sha256"] + suffix
        target = artifact_directory / target_name
        rewritten[(owner, field_name)] = {
            "path": str(target.relative_to(delivery)),
            "sha256": reference["sha256"],
        }

    _rewrite_manifest_artifact_refs(canonical, rewritten)
    encoded = json.dumps(canonical, indent=2, sort_keys=True) + "\n"
    if manifest_target.exists():
        existing = manifest_target.read_text(encoding="utf-8")
        if existing != encoded:
            raise UIEvidenceError("capture registry identity collision")
        _validate_canonical_artifacts(delivery, canonical)
        registry = _update_registry(delivery, capture_id, manifest_target, created=False)
        return {
            "capture_id": capture_id,
            "created": False,
            "manifest_path": str(manifest_target),
            "performance_event": performance_event,
            "source_identity": deepcopy(canonical["source_identity"]),
            "build_identity": deepcopy(canonical["build_identity"]),
            "deployment_identity": deepcopy(canonical["deployment_identity"]),
            "environment_identity": deepcopy(canonical["environment_identity"]),
            "collector_identity": deepcopy(canonical["collector_identity"]),
            "execution_identity": execution_identity,
            **registry,
        }

    captures_parent = capture_root.parent
    captures_parent.mkdir(parents=True, exist_ok=True)
    transaction_token = (
        _validate_transaction_id(transaction_id)
        if transaction_id is not None
        else uuid.uuid4().hex
    )
    ingest_root = delivery / "evidence" / (
        ".capture-ingest-" + transaction_token
    )
    ingest_artifacts = ingest_root / "artifacts"
    try:
        ingest_artifacts.mkdir(parents=True, exist_ok=False)
        copied: set[str] = set()
        for owner, field_name, reference, source in artifact_sources:
            target_ref = rewritten[(owner, field_name)]
            target_name = Path(target_ref["path"]).name
            if target_name in copied:
                continue
            copied.add(target_name)
            target = ingest_artifacts / target_name
            shutil.copyfile(source, target)
            if sha256_file(target) != reference["sha256"]:
                raise UIEvidenceError(
                    f"staging artifact changed during ingest: {reference['path']}"
                )
            _fsync_file(target)
        manifest_staged = ingest_root / "manifest.json"
        _write_fsynced_text(manifest_staged, encoded)
        _fsync_directory(ingest_artifacts)
        _fsync_directory(ingest_root)
        os.replace(ingest_root, capture_root)
        _fsync_directory(captures_parent)
        try:
            registry = _update_registry(
                delivery,
                capture_id,
                manifest_target,
                created=True,
                transaction_id=transaction_token,
            )
        except Exception:
            shutil.rmtree(capture_root, ignore_errors=True)
            raise
    finally:
        shutil.rmtree(ingest_root, ignore_errors=True)
    return {
        "capture_id": capture_id,
        "created": True,
        "manifest_path": str(manifest_target),
        "performance_event": performance_event,
        "source_identity": deepcopy(canonical["source_identity"]),
        "build_identity": deepcopy(canonical["build_identity"]),
        "deployment_identity": deepcopy(canonical["deployment_identity"]),
        "environment_identity": deepcopy(canonical["environment_identity"]),
        "collector_identity": deepcopy(canonical["collector_identity"]),
        "execution_identity": execution_identity,
        **registry,
    }


def inspect_capture_run(
    project_root: str | Path,
    delivery_root: str | Path,
    plan: dict[str, Any],
    manifest_path: str | Path,
    *,
    expected_registry_sha256: str | None = None,
    expected_registry_root_sha256: str | None = None,
    expected_execution_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate staging facts and calculate the immutable identity without writes."""
    root = Path(project_root).resolve()
    delivery = Path(delivery_root).resolve()
    _require_under(root, delivery, "delivery root")
    validate_delivery_evidence_root(delivery)
    if plan.get("closure_valid") is not True:
        raise UIEvidenceError("iteration capture cannot be inspected for canonical ingest")
    path = Path(manifest_path).resolve()
    _require_under(root, path, "capture manifest")
    try:
        manifest_bytes = path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as cause:
        raise UIEvidenceError("capture manifest must be valid JSON") from cause
    if not isinstance(manifest, dict):
        raise UIEvidenceError("capture manifest must be an object")
    forbidden = _forbidden_verdict_paths(manifest)
    if forbidden:
        raise UIEvidenceError(
            "raw capture manifest cannot contain authoritative verdicts: "
            + ", ".join(forbidden)
        )
    _validate_manifest_identity(plan, manifest)
    _validate_manifest_structure(plan, manifest)
    execution_identity = _execution_identity(manifest)
    if expected_execution_identity is not None and execution_identity != expected_execution_identity:
        raise UIEvidenceError(
            "capture execution identity does not match the frozen final build environment"
        )
    _validate_artifact_refs(root, path.parent, manifest)
    _validate_existing_registry_identity(
        delivery,
        expected_registry_sha256=expected_registry_sha256,
        expected_registry_root_sha256=expected_registry_root_sha256,
    )
    identity_manifest = deepcopy(manifest)
    identity_manifest.pop("capture_id", None)
    _canonicalize_artifact_identity(identity_manifest)
    capture_id = "capture-" + stable_hash(identity_manifest)
    if manifest.get("capture_id") not in {None, capture_id}:
        raise UIEvidenceError("declared capture_id does not match normalized capture facts")
    return {
        "capture_id": capture_id,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "capture_created": not (
            delivery / "evidence" / "captures" / capture_id / "manifest.json"
        ).is_file(),
        "execution_identity": execution_identity,
    }


def load_capture_run(delivery_root: str | Path, capture_id: str) -> dict[str, Any]:
    delivery = Path(delivery_root).resolve()
    validate_delivery_evidence_root(delivery)
    capture_id = _validate_capture_id(capture_id)
    captures_root = (delivery / "evidence" / "captures").resolve()
    path = (captures_root / capture_id / "manifest.json").resolve()
    _require_under(captures_root, path, "capture run manifest")
    if not path.is_file():
        raise UIEvidenceError(f"capture run is missing: {capture_id}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as cause:
        raise UIEvidenceError(f"capture run manifest is invalid: {capture_id}") from cause
    if not isinstance(value, dict) or value.get("capture_id") != capture_id:
        raise UIEvidenceError(f"capture run identity is invalid: {capture_id}")
    registry = validate_capture_registry(delivery)
    entry = next(
        (
            item
            for item in registry["captures"]
            if item.get("capture_id") == capture_id
        ),
        None,
    )
    if not isinstance(entry, dict):
        raise UIEvidenceError(f"capture run is not registered: {capture_id}")
    if (
        (delivery / str(entry.get("manifest_path") or "")).resolve() != path.resolve()
        or entry.get("manifest_sha256") != sha256_file(path)
    ):
        raise UIEvidenceError(f"capture registry binding changed: {capture_id}")
    identity = deepcopy(value)
    identity.pop("capture_id", None)
    identity.pop("ingested_schema_version", None)
    _canonicalize_artifact_identity(identity)
    if "capture-" + stable_hash(identity) != capture_id:
        raise UIEvidenceError(f"capture run content identity changed: {capture_id}")
    synthetic_plan = {
        "plan_id": value.get("plan_id"),
        "purpose": value.get("purpose"),
        "resolved_profile": value.get("profile"),
        "closure_valid": value.get("closure_valid"),
        "required_build_digest": (
            (value.get("build_identity") or {}).get("build_digest")
        ),
        "units": [
            {
                field: unit.get(field)
                for field in ("surface_id", "state_id", "viewport_class")
            }
            for unit in value.get("units") or []
            if isinstance(unit, dict)
        ],
        "journeys": [
            {
                field: segment.get(field)
                for field in ("obligation_id", "test_id")
            }
            for segment in value.get("journey_segments") or []
            if isinstance(segment, dict)
        ],
    }
    _validate_manifest_identity(synthetic_plan, value)
    _validate_manifest_structure(synthetic_plan, value)
    _validate_canonical_artifacts(delivery, value)
    return value


def browser_records_from_capture_runs(
    delivery_root: str | Path,
    capture_run_ids: list[str],
    *,
    authorized_exemptions: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Project registered raw journey facts into existing Browser E2E records."""
    delivery = Path(delivery_root).resolve()
    records: list[dict[str, Any]] = []
    for capture_id in _unique_texts(capture_run_ids, "capture_run_ids"):
        capture = load_capture_run(delivery, capture_id)
        if capture.get("closure_valid") is not True:
            raise UIEvidenceError("iteration capture cannot become formal browser evidence")
        actors = _capture_actor_identities(capture)
        deployment = capture["deployment_identity"]
        for segment in capture.get("journey_segments", []):
            segment_actor = _validate_actor_identity(
                segment.get("actor_identity_evidence"), "journey actor"
            )
            if segment_actor not in actors:
                raise UIEvidenceError("journey actor identity is not declared by capture")
            probe_path = _canonical_artifact_path(delivery, segment["probe"])
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            metadata_path = _canonical_artifact_path(
                delivery, segment["segment_metadata"]
            )
            try:
                segment_metadata = json.loads(
                    metadata_path.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError as cause:
                raise UIEvidenceError("journey segment metadata must be JSON") from cause
            _validate_segment_metadata(
                segment_metadata,
                segment=segment,
                actor=segment_actor,
                capture_run_ref=capture["capture_run_ref"],
            )
            business_requests = _validate_probe_against_segment(
                probe,
                segment,
                deployment,
                segment_actor,
                capture["capture_run_ref"],
            )
            if not _url_matches_origin(segment["acceptance_url"], deployment["origin"]):
                raise UIEvidenceError("acceptance URL does not use the production origin")
            if not _url_matches_origin(segment["api_health_url"], deployment["api_origin"]):
                raise UIEvidenceError("API health URL does not use the production API origin")
            _require_empty_or_exempted(
                segment,
                "console_errors",
                authorized_exemptions=authorized_exemptions,
            )
            _require_empty_or_exempted(
                segment,
                "network_errors",
                authorized_exemptions=authorized_exemptions,
            )
            mocked_routes = deepcopy(segment["mocked_routes"])
            for route in mocked_routes:
                if not isinstance(route, dict) or route.get("is_business_api") is not True:
                    continue
                exemption_ref = str(route.get("exemption_ref") or "")
                canonical_exemption = (authorized_exemptions or {}).get(
                    exemption_ref
                )
                if not _canonical_mock_exemption_matches(
                    canonical_exemption,
                    route,
                ):
                    raise UIEvidenceError(
                        "business API mock requires a canonical closure exemption"
                    )
                route["canonical_exemption_ref_verified"] = True
            error_exemptions = deepcopy(segment.get("error_exemptions") or [])
            for exemption in error_exemptions:
                if isinstance(exemption, dict):
                    exemption["canonical_exemption_ref_verified"] = True
            record = {
                "capture_id": capture_id,
                "capture_run_ref": capture["capture_run_ref"],
                "test_id": segment["test_id"],
                "obligation_id": segment["obligation_id"],
                "command": segment["command"],
                "exit_code": segment["exit_code"],
                "trace_path": _project_relative_path(
                    delivery, _canonical_artifact_path(delivery, segment["trace"])
                ),
                "screenshot_path": str(
                    _project_relative_path(
                        delivery,
                        _canonical_artifact_path(delivery, segment["screenshot"]),
                    )
                ),
                "console_errors": list(segment.get("console_errors") or []),
                "network_errors": list(segment.get("network_errors") or []),
                "error_exemptions": error_exemptions,
                "semantic_assertions": list(segment["semantic_assertions"]),
                "evidence_path": _project_relative_path(
                    delivery,
                    _canonical_artifact_path(delivery, segment["evidence"]),
                ),
                "evidence_strength": segment["evidence_strength"],
                "acceptance_url": segment["acceptance_url"],
                "api_health_url": segment["api_health_url"],
                "api_health_identity": segment["api_health_identity"],
                "network_probe_summary": {
                    "business_api_request_count": len(business_requests),
                    "html_shell_health_response": _probe_is_html_shell(probe),
                },
                "mocked_routes": mocked_routes,
                "probe_artifact_path": _project_relative_path(delivery, probe_path),
                "segment_metadata_path": _project_relative_path(
                    delivery, metadata_path
                ),
                "executed_actor_roles": list(segment["executed_actor_roles"]),
                "primary_actor_role": segment["primary_actor_role"],
                "actor_identity_evidence": segment_actor,
                "ordinary_path_observed": segment["ordinary_path_observed"],
                "execution_segment_id": segment["execution_segment_id"],
                "test_title_or_step": segment["test_title_or_step"],
            }
            records.append(record)
    return records


def unit_records_from_capture_runs(
    delivery_root: str | Path,
    capture_run_ids: list[str],
    *,
    authorized_exemptions: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return normalized UI unit facts for conformance projection builders."""
    delivery = Path(delivery_root).resolve()
    records: list[dict[str, Any]] = []
    for capture_id in _unique_texts(capture_run_ids, "capture_run_ids"):
        capture = load_capture_run(delivery, capture_id)
        if capture.get("closure_valid") is not True:
            raise UIEvidenceError("iteration capture cannot become formal conformance evidence")
        for unit in capture.get("units", []):
            _require_empty_or_exempted(
                unit,
                "console_errors",
                authorized_exemptions=authorized_exemptions,
            )
            _require_empty_or_exempted(
                unit,
                "network_errors",
                authorized_exemptions=authorized_exemptions,
            )
            records.append(
                {
                    **deepcopy(unit),
                    "capture_id": capture_id,
                    "production_screenshot_path": _project_relative_path(
                        delivery,
                        _canonical_artifact_path(delivery, unit["screenshot"]),
                    ),
                    "task_semantic_snapshot_path": _project_relative_path(
                        delivery,
                        _canonical_artifact_path(
                            delivery, unit["task_semantic_snapshot"]
                        ),
                    ),
                    "production_semantic_snapshot_path": _project_relative_path(
                        delivery,
                        _canonical_artifact_path(
                            delivery, unit["production_semantic_snapshot"]
                        ),
                    ),
                    "production_route": unit["route"],
                }
            )
    return records


def task_conformance_payload_from_capture_runs(
    delivery_root: str | Path,
    capture_run_ids: list[str],
    *,
    implementation_baseline: dict[str, Any],
    planned_task: dict[str, Any],
    authorized_exemptions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Project capture units into the existing task-conformance input schema."""
    bindings = planned_task.get("prototype_bindings") or []
    required = {
        (
            binding.get("surface_id"),
            binding.get("state_id"),
            viewport,
        )
        for binding in bindings
        if isinstance(binding, dict)
        for viewport in binding.get("viewport_classes") or []
    }
    records = []
    for unit in unit_records_from_capture_runs(
        delivery_root,
        capture_run_ids,
        authorized_exemptions=authorized_exemptions,
    ):
        key = (
            unit.get("surface_id"),
            unit.get("state_id"),
            unit.get("viewport_class"),
        )
        if key not in required:
            continue
        computed = unit.get("computed_style") or {}
        records.append(
            {
                "surface_id": key[0],
                "state_id": key[1],
                "viewport_class": key[2],
                "production_route": unit["production_route"],
                "production_screenshot_path": unit["production_screenshot_path"],
                "semantic_snapshot_path": unit["task_semantic_snapshot_path"],
                "computed_style_comparisons": deepcopy(
                    computed.get("comparisons") or []
                ),
                "capture_id": unit["capture_id"],
            }
        )
    if required - {
        (row["surface_id"], row["state_id"], row["viewport_class"])
        for row in records
    }:
        raise UIEvidenceError("capture runs do not cover the current TASK bindings")
    return {
        "implementation_baseline_sha256": implementation_baseline.get(
            "baseline_sha256"
        ),
        "planned_task_hash": planned_task.get("planned_task_hash"),
        "environment_status": "stable",
        "environment_reason": None,
        "records": records,
    }


def production_conformance_payload_from_capture_runs(
    delivery_root: str | Path,
    capture_run_ids: list[str],
    *,
    canonical_prototype: dict[str, Any],
    prototype_contract: dict[str, Any],
    authorized_exemptions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Project current capture units into final production-conformance input."""
    records = []
    for unit in unit_records_from_capture_runs(
        delivery_root,
        capture_run_ids,
        authorized_exemptions=authorized_exemptions,
    ):
        required_fields = (
            "acceptance_url",
            "production_component_refs",
            "region_results",
            "relationship_results",
            "interaction_results",
        )
        missing = [field for field in required_fields if field not in unit]
        if missing:
            raise UIEvidenceError(
                "formal production capture unit missing fields: " + ", ".join(missing)
            )
        records.append(
            {
                "surface_id": unit["surface_id"],
                "state_id": unit["state_id"],
                "viewport_class": unit["viewport_class"],
                "acceptance_url": unit["acceptance_url"],
                "execution_segment_id": unit["execution_segment_id"],
                "production_route": unit["production_route"],
                "production_screenshot_path": unit["production_screenshot_path"],
                "semantic_snapshot_path": unit[
                    "production_semantic_snapshot_path"
                ],
                "production_component_refs": deepcopy(
                    unit["production_component_refs"]
                ),
                "region_results": deepcopy(unit["region_results"]),
                "relationship_results": deepcopy(unit["relationship_results"]),
                "interaction_results": deepcopy(unit["interaction_results"]),
                "capture_id": unit["capture_id"],
            }
        )
    return {
        "prototype_revision": canonical_prototype.get("prototype_revision"),
        "prototype_contract_hash": prototype_contract.get("contract_sha256"),
        "records": records,
    }


def build_closure_manifest(
    delivery_root: str | Path,
    *,
    capture_run_ids: list[str],
    required_units: list[dict[str, Any]],
    required_journeys: list[dict[str, Any]],
    profile: str,
    registry_root_sha256: str | None = None,
    authorized_exemptions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build complete current-capture coverage without trusting gate status fields."""
    if profile not in {"standard", "strict"}:
        raise UIEvidenceError("closure manifest requires standard or strict profile")
    capture_ids = _unique_texts(capture_run_ids, "capture_run_ids")
    captures = [load_capture_run(delivery_root, capture_id) for capture_id in capture_ids]
    capture_profiles = {capture.get("profile") for capture in captures}
    if capture_profiles != {profile}:
        raise UIEvidenceError(
            "closure profile must match every selected capture profile"
        )
    units = unit_records_from_capture_runs(
        delivery_root,
        capture_ids,
        authorized_exemptions=authorized_exemptions,
    )
    journeys = browser_records_from_capture_runs(
        delivery_root,
        capture_ids,
        authorized_exemptions=authorized_exemptions,
    )
    actual_units = {
        (item.get("surface_id"), item.get("state_id"), item.get("viewport_class"))
        for item in units
    }
    expected_units = {
        (item.get("surface_id"), item.get("state_id"), item.get("viewport_class"))
        for item in required_units
    }
    missing_units = sorted(expected_units - actual_units)
    actual_journeys = {
        (item.get("obligation_id"), item.get("test_id")) for item in journeys
    }
    expected_journeys = {
        (item.get("obligation_id"), item.get("test_id"))
        for item in required_journeys
    }
    missing_journeys = sorted(expected_journeys - actual_journeys)
    if missing_units or missing_journeys:
        raise UIEvidenceError(
            "closure capture coverage is incomplete: "
            f"units={missing_units}, journeys={missing_journeys}"
        )
    builds = {capture["build_identity"]["build_digest"] for capture in captures}
    if len(builds) != 1:
        raise UIEvidenceError("closure cannot combine capture runs from different builds")
    execution_identities = {_execution_identity_hash(capture) for capture in captures}
    if len(execution_identities) != 1:
        raise UIEvidenceError(
            "closure cannot combine capture runs from different deployment environments"
        )
    body = {
        "schema_version": "ui-closure-manifest-v1",
        "profile": profile,
        "closure_valid": True,
        "build_digest": next(iter(builds)),
        "execution_identity_sha256": next(iter(execution_identities)),
        "registry_root_sha256": _require_text(
            registry_root_sha256, "registry_root_sha256"
        ),
        "capture_run_ids": sorted(capture_ids),
        "covered_units": [list(item) for item in sorted(actual_units)],
        "covered_journeys": [list(item) for item in sorted(actual_journeys)],
    }
    return {**body, "manifest_sha256": stable_hash(body)}


def append_performance_event(
    delivery_root: str | Path,
    event: dict[str, Any],
) -> dict[str, Any]:
    """Append non-authoritative orchestration telemetry."""
    if not isinstance(event, dict):
        raise UIEvidenceError("performance event must be an object")
    if _TOP_LEVEL_VERDICT_FIELDS.intersection(event):
        raise UIEvidenceError("performance telemetry cannot contain gate verdicts")
    operation = _require_text(event.get("operation"), "performance operation")
    normalized = {
        "schema_version": TELEMETRY_VERSION,
        "operation": operation,
        "wall_ms": _non_negative_number(event.get("wall_ms", 0), "wall_ms"),
        "browser_launches": _non_negative_int(
            event.get("browser_launches", 0), "browser_launches"
        ),
        "capture_units": _non_negative_int(
            event.get("capture_units", 0), "capture_units"
        ),
        "retries": _non_negative_int(event.get("retries", 0), "retries"),
        "reused_artifacts": _non_negative_int(
            event.get("reused_artifacts", 0), "reused_artifacts"
        ),
        "total_artifacts": _non_negative_int(
            event.get("total_artifacts", 0), "total_artifacts"
        ),
        "review_input_tokens": _non_negative_int(
            event.get("review_input_tokens", 0), "review_input_tokens"
        ),
        "raw_artifacts": _non_negative_int(
            event.get("raw_artifacts", 0), "raw_artifacts"
        ),
        "unique_artifacts": _non_negative_int(
            event.get("unique_artifacts", 0), "unique_artifacts"
        ),
        "projection_reuse_count": _non_negative_int(
            event.get("projection_reuse_count", 0), "projection_reuse_count"
        ),
        "validator_wall_ms": _non_negative_number(
            event.get("validator_wall_ms", 0), "validator_wall_ms"
        ),
        "recorded_at": _timestamp(),
    }
    delivery = Path(delivery_root).resolve()
    validate_delivery_evidence_root(delivery)
    path = delivery / "evidence" / "performance-telemetry.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(normalized, sort_keys=True) + "\n")
    return normalized


def performance_report(delivery_root: str | Path) -> dict[str, Any]:
    """Read and aggregate non-blocking UI evidence performance telemetry."""
    delivery = Path(delivery_root).resolve()
    validate_delivery_evidence_root(delivery)
    path = delivery / "evidence" / "performance-telemetry.jsonl"
    events: list[dict[str, Any]] = []
    if path.is_file():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as cause:
                raise UIEvidenceError(
                    f"performance telemetry line {line_number} is invalid"
                ) from cause
            if not isinstance(event, dict) or event.get("schema_version") != TELEMETRY_VERSION:
                raise UIEvidenceError(
                    f"performance telemetry line {line_number} has invalid schema"
                )
            events.append(event)
    total_artifacts = sum(int(item.get("total_artifacts") or 0) for item in events)
    reused = sum(int(item.get("reused_artifacts") or 0) for item in events)
    ingest_events = [item for item in events if item.get("operation") == "capture_ingest"]
    duplicate_ingests = sum(
        1 for item in ingest_events if int(item.get("reused_artifacts") or 0) > 0
    )
    wall_by_operation: dict[str, float] = {}
    for event in events:
        operation = str(event.get("operation") or "unknown")
        wall_by_operation[operation] = wall_by_operation.get(operation, 0.0) + float(
            event.get("wall_ms") or 0
        )
    return {
        "schema_version": TELEMETRY_VERSION,
        "event_count": len(events),
        "wall_ms": sum(float(item.get("wall_ms") or 0) for item in events),
        "browser_launches": sum(
            int(item.get("browser_launches") or 0) for item in events
        ),
        "capture_units": sum(int(item.get("capture_units") or 0) for item in events),
        "retries": sum(int(item.get("retries") or 0) for item in events),
        "reused_artifacts": reused,
        "total_artifacts": total_artifacts,
        "artifact_reuse_ratio": (reused / total_artifacts if total_artifacts else 0.0),
        "review_input_tokens": sum(
            int(item.get("review_input_tokens") or 0) for item in events
        ),
        "raw_artifacts": sum(int(item.get("raw_artifacts") or 0) for item in events),
        "unique_artifacts": sum(
            int(item.get("unique_artifacts") or 0) for item in events
        ),
        "projection_reuse_count": sum(
            int(item.get("projection_reuse_count") or 0) for item in events
        ),
        "validator_wall_ms": sum(
            float(item.get("validator_wall_ms") or 0) for item in events
        ),
        "gate_wall_clock_ms": wall_by_operation,
        "duplicate_capture_ratio": (
            duplicate_ingests / len(ingest_events) if ingest_events else 0.0
        ),
        "telemetry_path": str(path),
    }


def validate_capture_registry(
    delivery_root: str | Path,
    *,
    expected_registry_sha256: str | None = None,
    expected_registry_root_sha256: str | None = None,
) -> dict[str, Any]:
    """Replay registry root, manifest membership, and optional canonical state identity."""
    delivery = Path(delivery_root).resolve()
    validate_delivery_evidence_root(delivery)
    path = delivery / "evidence" / "capture-registry.json"
    if not path.is_file():
        raise UIEvidenceError("capture registry is missing")
    if expected_registry_sha256 and sha256_file(path) != expected_registry_sha256:
        raise UIEvidenceError("capture registry changed since canonical state")
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as cause:
        raise UIEvidenceError("capture registry is invalid") from cause
    if not isinstance(registry, dict) or registry.get("schema_version") != REGISTRY_VERSION:
        raise UIEvidenceError("capture registry schema is invalid")
    body = {
        "schema_version": REGISTRY_VERSION,
        "captures": registry.get("captures") or [],
    }
    computed_root = stable_hash(body)
    if registry.get("registry_root_sha256") != computed_root:
        raise UIEvidenceError("capture registry root hash is invalid")
    if expected_registry_root_sha256 and computed_root != expected_registry_root_sha256:
        raise UIEvidenceError("capture registry root changed since canonical state")
    entries = body["captures"]
    if not isinstance(entries, list):
        raise UIEvidenceError("capture registry entries are invalid")
    registered_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise UIEvidenceError("capture registry entry must be an object")
        capture_id = _validate_capture_id(entry.get("capture_id"))
        if capture_id in registered_ids:
            raise UIEvidenceError("capture registry contains duplicate capture IDs")
        registered_ids.add(capture_id)
        manifest_path = (delivery / str(entry.get("manifest_path") or "")).resolve()
        _require_under(delivery, manifest_path, "registered capture manifest")
        if (
            not manifest_path.is_file()
            or sha256_file(manifest_path) != entry.get("manifest_sha256")
        ):
            raise UIEvidenceError(f"registered capture manifest changed: {capture_id}")
    captures_root = delivery / "evidence" / "captures"
    disk_ids = {
        item.name
        for item in captures_root.iterdir()
        if item.is_dir() and (item / "manifest.json").is_file()
    } if captures_root.is_dir() else set()
    if registered_ids != disk_ids:
        raise UIEvidenceError("capture registry membership does not match capture storage")
    return registry


def run_capture_cli(argv: list[str] | None = None) -> int:
    """Run one project adapter and leave its output in staging for canonical ingest."""
    parser = argparse.ArgumentParser(
        description="Run one Waygate UI evidence adapter without shell interpretation."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--adapter-executable", required=True)
    parser.add_argument("--adapter-arg", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        path = run_capture_adapter(
            project_root=args.project_root,
            plan_path=args.plan,
            adapter_executable=args.adapter_executable,
            adapter_args=args.adapter_arg,
            output_dir=args.output_dir,
        )
    except UIEvidenceError as cause:
        print(f"capture rejected: {cause}", file=os.sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": "staging_capture_ready",
                "canonical_gate_advanced": False,
                "manifest_path": str(path),
            },
            sort_keys=True,
        )
    )
    return 0


def run_performance_report_cli(argv: list[str] | None = None) -> int:
    """Render non-authoritative capture telemetry as JSON."""
    parser = argparse.ArgumentParser(
        description="Report Waygate UI evidence orchestration telemetry."
    )
    parser.add_argument("--delivery-root", required=True)
    args = parser.parse_args(argv)
    try:
        report = performance_report(args.delivery_root)
    except UIEvidenceError as cause:
        print(f"report rejected: {cause}", file=os.sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _normalize_plan_units(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise UIEvidenceError(f"capture plan unit {index} must be an object")
        normalized = {
            field: _require_text(row.get(field), f"capture plan unit {index} {field}")
            for field in ("surface_id", "state_id", "viewport_class")
        }
        key = tuple(normalized.values())
        if key in seen:
            raise UIEvidenceError(f"duplicate capture plan unit: {key}")
        seen.add(key)
        result.append(normalized)
    return result


def _normalize_plan_journeys(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise UIEvidenceError(f"capture plan journey {index} must be an object")
        normalized = {
            field: _require_text(row.get(field), f"capture plan journey {index} {field}")
            for field in ("obligation_id", "test_id")
        }
        key = tuple(normalized.values())
        if key in seen:
            raise UIEvidenceError(f"duplicate capture plan journey: {key}")
        seen.add(key)
        result.append(normalized)
    return result


def _validate_manifest_identity(plan: dict[str, Any], manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != CAPTURE_RUN_VERSION:
        raise UIEvidenceError(f"capture manifest schema must be {CAPTURE_RUN_VERSION}")
    _require_text(manifest.get("capture_run_ref"), "capture manifest capture_run_ref")
    for field_name, plan_field in (
        ("plan_id", "plan_id"),
        ("purpose", "purpose"),
        ("profile", "resolved_profile"),
        ("closure_valid", "closure_valid"),
    ):
        if manifest.get(field_name) != plan.get(plan_field):
            raise UIEvidenceError(f"capture manifest {field_name} does not match plan")
    required_build = plan.get("required_build_digest")
    if required_build and (
        (manifest.get("build_identity") or {}).get("build_digest") != required_build
    ):
        raise UIEvidenceError("capture manifest build digest does not match final build")
    for object_name, fields in _IDENTITY_FIELDS.items():
        value = manifest.get(object_name)
        if not isinstance(value, dict):
            raise UIEvidenceError(f"capture manifest requires {object_name}")
        for field_name in fields:
            field_value = value.get(field_name)
            if field_name == "reduced_motion":
                if not isinstance(field_value, bool):
                    raise UIEvidenceError(
                        "environment_identity reduced_motion must be boolean"
                    )
            else:
                _require_text(field_value, f"{object_name} {field_name}")
    _capture_actor_identities(manifest)
    deployment = manifest["deployment_identity"]
    if not _url_matches_origin(deployment["origin"], deployment["origin"]):
        raise UIEvidenceError("production UI origin must be an HTTP(S) origin")
    if not _url_matches_origin(deployment["api_origin"], deployment["api_origin"]):
        raise UIEvidenceError("production API origin must be an HTTP(S) origin")
    prototype_origin = plan.get("prototype_origin")
    if prototype_origin and _origins_equal(prototype_origin, deployment["origin"]):
        raise UIEvidenceError("prototype and production origins must be distinct")


def _validate_manifest_structure(plan: dict[str, Any], manifest: dict[str, Any]) -> None:
    units = manifest.get("units")
    journeys = manifest.get("journey_segments")
    if not isinstance(units, list) or not isinstance(journeys, list):
        raise UIEvidenceError("capture manifest requires units and journey_segments")
    required_units = {
        (item["surface_id"], item["state_id"], item["viewport_class"])
        for item in plan.get("units", [])
    }
    actual_units: set[tuple[str, str, str]] = set()
    unit_screenshot_hashes: dict[str, tuple[str, str, str]] = {}
    unit_segment_ids: set[str] = set()
    production_origin = manifest["deployment_identity"]["origin"]
    prototype_origin = plan.get("prototype_origin")
    for index, unit in enumerate(units, 1):
        if not isinstance(unit, dict):
            raise UIEvidenceError(f"capture unit {index} must be an object")
        key = tuple(
            _require_text(unit.get(field), f"capture unit {index} {field}")
            for field in ("surface_id", "state_id", "viewport_class")
        )
        if key in actual_units:
            raise UIEvidenceError(f"duplicate capture unit: {key}")
        actual_units.add(key)
        _require_text(unit.get("route"), f"capture unit {index} route")
        unit_origin = _require_text(unit.get("origin"), f"capture unit {index} origin")
        if not _url_matches_origin(unit_origin, production_origin):
            raise UIEvidenceError(
                f"capture unit {index} must use the production origin"
            )
        if prototype_origin and _origins_equal(unit_origin, prototype_origin):
            raise UIEvidenceError(
                f"capture unit {index} cannot use the prototype origin as production"
            )
        acceptance_url = unit.get("acceptance_url")
        if acceptance_url is not None and not _url_matches_origin(
            _require_text(
                acceptance_url, f"capture unit {index} acceptance_url"
            ),
            production_origin,
        ):
            raise UIEvidenceError(
                f"capture unit {index} acceptance URL must use the production origin"
            )
        unit_segment_ids.add(_require_text(
            unit.get("execution_segment_id"),
            f"capture unit {index} execution_segment_id",
        ))
        dpr = unit.get("dpr")
        if isinstance(dpr, bool) or not isinstance(dpr, (int, float)) or dpr <= 0:
            raise UIEvidenceError(f"capture unit {index} dpr must be positive")
        for field_name in ("console_errors", "network_errors"):
            if not isinstance(unit.get(field_name), list):
                raise UIEvidenceError(f"capture unit {index} {field_name} must be a list")
        for field_name in (
            "screenshot",
            "task_semantic_snapshot",
            "production_semantic_snapshot",
        ):
            _validate_artifact_ref(unit.get(field_name), f"capture unit {index} {field_name}")
        screenshot_hash = unit["screenshot"]["sha256"]
        previous = unit_screenshot_hashes.get(screenshot_hash)
        if previous and previous != key:
            raise UIEvidenceError("different visual states cannot reuse one screenshot")
        unit_screenshot_hashes[screenshot_hash] = key
    if manifest.get("closure_valid") is True and not required_units.issubset(actual_units):
        raise UIEvidenceError("formal capture manifest is missing planned UI units")

    required_journeys = {
        (item["obligation_id"], item["test_id"])
        for item in plan.get("journeys", [])
    }
    actual_journeys: set[tuple[str, str]] = set()
    segment_ids: set[str] = set()
    capture_actors = _capture_actor_identities(manifest)
    for index, segment in enumerate(journeys, 1):
        if not isinstance(segment, dict):
            raise UIEvidenceError(f"journey segment {index} must be an object")
        key = tuple(
            _require_text(segment.get(field), f"journey segment {index} {field}")
            for field in ("obligation_id", "test_id")
        )
        actual_journeys.add(key)
        segment_id = _require_text(
            segment.get("execution_segment_id"),
            f"journey segment {index} execution_segment_id",
        )
        if segment_id in segment_ids:
            raise UIEvidenceError("execution segments cannot be reused across journeys")
        segment_ids.add(segment_id)
        for field_name in (
            "command",
            "evidence_strength",
            "acceptance_url",
            "api_health_url",
            "api_health_identity",
            "primary_actor_role",
            "test_title_or_step",
        ):
            _require_text(segment.get(field_name), f"journey segment {index} {field_name}")
        if segment.get("exit_code") != 0:
            raise UIEvidenceError("journey segment exit_code must be 0")
        for field_name in ("console_errors", "network_errors", "mocked_routes"):
            value = segment.get(field_name, [] if field_name != "mocked_routes" else None)
            if not isinstance(value, list):
                raise UIEvidenceError(
                    f"journey segment {index} {field_name} must be a list"
                )
            segment.setdefault(field_name, value)
        for field_name in (
            "trace",
            "screenshot",
            "evidence",
            "probe",
            "segment_metadata",
        ):
            _validate_artifact_ref(
                segment.get(field_name), f"journey segment {index} {field_name}"
            )
        segment_actor = _validate_actor_identity(
            segment.get("actor_identity_evidence"), f"journey segment {index} actor"
        )
        if segment_actor not in capture_actors:
            raise UIEvidenceError(
                f"journey segment {index} actor is not declared by the capture"
            )
        roles = segment.get("executed_actor_roles")
        if not isinstance(roles, list) or not roles or not all(
            isinstance(item, str) and item.strip() for item in roles
        ):
            raise UIEvidenceError(
                f"journey segment {index} executed_actor_roles are required"
            )
        if segment.get("ordinary_path_observed") is not True:
            raise UIEvidenceError("formal journey must observe the ordinary path")
        assertions = segment.get("semantic_assertions")
        if not isinstance(assertions, list) or not assertions:
            raise UIEvidenceError("journey semantic assertions are required")
    if manifest.get("closure_valid") is True and not required_journeys.issubset(
        actual_journeys
    ):
        raise UIEvidenceError("formal capture manifest is missing planned journeys")
    if not unit_segment_ids.issubset(segment_ids):
        raise UIEvidenceError(
            "every UI unit must bind an execution segment from the same capture"
        )


def _validate_artifact_refs(
    project_root: Path,
    staging_root: Path,
    manifest: dict[str, Any],
) -> list[tuple[str, str, dict[str, str], Path]]:
    found: list[tuple[str, str, dict[str, str], Path]] = []
    for collection_name in ("units", "journey_segments"):
        for index, row in enumerate(manifest.get(collection_name, [])):
            owner = f"{collection_name}:{index}"
            for field_name in _ARTIFACT_REF_FIELDS:
                reference = row.get(field_name)
                if reference is None:
                    continue
                _validate_artifact_ref(reference, f"{owner} {field_name}")
                raw_path = Path(reference["path"])
                if raw_path.is_absolute():
                    raise UIEvidenceError("staging artifact paths must be relative")
                source = (project_root / raw_path).resolve()
                _require_under(project_root, source, "staging artifact")
                _require_under(staging_root, source, "staging artifact")
                if not source.is_file():
                    raise UIEvidenceError(f"staging artifact is missing: {reference['path']}")
                if sha256_file(source) != reference["sha256"]:
                    raise UIEvidenceError(
                        f"staging artifact hash mismatch: {reference['path']}"
                    )
                found.append((owner, field_name, reference, source))
    return found


def _load_staging_performance_event(
    staging_root: Path,
    plan: dict[str, Any],
) -> dict[str, Any] | None:
    path = staging_root / "capture-run-telemetry.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as cause:
        raise UIEvidenceError("capture-run telemetry is invalid JSON") from cause
    if not isinstance(value, dict) or value.get("schema_version") != TELEMETRY_VERSION:
        raise UIEvidenceError("capture-run telemetry schema is invalid")
    if value.get("plan_id") != plan.get("plan_id"):
        raise UIEvidenceError("capture-run telemetry plan identity is stale")
    return {
        "operation": "capture_adapter",
        "wall_ms": _non_negative_number(value.get("wall_ms"), "wall_ms"),
        "browser_launches": _non_negative_int(
            value.get("browser_launches"), "browser_launches"
        ),
        "capture_units": _non_negative_int(
            value.get("capture_units"), "capture_units"
        ),
        "retries": _non_negative_int(value.get("retries", 0), "retries"),
        "reused_artifacts": _non_negative_int(
            value.get("reused_artifacts", 0), "reused_artifacts"
        ),
        "total_artifacts": _non_negative_int(
            value.get("total_artifacts", 0), "total_artifacts"
        ),
        "raw_artifacts": _non_negative_int(
            value.get("raw_artifacts", 0), "raw_artifacts"
        ),
        "unique_artifacts": _non_negative_int(
            value.get("unique_artifacts", 0), "unique_artifacts"
        ),
        "projection_reuse_count": _non_negative_int(
            value.get("projection_reuse_count", 0), "projection_reuse_count"
        ),
        "validator_wall_ms": _non_negative_number(
            value.get("validator_wall_ms", 0), "validator_wall_ms"
        ),
    }


def _rewrite_manifest_artifact_refs(
    manifest: dict[str, Any],
    rewritten: dict[tuple[str, str], dict[str, str]],
) -> None:
    for collection_name in ("units", "journey_segments"):
        for index, row in enumerate(manifest.get(collection_name, [])):
            owner = f"{collection_name}:{index}"
            for field_name in _ARTIFACT_REF_FIELDS:
                if (owner, field_name) in rewritten:
                    row[field_name] = rewritten[(owner, field_name)]


def _canonicalize_artifact_identity(manifest: dict[str, Any]) -> None:
    """Remove staging-path accidents from the content-addressed capture identity."""
    for collection_name in ("units", "journey_segments"):
        for row in manifest.get(collection_name, []):
            for field_name in _ARTIFACT_REF_FIELDS:
                reference = row.get(field_name)
                if not isinstance(reference, dict):
                    continue
                suffix = Path(str(reference.get("path") or "")).suffix.lower()
                reference["path"] = (
                    f"artifact://{reference.get('sha256', '')}{suffix}"
                )


def _update_registry(
    delivery_root: Path,
    capture_id: str,
    manifest_path: Path,
    *,
    created: bool,
    transaction_id: str | None = None,
) -> dict[str, Any]:
    registry_path = delivery_root / "evidence" / "capture-registry.json"
    if registry_path.is_file():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as cause:
            raise UIEvidenceError("capture registry is invalid") from cause
    else:
        registry = {"schema_version": REGISTRY_VERSION, "captures": []}
    if not isinstance(registry, dict) or registry.get("schema_version") != REGISTRY_VERSION:
        raise UIEvidenceError("capture registry schema is invalid")
    stored_root = registry.get("registry_root_sha256")
    if stored_root is not None:
        existing_body = {
            "schema_version": REGISTRY_VERSION,
            "captures": registry.get("captures") or [],
        }
        if stored_root != stable_hash(existing_body):
            raise UIEvidenceError("capture registry root hash is invalid")
    entries = list(registry.get("captures") or [])
    by_id = {
        entry.get("capture_id"): entry
        for entry in entries
        if isinstance(entry, dict)
    }
    captures_root = delivery_root / "evidence" / "captures"
    disk_ids = {
        item.name
        for item in captures_root.iterdir()
        if item.is_dir() and (item / "manifest.json").is_file()
    } if captures_root.is_dir() else set()
    registry_ids = set(by_id)
    unregistered = disk_ids - registry_ids - ({capture_id} if created else set())
    missing_on_disk = registry_ids - disk_ids
    if unregistered or missing_on_disk:
        raise UIEvidenceError(
            "capture registry append-only history is inconsistent: "
            f"unregistered={sorted(unregistered)}, missing={sorted(missing_on_disk)}"
        )
    for existing_id, existing_entry in by_id.items():
        existing_manifest = (
            delivery_root / str(existing_entry.get("manifest_path") or "")
        ).resolve()
        _require_under(delivery_root, existing_manifest, "registered capture manifest")
        if (
            not existing_manifest.is_file()
            or sha256_file(existing_manifest) != existing_entry.get("manifest_sha256")
        ):
            raise UIEvidenceError(
                f"registered capture manifest changed: {existing_id}"
            )
    entry = {
        "capture_id": capture_id,
        "manifest_path": str(manifest_path.relative_to(delivery_root)),
        "manifest_sha256": sha256_file(manifest_path),
    }
    if capture_id in by_id and by_id[capture_id] != entry:
        raise UIEvidenceError("capture registry entry is immutable")
    if capture_id not in by_id:
        entries.append(entry)
    registry_body = {
        "schema_version": REGISTRY_VERSION,
        "captures": sorted(entries, key=lambda item: item["capture_id"]),
    }
    registry = {**registry_body, "registry_root_sha256": stable_hash(registry_body)}
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = registry_path.with_name(
        registry_path.name
        + ".tmp-"
        + (
            _validate_transaction_id(transaction_id)
            if transaction_id is not None
            else uuid.uuid4().hex
        )
    )
    _write_fsynced_text(
        temporary,
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
    )
    os.replace(temporary, registry_path)
    _fsync_directory(registry_path.parent)
    return {
        "registry_path": str(registry_path),
        "registry_sha256": sha256_file(registry_path),
        "registry_root_sha256": registry["registry_root_sha256"],
        "registry_created_entry": created,
    }


def _validate_canonical_artifacts(delivery_root: Path, manifest: dict[str, Any]) -> None:
    for collection_name in ("units", "journey_segments"):
        for row in manifest.get(collection_name, []):
            for field_name in _ARTIFACT_REF_FIELDS:
                reference = row.get(field_name)
                if reference is None:
                    continue
                path = _canonical_artifact_path(delivery_root, reference)
                if sha256_file(path) != reference.get("sha256"):
                    raise UIEvidenceError("canonical capture artifact hash mismatch")


def _validate_existing_registry_identity(
    delivery_root: Path,
    *,
    expected_registry_sha256: str | None,
    expected_registry_root_sha256: str | None,
) -> None:
    if expected_registry_sha256 is None and expected_registry_root_sha256 is None:
        return
    validate_capture_registry(
        delivery_root,
        expected_registry_sha256=expected_registry_sha256,
        expected_registry_root_sha256=expected_registry_root_sha256,
    )


def _execution_identity(value: dict[str, Any]) -> dict[str, Any]:
    return {
        field_name: deepcopy(value.get(field_name) or {})
        for field_name in (
            "source_identity",
            "build_identity",
            "deployment_identity",
            "environment_identity",
            "collector_identity",
        )
    }


def _execution_identity_hash(value: dict[str, Any]) -> str:
    return stable_hash(_execution_identity(value))


def _canonical_artifact_path(delivery_root: Path, reference: dict[str, Any]) -> Path:
    _validate_artifact_ref(reference, "canonical artifact")
    path = (delivery_root / reference["path"]).resolve()
    _require_under(delivery_root, path, "canonical artifact")
    if not path.is_file():
        raise UIEvidenceError(f"canonical capture artifact is missing: {reference['path']}")
    return path


def _validate_artifact_ref(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise UIEvidenceError(f"{label} must be an artifact reference")
    _require_text(value.get("path"), f"{label} path")
    digest = _require_text(value.get("sha256"), f"{label} sha256")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise UIEvidenceError(f"{label} sha256 must be lowercase SHA-256")


def _validate_actor_identity(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise UIEvidenceError(f"{label} identity must be an object")
    normalized = {
        field_name: _require_text(value.get(field_name), f"{label} {field_name}")
        for field_name in (
            "role",
            "user_id",
            "session_id",
            "backend_identity_sha256",
        )
    }
    backend_hash = normalized["backend_identity_sha256"]
    if len(backend_hash) != 64 or any(
        character not in "0123456789abcdef" for character in backend_hash
    ):
        raise UIEvidenceError(f"{label} backend_identity_sha256 must be SHA-256")
    return normalized


def _capture_actor_identities(value: dict[str, Any]) -> list[dict[str, str]]:
    raw = value.get("actor_identities")
    if raw is None:
        raw = [value.get("actor_identity")]
    if not isinstance(raw, list) or not raw:
        raise UIEvidenceError("capture requires one or more actor identities")
    actors = [
        _validate_actor_identity(item, f"capture actor {index}")
        for index, item in enumerate(raw, 1)
    ]
    identities = {
        (item["role"], item["user_id"], item["session_id"])
        for item in actors
    }
    if len(identities) != len(actors):
        raise UIEvidenceError("capture actor identities must be unique")
    return actors


def _require_empty_or_exempted(
    value: dict[str, Any],
    field_name: str,
    *,
    authorized_exemptions: dict[str, dict[str, Any]] | None = None,
) -> None:
    errors = value.get(field_name)
    if not isinstance(errors, list):
        raise UIEvidenceError(f"{field_name} must be a list")
    if not errors:
        return
    exemptions = value.get("error_exemptions")
    if not isinstance(exemptions, list) or not exemptions:
        raise UIEvidenceError(f"non-empty {field_name} requires structured exemptions")
    accepted: set[str] = set()
    for exemption in exemptions:
        if not isinstance(exemption, dict) or exemption.get("field") != field_name:
            continue
        error_hash = str(exemption.get("error_sha256") or "")
        canonical = (authorized_exemptions or {}).get(
            str(exemption.get("exemption_ref") or "")
        )
        if _canonical_error_exemption_matches(canonical, field_name, error_hash):
            accepted.add(error_hash)
    for error in errors:
        if stable_hash(error) not in accepted:
            raise UIEvidenceError(f"unexempted {field_name} entry")


def _canonical_error_exemption_matches(
    exemption: Any,
    field_name: str,
    error_hash: str,
) -> bool:
    if not isinstance(exemption, dict) or exemption.get("allows_closure") is not True:
        return False
    if exemption.get("exemption_type") != field_name:
        return False
    if exemption.get("object_id") != f"{field_name}:{error_hash}":
        return False
    return _scope_allows(exemption.get("valid_scope"), {field_name})


def _canonical_mock_exemption_matches(exemption: Any, route: dict[str, Any]) -> bool:
    if not isinstance(exemption, dict) or exemption.get("allows_closure") is not True:
        return False
    if exemption.get("exemption_type") != "business_api_mock":
        return False
    identity = {
        field_name: route.get(field_name)
        for field_name in (
            "mechanism",
            "pattern",
            "classification",
            "is_business_api",
        )
    }
    if exemption.get("object_id") != "mocked_route:" + stable_hash(identity):
        return False
    return _scope_allows(
        exemption.get("valid_scope"),
        {"business_api_mock"},
    )


def _scope_allows(value: Any, accepted: set[str]) -> bool:
    if isinstance(value, str):
        scopes = {item.strip() for item in value.split(",") if item.strip()}
    elif isinstance(value, list):
        scopes = {str(item).strip() for item in value if str(item).strip()}
    else:
        return False
    return bool(scopes.intersection(accepted))


def _validate_probe_against_segment(
    probe: Any,
    segment: dict[str, Any],
    deployment: dict[str, Any],
    actor: dict[str, str],
    capture_run_ref: str,
) -> list[dict[str, Any]]:
    if not isinstance(probe, dict):
        raise UIEvidenceError("journey probe must contain an object")
    for field_name in ("acceptance_url", "api_health_url", "api_health_identity"):
        if probe.get(field_name) != segment.get(field_name):
            raise UIEvidenceError(f"journey probe {field_name} does not match segment")
    if probe.get("capture_run_ref") != capture_run_ref:
        raise UIEvidenceError("journey probe capture identity does not match capture")
    health_status = probe.get("health_response_status")
    if isinstance(health_status, bool) or not isinstance(health_status, int) or not 200 <= health_status < 300:
        raise UIEvidenceError("API health probe must return a successful HTTP status")
    if _probe_is_html_shell(probe):
        raise UIEvidenceError("API health probe cannot return an HTML shell")
    actor_response = probe.get("actor_identity_response")
    if not isinstance(actor_response, dict):
        raise UIEvidenceError("probe must include backend-observed actor identity")
    expected_actor = {
        field_name: actor[field_name]
        for field_name in ("role", "user_id", "session_id")
    }
    if {
        field_name: actor_response.get(field_name)
        for field_name in expected_actor
    } != expected_actor:
        raise UIEvidenceError("probe actor identity does not match browser actor")
    if stable_hash(actor_response) != actor["backend_identity_sha256"]:
        raise UIEvidenceError("probe actor identity hash does not match browser actor")
    business_requests = probe.get("business_api_requests")
    if not isinstance(business_requests, list) or not business_requests:
        raise UIEvidenceError("formal journey capture requires business API requests")
    normalized: list[dict[str, Any]] = []
    for index, request in enumerate(business_requests, 1):
        if not isinstance(request, dict):
            raise UIEvidenceError(f"business API request {index} must be an object")
        method = str(request.get("method") or "").upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            raise UIEvidenceError(f"business API request {index} method is invalid")
        if not _url_matches_origin(request.get("url"), deployment.get("api_origin")):
            raise UIEvidenceError(f"business API request {index} does not use API origin")
        if request.get("source") != "network":
            raise UIEvidenceError(f"business API request {index} must be network-observed")
        status = request.get("status")
        if isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599:
            raise UIEvidenceError(f"business API request {index} status is invalid")
        expected_status = request.get("expected_status")
        if expected_status is not None and expected_status != status:
            raise UIEvidenceError(
                f"business API request {index} did not return its expected status"
            )
        normalized.append(request)
    return normalized


def _validate_segment_metadata(
    value: Any,
    *,
    segment: dict[str, Any],
    actor: dict[str, str],
    capture_run_ref: str,
) -> None:
    expected = {
        "schema_version": "ui-journey-segment-metadata-v1",
        "capture_run_ref": capture_run_ref,
        "execution_segment_id": segment.get("execution_segment_id"),
        "actor_identity_sha256": stable_hash(actor),
        "screenshot_sha256": (segment.get("screenshot") or {}).get("sha256"),
        "trace_sha256": (segment.get("trace") or {}).get("sha256"),
        "evidence_sha256": (segment.get("evidence") or {}).get("sha256"),
        "probe_sha256": (segment.get("probe") or {}).get("sha256"),
    }
    if value != expected:
        raise UIEvidenceError(
            "journey segment artifacts do not share capture, segment, and actor identity"
        )


def _validate_capture_id(value: Any) -> str:
    capture_id = _require_text(value, "capture_id")
    digest = capture_id.removeprefix("capture-")
    if not capture_id.startswith("capture-") or len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise UIEvidenceError("capture_id must be content-addressed")
    return capture_id


def _probe_is_html_shell(probe: dict[str, Any]) -> bool:
    content_type = str(probe.get("health_response_content_type", "")).lower()
    body = str(probe.get("health_response_body_sample", "")).strip().lower()
    return "text/html" in content_type or body.startswith("<html") or body.startswith(
        "<!doctype html"
    )


def _url_matches_origin(value: Any, origin: Any) -> bool:
    try:
        actual = urlsplit(str(value))
        expected = urlsplit(str(origin))
    except ValueError:
        return False
    return bool(
        actual.scheme in {"http", "https"}
        and actual.scheme == expected.scheme
        and actual.hostname
        and expected.hostname
        and actual.hostname.lower() == expected.hostname.lower()
        and (actual.port or (443 if actual.scheme == "https" else 80))
        == (expected.port or (443 if expected.scheme == "https" else 80))
    )


def _origins_equal(first: Any, second: Any) -> bool:
    first_text = str(first or "").strip()
    second_text = str(second or "").strip()
    if first_text.startswith("file:") or second_text.startswith("file:"):
        return first_text.rstrip("/") == second_text.rstrip("/")
    return _url_matches_origin(first_text, second_text) and _url_matches_origin(
        second_text, first_text
    )


def _project_relative_path(delivery_root: Path, path: Path) -> str:
    """Return project-relative artifact paths for existing validator APIs."""
    project_root = delivery_root.parents[3]
    try:
        return str(path.relative_to(project_root))
    except ValueError as cause:
        raise UIEvidenceError("canonical artifact is outside the project root") from cause


def _unique_texts(values: Any, label: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise UIEvidenceError(f"{label} must be a non-empty list")
    result: list[str] = []
    for value in values:
        text = _require_text(value, label)
        if text in result:
            raise UIEvidenceError(f"{label} contains duplicate values")
        result.append(text)
    return result


def _require_under(root: Path, path: Path, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as cause:
        raise UIEvidenceError(f"{label} escapes its allowed root") from cause


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UIEvidenceError(f"{label} is required")
    return value.strip()


def _non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise UIEvidenceError(f"{label} must be a non-negative integer")
    return value


def _non_negative_number(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise UIEvidenceError(f"{label} must be a non-negative number")
    return value


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _validate_transaction_id(value: Any) -> str:
    transaction_id = _require_text(value, "capture transaction id")
    token = transaction_id.removeprefix("ui-capture-tx-")
    if transaction_id.startswith("ui-capture-tx-"):
        transaction_id = token
    if len(transaction_id) != 32 or any(
        character not in "0123456789abcdef" for character in transaction_id
    ):
        raise UIEvidenceError("capture transaction id must be a UUID hex token")
    return transaction_id


def validate_delivery_evidence_root(delivery_root: str | Path) -> Path:
    """Reject canonical evidence paths that traverse a symlink or leave delivery."""
    delivery = Path(delivery_root).resolve()
    evidence = delivery / "evidence"
    current = evidence
    while current != delivery:
        if current.is_symlink():
            raise UIEvidenceError("canonical delivery evidence path cannot be a symlink")
        current = current.parent
    resolved = evidence.resolve()
    _require_under(delivery, resolved, "canonical delivery evidence root")
    for child_name in ("captures", "transactions"):
        child = evidence / child_name
        if child.is_symlink():
            raise UIEvidenceError(
                f"canonical delivery evidence {child_name} path cannot be a symlink"
            )
        _require_under(delivery, child.resolve(), f"canonical {child_name} root")
    for filename in ("capture-registry.json", "performance-telemetry.jsonl"):
        candidate = evidence / filename
        if candidate.is_symlink():
            raise UIEvidenceError(
                f"canonical delivery evidence file cannot be a symlink: {filename}"
            )
        _require_under(delivery, candidate.resolve(), f"canonical {filename}")
    return evidence


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(path, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _fsync_file(path: Path) -> None:
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def _write_fsynced_text(path: Path, value: str) -> None:
    with path.open("w", encoding="utf-8") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _forbidden_verdict_paths(value: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}"
            if key in _TOP_LEVEL_VERDICT_FIELDS:
                found.append(path)
            found.extend(_forbidden_verdict_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_forbidden_verdict_paths(item, f"{prefix}[{index}]"))
    return found
