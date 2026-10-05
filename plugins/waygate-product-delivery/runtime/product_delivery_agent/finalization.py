"""Executable finalization entrypoint for Product Delivery closure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT, load_state, write_state
from product_delivery_agent.gatekeeper import render_closure_validator_result
from product_delivery_agent.workflow import ProductDeliveryWorkflow


def finalize_feature_closure(
    project_root: str | Path,
    closure_artifact_path: str | Path,
) -> dict:
    """Validate and record formal closure through the canonical workflow path."""
    root = Path(project_root)
    artifact_path = Path(closure_artifact_path)
    if not artifact_path.is_absolute():
        artifact_path = root / artifact_path
    try:
        artifact_bytes = artifact_path.read_bytes()
        artifact = json.loads(artifact_bytes.decode("utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _write_failure(root, [str(error)])
        raise

    state = load_state(root)
    if _terminal_closure_is_current(state, artifact_bytes):
        return state

    return ProductDeliveryWorkflow(root).record_feature_closure(
        artifact,
        source_artifact_path=str(artifact_path),
        source_artifact_sha256=hashlib.sha256(artifact_bytes).hexdigest(),
    )


def run_finalize_cli(argv: Sequence[str] | None = None) -> int:
    """CLI adapter used by packaged plugin scripts."""
    parser = argparse.ArgumentParser(
        description="Validate Product Delivery formal closure and update state.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root containing .product-delivery/state.json.",
    )
    parser.add_argument(
        "--closure-artifact",
        required=True,
        help="Path to the formal closure JSON artifact.",
    )
    args = parser.parse_args(argv)

    try:
        finalize_feature_closure(args.project_root, args.closure_artifact)
    except Exception as error:  # CLI must fail closed for all validator errors.
        _write_failure(Path(args.project_root), [str(error)])
        print("closure_validation=failed")
        print(str(error))
        return 1

    print("closure_validation=passed")
    return 0


def _write_failure(project_root: Path, errors: list[str]) -> None:
    state = load_state(project_root)
    if _terminal_closure_is_protected(state):
        return
    artifacts_dir = project_root / ARTIFACT_ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "closure-validator-result.md").write_text(
        render_closure_validator_result("closure_failed", errors),
        encoding="utf-8",
    )
    if state:
        state["closure_validation"] = {
            "status": "closure_failed",
            "errors": errors,
        }
        state["blocking_gates"] = {
            **(state.get("blocking_gates") or {}),
            "closure": False,
        }
        state["status"] = "closure_failed"
        state["stage"] = "closure_failed"
        state["next_gate"] = "feature_closure_after_implementation"
        write_state(project_root, state)


def _terminal_closure_is_protected(state: dict) -> bool:
    return bool(
        state
        and state.get("active") is False
        and state.get("status") == "closed"
        and state.get("stage") == "delivery_closed"
        and (state.get("delivery_lifecycle") or {}).get("status") == "closed"
        and (state.get("closure_validation") or {}).get("status") == "passed"
        and (state.get("feature_closure") or {}).get("status") == "passed"
        and (state.get("delivery_goal") or {}).get("status") == "complete"
    )


def _terminal_closure_is_current(state: dict, artifact_bytes: bytes) -> bool:
    if not _terminal_closure_is_protected(state):
        return False
    return (
        (state.get("closure_validation") or {}).get("closure_artifact_sha256")
        == hashlib.sha256(artifact_bytes).hexdigest()
    )


if __name__ == "__main__":
    raise SystemExit(run_finalize_cli())
