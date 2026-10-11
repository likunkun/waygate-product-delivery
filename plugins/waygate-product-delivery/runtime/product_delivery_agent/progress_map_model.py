"""Read-only, evidence-backed projection for the optional product map."""
from __future__ import annotations

import copy
from pathlib import Path

from product_delivery_agent.progress_map import (
    _approval_matches, _hash, _now, _source, _sources_in, _state_revision,
)

STAGES = (
    ("product_definition", "产品定义"),
    ("architecture_version_planning", "架构与版本"),
    ("open_spec_product_surface", "规格与产品表面"),
    ("test_design", "测试设计"),
    ("implementation_execution", "实现执行"),
    ("delivery_preparation", "交付准备"),
)


def _refs(root: Path, refs: list) -> list:
    result = []
    for ref in refs:
        try:
            result.append(_source(root, ref))
        except (ValueError, OSError) as exc:
            result.append({"path": ref.get("path", "未知来源"), "sha256": ref.get("sha256"), "status": "stale", "error": str(exc), "included": False})
    return result


def _evidence_refs(root: Path, data) -> list:
    """Understand runtime evidence field pairs, including behavior-path hashes."""
    refs = []
    if isinstance(data, dict):
        for field, path in data.items():
            if field.endswith("_path") and isinstance(path, str):
                digest = data.get(field + "_sha256") or data.get(field[:-5] + "_sha256")
                if digest:
                    refs.append({"path": path, "sha256": digest})
            elif isinstance(path, (list, dict)):
                refs.extend(_evidence_refs(root, path))
    elif isinstance(data, list):
        for row in data:
            refs.extend(_evidence_refs(root, row))
    return refs


def _change(kind, title, reason, *, identity=None, sources=None, impact="需要核实当前任务与目标的关系", next_action="由主线程核实关联与证据", owner="主线程", **extra):
    return {"id": identity or _hash([kind, title, reason])[:16], "kind": kind, "title": title,
            "reason": reason, "impact": impact, "owner": owner, "next_action": next_action,
            "sources": sources or [], **extra}


def _runs(root, state, warnings):
    from product_delivery_agent.team_orchestration import read_run
    result = []
    for run_id in state.get("team_runs", {}):
        try:
            result.append(read_run(root, state, run_id))
        except (ValueError, OSError) as exc:
            warnings.append(f"团队运行 {run_id} 无法验证：{exc}")
    return result


def _packages(root, runs, task_id):
    rows = []
    for run in runs:
        if run.get("task_id") != task_id or run.get("status") in {"stale", "cancelled"}:
            continue
        for key, value in run.get("work_packages", {}).items():
            sources = _refs(root, [{"path": r["ref"], "sha256": r["sha256"]} for r in value.get("accepted_artifacts", [])])
            rows.append({"id": key, "run_id": run["run_id"], "role_ids": value.get("task", {}).get("role_ids", []),
                         "status": value.get("status", "pending"), "agent_id": value.get("agent_id"),
                         "agent_display_name": value.get("agent_display_name"),
                         "agent_spawn_name": value.get("agent_spawn_name"), "spawn_source": value.get("spawn_source"),
                         "identity_status": "current" if value.get("agent_display_name") else "historical",
                         "identity_history": [{**{field: previous.get(field) for field in (
                             "agent_display_name", "agent_spawn_name", "agent_id", "spawn_source", "attempt", "status")},
                             "identity_status": "historical"} for previous in value.get("history", [])],
                         "attempt": value.get("attempt"), "stage": run.get("stage"), "sources": sources,
                         "valid": all(r["status"] == "current" for r in sources)})
    return rows


