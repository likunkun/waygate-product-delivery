"""Journey-sliced TASK derivation and completion gates."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any

from product_delivery_agent.delivery_goal import (
    DeliveryGoalError,
    deepcopy_bindings,
    normalize_planned_tasks,
)


JOURNEY_SLICE_POLICY_VERSION = "v1"
JOURNEY_SLICE_INTRODUCED_IN = "1.0.29"
MAX_ACTION_ASSERTIONS = 8
MAX_COVERAGE_ITEMS = 8
MAX_SURFACES = 3
MAX_PRIMARY_HAPPY_PATHS = 2
MAX_COLLECTION_ITEMS = 3
MAX_OBLIGATION_SHARE = 0.4
SHELL_SURFACE_IDS = {
    "global-shell",
    "app-shell",
    "navigation",
    "shell",
}
SHELL_REGION_PREFIXES = ("global-shell", "navigation", "app-shell", "shell", "nav-")
LEFTOVER_TITLE = re.compile(
    r"(remaining|leftover|catch[- ]?all|everything else|full[- ]?suite|全量|剩余|扫尾|其余)",
    re.IGNORECASE,
)


class JourneySliceTaskError(DeliveryGoalError):
    """Raised when journey-sliced TASKs cannot be derived or refined."""


def journey_slice_tasks_required(state: dict[str, Any]) -> bool:
    """Return whether this delivery must use journey-sliced TASKs."""
    policy = state.get("journey_slice_task_policy") or {}
    return policy.get("policy_version") == JOURNEY_SLICE_POLICY_VERSION and policy.get(
        "status"
    ) == "required"


def default_journey_slice_task_policy(*, status: str) -> dict[str, Any]:
    return {
        "policy_version": JOURNEY_SLICE_POLICY_VERSION,
        "status": status,
        "introduced_in": JOURNEY_SLICE_INTRODUCED_IN,
    }


def ensure_journey_slice_task_policy(state: dict[str, Any]) -> dict[str, Any]:
    """Attach policy to recovered state without changing confirmed old deliveries."""
    policy = state.get("journey_slice_task_policy")
    if isinstance(policy, dict) and policy.get("status"):
        return policy
    confirmed = (
        (state.get("user_confirmations") or {})
        .get("test_coverage_plan", {})
        .get("decision")
        == "approved"
        or (state.get("confirmation_readiness") or {}).get("test_coverage_plan")
        == "confirmed"
    )
    if confirmed:
        policy = default_journey_slice_task_policy(status="grandfathered")
        policy["upgrade_reason"] = "confirmed_test_coverage_plan"
    elif state.get("project_type") in {"ui", "non_ui"}:
        policy = default_journey_slice_task_policy(status="required")
    else:
        policy = default_journey_slice_task_policy(status="pending_project_type")
    state["journey_slice_task_policy"] = policy
    return policy


def derive_journey_slice_tasks(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive a vertical-slice TASK queue from planned E2E obligations."""
    planned = state.get("planned_e2e_obligations") or {}
    obligations = [
        dict(item)
        for item in planned.get("obligations", [])
        if isinstance(item, dict)
    ]
    if not obligations:
        raise JourneySliceTaskError(
            "planned E2E obligations are required to derive journey slice TASKs"
        )
    project_type = state.get("project_type") or "ui"
    _validate_obligation_slice_fields(obligations, project_type=project_type)
    groups = _split_obligations(obligations)
    _assert_balance(groups)
    baseline = state.get("implementation_baseline") or {}
    tasks = []
    for index, group in enumerate(groups, start=1):
        task = _task_from_group(
            group,
            index=index,
            first=(index == 1),
            project_type=project_type,
            implementation_baseline=baseline,
        )
        tasks.append(task)
    return normalize_planned_tasks(
        tasks,
        implementation_baseline=baseline if baseline.get("status") == "ready" else None,
        require_prototype_bindings=project_type == "ui" and baseline.get("status") == "ready",
    )


