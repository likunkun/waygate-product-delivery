"""Model execution profiles for Product Delivery orchestration."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


PROFILE_SCHEMA_VERSION = "v1"
USER_PROFILE_DIRECTORY = "waygate-product-delivery"
PROFILE_FILENAME = "model-profiles.json"
AUTOMATIC_STAGES = (
    "discovery",
    "product_design",
    "implementation",
    "browser_evidence",
    "review",
    "closure",
)
KNOWN_MODEL_REASONING_EFFORTS = {
    "gpt-5.6-sol": {"low", "medium", "high", "xhigh", "max", "ultra"},
    "gpt-5.6-terra": {"low", "medium", "high", "xhigh", "max", "ultra"},
    "gpt-5.6-luna": {"low", "medium", "high", "xhigh", "max"},
    "gpt-5.5": {"low", "medium", "high", "xhigh"},
    "gpt-5.4": {"low", "medium", "high", "xhigh"},
}
VALID_REASONING_EFFORTS = {
    effort
    for efforts in KNOWN_MODEL_REASONING_EFFORTS.values()
    for effort in efforts
}

DEFAULT_MODEL_PROFILES: dict[str, Any] = {
    "full_speed": {
        "model": "gpt-5.6-sol",
        "reasoning_effort": "xhigh",
        "service_tier": "priority",
    },
    "automatic": {
        "coordinator": {
            "model": "inherit",
            "reasoning_effort": "inherit",
        },
        "stages": {
            "discovery": {
                "model": "gpt-5.6-luna",
                "reasoning_effort": "medium",
            },
            "product_design": {
                "model": "gpt-5.6-sol",
                "reasoning_effort": "high",
            },
            "implementation": {
                "model": "gpt-5.6-terra",
                "reasoning_effort": "high",
            },
            "browser_evidence": {
                "model": "gpt-5.6-terra",
                "reasoning_effort": "medium",
            },
            "review": {
                "model": "gpt-5.6-terra",
                "reasoning_effort": "high",
            },
            "closure": {
                "model": "gpt-5.6-sol",
                "reasoning_effort": "xhigh",
            },
        },
        "escalation": {
            "model": "gpt-5.6-sol",
            "reasoning_effort": "xhigh",
            "after_consecutive_failures": 2,
        },
    },
}


class ModelProfileError(ValueError):
    """Raised when model profile configuration is invalid."""


def resolve_model_profiles(
    project_root: str | Path,
    *,
    codex_home: str | Path | None = None,
    delivery_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve built-in, user, project, and delivery profile layers."""
    project = Path(project_root)
    home = Path(
        codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex"
    ).expanduser()
    profiles = _clone(DEFAULT_MODEL_PROFILES)
    sources = ["builtin"]

    user_path = home / USER_PROFILE_DIRECTORY / PROFILE_FILENAME
    project_path = project / ".product-delivery" / "config" / PROFILE_FILENAME
    for source, path in (("user", user_path), ("project", project_path)):
        layer = _read_profile_layer(path)
        if layer is None:
            continue
        profiles = _deep_merge(profiles, layer)
        sources.append(source)
    if delivery_overrides:
        if not isinstance(delivery_overrides, dict):
            raise ModelProfileError("model_profile_overrides must be an object")
        profiles = _deep_merge(profiles, delivery_overrides)
        sources.append("delivery")

    validate_model_profiles(profiles)
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "profiles": profiles,
        "sources": sources,
        "profile_hash": stable_profile_hash(profiles),
        "paths": {
            "user": str(user_path),
            "project": str(project_path),
        },
    }


def save_model_profiles(
    project_root: str | Path,
    *,
    codex_home: str | Path | None,
    scope: str,
    profiles: dict[str, Any],
) -> dict[str, Any]:
    """Atomically save a user or project model profile layer."""
    if scope not in {"user", "project"}:
        raise ModelProfileError("scope must be 'user' or 'project'")
    if not isinstance(profiles, dict) or not profiles:
        raise ModelProfileError("profiles must be a non-empty object")

    # Validate the layer after merging defaults so partial overrides remain useful.
    validate_model_profiles(_deep_merge(_clone(DEFAULT_MODEL_PROFILES), profiles))
    project = Path(project_root)
    home = Path(
        codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex"
    ).expanduser()
    path = (
        home / USER_PROFILE_DIRECTORY / PROFILE_FILENAME
        if scope == "user"
        else project / ".product-delivery" / "config" / PROFILE_FILENAME
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "profiles": profiles,
    }
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)
    return {
        "scope": scope,
        "path": str(path),
        "profile_hash": stable_profile_hash(profiles),
    }


