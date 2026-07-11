"""Validated local artifacts used by Product Delivery evidence gates."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path
from typing import Any


class EvidenceArtifactError(RuntimeError):
    """Raised when a local evidence artifact is missing or malformed."""


def resolve_project_path(
    project_root: str | Path,
    artifact_path: str,
    *,
    artifact_only: bool = False,
) -> Path:
    """Resolve a relative path without allowing traversal or symlink escape."""
    root = Path(project_root).resolve()
    candidate = Path(str(artifact_path or ""))
    if not artifact_path or candidate.is_absolute() or ".." in candidate.parts:
        raise EvidenceArtifactError("artifact path must be a safe project-relative path")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as cause:
        raise EvidenceArtifactError("artifact path escapes project root") from cause
    if artifact_only:
        artifact_root = (root / ".product-delivery" / "artifacts").resolve()
        try:
            resolved.relative_to(artifact_root)
        except ValueError as cause:
            raise EvidenceArtifactError(
                "artifact path must be under .product-delivery/artifacts"
            ) from cause
    if not resolved.is_file():
        raise EvidenceArtifactError(f"artifact path does not exist: {artifact_path}")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def validate_png(
    project_root: str | Path,
    artifact_path: str,
    *,
    artifact_only: bool = True,
) -> dict[str, Any]:
    """Validate a canonical PNG and return runtime-computed metadata."""
    if Path(str(artifact_path or "")).suffix.lower() != ".png":
        raise EvidenceArtifactError("canonical screenshot must be a PNG file")
    path = resolve_project_path(
        project_root,
        artifact_path,
        artifact_only=artifact_only,
    )
    data = path.read_bytes()
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise EvidenceArtifactError("canonical screenshot is not a valid PNG")

    offset = 8
    width = height = None
    found_iend = False
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise EvidenceArtifactError("PNG file is truncated")
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length : chunk_end])[0]
        if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != expected_crc:
            raise EvidenceArtifactError("PNG chunk CRC is invalid")
        if chunk_type == b"IHDR":
            if length != 13 or width is not None:
                raise EvidenceArtifactError("PNG IHDR is invalid")
            width, height = struct.unpack(">II", chunk_data[:8])
        elif chunk_type == b"IEND":
            found_iend = True
            if chunk_end != len(data):
                raise EvidenceArtifactError("PNG contains data after IEND")
            break
        offset = chunk_end

    if not found_iend or not width or not height:
        raise EvidenceArtifactError("PNG must contain valid IHDR and IEND chunks")
    return {
        "path": artifact_path,
        "format": "png",
        "width": width,
        "height": height,
        "sha256": sha256_file(path),
    }


def load_json_artifact(
    project_root: str | Path,
    artifact_path: str,
    *,
    artifact_only: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = resolve_project_path(
        project_root,
        artifact_path,
        artifact_only=artifact_only,
    )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as cause:
        raise EvidenceArtifactError(f"JSON artifact is invalid: {artifact_path}") from cause
    if not isinstance(value, dict):
        raise EvidenceArtifactError(f"JSON artifact must contain an object: {artifact_path}")
    return value, {"path": artifact_path, "sha256": sha256_file(path)}