def refine_journey_slice_tasks(
    derived: list[dict[str, Any]],
    refinements: list[dict[str, Any]],
    *,
    implementation_baseline: dict[str, Any] | None = None,
    require_prototype_bindings: bool = False,
) -> list[dict[str, Any]]:
    """Allow title/description/verification and narrower bindings only."""
    if [task.get("task_id") for task in refinements] != [
        task.get("task_id") for task in derived
    ]:
        raise JourneySliceTaskError(
            "refined TASK queue must keep derived task ids and order"
        )
    merged = []
    for derived_task, refinement in zip(derived, refinements):
        if LEFTOVER_TITLE.search(str(refinement.get("title") or "")):
            raise JourneySliceTaskError(
                "TASK title cannot describe leftover or full-suite work"
            )
        derived_obligations = list(derived_task.get("obligation_ids") or [])
        refined_obligations = refinement.get("obligation_ids")
        if refined_obligations is not None and list(refined_obligations) != derived_obligations:
            raise JourneySliceTaskError(
                "refined TASK cannot move or drop journey E2E obligations"
            )
        derived_items = list(derived_task.get("owned_coverage_items") or [])
        refined_items = refinement.get("owned_coverage_items")
        if refined_items is not None and list(refined_items) != derived_items:
            raise JourneySliceTaskError(
                "refined TASK cannot move owned coverage items"
            )
        merged_task = dict(derived_task)
        for field_name in ("title", "description", "verification"):
            if refinement.get(field_name):
                merged_task[field_name] = refinement[field_name]
        if "prototype_bindings" in refinement:
            merged_task["prototype_bindings"] = _narrower_or_same_bindings(
                derived_task.get("prototype_bindings") or [],
                refinement.get("prototype_bindings") or [],
            )
        merged.append(merged_task)
    return normalize_planned_tasks(
        merged,
        implementation_baseline=implementation_baseline,
        require_prototype_bindings=require_prototype_bindings,
    )


