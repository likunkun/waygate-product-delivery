"""Delivery-scoped artifact storage with identity isolation.

Every delivery stores its authoritative artifacts under
``.product-delivery/deliveries/<feature_slug>/<delivery_id>/artifacts/``.
A ``current.json`` pointer records the active delivery so that V0.5
evidence is never overwritten by V0.5.5 evidence.  The legacy
``.product-delivery/artifacts/`` directory is kept as a compatibility
mirror whose contents must match the canonical delivery.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT

MANIFEST_SCHEMA_VERSION = "v1"
CURRENT_POINTER_SCHEMA_VERSION = "v1"
DELIVERIES_DIRNAME = "deliveries"
LEGACY_UNBOUND_DIRNAME = "legacy-unbound"
COMPAT_ARTIFACTS_DIRNAME = "artifacts"
CURRENT_POINTER_FILENAME = "current.json"
CURRENT_SYMLINK_NAME = "current"


class ArtifactStoreError(RuntimeError):
    """Raised when delivery-scoped artifact storage cannot proceed."""


# ------------------------------------------------------------------
# Path helpers
# ------------------------------------------------------------------


def _root(project_root: str | Path) -> Path:
    return Path(project_root) / ARTIFACT_ROOT


def deliveries_dir(project_root: str | Path) -> Path:
    return _root(project_root) / DELIVERIES_DIRNAME


def delivery_dir(
    project_root: str | Path,
    feature_slug: str,
    delivery_id: str,
) -> Path:
    return deliveries_dir(project_root) / feature_slug / delivery_id


def delivery_artifacts_dir(
    project_root: str | Path,
    feature_slug: str,
    delivery_id: str,
) -> Path:
    return delivery_dir(project_root, feature_slug, delivery_id) / "artifacts"


def current_pointer_path(project_root: str | Path) -> Path:
    return _root(project_root) / CURRENT_POINTER_FILENAME


def compat_artifacts_dir(project_root: str | Path) -> Path:
    return _root(project_root) / COMPAT_ARTIFACTS_DIRNAME


def legacy_unbound_dir(project_root: str | Path) -> Path:
    return _root(project_root) / LEGACY_UNBOUND_DIRNAME


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ------------------------------------------------------------------
# Current pointer
# ------------------------------------------------------------------


def load_current_pointer(project_root: str | Path) -> dict[str, Any] | None:
    """Return the current delivery pointer or ``None`` if absent."""
    path = current_pointer_path(project_root)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactStoreError(
            f"current.json is unreadable: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ArtifactStoreError("current.json must contain an object")
    return value


def _archive_compat_view_before_switch(
    project_root: str | Path,
    previous: dict[str, Any] | None,
    feature_slug: str,
    delivery_id: str,
) -> None:
    """Preserve the old compatibility view before switching owners.

    Files are copied into ``history/<delivery_id>/compat-artifacts`` and
    removed from the *current view* only after the copy succeeds. Their
    delivery-scoped canonical copies remain untouched.
    """
    if not previous:
        return
    old_feature = previous.get("feature_slug")
    old_delivery = previous.get("delivery_id")
    if not old_delivery or (old_feature, old_delivery) == (feature_slug, delivery_id):
        return
    compat = compat_artifacts_dir(project_root)
    if not compat.is_dir():
        return
    archive = _root(project_root) / "history" / str(old_delivery) / "compat-artifacts"
    for source in sorted(compat.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(compat)
        target = archive / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
        source.unlink()
    for directory in sorted(
        (item for item in compat.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass


def ensure_delivery_layout(
    project_root: str | Path,
    state: dict[str, Any],
) -> dict[str, Any] | None:
    """Ensure a delivery directory, state snapshot, manifest, and pointer exist."""
    feature_slug = state.get("feature_slug") or "_unscoped"
    delivery_id = state.get("delivery_id")
    if not isinstance(delivery_id, str) or not delivery_id:
        return None
    ddir = delivery_dir(project_root, feature_slug, delivery_id)
    ddir.mkdir(parents=True, exist_ok=True)
    (ddir / "artifacts").mkdir(parents=True, exist_ok=True)
    state_payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    state_path = ddir / "state.json"
    state_tmp = state_path.with_suffix(".json.tmp")
    state_tmp.write_text(state_payload, encoding="utf-8")
    os.replace(state_tmp, state_path)
    manifest = load_manifest(project_root, feature_slug, delivery_id)
    if manifest.get("frozen_at"):
        return load_current_pointer(project_root)
    manifest["lifecycle_status"] = (
        (state.get("delivery_lifecycle") or {}).get("status")
        or ("active" if state.get("active") else state.get("status"))
    )
    manifest_sha = _save_manifest(project_root, feature_slug, delivery_id, manifest)
    return write_current_pointer(
        project_root,
        feature_slug,
        delivery_id,
        manifest_sha256=manifest_sha,
        state_sha256=_sha256_bytes(state_payload.encode("utf-8")),
    )


def write_current_pointer(
    project_root: str | Path,
    feature_slug: str,
    delivery_id: str,
    *,
    manifest_sha256: str,
    state_sha256: str | None = None,
) -> dict[str, Any]:
    """Atomically update ``current.json`` and best-effort refresh symlink."""
    root = _root(project_root)
    root.mkdir(parents=True, exist_ok=True)
    path = current_pointer_path(project_root)
    previous = load_current_pointer(project_root) if path.is_file() else None
    if state_sha256 is None and previous and (
        previous.get("feature_slug"), previous.get("delivery_id")
    ) == (feature_slug, delivery_id):
        state_sha256 = previous.get("state_sha256")
    pointer = {
        "schema_version": CURRENT_POINTER_SCHEMA_VERSION,
        "feature_slug": feature_slug,
        "delivery_id": delivery_id,
        "delivery_path": (
            f"{DELIVERIES_DIRNAME}/{feature_slug}/{delivery_id}"
        ),
        "manifest_sha256": manifest_sha256,
        "state_sha256": state_sha256,
        "updated_at": _now(),
    }
    _archive_compat_view_before_switch(
        project_root, previous, feature_slug, delivery_id
    )
    pointer["symlink_status"] = _try_update_symlink(
        project_root, feature_slug, delivery_id
    )
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(pointer, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
    return pointer


def _try_update_symlink(
    project_root: str | Path,
    feature_slug: str,
    delivery_id: str,
) -> str:
    """Best-effort create/refresh the ``current`` symlink."""
    link = _root(project_root) / CURRENT_SYMLINK_NAME
    target = f"{DELIVERIES_DIRNAME}/{feature_slug}/{delivery_id}"
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target)
        return "ready"
    except (OSError, NotImplementedError):
        # The JSON pointer remains authoritative on unsupported platforms.
        return "unsupported"


# ------------------------------------------------------------------
# Manifest
# ------------------------------------------------------------------


def manifest_path(
    project_root: str | Path,
    feature_slug: str,
    delivery_id: str,
) -> Path:
    return delivery_dir(project_root, feature_slug, delivery_id) / "manifest.json"


def load_manifest(
    project_root: str | Path,
    feature_slug: str,
    delivery_id: str,
) -> dict[str, Any]:
    path = manifest_path(project_root, feature_slug, delivery_id)
    if not path.is_file():
        return _empty_manifest(feature_slug, delivery_id)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactStoreError(
            f"manifest.json is unreadable: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ArtifactStoreError("manifest.json must contain an object")
    return value


def _empty_manifest(feature_slug: str, delivery_id: str) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "feature_slug": feature_slug,
        "delivery_id": delivery_id,
        "artifacts": {},
        "updated_at": _now(),
    }


def _save_manifest(
    project_root: str | Path,
    feature_slug: str,
    delivery_id: str,
    manifest: dict[str, Any],
) -> str:
    """Persist manifest atomically and return its SHA-256."""
    manifest["updated_at"] = _now()
    path = manifest_path(project_root, feature_slug, delivery_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    return _sha256_bytes(payload.encode("utf-8"))


# ------------------------------------------------------------------
# Identity header injection
# ------------------------------------------------------------------


def _inject_identity_header(
    content: str,
    artifact_type: str,
    feature_slug: str,
    delivery_id: str,
) -> str:
    """Prepend a readable identity block to markdown artifacts.

    If the artifact already starts with ``#`` we insert the identity
    lines right after the first heading so that titles remain at the
    very top.
    """
    header_lines = [
        f"Artifact Type: {artifact_type}",
        f"Feature Slug: {feature_slug}",
        f"Delivery ID: {delivery_id}",
        "Artifact Status: Current",
        "",
    ]
    if content.lstrip().startswith("#"):
        stripped = content.lstrip()
        newline = stripped.find("\n")
        if newline == -1:
            return stripped + "\n" + "\n".join(header_lines)
        return (
            stripped[: newline + 1]
            + "\n".join(header_lines)
            + stripped[newline + 1 :]
        )
    return "\n".join(header_lines) + content


# ------------------------------------------------------------------
# Core write API
# ------------------------------------------------------------------


def write_artifact(
    project_root: str | Path,
    feature_slug: str,
    delivery_id: str,
    artifact_type: str,
    filename: str,
    content: str,
    *,
    transition_name: str | None = None,
) -> dict[str, Any]:
    """Write an artifact to the canonical delivery directory.

    Steps (atomic ordering):
    1. Write to ``deliveries/<feature>/<delivery>/artifacts/<filename>``.
    2. Compute SHA-256 and update ``manifest.json``.
    3. Refresh ``current.json``.
    4. Mirror to legacy ``.product-delivery/artifacts/<filename>``.
    """
    if not feature_slug or not delivery_id:
        raise ArtifactStoreError(
            "feature_slug and delivery_id are required for artifact writes"
        )
    if not artifact_type:
        raise ArtifactStoreError("artifact_type is required")
    if not filename:
        raise ArtifactStoreError("filename is required")

    canonical_dir = delivery_artifacts_dir(
        project_root, feature_slug, delivery_id
    )
    canonical_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = canonical_dir / filename
    canonical_path.parent.mkdir(parents=True, exist_ok=True)

    if filename.endswith(".md"):
        body = _inject_identity_header(
            content, artifact_type, feature_slug, delivery_id
        )
    else:
        body = content

    manifest = load_manifest(project_root, feature_slug, delivery_id)
    if manifest.get("frozen_at"):
        raise ArtifactStoreError(
            f"delivery {delivery_id} is frozen and cannot be overwritten"
        )
    canonical_tmp = canonical_path.with_name(canonical_path.name + ".tmp")
    canonical_tmp.write_text(body, encoding="utf-8")
    os.replace(canonical_tmp, canonical_path)
    sha = _sha256_file(canonical_path)

    artifacts = manifest.setdefault("artifacts", {})
    artifacts[artifact_type] = {
        "filename": filename,
        "canonical_path": (
            f"{DELIVERIES_DIRNAME}/{feature_slug}/{delivery_id}/artifacts/{filename}"
        ),
        "compatibility_path": f"{COMPAT_ARTIFACTS_DIRNAME}/{filename}",
        "sha256": sha,
        "feature_slug": feature_slug,
        "delivery_id": delivery_id,
        "artifact_status": "current",
        "transition_name": transition_name,
        "written_at": _now(),
    }
    manifest_sha = _save_manifest(
        project_root, feature_slug, delivery_id, manifest
    )

    pointer = write_current_pointer(
        project_root,
        feature_slug,
        delivery_id,
        manifest_sha256=manifest_sha,
    )

    # Compatibility mirror
    compat_dir = compat_artifacts_dir(project_root)
    compat_dir.mkdir(parents=True, exist_ok=True)
    compat_path = compat_dir / filename
    compat_path.parent.mkdir(parents=True, exist_ok=True)
    compat_tmp = compat_path.with_name(compat_path.name + ".tmp")
    compat_tmp.write_text(body, encoding="utf-8")
    os.replace(compat_tmp, compat_path)

    return {
        "artifact_type": artifact_type,
        "filename": filename,
        "canonical_path": artifacts[artifact_type]["canonical_path"],
        "compatibility_path": artifacts[artifact_type]["compatibility_path"],
        "sha256": sha,
        "manifest_sha256": manifest_sha,
        "current_pointer": pointer,
    }


def write_artifact_bytes(
    project_root: str | Path,
    feature_slug: str,
    delivery_id: str,
    artifact_type: str,
    filename: str,
    data: bytes,
    *,
    transition_name: str | None = None,
) -> dict[str, Any]:
    """Write a binary artifact (e.g. PNG) to the canonical delivery dir."""
    if not feature_slug or not delivery_id:
        raise ArtifactStoreError(
            "feature_slug and delivery_id are required for artifact writes"
        )
    canonical_dir = delivery_artifacts_dir(
        project_root, feature_slug, delivery_id
    )
    canonical_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = canonical_dir / filename
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(project_root, feature_slug, delivery_id)
    if manifest.get("frozen_at"):
        raise ArtifactStoreError(
            f"delivery {delivery_id} is frozen and cannot be overwritten"
        )
    canonical_tmp = canonical_path.with_name(canonical_path.name + ".tmp")
    canonical_tmp.write_bytes(data)
    os.replace(canonical_tmp, canonical_path)
    sha = _sha256_file(canonical_path)

    artifacts = manifest.setdefault("artifacts", {})
    artifacts[artifact_type] = {
        "filename": filename,
        "canonical_path": (
            f"{DELIVERIES_DIRNAME}/{feature_slug}/{delivery_id}/artifacts/{filename}"
        ),
        "compatibility_path": f"{COMPAT_ARTIFACTS_DIRNAME}/{filename}",
        "sha256": sha,
        "feature_slug": feature_slug,
        "delivery_id": delivery_id,
        "artifact_status": "current",
        "transition_name": transition_name,
        "written_at": _now(),
    }
    manifest_sha = _save_manifest(
        project_root, feature_slug, delivery_id, manifest
    )
    write_current_pointer(
        project_root,
        feature_slug,
        delivery_id,
        manifest_sha256=manifest_sha,
    )
    compat_path = compat_artifacts_dir(project_root) / filename
    compat_path.parent.mkdir(parents=True, exist_ok=True)
    compat_tmp = compat_path.with_name(compat_path.name + ".tmp")
    compat_tmp.write_bytes(data)
    os.replace(compat_tmp, compat_path)
    return {
        "artifact_type": artifact_type,
        "filename": filename,
        "canonical_path": artifacts[artifact_type]["canonical_path"],
        "sha256": sha,
        "manifest_sha256": manifest_sha,
    }


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


def validate_current_artifact_identity(
    project_root: str | Path,
    state: dict[str, Any],
) -> list[str]:
    """Validate pointer, manifest, canonical artifacts, and compatibility view."""
    feature_slug = state.get("feature_slug")
    delivery_id = state.get("delivery_id")
    if not feature_slug or not delivery_id:
        return []
    pointer = load_current_pointer(project_root)
    if pointer is None:
        return []

    blockers: list[str] = []
    if pointer.get("feature_slug") != feature_slug:
        blockers.append("stale_current_artifact_owner")
    if pointer.get("delivery_id") != delivery_id:
        blockers.append("artifact_identity_mismatch")
    if blockers:
        return list(dict.fromkeys(blockers))

    mpath = manifest_path(project_root, feature_slug, delivery_id)
    if not mpath.is_file():
        return ["artifact_identity_mismatch"]
    if _sha256_file(mpath) != pointer.get("manifest_sha256"):
        blockers.append("artifact_identity_mismatch")
    delivery_state = delivery_dir(project_root, feature_slug, delivery_id) / "state.json"
    root_state = _root(project_root) / "state.json"
    expected_state_sha = pointer.get("state_sha256")
    if (
        not expected_state_sha
        or not delivery_state.is_file()
        or _sha256_file(delivery_state) != expected_state_sha
        or not root_state.is_file()
        or _sha256_file(root_state) != expected_state_sha
    ):
        blockers.append("artifact_identity_mismatch")
    manifest = load_manifest(project_root, feature_slug, delivery_id)
    if (
        manifest.get("feature_slug") != feature_slug
        or manifest.get("delivery_id") != delivery_id
    ):
        blockers.append("artifact_identity_mismatch")

    for artifact_type, record in manifest.get("artifacts", {}).items():
        if (
            record.get("feature_slug") != feature_slug
            or record.get("delivery_id") != delivery_id
        ):
            blockers.append("artifact_identity_mismatch")
            continue
        canonical_rel = record.get("canonical_path")
        canonical = _root(project_root) / str(canonical_rel or "")
        if not canonical.is_file() or _sha256_file(canonical) != record.get("sha256"):
            blockers.append("artifact_identity_mismatch")
            continue
        compat_rel = record.get("compatibility_path")
        compat = _root(project_root) / str(compat_rel or "")
        if not compat.is_file() or _sha256_file(compat) != record.get("sha256"):
            blockers.append(f"stale_compat_mirror:{artifact_type}")
    return list(dict.fromkeys(blockers))


# ------------------------------------------------------------------
# Archival — freeze a previous delivery without deleting anything
# ------------------------------------------------------------------


def freeze_delivery(
    project_root: str | Path,
    feature_slug: str,
    delivery_id: str,
) -> dict[str, Any]:
    """Mark a delivery directory as immutable history.

    This does NOT delete or move files.  It only stamps ``manifest.json``
    with ``artifact_status=archived`` so subsequent deliveries never
    overwrite this directory.
    """
    ddir = delivery_dir(project_root, feature_slug, delivery_id)
    if not ddir.is_dir():
        return {"frozen": False, "reason": "delivery_dir_missing"}
    manifest = load_manifest(project_root, feature_slug, delivery_id)
    for record in manifest.get("artifacts", {}).values():
        record["artifact_status"] = "archived"
    manifest["frozen_at"] = _now()
    manifest_sha = _save_manifest(
        project_root, feature_slug, delivery_id, manifest
    )
    pointer = load_current_pointer(project_root)
    if pointer and (
        pointer.get("feature_slug"), pointer.get("delivery_id")
    ) == (feature_slug, delivery_id):
        write_current_pointer(
            project_root,
            feature_slug,
            delivery_id,
            manifest_sha256=manifest_sha,
        )
    return {"frozen": True, "manifest_sha256": manifest_sha}


# ------------------------------------------------------------------
# Legacy layout migration
# ------------------------------------------------------------------


def detect_legacy_layout(project_root: str | Path) -> dict[str, Any]:
    """Report flat files not represented by the current delivery manifest."""
    flat = compat_artifacts_dir(project_root)
    flat_files = [
        str(path.relative_to(flat))
        for path in sorted(flat.rglob("*"))
        if path.is_file() and not path.name.endswith(".tmp")
    ] if flat.is_dir() else []
    tracked: set[str] = set()
    pointer = load_current_pointer(project_root)
    if pointer:
        manifest = load_manifest(
            project_root,
            str(pointer.get("feature_slug") or ""),
            str(pointer.get("delivery_id") or ""),
        )
        tracked = {
            str(record.get("filename"))
            for record in manifest.get("artifacts", {}).values()
            if record.get("filename")
        }
    legacy_files = [name for name in flat_files if name not in tracked]
    return {
        "migration_required": bool(legacy_files),
        "legacy_files": legacy_files,
        "deliveries_dir_exists": deliveries_dir(project_root).is_dir(),
    }


def migrate_legacy_layout(
    project_root: str | Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Copy the flat compatibility tree into delivery-scoped history.

    State-referenced paths are bound to the delivery. Other files are copied
    to ``legacy-unbound`` and remain supporting evidence. Source files are not
    deleted; switching ``current.json`` later archives the compatibility view.
    """
    feature_slug = state.get("feature_slug")
    delivery_id = state.get("delivery_id")
    if not feature_slug or not delivery_id:
        raise ArtifactStoreError(
            "state must have feature_slug and delivery_id to migrate"
        )
    flat = compat_artifacts_dir(project_root)
    if not flat.is_dir():
        return {
            "migrated": False,
            "reason": "no_flat_artifacts",
            "copied": [],
            "unbound": [],
        }

    referenced: dict[str, str] = {}

    def collect(value: Any, key_path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                collect(item, (*key_path, str(key)))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                collect(item, (*key_path, str(index)))
        elif isinstance(value, str):
            relative = value
            if relative.startswith(".product-delivery/artifacts/"):
                relative = relative.removeprefix(".product-delivery/artifacts/")
            elif relative.startswith("artifacts/"):
                relative = relative.removeprefix("artifacts/")
            else:
                return
            if not relative or ".." in Path(relative).parts:
                return
            logical = "_".join(
                part.replace("-", "_") for part in key_path if not part.isdigit()
            ) or Path(relative).stem.replace("-", "_")
            referenced.setdefault(relative, logical)

    collect(state)
    canonical_root = delivery_artifacts_dir(
        project_root, str(feature_slug), str(delivery_id)
    )
    canonical_root.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(project_root, str(feature_slug), str(delivery_id))
    if manifest.get("frozen_at"):
        raise ArtifactStoreError(
            f"delivery {delivery_id} is frozen and cannot be migrated"
        )

    copied: list[str] = []
    unbound: list[str] = []
    for source in sorted(flat.rglob("*")):
        if not source.is_file() or source.name.endswith(".tmp"):
            continue
        relative = str(source.relative_to(flat))
        sha = _sha256_file(source)
        if relative in referenced:
            target = canonical_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(source, target)
                copied.append(relative)
            logical = referenced[relative]
            artifact_key = logical
            suffix = 2
            while (
                artifact_key in manifest.setdefault("artifacts", {})
                and manifest["artifacts"][artifact_key].get("filename") != relative
            ):
                artifact_key = f"{logical}_{suffix}"
                suffix += 1
            manifest["artifacts"][artifact_key] = {
                "filename": relative,
                "canonical_path": (
                    f"{DELIVERIES_DIRNAME}/{feature_slug}/{delivery_id}/artifacts/{relative}"
                ),
                "compatibility_path": f"{COMPAT_ARTIFACTS_DIRNAME}/{relative}",
                "sha256": sha,
                "feature_slug": feature_slug,
                "delivery_id": delivery_id,
                "artifact_status": "migrated",
                "transition_name": "legacy_layout_migrated",
                "written_at": _now(),
            }
        else:
            target = legacy_unbound_dir(project_root) / sha[:16] / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(source, target)
            unbound.append(relative)

    manifest_sha = _save_manifest(
        project_root, str(feature_slug), str(delivery_id), manifest
    )
    write_current_pointer(
        project_root,
        str(feature_slug),
        str(delivery_id),
        manifest_sha256=manifest_sha,
    )
    return {
        "migrated": True,
        "copied": copied,
        "unbound": unbound,
        "manifest_sha256": manifest_sha,
    }

