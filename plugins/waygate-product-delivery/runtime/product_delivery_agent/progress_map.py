"""Optional static progress maps; all writes are isolated from delivery authority.

The owner records explanatory relationships, never completion. Canonical state
supplies progress. This module neither creates agents nor runs an HTTP service.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProgressMapError(ValueError):
    """A map input or identity cannot be accepted."""


LIVE_PATH = ".product-delivery/maps/index.html"
PROJECT_CONFIG = ".product-delivery/progress-map-settings.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _safe(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ProgressMapError("invalid relative path")
    part = Path(relative)
    if part.is_absolute() or ".." in part.parts:
        raise ProgressMapError("path escapes project")
    current = root.resolve()
    for segment in part.parts:
        current = current / segment
        if current.is_symlink():
            raise ProgressMapError("symlink paths are not allowed")
    return current


def _json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ProgressMapError(f"unreadable map data {path.name}: {exc}") from exc


def _atomic(path: Path, value: Any, *, text: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if text else json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".map-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _state(root: Path) -> dict:
    return _json(_safe(root, ".product-delivery/state.json"), {})


def delivery_map_dir(root: str | Path, state: dict) -> Path:
    slug = state.get("feature_slug") or "_unscoped"
    identity = state.get("delivery_id")
    if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", identity):
        raise ProgressMapError("valid delivery_id required")
    if not isinstance(slug, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", slug) or slug in {".", ".."}:
        raise ProgressMapError("valid feature slug required")
    return _safe(Path(root), f".product-delivery/deliveries/{slug}/{identity}/progress-map")


def _map_file(root: Path, state: dict, name: str) -> Path:
    return _safe(root, str((delivery_map_dir(root, state) / name).relative_to(root.resolve())))


def _config(root: Path, state: dict) -> dict:
    default = {"schema_version": "v1", "delivery_id": state.get("delivery_id"),
               "enabled": False, "source": "system_default"}
    if not state.get("delivery_id"):
        return default
    value = _json(_map_file(root, state, "config.json"), default)
    if not isinstance(value, dict) or type(value.get("enabled")) is not bool or value.get("delivery_id") != state["delivery_id"]:
        raise ProgressMapError("map config delivery identity or enabled value mismatch")
    return value


def _project_default(root: Path) -> dict:
    value = _json(_safe(root, PROJECT_CONFIG), {"enabled": False, "source": "system_default"})
    if not isinstance(value, dict) or type(value.get("enabled")) is not bool:
        raise ProgressMapError("invalid project map default")
    return value


def _plan_revisions(root: Path, state: dict) -> list[dict]:
    directory = _map_file(root, state, "plans")
    if not directory.exists():
        return []
    values = []
    for path in sorted(directory.glob("*.json")):
        path = _safe(root, str(path.relative_to(root.resolve())))
        row = _json(path)
        if not isinstance(row, dict) or row.get("delivery_id") != state["delivery_id"]:
            raise ProgressMapError("map revision delivery mismatch")
        if row.get("revision") != len(values) + 1 or row.get("sha256") != _hash(row.get("plan")):
            raise ProgressMapError("map revision integrity mismatch")
        if row.get("previous_sha256") != (values[-1]["sha256"] if values else None):
            raise ProgressMapError("map revision chain mismatch")
        values.append(row)
    return values


def _source(root: Path, ref: dict) -> dict:
    if not isinstance(ref, dict) or not isinstance(ref.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", ref["sha256"]):
        raise ProgressMapError("source requires path and SHA-256")
    path = _safe(root, ref.get("path"))
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {"path": ref["path"], "sha256": ref["sha256"], "actual_sha256": actual,
            "status": "current" if actual == ref["sha256"] else "stale", "included": False}


def _sources_in(plan: dict) -> list[dict]:
    refs = list(plan.get("sources", []))
    for group in ("goals", "components", "capabilities", "changes"):
        for row in plan.get(group, []):
            refs.extend(row.get("sources", []))
    return list({(r.get("path"), r.get("sha256")): r for r in refs}.values())


def _approval_matches(state: dict, approval: dict | None) -> bool:
    if not isinstance(approval, dict) or not isinstance(approval.get("target"), str) or approval.get("target") not in {"product_baseline", "test_coverage_plan"}:
        return False
    saved = (state.get("user_confirmations") or {}).get(approval["target"], {})
    if not (saved.get("decision") == "approved" and saved.get("artifact_hash") and
            saved.get("artifact_hash") == approval.get("artifact_hash")):
        return False
    from product_delivery_agent.gatekeeper import product_baseline_hash, test_coverage_plan_hash
    current = product_baseline_hash(state) if approval["target"] == "product_baseline" else test_coverage_plan_hash(state)
    return current == saved["artifact_hash"]


def _validate_plan(root: Path, state: dict, plan: dict) -> None:
    if not isinstance(plan, dict) or plan.get("schema_version") != "v1":
        raise ProgressMapError("map plan schema_version must be v1")
    if plan.get("delivery_id") != state.get("delivery_id"):
        raise ProgressMapError("map plan delivery mismatch")
    # Reject malformed nested containers before hashing or persisting a revision.
    # A broken immutable revision must never make subsequent map rendering fail.
    text_lists = ("goal_ids", "component_ids", "capability_ids", "version_ids", "scenario_ids", "obligation_ids", "affected_ids")
    scalar_fields = ("id", "title", "description", "kind", "from", "to", "label", "task_id", "planned_task_hash",
                     "delivery_id", "reason", "impact", "owner", "next_action", "comparison")
    criteria = plan.get("success_criteria", [])
    if not isinstance(criteria, list) or any(not isinstance(value, str) for value in criteria):
        raise ProgressMapError("success_criteria must be a string list")
    all_sources = []
    for group in ("versions", "goals", "components", "capabilities", "changes", "edges", "task_bindings"):
        rows = plan.get(group, [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ProgressMapError(f"{group} must be an object list")
        for row in rows:
            for field in scalar_fields:
                if field in row and not isinstance(row[field], str):
                    raise ProgressMapError(f"{group}.{field} must be a string")
            for field in text_lists:
                if field in row and (not isinstance(row[field], list) or any(not isinstance(v, str) or not v for v in row[field])):
                    raise ProgressMapError(f"{group}.{field} must be a string list")
            if "sources" in row:
                all_sources.append(row["sources"])
    all_sources.append(plan.get("sources", []))
    for refs in all_sources:
        if not isinstance(refs, list) or any(not isinstance(r, dict) or not isinstance(r.get("path"), str)
                                             or not isinstance(r.get("sha256"), str) for r in refs):
            raise ProgressMapError("sources must contain path/SHA-256 objects")
    for field in ("title", "objective", "current_version"):
        if not isinstance(plan.get(field), str) or not plan[field].strip():
            raise ProgressMapError(f"map plan {field} required")
    groups = {}
    for group in ("versions", "goals", "components", "capabilities"):
        rows = plan.get(group)
        if not isinstance(rows, list) or not rows:
            raise ProgressMapError(f"{group} must contain rows")
        ids = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] or not row.get("title"):
                raise ProgressMapError(f"{group} row requires id and title")
            if row["id"] in ids:
                raise ProgressMapError(f"duplicate {group} id")
            ids.add(row["id"])
        groups[group] = ids
    if plan["current_version"] not in groups["versions"]:
        raise ProgressMapError("current_version not in versions")
    for group in ("components", "capabilities"):
        for row in plan[group]:
            fields = {"goal_ids": "goals"}
            if group == "capabilities":
                fields.update(component_ids="components", version_ids="versions")
            for field, target in fields.items():
                if not isinstance(row.get(field), list) or not row[field] or not set(row[field]) <= groups[target]:
                    raise ProgressMapError(f"invalid {field} in {group}")
            if not row.get("sources"):
                raise ProgressMapError(f"{group} sources required")
    for edge in plan.get("edges", []):
        if edge.get("from") not in groups["components"] or edge.get("to") not in groups["components"] or edge.get("kind") not in {"dependency", "interface"} or not edge.get("label"):
            raise ProgressMapError("invalid architecture edge")
    tasks = {t["task_id"]: t for t in (state.get("delivery_goal") or {}).get("planned_tasks", [])}
    seen_tasks = set()
    for binding in plan.get("task_bindings", []):
        if binding.get("delivery_id") != state["delivery_id"]:
            raise ProgressMapError("task binding delivery mismatch")
        task = tasks.get(binding.get("task_id"))
        if not task or not task.get("planned_task_hash") or binding.get("planned_task_hash") != task["planned_task_hash"]:
            raise ProgressMapError("task binding current TASK/hash mismatch")
        if not binding.get("capability_ids") or not set(binding["capability_ids"]) <= groups["capabilities"]:
            raise ProgressMapError("task binding capability mismatch")
        if binding["task_id"] in seen_tasks:
            raise ProgressMapError("duplicate task binding")
        seen_tasks.add(binding["task_id"])
    obligations = {o.get("obligation_id") for o in (state.get("planned_e2e_obligations") or {}).get("obligations", [])}
    scenarios = {s.get("scenario_id") for s in (state.get("scenario_matrix") or {}).get("rows", [])} if isinstance(state.get("scenario_matrix"), dict) else {s.get("scenario_id") for s in state.get("scenario_matrix", [])}
    for capability in plan["capabilities"]:
        if not set(capability.get("obligation_ids", [])) <= obligations or not set(capability.get("scenario_ids", [])) <= scenarios:
            raise ProgressMapError("unknown scenario or obligation binding")
    if plan.get("approval") and not _approval_matches(state, plan["approval"]):
        raise ProgressMapError("approval must match current canonical confirmation")
    kinds = {"planned", "implementation_detail", "review_gap", "approved_change", "unexplained"}
    for change in plan.get("changes", []):
        if change.get("kind") not in kinds or not all(change.get(f) for f in ("id", "title", "reason", "impact", "owner", "next_action")):
            raise ProgressMapError("change requires kind, explanation, impact, owner and next action")
        if change["kind"] == "approved_change" and not _approval_matches(state, change.get("approval")):
            raise ProgressMapError("approved change requires canonical approval")
        if change["kind"] != "unexplained" and not change.get("sources"):
            raise ProgressMapError("explained change requires sources")
    refs = _sources_in(plan)
    if not refs:
        raise ProgressMapError("source references required")
    for ref in refs:
        if _source(root, ref)["status"] != "current":
            raise ProgressMapError("source hash missing or stale: " + ref["path"])


def set_progress_map_mode(project_root: str | Path, mode: str, *, scope: str = "delivery", delivery_id: str | None = None) -> dict:
    from product_delivery_agent.artifact_protocol import state_write_lock
    if not isinstance(mode, str) or not isinstance(scope, str) or mode not in {"on", "off"} or scope not in {"delivery", "project"}:
        raise ProgressMapError("mode must be on/off and scope delivery/project")
    root = Path(project_root).resolve()
    with state_write_lock(root):
        state = _state(root)
        if scope == "project":
            if delivery_id is not None:
                raise ProgressMapError("project default does not take a delivery_id")
            _atomic(_safe(root, PROJECT_CONFIG), {"schema_version": "v1", "enabled": mode == "on", "source": "project_default"})
        else:
            if not delivery_id or delivery_id != state.get("delivery_id"):
                raise ProgressMapError("delivery_id must match current delivery")
            _atomic(_map_file(root, state, "config.json"), {"schema_version": "v1", "delivery_id": delivery_id,
                    "enabled": mode == "on", "source": "delivery_override"})
            _render_best_effort(root, state)
        return inspect_progress_map(root, state=state)


def record_progress_map_plan(project_root: str | Path, plan: dict, *, expected_revision: int) -> dict:
    from product_delivery_agent.artifact_protocol import state_write_lock
    root = Path(project_root).resolve()
    with state_write_lock(root):
        state = _state(root)
        if not _config(root, state)["enabled"]:
            raise ProgressMapError("progress map disabled; use map on / 地图已关闭")
        revisions = _plan_revisions(root, state)
        if type(expected_revision) is not int or expected_revision != len(revisions):
            raise ProgressMapError("expected_revision mismatch")
        _validate_plan(root, state, plan)
        revision = len(revisions) + 1
        row = {"delivery_id": state["delivery_id"], "revision": revision, "generated_at": _now(), "plan": copy.deepcopy(plan),
               "sha256": _hash(plan), "previous_sha256": revisions[-1]["sha256"] if revisions else None,
               "baseline_status": "approved" if plan.get("approval") else "draft",
               "summary": plan.get("revision_summary", "登记产品目标、架构和任务关联")}
        _atomic(_map_file(root, state, f"plans/{revision:06d}.json"), row)
        _render_best_effort(root, state)
        return {"revision": revision, "sha256": row["sha256"], "map": inspect_progress_map(root, state=state)}


def _state_revision(state: dict) -> str:
    from product_delivery_agent.artifact_protocol import lifecycle_state_hash
    return lifecycle_state_hash(state)


def inspect_progress_map(project_root: str | Path, *, state: dict | None = None) -> dict:
    root = Path(project_root).resolve()
    result = {"enabled": False, "source": "system_default", "path": None, "freshness": "disabled", "error": None}
    try:
        state = _state(root) if state is None else state
        config = _config(root, state)
        result.update(enabled=config["enabled"], source=config["source"], delivery_id=state.get("delivery_id"),
                      project_default=_project_default(root)["enabled"])
        if not state.get("delivery_id"):
            return result
        receipt = _json(_map_file(root, state, "receipt.json"), {})
        diagnostic = _json(_map_file(root, state, "error.json"), {})
        result.update(generated_at=receipt.get("generated_at"), error=diagnostic.get("error"),
                      path=LIVE_PATH if _safe(root, LIVE_PATH).exists() else None)
        if config["enabled"]:
            revisions = _plan_revisions(root, state)
            refs = _sources_in(revisions[-1]["plan"]) if revisions else []
            stale = any(_source(root, ref)["status"] != "current" for ref in refs)
            current_model = build_progress_map(root, state=state)
            live_hash = hashlib.sha256(_safe(root, LIVE_PATH).read_bytes()).hexdigest() if result["path"] else None
            result["freshness"] = "fresh" if (not stale and not result["error"] and result["path"] and
                receipt.get("state_revision") == _state_revision(state) and receipt.get("plan_revision", 0) == len(revisions)
                and receipt.get("source_revision") == current_model["source_revision"]
                and live_hash == receipt.get("html_sha256")) else "stale"
        return result
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result.update(freshness="error", error=str(exc))
        return result


def build_progress_map(project_root: str | Path, *, state: dict | None = None) -> dict:
    from product_delivery_agent.progress_map_model import project_map
    root = Path(project_root).resolve()
    if state is None:
        from product_delivery_agent.artifact_protocol import state_write_lock
        with state_write_lock(root):
            return build_progress_map(root, state=_state(root))
    revisions = _plan_revisions(root, state)
    config = _config(root, state)
    return project_map(root, state, revisions, config)


def render_progress_map(model: dict, *, live: bool = True, enabled: bool = True) -> str:
    # Lazy import keeps default-off deliveries independent of presentation errors.
    from product_delivery_agent.progress_map_html import render_progress_map as render
    return render(model, live=live, enabled=enabled)


def _milestone(state: dict) -> str:
    return _hash({"stage": state.get("stage"), "confirmations": state.get("user_confirmations"),
                  "closure": state.get("closure_validation"), "freeze": state.get("freeze")})


def _snapshot(root: Path, state: dict, model: dict, *, prefix: str) -> str:
    stamp = model["generated_at"].replace(":", "-")
    filename = f"snapshots/{prefix}-{stamp}-{model['source_revision'][:16]}.html"
    path = _map_file(root, state, filename)
    if not path.exists():
        _atomic(path, render_progress_map(model, live=False, enabled=True), text=True)
    return str(path.relative_to(root))


def _refresh(root: Path, state: dict) -> None:
    config = _config(root, state)
    live_path = _safe(root, LIVE_PATH)
    if not config["enabled"] and not live_path.exists():
        return
    receipt_path = _map_file(root, state, "receipt.json")
    receipt = _json(receipt_path, {})
    if not config["enabled"]:
        # Freeze what the developer actually saw. A previously failed refresh
        # may have written metadata for newer data before publishing the HTML.
        match = re.search(r'<script id="progress-map-data" type="application/json">(.*?)</script>', live_path.read_text(encoding="utf-8"), re.S)
        model = None
        if match:
            candidate = json.loads(match.group(1)).get("model")
            if isinstance(candidate, dict) and candidate.get("delivery_id") == state["delivery_id"]:
                model = candidate
        if not model:
            model = {"schema_version": "v1", "delivery_id": state["delivery_id"], "feature_slug": state.get("feature_slug"),
                     "generated_at": _now(), "source_revision": _state_revision(state), "title": "产品交付地图", "warnings": []}
        model.update(enabled=False, settings_source=config["source"], frozen_reason="自动更新已关闭")
        _atomic(live_path, render_progress_map(model, live=False, enabled=False), text=True)
        _atomic(_map_file(root, state, "error.json"), {})
        return
    model = build_progress_map(root, state=state)
    html = render_progress_map(model, live=True, enabled=True)
    # Write live last: an earlier projection/snapshot failure retains its old bytes.
    milestone = _milestone(state)
    if receipt.get("milestone") != milestone:
        _snapshot(root, state, model, prefix="milestone")
    _atomic(receipt_path, {"generated_at": model["generated_at"], "state_revision": _state_revision(state),
            "plan_revision": model["plan_revision"], "source_revision": model["source_revision"], "milestone": milestone,
            "html_sha256": hashlib.sha256(html.encode()).hexdigest()})
    _atomic(_map_file(root, state, "error.json"), {})
    # The single visible publication point. Receipts are checked against these
    # exact bytes, so failure here cannot make an old page appear fresh.
    _atomic(live_path, html, text=True)


def _render_best_effort(root: Path, state: dict) -> None:
    try:
        _refresh(root, state)
    except Exception as exc:
        # Never turn a committed canonical operation into an apparent failure.
        try:
            _atomic(_map_file(root, state, "error.json"), {"error": str(exc), "occurred_at": _now()})
        except Exception:
            sys.stderr.write(f"progress map generation failed: {exc}\n")


def on_state_committed(project_root: str | Path, state: dict, *, new_delivery: bool = False) -> None:
    """Called under the canonical write lock, strictly after layout commit."""
    if not state.get("delivery_id") or (not state.get("active") and not state.get("feature_slug")):
        return
    root = Path(project_root).resolve()
    try:
        config_path = _map_file(root, state, "config.json")
        if new_delivery and not config_path.exists():
            default = _project_default(root)
            _atomic(config_path, {"schema_version": "v1", "delivery_id": state["delivery_id"],
                    "enabled": default["enabled"], "source": default.get("source", "project_default")})
        _render_best_effort(root, state)
    except Exception as exc:
        sys.stderr.write(f"progress map configuration failed: {exc}\n")


def generate_progress_map(project_root: str | Path) -> dict:
    from product_delivery_agent.artifact_protocol import state_write_lock
    root = Path(project_root).resolve()
    with state_write_lock(root):
        state = _state(root)
        if _config(root, state)["enabled"]:
            _render_best_effort(root, state)
        return inspect_progress_map(root, state=state)


def export_progress_map(project_root: str | Path) -> dict:
    from product_delivery_agent.artifact_protocol import state_write_lock
    root = Path(project_root).resolve()
    with state_write_lock(root):
        state = _state(root)
        if not _config(root, state)["enabled"]:
            raise ProgressMapError("progress map disabled; use map on / 地图已关闭")
        model = build_progress_map(root, state=state)
        return {"path": _snapshot(root, state, model, prefix="export"), "delivery_id": state["delivery_id"],
                "source_revision": model["source_revision"]}


def run_map_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate static product maps; no HTTP service")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--delivery-id")
    parser.add_argument("command", nargs="?", choices=("on", "off", "default", "export", "record", "inspect"))
    parser.add_argument("value", nargs="?")
    parser.add_argument("--expected-revision", type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "default":
            result = set_progress_map_mode(args.project_root, args.value, scope="project")
        elif args.command in {"on", "off"}:
            if args.value is not None:
                raise ProgressMapError("unexpected argument")
            result = set_progress_map_mode(args.project_root, args.command, delivery_id=args.delivery_id)
        elif args.command == "record":
            if args.value != "-":
                raise ProgressMapError("record requires '-' and JSON on stdin")
            result = record_progress_map_plan(args.project_root, json.load(sys.stdin), expected_revision=args.expected_revision)
        else:
            if args.value is not None or args.delivery_id is not None or args.expected_revision is not None:
                raise ProgressMapError("unexpected argument")
            function = export_progress_map if args.command == "export" else inspect_progress_map if args.command == "inspect" else generate_progress_map
            result = function(args.project_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("error") else 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run_map_cli())