def rewrite_coverage_task_column(
    rows: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Write derived TASK ids back onto coverage audit rows."""
    rewritten = []
    for row in rows:
        next_row = dict(row)
        next_row["task"] = _task_id_for_coverage_row(row, tasks)
        rewritten.append(next_row)
    return rewritten


def journey_slice_task_identity(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the user-visible TASK identity included in confirmation hashes."""
    identity = []
    for task in tasks:
        identity.append(
            {
                "task_id": task.get("task_id"),
                "journey": task.get("journey"),
                "obligation_ids": list(task.get("obligation_ids") or []),
                "owned_coverage_items": list(task.get("owned_coverage_items") or []),
                "ui_impact": task.get("ui_impact"),
                "includes_minimum_shell": bool(task.get("includes_minimum_shell")),
                "prototype_bindings": deepcopy(task.get("prototype_bindings") or []),
            }
        )
    return identity


def task_obligation_keys(task: dict[str, Any], obligations: list[dict[str, Any]]) -> set[tuple[str, str]]:
    owned_ids = set(task.get("obligation_ids") or [])
    keys = set()
    for obligation in obligations:
        if obligation.get("obligation_id") not in owned_ids:
            continue
        keys.add((obligation.get("obligation_id"), obligation.get("test_id")))
    return keys


def _validate_obligation_slice_fields(
    obligations: list[dict[str, Any]],
    *,
    project_type: str,
) -> None:
    for index, obligation in enumerate(obligations, start=1):
        if not str(obligation.get("journey") or "").strip():
            raise JourneySliceTaskError(
                f"planned obligation row {index} missing journey"
            )
        items = _string_list(obligation.get("coverage_items"))
        assertions = obligation.get("action_assertions") or []
        if len(items) > MAX_COVERAGE_ITEMS:
            raise JourneySliceTaskError(
                f"planned obligation row {index} exceeds {MAX_COVERAGE_ITEMS} coverage items"
            )
        if len(items) > MAX_COLLECTION_ITEMS:
            raise JourneySliceTaskError(
                f"planned obligation row {index} collection items must be grouped into sets of at most {MAX_COLLECTION_ITEMS}"
            )
        if isinstance(assertions, list) and len(assertions) > MAX_ACTION_ASSERTIONS:
            raise JourneySliceTaskError(
                f"planned obligation row {index} exceeds {MAX_ACTION_ASSERTIONS} action assertions"
            )
        if project_type == "ui":
            surfaces = _string_list(obligation.get("surface_ids"))
            if not surfaces:
                raise JourneySliceTaskError(
                    f"planned obligation row {index} missing fields: surface_ids"
                )
            if len(surfaces) > MAX_SURFACES:
                raise JourneySliceTaskError(
                    f"planned obligation row {index} exceeds {MAX_SURFACES} surfaces"
                )


def _split_obligations(obligations: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    journeys: list[tuple[str, list[dict[str, Any]]]] = []
    seen: dict[str, int] = {}
    for obligation in obligations:
        journey = str(obligation.get("journey") or "").strip()
        if journey not in seen:
            seen[journey] = len(journeys)
            journeys.append((journey, []))
        journeys[seen[journey]][1].append(obligation)

    groups: list[list[dict[str, Any]]] = []
    for _journey, rows in journeys:
        if _group_is_overloaded(rows):
            groups.extend(_pack_obligations(rows))
        else:
            groups.append(rows)
    if not groups:
        raise JourneySliceTaskError("journey slice TASK queue is required")
    return groups


def _group_is_overloaded(rows: list[dict[str, Any]]) -> bool:
    items = sum(len(_string_list(row.get("coverage_items"))) for row in rows)
    assertions = sum(
        len(row.get("action_assertions") or [])
        if isinstance(row.get("action_assertions"), list)
        else 0
        for row in rows
    )
    surfaces: set[str] = set()
    happy_paths = 0
    for row in rows:
        surfaces.update(_string_list(row.get("surface_ids")))
        if str(row.get("path_kind") or "").strip() == "primary_happy_path":
            happy_paths += 1
    return (
        items > MAX_COVERAGE_ITEMS
        or assertions > MAX_ACTION_ASSERTIONS
        or len(surfaces) > MAX_SURFACES
        or happy_paths > MAX_PRIMARY_HAPPY_PATHS
    )


def _pack_obligations(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    packed: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for row in rows:
        candidate = current + [row]
        if current and _group_is_overloaded(candidate):
            packed.append(current)
            current = [row]
            if _group_is_overloaded(current):
                raise JourneySliceTaskError(
                    "a single planned obligation exceeds journey slice thresholds"
                )
        else:
            current = candidate
    if current:
        packed.append(current)
    return packed


def _assert_balance(groups: list[list[dict[str, Any]]]) -> None:
    counts = [len(group) for group in groups]
    if len(counts) < 2:
        return
    total = sum(counts)
    limit = max(1, math.ceil(total * MAX_OBLIGATION_SHARE))
    if any(count > limit for count in counts):
        raise JourneySliceTaskError(
            "no TASK may own more than 40% of planned E2E obligations"
        )
    median = sorted(counts)[len(counts) // 2]
    if counts[-1] > median:
        raise JourneySliceTaskError(
            "the last TASK may not own more obligations than the median TASK"
        )


def _task_from_group(
    group: list[dict[str, Any]],
    *,
    index: int,
    first: bool,
    project_type: str,
    implementation_baseline: dict[str, Any],
) -> dict[str, Any]:
    journey = str(group[0].get("journey") or "").strip()
    obligation_ids = [str(item["obligation_id"]) for item in group]
    owned_items: list[str] = []
    for item in group:
        for coverage_item in _string_list(item.get("coverage_items")):
            if coverage_item not in owned_items:
                owned_items.append(coverage_item)
    title_suffix = "" if index == 1 or len(group) == len(set(obligation_ids)) else f" slice {index}"
    task: dict[str, Any] = {
        "task_id": f"TASK-{index:03d}",
        "title": f"Implement journey {journey}{title_suffix}",
        "description": (
            f"Implement the user-visible increment for journey '{journey}' "
            f"and pass its bound full-stack evidence."
        ),
        "verification": "Run bound full-stack evidence for this journey slice.",
        "journey": journey,
        "obligation_ids": obligation_ids,
        "owned_coverage_items": owned_items,
        "includes_minimum_shell": bool(first),
    }
    if LEFTOVER_TITLE.search(task["title"]):
        raise JourneySliceTaskError(
            "TASK title cannot describe leftover or full-suite work"
        )
    if project_type == "ui":
        task["ui_impact"] = "prototype_bound"
        task["prototype_bindings"] = _bindings_for_group(
            group,
            include_shell=first,
            implementation_baseline=implementation_baseline,
        )
    else:
        task["ui_impact"] = "none"
        task["ui_impact_reason"] = "non-UI behavior slice"
        task["prototype_bindings"] = []
    return task


def _bindings_for_group(
    group: list[dict[str, Any]],
    *,
    include_shell: bool,
    implementation_baseline: dict[str, Any],
) -> list[dict[str, Any]]:
    surface_ids: list[str] = []
    state_ids: list[str] = []
    viewport_classes: list[str] = []
    for obligation in group:
        for surface_id in _string_list(obligation.get("surface_ids")):
            if surface_id not in surface_ids:
                surface_ids.append(surface_id)
        for state_id in _string_list(obligation.get("state_ids")):
            if state_id not in state_ids:
                state_ids.append(state_id)
        for viewport in _string_list(obligation.get("viewport_classes")):
            if viewport not in viewport_classes:
                viewport_classes.append(viewport)
    units = [
        unit
        for unit in implementation_baseline.get("units", [])
        if isinstance(unit, dict)
    ]
    selected = []
    for unit in units:
        if unit.get("surface_id") in surface_ids and (
            not state_ids or unit.get("state_id") in state_ids
        ) and (
            not viewport_classes or unit.get("viewport_class") in viewport_classes
        ):
            selected.append(unit)
        elif include_shell and _unit_is_shell(unit):
            selected.append(unit)
    if implementation_baseline.get("status") == "ready":
        if not selected:
            raise JourneySliceTaskError(
                "journey slice TASKs require baseline units for bound surfaces"
            )
        return _bindings_from_units(selected)
    if not surface_ids:
        raise JourneySliceTaskError("surface_ids are required for UI journey slices")
    fallback_states = state_ids or ["ready"]
    fallback_viewports = viewport_classes or ["desktop"]
    return [
        {
            "surface_id": surface_id,
            "state_id": state_id,
            "viewport_classes": list(fallback_viewports),
            "region_ids": [f"{surface_id}-region"],
            "interaction_ids": [f"{surface_id}-action"],
        }
        for surface_id in surface_ids
        for state_id in fallback_states
    ]


def _unit_is_shell(unit: dict[str, Any]) -> bool:
    surface_id = str(unit.get("surface_id") or "")
    if surface_id in SHELL_SURFACE_IDS:
        return True
    for region_id in unit.get("region_ids") or []:
        value = str(region_id)
        if value in SHELL_SURFACE_IDS or value.startswith(SHELL_REGION_PREFIXES):
            return True
    return False


def _bindings_from_units(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for unit in units:
        key = (str(unit["surface_id"]), str(unit["state_id"]))
        current = grouped.setdefault(
            key,
            {
                "surface_id": key[0],
                "state_id": key[1],
                "viewport_classes": [],
                "region_ids": [],
                "interaction_ids": [],
            },
        )
        viewport = str(unit.get("viewport_class") or "")
        if viewport and viewport not in current["viewport_classes"]:
            current["viewport_classes"].append(viewport)
        for region_id in unit.get("region_ids") or []:
            if region_id not in current["region_ids"]:
                current["region_ids"].append(region_id)
        for interaction_id in unit.get("interaction_ids") or []:
            if interaction_id not in current["interaction_ids"]:
                current["interaction_ids"].append(interaction_id)
    return [deepcopy_bindings([binding])[0] for binding in grouped.values()]


def _narrower_or_same_bindings(
    derived: list[dict[str, Any]],
    refined: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    derived_map = {
        (item["surface_id"], item["state_id"]): item
        for item in derived
    }
    narrowed = []
    for binding in refined:
        key = (binding.get("surface_id"), binding.get("state_id"))
        source = derived_map.get(key)
        if source is None:
            raise JourneySliceTaskError(
                "refined prototype bindings cannot add surfaces or states"
            )
        if not set(binding.get("viewport_classes") or []).issubset(
            set(source.get("viewport_classes") or [])
        ):
            raise JourneySliceTaskError(
                "refined prototype bindings cannot expand viewports"
            )
        if not set(binding.get("region_ids") or []).issubset(
            set(source.get("region_ids") or [])
        ):
            raise JourneySliceTaskError(
                "refined prototype bindings cannot expand regions"
            )
        if not set(binding.get("interaction_ids") or []).issubset(
            set(source.get("interaction_ids") or [])
        ):
            raise JourneySliceTaskError(
                "refined prototype bindings cannot expand interactions"
            )
        if not binding.get("viewport_classes") or not binding.get("region_ids"):
            raise JourneySliceTaskError(
                "refined prototype bindings must keep at least one viewport and region"
            )
        narrowed.append(binding)
    if not narrowed:
        raise JourneySliceTaskError("refined prototype bindings cannot be empty")
    return deepcopy_bindings(narrowed)


def _task_id_for_coverage_row(row: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    obligation_ref = str(row.get("obligation_ref") or "")
    journey = str(row.get("journey") or "")
    for task in tasks:
        if obligation_ref and obligation_ref in set(task.get("obligation_ids") or []):
            return str(task["task_id"])
        owned_items = set(task.get("owned_coverage_items") or [])
        if obligation_ref and obligation_ref in owned_items:
            return str(task["task_id"])
    for task in tasks:
        if journey and journey == task.get("journey"):
            return str(task["task_id"])
    if tasks:
        return str(tasks[0]["task_id"])
    raise JourneySliceTaskError("derived TASK queue is required to rewrite coverage tasks")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]