def _tasks(root, state, runs):
    goal = state.get("delivery_goal") or {}
    planned = goal.get("planned_tasks") or (state.get("journey_slice_task_queue") or {}).get("tasks", [])
    completed = set(goal.get("completed_tasks", []))
    results = []
    for task in planned:
        task_id = task["task_id"]
        artifact = goal.get("task_completion_artifacts", {}).get(task_id, {})
        slice_record = (state.get("task_executed_evidence") or {}).get("records", {}).get(task_id, {})
        evidence = _refs(root, _evidence_refs(root, artifact) + _evidence_refs(root, slice_record))
        verified = bool(task_id in completed and artifact.get("planned_task_hash") == task.get("planned_task_hash") and
                        task.get("planned_task_hash") and artifact.get("verification_exit_code") == 0 and
                        artifact.get("verification_command") == task.get("verification") and evidence and
                        all(r["status"] == "current" for r in evidence))
        if (state.get("journey_slice_task_policy") or {}).get("status") == "required":
            verified = verified and bool(slice_record.get("status") == "passed" and
                slice_record.get("planned_task_hash") == task.get("planned_task_hash") and
                slice_record.get("obligation_ids") == task.get("obligation_ids") and slice_record.get("records"))
        packages = _packages(root, runs, task_id)
        current = task_id == goal.get("current_task_cursor")
        produced = task_id in completed or bool(packages and all(p["status"] in {"ready", "integrated"} and p["valid"] for p in packages))
        integrated = task_id in completed or bool(packages and all(p["status"] == "integrated" and p["valid"] for p in packages))
        status = "verified" if verified else "integrated" if integrated else "produced" if produced else "working" if current else "planned"
        results.append({**task, "status": status, "current": current, "verified": verified, "produced": produced,
            "integrated": integrated, "work_packages": packages, "evidence": evidence,
            "owner": ", ".join((p.get("agent_display_name") or "历史成员") + " (" + p["agent_id"] + ")" for p in packages if p.get("agent_id") and p["status"] == "running") or "主线程"})
    return results


def _reviews(root, state):
    from product_delivery_agent.gatekeeper import _review_is_current, role_review_stale_reason
    rows = []
    for gate, value in (state.get("multi_agent_reviews") or {}).items():
        status = value.get("status", "missing")
        if status == "passed":
            try:
                if not _review_is_current(state, gate, root):
                    status = "stale"
            except (ValueError, KeyError, TypeError):
                status = "stale"
        refs = [{"path": r.get("ref"), "sha256": r.get("sha256")} for r in (value.get("role_context") or {}).get("input_refs", {}).values()]
        if value.get("role_artifact_ref"):
            refs.append({"path": value["role_artifact_ref"].get("ref"), "sha256": value["role_artifact_ref"].get("sha256")})
        rows.append({"gate": gate, "status": status, "sources": _refs(root, refs),
                     "agent_identities": copy.deepcopy(value.get("agent_identities") or []),
                     "reason": role_review_stale_reason(state, gate, root) if status == "stale" else None})
    return rows


def _stages(state, runs, closure):
    from product_delivery_agent.team_orchestration import entry_stage
    current = entry_stage(state)
    if str(state.get("stage", "")).startswith(("architecture", "version", "roadmap")):
        current = "architecture_version_planning"
    active_run = next((r for r in reversed(runs) if r["status"] not in {"completed", "cancelled", "stale"}), None)
    if active_run:
        current = active_run["stage"]
    finished = {r["stage"] for r in runs if r["status"] == "completed"}
    # Coordinator deliveries do not have TeamRun rows. Only mark a stage
    # complete when canonical evidence says so; otherwise leave it unknown so
    # the map cannot invent architectural progress from a later gate.
    readiness = state.get("confirmation_readiness") or {}
    reviews = state.get("multi_agent_reviews") or {}
    if state.get("open_spec_draft_ready") and reviews.get("scenario", {}).get("status") == "passed":
        finished.add("product_definition")
    if readiness.get("product_baseline") == "confirmed":
        finished.add("open_spec_product_surface")
    if readiness.get("test_coverage_plan") == "confirmed":
        finished.add("test_design")
    rows = []
    for identity, title in STAGES:
        status = "completed" if identity in finished else "current" if identity == current else "unknown"
        if state.get("paused") and identity == current:
            status = "paused"
        if closure and identity == "delivery_preparation":
            status = "completed"
        rows.append({"id": identity, "title": title, "status": status})
    return rows


