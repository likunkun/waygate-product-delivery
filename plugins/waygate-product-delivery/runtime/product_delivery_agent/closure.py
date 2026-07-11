"""Formal feature closure artifact validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from product_delivery_agent.gatekeeper import (
    CANONICAL_SCHEMA_VERSION,
    CANONICAL_VALIDATOR,
    PLUGIN_VERSION,
)


class ClosureGateError(RuntimeError):
    """Raised when a formal closure artifact is not acceptable."""


INTEGRITY_FIELDS = (
    "secret_values_recorded",
    "controller_session_modified",
    "created_fake_controller_state",
)


def validate_feature_closure(
    artifact: dict[str, Any],
    *,
    expected_matrix_range: str,
    expected_latest_test_case: str,
    required_commands: list[str],
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate a version-specific formal closure artifact."""
    if not artifact or "status" not in artifact:
        raise ClosureGateError("version-specific closure artifact is required")

    _require_equal(artifact, "status", "passed")
    _require_equal(artifact, "passed", True)
    _require_equal(artifact, "canonical_validator", CANONICAL_VALIDATOR)
    _require_equal(
        artifact,
        "canonical_schema_version",
        CANONICAL_SCHEMA_VERSION,
    )
    _require_equal(artifact, "plugin_version", PLUGIN_VERSION)
    if not _has_value(artifact.get("closure_flag")):
        raise ClosureGateError("closure_flag is required")
    _require_equal(artifact, "matrix_range", expected_matrix_range)
    _require_equal(artifact, "latest_test_case", expected_latest_test_case)
    _require_non_empty_list(artifact, "e2e_covered_tc")
    _require_non_empty_list(artifact, "covered_user_stories")
    _require_non_empty_list(artifact, "covered_journeys")
    _validate_artifact_metadata(artifact, project_root=project_root)
    _validate_high_risk_subresults(artifact)
    _validate_negative_scope_guard(artifact)
    _validate_commands(artifact, required_commands)
    _validate_integrity(artifact)
    _validate_supersession(artifact)
    return {
        **artifact,
        "status": "passed",
        "passed": True,
    }


def render_feature_closure(closure: dict[str, Any]) -> str:
    """Render a formal closure artifact as Markdown."""
    lines = [
        "# Feature Closure Artifact",
        "",
        "Status: passed",
        "",
        f"Closure Flag: {closure['closure_flag']}",
        f"Matrix Range: {closure['matrix_range']}",
        f"Latest Test Case: {closure['latest_test_case']}",
        "",
        "## E2E Covered TC",
        *_bullets(closure["e2e_covered_tc"]),
        "",
        "## Covered User Stories",
        *_bullets(closure["covered_user_stories"]),
        "",
        "## Covered Journeys",
        *_bullets(closure["covered_journeys"]),
        "",
        "## Artifact Metadata",
        f"- Artifact Root: {closure['artifact_root']}",
        f"- Artifact Generation Command: {closure['artifact_generation_command']}",
        "## E2E Evidence Paths",
        *_bullets(closure["e2e_evidence_paths"]),
        "",
        "## Negative Scope Guard",
        f"- {closure['negative_scope_guard_result']}",
        "",
        "## Required Commands",
    ]
    lines.extend(
        f"- {record['command']}: output recorded"
        for record in closure["required_commands"]
    )
    prototype_conformance = closure.get("prototype_conformance")
    if isinstance(prototype_conformance, dict):
        lines.extend(
            [
                "",
                "## Prototype Conformance",
                f"- Prototype Revision: {prototype_conformance.get('prototype_revision', '')}",
                f"- Prototype Hash: {prototype_conformance.get('prototype_sha256', '')}",
                f"- Contract Hash: {prototype_conformance.get('prototype_contract_sha256', '')}",
                f"- Evidence Hash: {prototype_conformance.get('conformance_evidence_sha256', '')}",
                f"- UI Review Hash: {prototype_conformance.get('ui_conformance_review_sha256', '')}",
                "",
                "### Covered Surfaces",
                *_bullets(prototype_conformance.get("covered_surface_ids", [])),
                "",
                "### Covered Regions",
                *_bullets(prototype_conformance.get("covered_region_ids", [])),
            ]
        )
    lines.extend(
        [
            "",
            "## Integrity",
            f"- secret_values_recorded={closure['secret_values_recorded']}",
            f"- controller_session_modified={closure['controller_session_modified']}",
            f"- created_fake_controller_state={closure['created_fake_controller_state']}",
            "",
        ]
    )
    return "\n".join(lines)


