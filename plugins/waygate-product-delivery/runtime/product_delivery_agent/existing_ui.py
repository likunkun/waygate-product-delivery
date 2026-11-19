"""Compare browser observations of an existing product and its proposed UI."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from product_delivery_agent.evidence_artifacts import (
    load_json_artifact,
    resolve_project_path,
    sha256_file,
    stable_json_hash,
    validate_png,
)


EXISTING_UI_TYPES = {"incremental_existing_surface", "new_surface_in_existing_product"}
CAPTURE_SCHEMA = "existing-ui-browser-capture-v1"
REPORT_SCHEMA = "existing-ui-continuity-v1"
MISSING_BASELINE = "real product browser baseline and prototype comparison are required"


def validate_existing_ui_roles(report, scenario_rows):
    roles = {row["role"] for row in scenario_rows if isinstance(row.get("role"), str)}
    observed = {comparison["unit"][3] for comparison in report["comparisons"]}
    if roles and not observed <= roles:
        raise ValueError("existing UI capture role must match the current scenario matrix")


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"existing UI {label} is required")
    return value.strip()


def _shape(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise ValueError(f"existing UI {label} requires exactly: {fields}")


def _route(value):
    value = _text(value, "route")
    parsed = urlsplit(value)
    if not value.startswith("/") or value.startswith("//") or parsed.query or parsed.fragment:
        raise ValueError("existing UI routes must be local paths without query or fragment")
    return value


def _capture_time(value):
    try:
        timestamp = datetime.fromisoformat(_text(value, "captured_at"))
    except ValueError as error:
        raise ValueError("existing UI captured_at must be an ISO timestamp") from error
    if timestamp.utcoffset() is None:
        raise ValueError("existing UI captured_at must include a timezone")
    return timestamp


def _origin(url):
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("existing UI product evidence requires a real HTTP(S) browser URL")
    return f"{parsed.scheme}://{parsed.netloc}"


def _elements(raw):
    if not isinstance(raw, list) or not raw:
        raise ValueError("existing UI browser observation requires elements")
    elements = {}
    for item in raw:
        _shape(item, "id parent_id kind role name visible enabled layout dynamic_text", "element")
        element_id = _text(item["id"], "element id")
        if element_id in elements or item["kind"] not in ("region", "control"):
            raise ValueError(f"existing UI invalid or duplicate element: {element_id}")
        if any(type(item[field]) is not bool for field in ("visible", "enabled", "dynamic_text")):
            raise ValueError(f"existing UI element {element_id} requires observed boolean states")
        if item["kind"] == "control" and item["dynamic_text"]:
            raise ValueError(f"existing UI control {element_id} cannot mask its name")
        if not isinstance(item["name"], str):
            raise ValueError(f"existing UI element {element_id} has an invalid name")
        parent_id = item["parent_id"]
        if parent_id is not None and (not isinstance(parent_id, str) or parent_id not in elements):
            raise ValueError(f"existing UI element {element_id} requires its parent first")
        _text(item["role"], "element role")
        _text(item["layout"], "element layout")
        elements[element_id] = item
    root = elements.get("product-root") or {}
    if root.get("kind") != "region" or not root.get("visible") or any(
        element_id != "product-root" and item["parent_id"] is None
        for element_id, item in elements.items()
    ):
        raise ValueError("existing UI browser inventory must cover the full product root")
    return elements


def _actions(raw, entry_route, route):
    if not isinstance(raw, list) or not raw:
        raise ValueError("existing UI browser observation requires the ordinary journey actions")
    actions = {}
    current = entry_route
    for action in raw:
        _shape(action, "id control_id before_route after_route outcome", "action")
        action_id = _text(action["id"], "action id")
        _text(action["control_id"], "action control")
        _text(action["outcome"], "observed action outcome")
        if action_id in actions or _route(action["before_route"]) != current:
            raise ValueError(f"existing UI ordinary journey is disconnected at {action_id}")
        current = _route(action["after_route"])
        actions[action_id] = action
    if current != route:
        raise ValueError("existing UI ordinary journey did not reach the observed route")
    return actions


def _units(root, observations, *, origin=None, prototype_file=None):
    if not isinstance(observations, list) or not observations:
        raise ValueError("existing UI browser captures require observations")
    units = {}
    fields = "surface_id state_id viewport actor_role context_id actual_url route entry_route screenshot width height elements actions"
    for item in observations:
        _shape(item, fields if origin else fields + " baseline_unit", "browser observation")
        key = tuple(_text(item[field], field) for field in ("surface_id", "state_id", "viewport", "actor_role"))
        if key in units:
            raise ValueError(f"duplicate existing UI browser unit: {key}")
        _text(item["context_id"], "observed business context")
        actual_url = _text(item["actual_url"], "actual browser URL")
        parsed = urlsplit(actual_url)
        if parsed.query or (parsed.fragment and parsed.scheme != "file"):
            raise ValueError("existing UI capture URLs must omit query and product fragments")
        route = _route(item["route"])
        entry_route = _route(item["entry_route"])
        if origin:
            if _origin(actual_url) != origin or (parsed.path or "/") != route:
                raise ValueError(f"existing UI product URL does not match observed route: {key}")
        elif parsed.scheme == "file":
            if parsed.netloc or Path(unquote(parsed.path)).resolve() != prototype_file:
                raise ValueError("existing UI candidate file is not the clean prototype")
        else:
            _origin(actual_url)
            if (parsed.path or "/") != route:
                raise ValueError(f"existing UI candidate URL does not match observed route: {key}")
        screenshot = item["screenshot"]
        _shape(screenshot, "path sha256", "screenshot")
        actual_png = validate_png(root, screenshot["path"])
        if any(type(item[field]) is not int or item[field] != actual_png[field] for field in ("width", "height")):
            raise ValueError(f"existing UI screenshot dimensions do not match viewport: {key}")
        if actual_png["sha256"] != screenshot["sha256"]:
            raise ValueError(f"existing UI screenshot hash mismatch: {key}")
        units[key] = {
            **item,
            "elements": _elements(item["elements"]),
            "actions": _actions(item["actions"], entry_route, route),
        }
    return units


def _changed_rows(baseline, candidate):
    for field in ("route", "entry_route"):
        if baseline[field] != candidate[field]:
            yield "route", field, baseline[field], candidate[field]
    for kind in ("elements", "actions"):
        before, after = baseline[kind], candidate[kind]
        for key in sorted(before.keys() | after.keys()):
            old, new = before.get(key), after.get(key)
            if kind == "elements" and old and new and old["dynamic_text"] and new["dynamic_text"]:
                if {k: v for k, v in old.items() if k != "name"} == {k: v for k, v in new.items() if k != "name"}:
                    continue
            if old != new:
                yield kind, key, old, new
        # Additions and removals do not change the relative order of inherited items.
        common = before.keys() & after.keys()
        for parent in sorted({before[key].get("parent_id") or "" for key in common}):
            siblings = {key for key in common if (before[key].get("parent_id") or "") == parent
                        and (after[key].get("parent_id") or "") == parent}
            old_order = [key for key in before if key in siblings]
            new_order = [key for key in after if key in siblings]
            if old_order != new_order:
                yield f"{kind}_order", parent or "root", old_order, new_order


def _matches_route(template, route):
    if not template:
        return False
    segments = urlsplit(template).path.strip("/").split("/")
    actual = route.strip("/").split("/")
    return len(segments) == len(actual) and all(
        expected == found or (found and (expected.startswith(":") or
        expected.startswith("{") and expected.endswith("}")))
        for expected, found in zip(segments, actual)
    )


def _declared_changes(root, declarations, requirements_path):
    if not isinstance(declarations, list):
        raise ValueError("existing UI changes must be a list")
    if not declarations:
        if requirements_path is not None:
            raise ValueError("existing UI requirements path is only used for declared changes")
        return {}, None
    source = resolve_project_path(root, _text(requirements_path, "requirements path"))
    document = source.read_text(encoding="utf-8")
    changes = {}
    ids = set()
    for change in declarations:
        _shape(change, "change_id unit kind target requirement_ids", "declared change")
        change_id = _text(change["change_id"], "change id")
        unit = change["unit"]
        if not isinstance(unit, list) or len(unit) != 4:
            raise ValueError("existing UI change unit must be [surface, state, viewport, role]")
        key = (tuple(_text(value, "change unit") for value in unit),
               _text(change["kind"], "change kind"), _text(change["target"], "change target"))
        if key in changes or change_id in ids:
            raise ValueError(f"duplicate existing UI change: {change_id}")
        reqs = change["requirement_ids"]
        if not isinstance(reqs, list) or not reqs or any(
            not isinstance(req, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", req)
            or not re.search(rf"(?<![\w-]){re.escape(req)}(?![\w-])", document)
            for req in reqs
        ):
            raise ValueError(f"existing UI change {change_id} must cite a documented requirement ID")
        changes[key] = change
        ids.add(change_id)
    return changes, {"path": requirements_path, "sha256": sha256_file(source)}


def build_existing_ui_continuity(root, value, *, prototype, contract, screenshots):
    """Validate the captured units, then derive the inherited items and actual changes."""
    _shape(value, "baseline_path prototype_capture_path requirements_path changes", "continuity input")
    baseline, baseline_meta = load_json_artifact(root, value["baseline_path"])
    candidate, candidate_meta = load_json_artifact(root, value["prototype_capture_path"])
    common = "schema_version source captured_at browser_engine observations"
    _shape(baseline, common + " origin build_id", "product capture")
    _shape(candidate, common + " baseline_sha256 prototype_sha256", "prototype capture")
    for data, source in ((baseline, "product_runtime"), (candidate, "interactive_prototype")):
        if data["schema_version"] != CAPTURE_SCHEMA or data["source"] != source or data["browser_engine"] not in ("chromium", "firefox", "webkit"):
            raise ValueError(f"existing UI requires {source} browser captures")
    if _capture_time(candidate["captured_at"]) < _capture_time(baseline["captured_at"]) or candidate["baseline_sha256"] != baseline_meta["sha256"]:
        raise ValueError("existing UI prototype capture has a stale product baseline")
    if candidate["prototype_sha256"] != prototype["sha256"]:
        raise ValueError("existing UI comparison does not match the current clean prototype")
    origin = _origin(_text(baseline["origin"], "product origin"))
    if origin != baseline["origin"]:
        raise ValueError("existing UI product origin must not contain a route")
    build_id = _text(baseline["build_id"], "running product build identity")
    before = _units(root, baseline["observations"], origin=origin)
    after = _units(root, candidate["observations"], prototype_file=resolve_project_path(root, prototype["path"]))
    required = {(s["surface_id"], s["state_id"], viewport): s
                for s in contract["surfaces"] for viewport in s["required_viewports"]}
    if set(required) != {key[:3] for key in after}:
        raise ValueError("existing UI comparison must cover every prototype surface, state and viewport")
    if {row["screenshot"]["path"] for row in before.values()} & {row["screenshot"]["path"] for row in after.values()}:
        raise ValueError("existing UI product and prototype require distinct browser captures")
    declarations, requirement = _declared_changes(root, value["changes"], value["requirements_path"])
    paired = set()
    comparisons = []
    for key, row in sorted(after.items()):
        reference = row["baseline_unit"]
        if not isinstance(reference, list) or len(reference) != 4 or any(not isinstance(field, str) for field in reference):
            raise ValueError(f"existing UI comparison requires a baseline unit for {key}")
        reference = tuple(reference)
        original = before.get(reference)
        if not original or reference[2:] != key[2:] or (key in before and reference != key):
            raise ValueError(f"existing UI baseline does not match surface, state, viewport or role: {key}")
        paired.add(reference)
        if original["context_id"] != row["context_id"] or any(original[field] != row[field] for field in ("width", "height")):
            raise ValueError(f"existing UI business state or viewport dimensions do not match: {key}")
        surface = required[key[:3]]
        if not _matches_route(surface.get("route"), row["route"]):
            raise ValueError(f"existing UI prototype route is outside its contract: {key}")
        if row["screenshot"] != {field: screenshots[key[:3]]["artifact"][field] for field in ("path", "sha256")}:
            raise ValueError(f"existing UI comparison does not bind the clean screenshot: {key}")
        changes = []
        changed_elements = set()
        changed_actions = set()
        for kind, target, old, new in _changed_rows(original, row):
            declaration = declarations.pop((key, kind, target), None)
            if not declaration:
                raise ValueError(f"undeclared existing UI difference at {'/'.join(key)}: {kind} {target}")
            changes.append({**declaration, "before": old, "after": new})
            if kind == "elements":
                changed_elements.add(target)
            elif kind == "actions":
                changed_actions.add(target)
        for region in surface["critical_regions"]:
            region_id = region["region_id"]
            observed = row["elements"].get(region_id)
            if not observed or observed["kind"] != "region":
                raise ValueError(f"existing UI capture did not observe contract region {region_id}: {key}")
            expected_parent = region.get("parent_region_id") or "product-root"
            if "parent_region_id" in region and expected_parent != observed["parent_id"]:
                raise ValueError(f"existing UI capture parent does not match contract region {region_id}: {key}")
        comparisons.append({
            "unit": list(key), "baseline_unit": list(reference), "entry_route": row["entry_route"],
            "route": row["route"], "baseline_url": original["actual_url"],
            "baseline_screenshot": original["screenshot"], "prototype_screenshot": row["screenshot"],
            "inherited_elements": [item for item in row["elements"] if item not in changed_elements],
            "inherited_actions": [item for item in row["actions"] if item not in changed_actions],
            "changes": changes,
        })
    if paired != set(before):
        raise ValueError("existing UI comparison dropped a captured product unit")
    if declarations:
        raise ValueError("existing UI declared changes do not match observed differences")
    report = {
        "schema_version": REPORT_SCHEMA, "build_id": build_id, "origin": origin,
        "baseline": baseline_meta, "prototype_capture": candidate_meta,
        "requirements": requirement, "comparisons": comparisons,
        "change_ids": sorted(change["change_id"] for unit in comparisons for change in unit["changes"]),
    }
    return {**report, "sha256": stable_json_hash(report)}