def _diff(old: dict, current: dict, label: str) -> list:
    changes = []
    for group in ("goals", "components", "capabilities", "task_bindings", "edges"):
        def row_key(row):
            return row.get("id") or row.get("task_id") or _hash([row.get("from"), row.get("to"), row.get("kind")])
        before = {row_key(r): r for r in old.get(group, [])}
        after = {row_key(r): r for r in current.get(group, [])}
        for key in sorted(set(before) | set(after)):
            left, right = before.get(key), after.get(key)
            if left == right:
                continue
            operation = "新增" if left is None else "移除" if right is None else "调整"
            name = (right or left).get("title", key)
            changes.append(_change("unexplained", f"{label}：{operation} {name}",
                "结构化计划存在差异；查看具体变更依据。", identity=f"diff-{label}-{group}-{key}",
                before=(left or {}).get("title", "无"), after=(right or {}).get("title", "无"),
                before_detail=left, after_detail=right, affected_ids=[key], comparison=label))
    return changes


def project_map(root: Path, state: dict, revisions: list, config: dict) -> dict:
    plan = copy.deepcopy(revisions[-1]["plan"]) if revisions else {}
    warnings = []
    if not plan:
        warnings.append("尚未登记目标与架构关联。运行进度仍可查看；由主线程根据产品蓝图和架构资料补建地图。")
    runs = _runs(root, state, warnings)
    all_packages = [p for task_id in sorted({r.get("task_id") for r in runs}, key=str) for p in _packages(root, runs, task_id)]
    tasks = _tasks(root, state, runs)
    task_index = {t["task_id"]: t for t in tasks}
    current_version = plan.get("current_version", state.get("feature_slug") or "当前交付")
    source_refs = _refs(root, _sources_in(plan))
    changes = []
    for row in plan.get("changes", []):
        row = copy.deepcopy(row)
        row["sources"] = _refs(root, row.get("sources", []))
        if row["kind"] == "approved_change" and not _approval_matches(state, row.get("approval")):
            row.update(kind="unexplained", reason=row["reason"] + "；原批准已不对应当前基线，需要复核。")
        changes.append(row)
    if len(revisions) > 1:
        delta = _diff(revisions[0]["plan"], plan, "相对初始计划")
        approved = [r for r in revisions[:-1] if r["baseline_status"] == "approved"]
        if approved and approved[-1]["revision"] != 1:
            delta += _diff(approved[-1]["plan"], plan, "相对最近批准计划")
        for change in delta:
            explanation = next((c for c in changes if set(c.get("affected_ids", [])) & set(change["affected_ids"])), None)
            if explanation:
                change.update({k: explanation[k] for k in ("kind", "reason", "impact", "owner", "next_action", "sources")})
            changes.append(change)
    for ref in source_refs:
        if ref["status"] != "current":
            changes.append(_change("stale_evidence", "资料已变化：" + ref["path"], "实际文件与登记哈希不一致或文件缺失。", sources=[ref],
                impact="相关目标与架构解释需要重新核实", next_action="核对变更，登记新的计划修订；涉及范围变化时沿用既有确认流程"))
    for package in all_packages:
        if not package["valid"]:
            changes.append(_change("stale_evidence", "工作包产物已失效：" + package["id"],
                "归档产物与接纳时哈希不一致。", sources=package["sources"], next_action="由主线程核实产物并复验相关阶段"))
    valid_bindings = []
    for binding in plan.get("task_bindings", []):
        task = task_index.get(binding["task_id"])
        if (binding.get("delivery_id") == state["delivery_id"] and task and task.get("planned_task_hash") == binding.get("planned_task_hash")):
            valid_bindings.append(binding)
        else:
            changes.append(_change("stale_evidence", "任务关联失效：" + binding["task_id"], "任务已变更或不属于当前交付，旧关联不能复用。"))
    mapped = {b["task_id"] for b in valid_bindings}
    for task in tasks:
        if task["task_id"] not in mapped:
            changes.append(_change("unexplained", "任务尚未关联目标：" + task["task_id"], task.get("title", ""),
                                  next_action="补充任务服务的能力与目标；若是范围新增，登记变更依据"))
        for ref in task["evidence"]:
            if ref["status"] != "current":
                changes.append(_change("stale_evidence", "任务证据失效：" + task["task_id"], ref["path"], sources=[ref], next_action="重新验证该任务并登记真实证据"))
    reviews = _reviews(root, state)
    for review in reviews:
        if review["status"] == "stale":
            changes.append(_change("stale_evidence", "评审输入或证据已失效：" + review["gate"],
                review.get("reason") or "评审不再对应当前输入快照", sources=review["sources"], next_action="复验受影响的评审门禁"))
    required_reviews = {"scenario", "test", "test_coverage", "test_implementation"}
    if state.get("project_type") == "ui":
        required_reviews.add("ui_conformance")
    reviewed = required_reviews <= {r["gate"] for r in reviews if r["status"] == "passed"}
    from product_delivery_agent.gatekeeper import closure_integrity_errors
    closure = bool((state.get("closure_validation") or {}).get("status") == "passed" and
        (state.get("feature_closure") or {}).get("status") == "passed" and
        (state.get("delivery_goal") or {}).get("status") == "complete" and not closure_integrity_errors(state))
    capabilities, remaining = [], []
    obligations = {o["obligation_id"]: o for o in (state.get("planned_e2e_obligations") or {}).get("obligations", [])}
    scenario_rows = (state.get("scenario_matrix") or {}).get("rows", [])
    scenarios = {s["scenario_id"]: s for s in scenario_rows}
    for item in plan.get("capabilities", []):
        capability = copy.deepcopy(item)
        bound_tasks = [task_index[b["task_id"]] for b in valid_bindings if item["id"] in b["capability_ids"]]
        capability["task_ids"] = [t["task_id"] for t in bound_tasks]
        capability["sources"] = _refs(root, item.get("sources", []))
        sources_ok = bool(capability["sources"] and all(r["status"] == "current" for r in source_refs + capability["sources"]))
        required_obligations = set(item.get("obligation_ids", []))
        required_scenarios = set(item.get("scenario_ids", []))
        required_obligations.update(oid for oid, o in obligations.items() if o.get("scenario_id") in required_scenarios)
        task_obligations = {oid for t in bound_tasks for oid in t.get("obligation_ids", [])}
        missing_obligations = required_obligations - task_obligations
        missing_scenarios = required_scenarios - {obligations[oid].get("scenario_id") for oid in required_obligations if oid in obligations}
        verified = bool(bound_tasks and all(t["verified"] for t in bound_tasks) and sources_ok and not missing_obligations and not missing_scenarios)
        capability["scenarios"] = [scenarios[sid] for sid in sorted(required_scenarios) if sid in scenarios]
        capability["obligations"] = [{**obligations[oid], "status": "verified" if verified else "missing" if oid in missing_obligations else "pending"}
                                      for oid in sorted(required_obligations | task_obligations) if oid in obligations]
        milestones = {"produced": bool(bound_tasks and all(t["produced"] for t in bound_tasks)),
                      "integrated": bool(bound_tasks and all(t["integrated"] for t in bound_tasks)),
                      "verified": verified, "reviewed": verified and reviewed, "delivered": verified and reviewed and closure}
        status = next((key for key in ("delivered", "reviewed", "verified", "integrated", "produced") if milestones[key]), None)
        capability["current"] = any(t["current"] for t in bound_tasks)
        capability["status"] = status or ("working" if capability["current"] else "planned")
        capability["milestones"] = milestones
        gaps = []
        if current_version in item.get("version_ids", []):
            if not bound_tasks:
                gaps.append("尚未关联当前交付的 TASK")
            if not sources_ok:
                gaps.append("计划来源需核实")
            if missing_obligations:
                gaps.append("未被关联 TASK 覆盖的测试义务：" + "、".join(sorted(missing_obligations)))
            if missing_scenarios:
                gaps.append("缺少测试义务的场景：" + "、".join(sorted(missing_scenarios)))
            if not verified:
                gaps.append("尚未取得全部适用任务的有效验证证据")
            elif not reviewed:
                gaps.append("尚需当前快照的独立评审")
            elif not closure:
                gaps.append("尚需正式交付闭包")
            if gaps:
                remaining.append({"id": item["id"], "title": item["title"], "reason": "；".join(gaps),
                                  "next_action": "关联任务并补齐证据" if not bound_tasks else "完成适用验证、评审与交付门禁"})
        capability["gaps"] = gaps
        capabilities.append(capability)
    components = []
    for item in plan.get("components", []):
        related = [c for c in capabilities if item["id"] in c["component_ids"]]
        components.append({**item, "capability_ids": [c["id"] for c in related], "current": any(c["current"] for c in related),
                           "version_ids": sorted({v for c in related for v in c["version_ids"]}), "sources": _refs(root, item.get("sources", []))})
    current = next((t for t in tasks if t["current"]), {})
    active_packages = _packages(root, runs, current.get("task_id"))
    active_packages = [p for p in active_packages if p["status"] not in {"integrated", "failed"}]
    active_caps = [c for c in capabilities if c["current"]]
    active_components = {i for c in active_caps for i in c["component_ids"]}
    unlocks = [next(c["title"] for c in components if c["id"] == e["to"]) for e in plan.get("edges", []) if e["from"] in active_components]
    next_action = state.get("next_gate") or (state.get("delivery_goal") or {}).get("next_action") or "完善产品定义与计划"
    blockers = list(state.get("blocked_until") or [])
    blockers += [str(k) for k in (state.get("pending_user_decisions") or {})]
    if state.get("paused"):
        blockers.insert(0, "交付已暂停，恢复后继续")
    history = [{"revision": r["revision"], "generated_at": r["generated_at"], "summary": r["summary"], "baseline_status": r["baseline_status"],
                "plan": r["plan"], "sources": _refs(root, _sources_in(r["plan"]))} for r in revisions]
    approved_rows = [r for r in revisions if r["baseline_status"] == "approved"]
    source_revision = _hash({"state": _state_revision(state), "plan": revisions[-1]["sha256"] if revisions else None,
                             "sources": source_refs, "task_evidence": [t["evidence"] for t in tasks],
                             "reviews": reviews, "packages": all_packages,
                             "active_packages": active_packages, "history": history, "warnings": warnings})
    return {"schema_version": "v1", "delivery_id": state["delivery_id"], "feature_slug": state.get("feature_slug"),
            "generated_at": _now(), "source_revision": source_revision, "plan_revision": len(revisions),
            "enabled": config["enabled"], "settings_source": config["source"], "project_type": state.get("project_type"),
            "production_mode": (state.get("production_policy") or {}).get("mode", "coordinator"),
            "title": plan.get("title", "产品交付地图"), "objective": plan.get("objective") or (state.get("input_enrichment") or {}).get("raw_request") or "产品目标待登记",
            "success_criteria": plan.get("success_criteria", []), "current_version": current_version,
            "versions": plan.get("versions", [{"id": current_version, "title": current_version}]), "goals": plan.get("goals", []),
            "components": components, "capabilities": capabilities, "edges": plan.get("edges", []), "tasks": tasks,
            "current_work": {"task_id": current.get("task_id"), "title": current.get("title", "当前阶段：" + str(state.get("stage", "未知"))),
                "description": current.get("description", "本阶段尚无实现 TASK；查看生产工作包与下一门禁。"),
                "why": current.get("why") or ("服务能力：" + "、".join(c["title"] for c in active_caps) if active_caps else "目标关联待补充，暂不能判断当前工作与产品目标的一致性"),
                "unlocks": unlocks, "owner": current.get("owner", "主线程"), "blockers": blockers,
                "next_action": next_action, "work_packages": active_packages},
            "stages": _stages(state, runs, closure), "remaining": remaining, "changes": changes,
            "history": history, "reviews": reviews,
            "confirmations": [{"target": k, "status": v.get("decision", "pending")} for k, v in (state.get("user_confirmations") or {}).items()],
            "warnings": warnings, "counts": {"current_capabilities": sum(current_version in c["version_ids"] for c in capabilities),
                "verified_capabilities": sum(current_version in c["version_ids"] and c["milestones"]["verified"] for c in capabilities)},
            "closure": {"status": "passed" if closure else "unverified" if (state.get("closure_validation") or {}).get("status") == "passed" else (state.get("closure_validation") or {}).get("status", "not_run")},
            "baseline": {"initial_revision": 1 if revisions else None, "approved_revision": approved_rows[-1]["revision"] if approved_rows else None,
                         "history_complete": bool(revisions and not revisions[0]["plan"].get("history_incomplete", True))}}
