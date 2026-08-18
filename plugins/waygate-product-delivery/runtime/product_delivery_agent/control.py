"""Strict JSON lifecycle control for Waygate Product Delivery."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from product_delivery_agent.artifact_protocol import lifecycle_state_hash, load_state
from product_delivery_agent.artifact_store import (
    detect_legacy_layout,
    validate_current_artifact_identity,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError

CONTROL_SCHEMA_VERSION = "v1"
ABANDON_TOKEN_TTL_MINUTES = 30

EXIT_OK = 0
EXIT_PARAM_ERROR = 2
EXIT_IDENTITY_CONFLICT = 3
EXIT_CONFIRMATION_MISSING = 4
EXIT_GATE_BLOCKED = 5
EXIT_RUNTIME_ERROR = 6

ACTIONS = frozenset(
    {
        "inspect",
        "status",
        "start",
        "pause",
        "resume",
        "prepare_abandon",
        "abandon",
        "close",
    }
)
START_MODES = frozenset({"resume_or_create", "resume_only", "create_only"})
REVIEW_MODES_IF_CREATED = frozenset(
    {
        "pending_selection",
        "spawned_subagents_authorized",
        "role_simulation_allowed",
    }
)


class ControlError(RuntimeError):
    """A stable, user-facing lifecycle control failure."""

    def __init__(self, message: str, *, exit_code: int = EXIT_PARAM_ERROR):
        super().__init__(message)
        self.exit_code = exit_code


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ControlError(f"{field} is required")
    return value.strip()


def validate_request(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate the exact v1 request shape; unknown fields fail closed."""
    if not isinstance(raw, dict):
        raise ControlError("request must be a JSON object")
    if raw.get("schema_version") != CONTROL_SCHEMA_VERSION:
        raise ControlError(f"schema_version must be '{CONTROL_SCHEMA_VERSION}'")
    action = raw.get("action")
    if action not in ACTIONS:
        raise ControlError(f"action must be one of {sorted(ACTIONS)}")

    allowed = {"schema_version", "action", "dry_run"}
    if action == "inspect":
        allowed.add("feature_slug")
    elif action == "start":
        allowed.update(
            {
                "feature_slug",
                "start_mode",
                "review_mode_if_created",
                "expected_delivery_id",
                "idempotency_key",
            }
        )
    elif action in {"pause", "resume", "prepare_abandon", "abandon", "close"}:
        allowed.add("delivery_id")
    if action == "prepare_abandon":
        allowed.add("reason")
    if action == "abandon":
        allowed.add("confirmation_token")

    extras = sorted(set(raw) - allowed)
    if extras:
        raise ControlError(f"unknown fields: {extras}")
    dry_run = raw.get("dry_run", False)
    if not isinstance(dry_run, bool):
        raise ControlError("dry_run must be boolean")

    result: dict[str, Any] = {
        "schema_version": CONTROL_SCHEMA_VERSION,
        "action": action,
        "dry_run": dry_run,
    }
    if action == "inspect" and raw.get("feature_slug") is not None:
        result["feature_slug"] = _required_string(raw["feature_slug"], "feature_slug")
    if action == "start":
        result["feature_slug"] = _required_string(raw.get("feature_slug"), "feature_slug")
        start_mode = raw.get("start_mode", "resume_or_create")
        if start_mode not in START_MODES:
            raise ControlError(f"start_mode must be one of {sorted(START_MODES)}")
        result["start_mode"] = start_mode
        review_mode = raw.get("review_mode_if_created", "pending_selection")
        if review_mode not in REVIEW_MODES_IF_CREATED:
            raise ControlError(
                "review_mode_if_created must be one of "
                f"{sorted(REVIEW_MODES_IF_CREATED)}"
            )
        result["review_mode_if_created"] = review_mode
        for field in ("expected_delivery_id", "idempotency_key"):
            if raw.get(field) is not None:
                result[field] = _required_string(raw[field], field)

    if action == "resume":
        result["delivery_id"] = _required_string(raw.get("delivery_id"), "delivery_id")
    elif action in {"pause", "close"} and raw.get("delivery_id") is not None:
        result["delivery_id"] = _required_string(raw["delivery_id"], "delivery_id")
    elif action in {"prepare_abandon", "abandon"}:
        result["delivery_id"] = _required_string(raw.get("delivery_id"), "delivery_id")

    if action == "prepare_abandon":
        result["reason"] = _required_string(raw.get("reason"), "reason")
    if action == "abandon":
        token = raw.get("confirmation_token")
        if not isinstance(token, str) or not token.strip():
            raise ControlError(
                "confirmation_token is required for abandon",
                exit_code=EXIT_CONFIRMATION_MISSING,
            )
        result["confirmation_token"] = token.strip()
    return result


def _control_state_hash(state: dict[str, Any]) -> str:
    return lifecycle_state_hash(state)