def _require_equal(artifact: dict[str, Any], field_name: str, expected: Any) -> None:
    if artifact.get(field_name) != expected:
        raise ClosureGateError(f"{field_name} must be {expected!r}")


def _require_non_empty_list(artifact: dict[str, Any], field_name: str) -> None:
    value = artifact.get(field_name)
    if not isinstance(value, list) or not value:
        raise ClosureGateError(f"{field_name} is required")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ClosureGateError(f"{field_name} must contain non-empty strings")


def _validate_high_risk_subresults(artifact: dict[str, Any]) -> None:
    value = artifact.get("high_risk_gate_subresults")
    if not isinstance(value, dict) or not value:
        raise ClosureGateError("high_risk_gate_subresults are required")
    failed = [name for name, result in value.items() if result != "passed"]
    if failed:
        raise ClosureGateError(
            "high_risk_gate_subresults failed: " + ", ".join(failed)
        )


def _validate_artifact_metadata(
    artifact: dict[str, Any],
    *,
    project_root: str | Path | None = None,
) -> None:
    if not _has_value(artifact.get("artifact_root")):
        raise ClosureGateError("artifact_root is required")
    if not _has_value(artifact.get("artifact_generation_command")):
        raise ClosureGateError("artifact_generation_command is required")
    _require_non_empty_list(artifact, "e2e_evidence_paths")
    if project_root is not None:
        root = Path(project_root)
        missing = [
            path
            for path in artifact["e2e_evidence_paths"]
            if not (root / path).is_file()
        ]
        if missing:
            raise ClosureGateError(
                "e2e evidence path missing: " + ", ".join(missing)
            )


def _validate_negative_scope_guard(artifact: dict[str, Any]) -> None:
    if artifact.get("negative_scope_guard_result") != "passed":
        raise ClosureGateError("negative scope guard must pass")


def _validate_commands(
    artifact: dict[str, Any],
    required_commands: list[str],
) -> None:
    commands = artifact.get("required_commands")
    if not isinstance(commands, list) or not commands:
        raise ClosureGateError("required_commands are required")
    by_command = {
        record.get("command"): record
        for record in commands
        if isinstance(record, dict)
    }
    for command in required_commands:
        record = by_command.get(command)
        if not record:
            raise ClosureGateError(f"required command missing: {command}")
        if not _has_value(record.get("output")):
            raise ClosureGateError(f"command output missing: {command}")
        if not _command_succeeded_or_structurally_skipped(record):
            raise ClosureGateError(f"command exit_code missing or failed: {command}")


def _validate_integrity(artifact: dict[str, Any]) -> None:
    for field_name in INTEGRITY_FIELDS:
        value = artifact.get(field_name)
        if not isinstance(value, bool):
            raise ClosureGateError(f"{field_name} must be a boolean")
        if value is not False:
            raise ClosureGateError(f"{field_name} must be false")


def _validate_supersession(artifact: dict[str, Any]) -> None:
    if artifact.get("superseded_by") and not _has_value(artifact.get("triggering_cr")):
        raise ClosureGateError("superseded closure must link to triggering CR")


def _has_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _command_succeeded_or_structurally_skipped(record: dict[str, Any]) -> bool:
    if record.get("exit_code") == 0:
        return True
    if record.get("status") != "skipped":
        return False
    return all(
        _has_value(record.get(field_name))
        for field_name in ("skip_reason", "skip_scope", "approved_by")
    )


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]