def validate_model_profiles(profiles: dict[str, Any]) -> None:
    if not isinstance(profiles, dict):
        raise ModelProfileError("profiles must be an object")
    unknown_profiles = sorted(set(profiles) - {"full_speed", "automatic"})
    if unknown_profiles:
        raise ModelProfileError(
            "unsupported model profiles: " + ", ".join(unknown_profiles)
        )
    full_speed = profiles.get("full_speed")
    automatic = profiles.get("automatic")
    if not isinstance(full_speed, dict):
        raise ModelProfileError("full_speed profile is required")
    if not isinstance(automatic, dict):
        raise ModelProfileError("automatic profile is required")
    unknown_automatic = sorted(
        set(automatic) - {"coordinator", "stages", "escalation"}
    )
    if unknown_automatic:
        raise ModelProfileError(
            "unsupported automatic profile fields: "
            + ", ".join(unknown_automatic)
        )

    _validate_model_assignment(full_speed, path="full_speed")
    coordinator = automatic.get("coordinator")
    if not isinstance(coordinator, dict):
        raise ModelProfileError("automatic.coordinator is required")
    _validate_model_assignment(
        coordinator,
        path="automatic.coordinator",
        allow_inherit=True,
    )
    stages = automatic.get("stages")
    if not isinstance(stages, dict):
        raise ModelProfileError("automatic.stages is required")
    unknown_stages = sorted(set(stages) - set(AUTOMATIC_STAGES))
    if unknown_stages:
        raise ModelProfileError(
            "unsupported automatic stages: " + ", ".join(unknown_stages)
        )
    for stage in AUTOMATIC_STAGES:
        assignment = stages.get(stage)
        if not isinstance(assignment, dict):
            raise ModelProfileError(f"automatic.stages.{stage} is required")
        _validate_model_assignment(
            assignment,
            path=f"automatic.stages.{stage}",
        )

    escalation = automatic.get("escalation")
    if not isinstance(escalation, dict):
        raise ModelProfileError("automatic.escalation is required")
    _validate_model_assignment(escalation, path="automatic.escalation")
    threshold = escalation.get("after_consecutive_failures")
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 1:
        raise ModelProfileError(
            "automatic.escalation.after_consecutive_failures must be a positive integer"
        )


def select_model_for_stage(
    profile: dict[str, Any],
    stage: str,
    *,
    full_speed: bool = False,
    consecutive_failures: int = 0,
    risk_flags: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve the model assignment for a bounded stage worker."""
    if stage not in AUTOMATIC_STAGES:
        raise ModelProfileError(f"unsupported execution stage: {stage}")
    risk_flags = list(risk_flags or [])
    if full_speed:
        assignment = dict(profile)
        selection_reason = "full_speed_uniform_profile"
    else:
        threshold = profile["escalation"]["after_consecutive_failures"]
        escalation_risks = {
            "cross_service_consistency",
            "authorization_or_permission",
            "schema_or_migration",
            "review_blocker",
            "skeptic_adjudication",
        }
        if stage == "closure":
            assignment = dict(profile["escalation"])
            selection_reason = "closure_escalation"
        elif consecutive_failures >= threshold:
            assignment = dict(profile["escalation"])
            selection_reason = "consecutive_failures"
        elif escalation_risks.intersection(risk_flags):
            assignment = dict(profile["escalation"])
            selection_reason = "risk_escalation"
        else:
            assignment = dict(profile["stages"][stage])
            selection_reason = "automatic_stage_profile"
    assignment.pop("after_consecutive_failures", None)
    assignment.pop("allow_unverified_model", None)
    return {
        **assignment,
        "stage": stage,
        "selection_reason": selection_reason,
        "fork_context": False,
        "canonical_state_writes": False,
    }


def stable_profile_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_profile_layer(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelProfileError(f"invalid model profile file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ModelProfileError(f"model profile file must contain an object: {path}")
    if payload.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ModelProfileError(
            f"unsupported model profile schema in {path}: {payload.get('schema_version')}"
        )
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        raise ModelProfileError(f"model profile file has no profiles object: {path}")
    return profiles


def _validate_model_assignment(
    assignment: dict[str, Any],
    *,
    path: str,
    allow_inherit: bool = False,
) -> None:
    model = assignment.get("model")
    effort = assignment.get("reasoning_effort")
    if allow_inherit and model == "inherit" and effort == "inherit":
        return
    if not isinstance(model, str) or not model.strip():
        raise ModelProfileError(f"{path}.model must be a non-empty string")
    if effort not in VALID_REASONING_EFFORTS:
        raise ModelProfileError(f"unsupported reasoning effort for {path}: {effort}")
    known_efforts = KNOWN_MODEL_REASONING_EFFORTS.get(model)
    if known_efforts is None:
        if assignment.get("allow_unverified_model") is not True:
            raise ModelProfileError(
                f"unknown model for {path}: {model}; set allow_unverified_model=true to opt in"
            )
    elif effort not in known_efforts:
        raise ModelProfileError(
            f"model {model} does not support reasoning effort {effort} at {path}"
        )
    service_tier = assignment.get("service_tier")
    if service_tier is not None and (
        not isinstance(service_tier, str) or not service_tier.strip()
    ):
        raise ModelProfileError(f"{path}.service_tier must be a non-empty string")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = _clone(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = _clone(value)
    return merged


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value))