def _response(
    action: str,
    result: str,
    state: dict[str, Any],
    *,
    created_new_delivery: bool = False,
    warnings: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    feature_slug = state.get("feature_slug")
    delivery_id = state.get("delivery_id")
    current_root = None
    if feature_slug and delivery_id:
        current_root = (
            f".product-delivery/deliveries/{feature_slug}/{delivery_id}"
        )
    response = {
        "schema_version": CONTROL_SCHEMA_VERSION,
        "action": action,
        "result": result,
        "feature_slug": feature_slug,
        "delivery_id": delivery_id,
        "created_new_delivery": created_new_delivery,
        "current_stage": state.get("stage"),
        "next_gate": state.get("next_gate"),
        "current_root": current_root,
        "warnings": list(warnings or []),
    }
    if extra:
        response.update(extra)
    return response


def _assert_target_delivery(state: dict[str, Any], delivery_id: str) -> None:
    if state.get("delivery_id") != delivery_id:
        raise ControlError(
            f"delivery_id={delivery_id} does not match current={state.get('delivery_id')}",
            exit_code=EXIT_IDENTITY_CONFLICT,
        )


def _generate_abandon_token(state: dict[str, Any], reason: str) -> dict[str, Any]:
    delivery_id = _required_string(state.get("delivery_id"), "current delivery_id")
    feature_slug = _required_string(state.get("feature_slug"), "current feature_slug")
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ABANDON_TOKEN_TTL_MINUTES
    )
    material = {
        "action": "abandon",
        "delivery_id": delivery_id,
        "feature_slug": feature_slug,
        "state_hash": _control_state_hash(state),
        "expires_at": expires_at.isoformat(),
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        **material,
        "confirmation_token": f"ABANDON-{delivery_id}-{digest[:24]}",
        "reason": reason,
    }


def _verify_abandon_token(
    state: dict[str, Any], token: str, pending_tokens: dict[str, Any]
) -> None:
    record = pending_tokens.get(token)
    if not isinstance(record, dict):
        raise ControlError(
            "confirmation_token does not match a pending abandon request",
            exit_code=EXIT_CONFIRMATION_MISSING,
        )
    if record.get("action") != "abandon":
        raise ControlError(
            "confirmation_token is not bound to abandon",
            exit_code=EXIT_CONFIRMATION_MISSING,
        )
    try:
        expires_at = datetime.fromisoformat(str(record.get("expires_at") or ""))
    except ValueError as exc:
        raise ControlError(
            "confirmation_token expiry is malformed",
            exit_code=EXIT_CONFIRMATION_MISSING,
        ) from exc
    if datetime.now(timezone.utc) > expires_at:
        raise ControlError(
            "confirmation_token has expired",
            exit_code=EXIT_CONFIRMATION_MISSING,
        )
    if record.get("delivery_id") != state.get("delivery_id"):
        raise ControlError(
            "confirmation_token delivery_id does not match current delivery",
            exit_code=EXIT_IDENTITY_CONFLICT,
        )
    if record.get("feature_slug") != state.get("feature_slug"):
        raise ControlError(
            "confirmation_token feature_slug does not match current delivery",
            exit_code=EXIT_IDENTITY_CONFLICT,
        )
    if record.get("state_hash") != _control_state_hash(state):
        raise ControlError(
            "state has changed since prepare_abandon; request a new token",
            exit_code=EXIT_CONFIRMATION_MISSING,
        )


def dispatch(project_root: str | Path, request: dict[str, Any]) -> dict[str, Any]:
    """Validate and execute one strict lifecycle request."""
    project_root = Path(project_root)
    validated = validate_request(request)
    action = validated["action"]
    dry_run = validated["dry_run"]
    workflow = ProductDeliveryWorkflow(project_root)

    if action == "inspect":
        inspection = workflow.inspect_startup_request(
            feature_slug=validated.get("feature_slug")
        )
        state = load_state(project_root)
        migration = detect_legacy_layout(project_root)
        return {
            "schema_version": CONTROL_SCHEMA_VERSION,
            "action": "inspect",
            "result": "reported",
            "startup_action": inspection["action"],
            "current_feature_slug": inspection.get("current_feature_slug"),
            "current_delivery_id": inspection.get("current_delivery_id"),
            "review_authorization_reusable": inspection.get(
                "review_authorization_reusable", False
            ),
            "migration_required": migration["migration_required"],
            "legacy_files": migration["legacy_files"],
            "identity_blockers": validate_current_artifact_identity(
                project_root, state
            ),
            "current_stage": state.get("stage"),
            "next_gate": state.get("next_gate"),
            "warnings": [],
        }

    if action == "status":
        state = load_state(project_root)
        return _response(
            "status",
            "reported",
            state,
            warnings=validate_current_artifact_identity(project_root, state),
        )

    if action == "start":
        return _dispatch_start(project_root, workflow, validated)

    state = load_state(project_root)
    if not state:
        raise ControlError("no current delivery", exit_code=EXIT_IDENTITY_CONFLICT)
    if validated.get("delivery_id"):
        _assert_target_delivery(state, validated["delivery_id"])

    if action == "pause":
        if dry_run:
            return _response("pause", "dry_run", state)
        return _response("pause", "paused", workflow.pause_delivery())

    if action == "resume":
        if dry_run:
            return _response("resume", "dry_run", state)
        return _response("resume", "resumed", workflow.resume_delivery())

    if action == "prepare_abandon":
        token_info = _generate_abandon_token(state, validated["reason"])
        if not dry_run:
            workflow.record_pending_abandon_token(token_info)
        return {
            "schema_version": CONTROL_SCHEMA_VERSION,
            "action": "prepare_abandon",
            "result": "token_issued" if not dry_run else "dry_run",
            "confirmation_token": token_info["confirmation_token"],
            "expires_at": token_info["expires_at"],
            "delivery_id": token_info["delivery_id"],
            "feature_slug": token_info["feature_slug"],
            "dry_run": dry_run,
            "warnings": [],
        }

    if action == "abandon":
        _verify_abandon_token(
            state,
            validated["confirmation_token"],
            state.get("pending_abandon_tokens") or {},
        )
        if dry_run:
            return _response("abandon", "dry_run", state)
        return _response(
            "abandon",
            "abandoned",
            workflow.abandon_delivery(validated["confirmation_token"]),
        )

    if action == "close":
        if not _closure_is_passed(state):
            raise ControlError(
                "canonical closure has not passed; close is not allowed",
                exit_code=EXIT_GATE_BLOCKED,
            )
        if dry_run:
            return _response("close", "dry_run", state)
        return _response("close", "closed", workflow.close_delivery())

    raise ControlError(f"unhandled action: {action}")


def _dispatch_start(
    project_root: Path,
    workflow: ProductDeliveryWorkflow,
    request: dict[str, Any],
) -> dict[str, Any]:
    feature_slug = request["feature_slug"]
    start_mode = request["start_mode"]
    inspection = workflow.inspect_startup_request(feature_slug=feature_slug)
    startup_action = inspection["action"]

    if startup_action == "blocked_by_active_delivery":
        raise ControlError(
            "a different active delivery exists; close or abandon it first",
            exit_code=EXIT_IDENTITY_CONFLICT,
        )
    if startup_action == "legacy_recovery_required":
        raise ControlError(
            "active delivery is legacy_unverified; recover it before starting",
            exit_code=EXIT_GATE_BLOCKED,
        )
    if start_mode == "resume_only" and startup_action != "resume_current_delivery":
        raise ControlError(
            "resume_only requested but no resumable delivery was found",
            exit_code=EXIT_IDENTITY_CONFLICT,
        )
    if start_mode == "create_only" and startup_action == "resume_current_delivery":
        raise ControlError(
            "create_only requested but this feature already has a resumable delivery",
            exit_code=EXIT_IDENTITY_CONFLICT,
        )
    current_id = inspection.get("current_delivery_id")
    expected_id = request.get("expected_delivery_id")
    if expected_id and expected_id != current_id:
        raise ControlError(
            f"expected_delivery_id={expected_id} does not match current={current_id}",
            exit_code=EXIT_IDENTITY_CONFLICT,
        )

    current_state = load_state(project_root)
    if request["dry_run"]:
        return _response(
            "start",
            "dry_run",
            current_state,
            created_new_delivery=startup_action == "new_delivery_required",
            extra={"startup_action": startup_action},
        )

    if startup_action == "resume_current_delivery":
        resumed = workflow.start(feature_slug=feature_slug)
        if resumed.get("paused"):
            resumed = workflow.resume_delivery()
        return _response("start", "resumed", resumed)

    mode = request["review_mode_if_created"]
    runtime_mode = None if mode == "pending_selection" else mode
    created = workflow.start(
        feature_slug=feature_slug,
        multi_agent_mode=runtime_mode,
    )
    return _response("start", "created", created, created_new_delivery=True)


def _closure_is_passed(state: dict[str, Any]) -> bool:
    return (
        (state.get("closure_validation") or {}).get("status") == "passed"
        and (state.get("feature_closure") or {}).get("status") == "passed"
        and (state.get("delivery_goal") or {}).get("status") == "complete"
    )


def _resolve_project_root(argv: list[str]) -> Path:
    if not argv:
        return Path.cwd()
    if argv[0] == "--project-root":
        if len(argv) != 2:
            raise ControlError("--project-root requires exactly one path")
        return Path(argv[1])
    if len(argv) == 1:
        return Path(argv[0])
    raise ControlError("usage: waygate-control.py [--project-root PATH | PATH]")


def run_control_cli(argv: list[str] | None = None) -> int:
    """Read one JSON object from stdin and emit one JSON response."""
    try:
        project_root = _resolve_project_root(
            list(sys.argv[1:] if argv is None else argv)
        )
        request = json.loads(sys.stdin.read())
        response = dispatch(project_root, request)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"invalid JSON: {exc}\n")
        return EXIT_PARAM_ERROR
    except ControlError as exc:
        sys.stderr.write(f"{exc}\n")
        return exc.exit_code
    except WorkflowError as exc:
        sys.stderr.write(f"gate blocked: {exc}\n")
        return EXIT_GATE_BLOCKED
    except Exception as exc:  # pragma: no cover - final CLI safety net
        sys.stderr.write(f"runtime error: {exc}\n")
        return EXIT_RUNTIME_ERROR
    sys.stdout.write(json.dumps(response, indent=2, sort_keys=True) + "\n")
    return EXIT_OK
