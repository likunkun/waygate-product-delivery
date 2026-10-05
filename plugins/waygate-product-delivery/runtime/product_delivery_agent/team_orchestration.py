"""Owner-controlled production runs; the host executes agents, not this module.

All mutation entrypoints are called under the workflow's state lock. Run revisions
are immutable and content-addressed by the canonical state. File integration uses
an immutable intent so interruption never licenses overwriting unrelated edits.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from product_delivery_agent.artifact_protocol import _write_state_locked
from product_delivery_agent.gatekeeper import PLUGIN_VERSION, review_input_hash
from product_delivery_agent.host_goal import assert_host_goal_owner
from product_delivery_agent.transition_journal import append_transition


class TeamError(ValueError):
    """A production operation cannot safely proceed."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable(value: Any) -> str:
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise TeamError("invalid relative path")
    p = PurePosixPath(name)
    if p.is_absolute() or any(x in {"..", "."} for x in name.split("/")) or "//" in name:
        raise TeamError("path escapes allowed root")
    dest = root
    for part in p.parts:
        dest = dest / part
        if dest.is_symlink():
            raise TeamError("symlink paths are forbidden")
    if not dest.resolve().is_relative_to(root.resolve()):
        raise TeamError("path escapes allowed root")
    return dest


def file_hash(path: Path) -> str | None:
    if path.exists() and not path.is_file():
        raise TeamError("expected a regular file")
    return sha(path.read_bytes()) if path.exists() else None


def atomic_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".team-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(name, mode & 0o777)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def entry_stage(state: dict) -> str:
    if state.get("handoff"):
        return "implementation_execution" if (state.get("delivery_goal") or {}).get("current_task_cursor") else "delivery_preparation"
    if (state.get("confirmation_readiness") or {}).get("product_baseline") == "confirmed":
        return "test_design"
    if state.get("open_spec_draft_ready"):
        return "open_spec_product_surface"
    return "product_definition"


def production_policy(state: dict, mode: str) -> dict:
    if mode not in {"coordinator", "team"}:
        raise TeamError("production mode must be coordinator or team")
    policy = {"schema_version": "production-policy-v1", "introduced_in": "1.2.0",
              "mode": mode, "delivery_id": state["delivery_id"], "feature_slug": state.get("feature_slug"),
              "owner_thread_id": (state.get("host_goal_owner") or {}).get("coordinator_thread_id"),
              "max_parallel": 2, "authorization_source": "explicit_production_mode", "entry_stage": entry_stage(state)}
    policy["policy_hash"] = stable(policy)
    return policy


def require_team(state: dict, *, allow_paused: bool = False) -> None:
    assert_host_goal_owner(state, require_binding=False)
    policy = state.get("production_policy") or {}
    if policy.get("mode") != "team":
        raise TeamError("production team authorization is required")
    if (policy.get("policy_hash") != stable({k: v for k,v in policy.items() if k != "policy_hash"})
            or policy.get("delivery_id") != state.get("delivery_id") or policy.get("feature_slug") != state.get("feature_slug")
            or policy.get("owner_thread_id") != (state.get("host_goal_owner") or {}).get("coordinator_thread_id")
            or policy.get("introduced_in") != "1.2.0" or policy.get("max_parallel") != 2):
        raise TeamError("production authorization identity or policy mismatch")
    if state.get("paused") and not allow_paused:
        raise TeamError("delivery is paused")


def scope_hash(state: dict) -> str:
    return stable({"delivery": state.get("delivery_id"), "policy": state.get("production_policy"),
                   "confirmations": state.get("user_confirmations"),
                   "launch": state.get("implementation_launch_authorization"),
                   "task": (state.get("delivery_goal") or {}).get("current_task_cursor"),
                   "task_generation": (state.get("team_task_generations") or {}).get((state.get("delivery_goal") or {}).get("current_task_cursor"), 0)})


def mode_change_ready(state: dict, mode: str, delivery_id: str) -> None:
    if mode not in {"coordinator", "team"}:
        raise TeamError("production mode must be coordinator or team")
    assert_host_goal_owner(state, require_binding=False)
    if state.get("delivery_id") != delivery_id:
        raise TeamError("production delivery identity mismatch")
    if (state.get("production_policy") or {}).get("introduced_in") != "1.2.0":
        raise TeamError("legacy active deliveries cannot change production mode")
    if any(r.get("status") not in {"completed", "cancelled", "stale"} for r in state.get("team_runs", {}).values()):
        raise TeamError("safe boundary requires no unfinished production run")
    if state.get("team_review_locks"):
        raise TeamError("safe boundary requires no active review")
    cursor = (state.get("delivery_goal") or {}).get("current_task_cursor")
    if cursor:
        # An enabled team proves a boundary through its completed prior run.
        # Coordinator mode must not claim a boundary after partial TASK evidence.
        for key in ("task_executed_evidence", "task_prototype_conformance", "ui_visual_loop"):
            if cursor in ((state.get(key) or {}).get("records") or {}):
                raise TeamError("production mode can change only between TASKs")
        if state.get("implementation", {}).get("task_started") == cursor:
            raise TeamError("production mode can change only between TASKs")


def stage_ready(state: dict, stage: str, task_id: str | None) -> None:
    from product_delivery_agent.production_profiles import get_stage_profile
    get_stage_profile(stage, state.get("project_type"))
    confirmed = state.get("confirmation_readiness") or {}
    if stage in {"test_design", "implementation_execution", "delivery_preparation"}:
        if confirmed.get("product_baseline") != "confirmed":
            raise TeamError("product baseline confirmation is required for this stage")
    elif confirmed.get("product_baseline") == "confirmed":
        raise TeamError("frozen product baseline requires the existing change workflow")
    if stage in {"implementation_execution", "delivery_preparation"}:
        if confirmed.get("test_coverage_plan") != "confirmed" or not state.get("handoff"):
            raise TeamError("test confirmation and canonical handoff required")
        if not state.get("implementation_launch_authorization"):
            raise TeamError("implementation authorization is required")
        goal = state.get("delivery_goal") or {}
        if stage == "implementation_execution":
            if not task_id or task_id != goal.get("current_task_cursor"):
                raise TeamError("implementation must bind current authoritative TASK")
        elif goal.get("current_task_cursor") is not None or not goal.get("planned_tasks"):
            raise TeamError("delivery preparation requires completed implementation TASKs")
    elif task_id is not None:
        raise TeamError("task_id is only accepted for implementation")
    if stage == "test_design" and confirmed.get("test_coverage_plan") == "confirmed":
        raise TeamError("frozen test coverage requires the existing change workflow")


def _run_root(state: dict, run_id: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", run_id):
        raise TeamError("invalid run id")
    return f".product-delivery/deliveries/{state['feature_slug']}/{state['delivery_id']}/team-runs/{run_id}"


def pending_merge_intent(root: Path, state: dict, run: dict) -> Path | None:
    directory = safe(root, _run_root(state, run["run_id"]) + "/intents")
    if not directory.exists():
        return None
    candidates = sorted(directory.glob("integrate-*.json"))
    consumed = {str(r.get("intent_path")) for r in run.get("integration_receipts", [])}
    for candidate in candidates:
        if str(candidate.relative_to(root)) not in consumed:
            return candidate
    return None


def read_run(root: Path, state: dict, run_id: str) -> dict:
    summary = state.get("team_runs", {}).get(run_id)
    if not summary:
        raise TeamError("unknown current-delivery team run")
    path = safe(root, summary["run_path"])
    if file_hash(path) != summary["run_sha256"]:
        raise TeamError("team run artifact hash mismatch")
    run = json.loads(path.read_text())
    if run.get("delivery_id") != state["delivery_id"] or run.get("run_id") != run_id:
        raise TeamError("team run identity mismatch")
    return run


def save_run(root: Path, state: dict, run: dict, transition: str) -> dict:
    relative = _run_root(state, run["run_id"]) + f"/revisions/{run['revision']}-{stable(run)[:16]}.json"
    path = safe(root, relative)
    atomic_json(path, run)
    state.setdefault("team_runs", {})[run["run_id"]] = {
        "run_path": relative, "run_sha256": file_hash(path), "stage": run["stage"],
        "status": run["status"], "revision": run["revision"], "task_id": run["task_id"],
        "work_packages": {k: {f: v.get(f) for f in ("status", "attempt", "agent_id")} for k, v in run["work_packages"].items()},
    }
    updated = append_transition(state, transition, feature_slug=state.get("feature_slug"), runtime_version=PLUGIN_VERSION,
                              output_artifact_hashes={relative: file_hash(path)}, metadata={"run_id": run["run_id"], "revision": run["revision"]})
    state.update(updated)
    _write_state_locked(root, state)
    return copy.deepcopy(run)


def integrated_outputs(run: dict) -> dict:
    outputs = {}
    for receipt in run.get("integration_receipts", []):
        outputs.update(receipt.get("outputs", {}))
    return outputs


def check_current(root: Path, state: dict, run: dict, *, integrating: bool = False) -> None:
    if run["scope_hash"] != scope_hash(state):
        raise TeamError("production input scope is stale")
    integrated = integrated_outputs(run)
    for ref in run["input_refs"].values():
        expected = integrated.get(ref["ref"], ref["sha256"])
        if file_hash(safe(root, ref["ref"])) != expected:
            raise TeamError("input snapshot changed; run is stale")


def prepare(root: Path, state: dict, stage: str, packages: list, refs: dict, task_id=None, condition_flags=None, implementation_roles=None) -> dict:
    from product_delivery_agent.production_profiles import build_stage_tasks
    require_team(state)
    stage_ready(state, stage, task_id)
    if any(r["status"] not in {"completed", "cancelled", "stale"} for r in state.get("team_runs", {}).values()):
        raise TeamError("an unfinished team run already exists")
    if state.get("team_review_locks"):
        raise TeamError("review snapshot is frozen")
    used_refs = copy.deepcopy(refs)
    for ref in used_refs.values():
        if file_hash(safe(root, ref["ref"])) != ref["sha256"]:
            raise TeamError("input file hash does not match snapshot")
    context = {"delivery_id": state["delivery_id"], "feature_slug": state["feature_slug"],
               "project_type": state["project_type"], "input_snapshot_hash": stable(used_refs),
               "task_id": task_id, "input_refs": used_refs, "condition_flags": condition_flags or []}
    if implementation_roles is not None:
        context["implementation_roles"] = implementation_roles
    bundle = build_stage_tasks(stage, context, packages)
    selected_refs = {key: ref for task in bundle["tasks"] for key,ref in task["input_refs"].items()}
    if selected_refs != used_refs:
        used_refs = selected_refs
        context.update(input_refs=used_refs, input_snapshot_hash=stable(used_refs))
        bundle = build_stage_tasks(stage, context, packages)
    material_hash = stable({"stage": stage, "task_id": task_id, "scope_hash": scope_hash(state), "input_refs": used_refs,
        "outputs": {path: file_hash(safe(root, path)) for task in bundle["tasks"] for path in task["allowed_write_paths"]}})
    if any(old.get("fingerprint") == material_hash for old in state.get("team_run_failures", [])):
        raise TeamError("identical failed production input requires material repair before retry")
    from product_delivery_agent.production_profiles import STAGES
    starting = (state.get("production_policy") or {}).get("entry_stage", "product_definition")
    completed = {r["stage"] for r in state.get("team_runs", {}).values() if r["status"] == "completed"}
    if completed and STAGES.index(stage) < max(STAGES.index(s) for s in completed) and not (stage == "implementation_execution" and (state.get("delivery_goal") or {}).get("current_task_cursor")):
        raise TeamError("earlier production stage requires explicit downstream invalidation")
    if stage != starting and STAGES.index(stage) > STAGES.index(starting):
        missing = set(bundle["profile"]["depends_on"]) - completed
        if missing:
            raise TeamError("preceding production stage required: " + ", ".join(sorted(missing)))
    run = {"schema_version": "team-run-v1", "run_id": uuid.uuid4().hex, "delivery_id": state["delivery_id"],
           "stage": stage, "project_type": state["project_type"], "task_id": task_id, "profile": bundle["profile"],
           "revision": 0, "status": "prepared", "input_refs": used_refs, "scope_hash": scope_hash(state), "material_hash": material_hash,
           "created_at": now(), "events": {}, "event_log": [], "work_packages": {}, "protection_level": "shared_fs",
           "usage": {"status": "unavailable"}, "merge_intent": None}
    for task in bundle["tasks"]:
        if stage not in {"implementation_execution", "delivery_preparation"}:
            for path in task["allowed_write_paths"]:
                if not (path.startswith(("docs/", "prototypes/")) or ("/" not in path and path.endswith(".md"))):
                    raise TeamError("design stage cannot write implementation paths")
        baseline = {p: file_hash(safe(root, p)) for p in task["allowed_write_paths"]}
        run["work_packages"][task["work_package_id"]] = {"task": task, "baseline": baseline, "attempt": 1,
             "status": "pending", "recovery_count": 0, "revision_count": 0, "history": [], "agent_id": None}
    return save_run(root, state, run, "team_run_prepared")


def stage_workspace(root: Path, state: dict, run: dict, key: str) -> None:
    row = run["work_packages"][key]
    relative = _run_root(state, run["run_id"]) + f"/work/{key}/{row['attempt']}/workspace"
    target = safe(root, relative)
    if target.exists():
        # A failed event never authorizes adopting someone else's staged bytes.
        relative = _run_root(state, run["run_id"]) + f"/work/{key}/{row['attempt']}-{uuid.uuid4().hex}/workspace"
        target = safe(root, relative)
    target.mkdir(parents=True)
    row["staging_root"] = relative
    refs = row["task"]["input_refs"]
    actual_refs = {name: {**ref, "sha256": file_hash(safe(root, ref["ref"]))} for name, ref in refs.items()}
    if actual_refs != refs:
        from product_delivery_agent.production_profiles import stable_hash
        row.setdefault("brief_history", []).append(copy.deepcopy(row["task"]))
        row["task"]["input_refs"] = actual_refs
        row["task"]["input_snapshot_hash"] = stable_hash(actual_refs)
        row["task"]["task_hash"] = stable_hash({k:v for k,v in row["task"].items() if k != "task_hash"})
    files = {v["ref"] for v in row["task"]["input_refs"].values()} | set(row["task"]["allowed_write_paths"])
    row["workspace_inputs"] = {}
    for name in files:
        source = safe(root, name)
        if source.exists():
            dest = safe(target, name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source.read_bytes())
            row["workspace_inputs"][name] = file_hash(dest)
    # Downstream patches bind to the actual accepted dependency state.
    row["baseline"] = {p: file_hash(safe(root, p)) for p in row["task"]["allowed_write_paths"]}


def verify_result_files(root: Path, row: dict) -> None:
    result = row["result"]
    stage = safe(root, row["staging_root"])
    for name, expected in row.get("workspace_inputs", {}).items():
        if name not in row["task"]["allowed_write_paths"] and file_hash(safe(stage, name)) != expected:
            raise TeamError("worker changed a readonly snapshot input")
    for art in result["artifacts"]:
        if file_hash(safe(stage, art["path"])) != art["sha256"]:
            raise TeamError("staged artifact hash changed")
    seen = set()
    for change in result["changes"]:
        name = change["path"]
        if name in seen or name not in row["task"]["allowed_write_paths"]:
            raise TeamError("change is outside assigned write paths")
        seen.add(name)
        if change["base_sha256"] != row["baseline"][name]:
            raise TeamError("patch baseline mismatch")
        op = change["operation"]
        if (op == "add") != (change["base_sha256"] is None):
            raise TeamError("patch operation conflicts with baseline")
        if op == "delete":
            if change.get("staged_path") is not None or change.get("result_sha256") is not None:
                raise TeamError("delete must have no output bytes")
        elif file_hash(safe(stage, change["staged_path"])) != change["result_sha256"]:
            raise TeamError("patch output hash changed")


def _new_attempt(row: dict, *, recovery: bool) -> None:
    counter = "recovery_count" if recovery else "revision_count"
    if row[counter] >= 1:
        raise TeamError("work package recovery/remediation limit exhausted")
    row[counter] += 1
    row["history"].append({k: copy.deepcopy(v) for k,v in row.items() if k not in {"task", "history"}})
    row["attempt"] += 1
    row["status"] = "pending"
    for k in (
        "result",
        "accepted_artifacts",
        "agent_id",
        "spawn_source",
        "started_at",
        "finished_at",
        "elapsed_seconds",
        "deadline",
        "staging_root",
        "failure_reason",
    ):
        row.pop(k, None)


def exact_replay(root: Path, state: dict, operation: str, args: tuple) -> dict | None:
    """Authenticate an already committed response without consuming a Goal observation."""
    if operation not in {"events", "integrate", "finalize"} or not args:
        return None
    run = read_run(root, state, args[0])
    if operation == "events":
        batch = args[1]
        if isinstance(batch, list) and batch and all(isinstance(e,dict) and run["events"].get(e.get("event_id")) == stable(e) for e in batch):
            return run
    elif operation == "integrate":
        receipt = next((r for r in run.get("integration_receipts", []) if r.get("source_revision") == args[1]), None)
        if receipt:
            for path, expected in receipt["outputs"].items():
                if file_hash(safe(root,path)) != integrated_outputs(run).get(path, expected):
                    raise TeamError("integration replay output conflict")
            return run
    elif run["status"] == "completed":
        receipt = run.get("finalization_receipt") or {}
        if args[1] in {run["revision"], receipt.get("source_revision")}:
            _assert_completed_outputs_current(root, run)
            return run
    return None


def events(root: Path, state: dict, run_id: str, batch: list, expected_revision: int) -> dict:
    from product_delivery_agent.production_profiles import validate_production_result
    require_team(state)
    run = read_run(root, state, run_id)
    if not isinstance(batch, list) or not batch or any(not isinstance(e,dict) for e in batch):
        raise TeamError("events must be a nonempty object list")
    ids = [e.get("event_id") for e in batch]
    if any(not isinstance(i,str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise TeamError("event ids must be unique")
    known = [e["event_id"] in run["events"] for e in batch]
    for e, exists in zip(batch, known):
        if exists and run["events"][e["event_id"]] != stable(e):
            raise TeamError("event identity conflicts with recorded payload")
    if all(known):
        return run
    if any(known) or type(expected_revision) is not int or expected_revision != run["revision"]:
        raise TeamError("event revision conflict")
    if pending_merge_intent(root, state, run) is not None:
        raise TeamError("durable merge intent must be integrated or recovered before new events")
    if run["status"] in {"completed", "cancelled", "stale", "paused"}:
        raise TeamError("run cannot accept new events")
    check_current(root, state, run)
    for event in batch:
        kind = event.get("type")
        if kind in {"review_started", "review_member", "review_rejected"}:
            _review_event(root, state, run, event)
            run["events"][event["event_id"]] = stable(event)
            run.setdefault("event_log", []).append({"event": copy.deepcopy(event), "recorded_at": now()})
            continue
        if state.get("team_review_locks"):
            raise TeamError("review snapshot is frozen")
        key = event.get("work_package_id")
        if key not in run["work_packages"]:
            raise TeamError("unknown work package")
        row = run["work_packages"][key]
        if kind == "dispatched":
            if row["status"] != "pending" or event.get("attempt") != row["attempt"]:
                raise TeamError("dispatch requires current pending attempt")
            if sum(w["status"] == "running" for w in run["work_packages"].values()) >= 2:
                raise TeamError("at most two production workers may run")
            if any(run["work_packages"][d]["status"] != "integrated" for d in row["task"]["depends_on"]):
                raise TeamError("work package dependencies are not integrated")
            for other in run["work_packages"].values():
                if other["status"] == "running" and set(other["task"]["allowed_write_paths"]) & set(row["task"]["allowed_write_paths"]):
                    raise TeamError("parallel write paths overlap")
            agent = event.get("agent_id")
            if not isinstance(agent,str) or not agent or agent == (state.get("host_goal_owner") or {}).get("coordinator_thread_id") or not event.get("spawn_source"):
                raise TeamError("real distinct worker identity and spawn source required")
            if any(w.get("agent_id") == agent and w["status"] == "running" for w in run["work_packages"].values()):
                raise TeamError("worker identity already running")
            stage_workspace(root, state, run, key)
            row.update(status="running", agent_id=agent, spawn_source=event["spawn_source"], started_at=now(),
                       deadline=(datetime.now(timezone.utc)+timedelta(seconds=1800)).isoformat())
            run["status"] = "running"
        elif kind in {"result", "failed", "timeout"}:
            if row["status"] != "running" or event.get("attempt") != row["attempt"] or event.get("agent_id") != row.get("agent_id"):
                raise TeamError("result must match the running identity and attempt")
            expired = datetime.now(timezone.utc) >= datetime.fromisoformat(row["deadline"])
            if kind == "result":
                if expired:
                    raise TeamError("late result after deadline")
                result = event.get("result")
                if not isinstance(result, dict) or result.get("identity_kind", "spawned") != "spawned" or result.get("simulated_identity") is not None or result.get("agent_id", row["agent_id"]) != row["agent_id"] or result.get("spawn_source", row["spawn_source"]) != row["spawn_source"]:
                    raise TeamError("production result identity must match the real worker")
                validate_production_result(row["task"], result)
                row["result"] = copy.deepcopy(result)
                row["finished_at"] = now()
                row["elapsed_seconds"] = (datetime.fromisoformat(row["finished_at"]) - datetime.fromisoformat(row["started_at"])).total_seconds()
                if result["status"] == "ready_for_integration":
                    verify_result_files(root, row)
                    row["status"] = "ready"
                else:
                    row["status"] = result["status"]
                    run["status"] = "needs_remediation"
            else:
                if kind == "timeout" and not expired:
                    raise TeamError("attempt deadline has not elapsed")
                if not event.get("reason"):
                    raise TeamError("failure requires reason")
                row.update(status="failed", failure_reason=event["reason"])
                run["status"] = "needs_remediation"
        elif kind in {"retry", "revise"}:
            if row["status"] not in {"failed", "needs_input", "needs_rework"} or not event.get("reason"):
                raise TeamError("retry requires failed work and a reason")
            if row["status"] == "needs_input":
                raise TeamError("new inputs require a new run snapshot")
            _new_attempt(row, recovery=kind == "retry")
            run["status"] = "running"
        elif kind == "cancel":
            if not event.get("reason") or any(w["status"] == "running" for w in run["work_packages"].values()):
                raise TeamError("cancel requires reason and quiesced workers")
            if pending_merge_intent(root, state, run) is not None:
                raise TeamError("pending integration must be recovered")
            run["status"] = "cancelled"
            state.setdefault("team_run_failures", []).append({"run_id": run["run_id"], "fingerprint": run["material_hash"], "reason": event["reason"]})
        else:
            raise TeamError("unknown team event type")
        run["events"][event["event_id"]] = stable(event)
        run.setdefault("event_log", []).append({"event": copy.deepcopy(event), "recorded_at": now()})
    run["revision"] += 1
    return save_run(root, state, run, "team_events_recorded")


def _review_event(root: Path, state: dict, run: dict, event: dict) -> None:
    gate = event.get("review_type")
    required = required_reviews(run)
    if gate not in required:
        raise TeamError("review does not belong to this production stage")
    locks = state.setdefault("team_review_locks", {})
    kind = event["type"]
    if kind == "review_started":
        if gate in locks or any(w["status"] != "integrated" for w in run["work_packages"].values()):
            raise TeamError("review requires integrated and unfrozen production")
        mode = event.get("review_mode", "spawned_subagents")
        if mode not in ("spawned_subagents", "role_simulation"):
            raise TeamError("invalid team review mode")
        simulated = mode == "role_simulation"
        if simulated and (state.get("multi_agent_policy") or {}).get("mode") != "role_simulation_allowed":
            raise TeamError("role simulation needs explicit degradation authorization")
        if simulated and event.get("reviewer_agent_ids"):
            raise TeamError("simulated review must not invent real agent identities")
        agents = event.get("reviewer_seat_ids", []) if simulated else event.get("reviewer_agent_ids", [])
        contributors = contributor_ids(state)
        owner = (state.get("host_goal_owner") or {}).get("coordinator_thread_id")
        if not isinstance(agents,list) or len(agents) != 2 or any(not isinstance(a,str) or not a for a in agents) or len(set(agents)) != 2 or (not simulated and set(agents)&(contributors|{owner})):
            raise TeamError("reviewers must be two independent non-producer identities")
        locks[gate] = {"run_id":run["run_id"], "review_mode": mode, "reviewer_agent_ids": [] if simulated else agents, "member_ids": agents, "phase":"independent", "members":{},
                       "input_hash":review_input_hash(state,gate), "sources": {**integrated_outputs(run), **{a["ref"]: a["sha256"] for w in run["work_packages"].values() for a in w.get("accepted_artifacts", [])}}}
    elif kind == "review_member":
        lock = locks.get(gate) or {}
        member_id = event.get("seat_id") if lock.get("review_mode") == "role_simulation" else event.get("agent_id")
        if lock.get("run_id") != run["run_id"] or member_id not in lock.get("member_ids",[]) or event.get("phase") != lock.get("phase"):
            raise TeamError("review phase or member identity mismatch")
        phase = lock["phase"]
        members = lock["members"].setdefault(phase,{})
        if member_id in members:
            raise TeamError("review member already returned")
        ref = event.get("artifact") or {}
        if ref.get("ref") in lock.get("sources", {}):
            raise TeamError("review evidence must be distinct from production sources")
        if file_hash(safe(root, ref.get("ref", ""))) != ref.get("sha256"):
            raise TeamError("review member evidence hash mismatch")
        members[member_id] = copy.deepcopy(ref)
        if len(members) == 2:
            lock["phase"] = {"independent":"challenge", "challenge":"revision", "revision":"complete"}[phase]
    else:
        lock = locks.get(gate) or {}
        if lock.get("phase") != "complete" or not event.get("reason"):
            raise TeamError("batch review barrier and reason required before remediation")
        targets = event.get("work_package_ids",[])
        if not targets or any(k not in run["work_packages"] for k in targets):
            raise TeamError("review remediation requires explicit work packages")
        affected_tasks = event.get("affected_task_ids", [])
        if not isinstance(affected_tasks, list) or any(not isinstance(t, str) for t in affected_tasks) or len(affected_tasks) != len(set(affected_tasks)):
            raise TeamError("affected_task_ids must be unique TASK identities")
        if affected_tasks:
            if run["stage"] != "delivery_preparation" or gate not in {"test_implementation", "ui_conformance"}:
                raise TeamError("affected TASK rework requires post-implementation review")
            completed = set((state.get("delivery_goal") or {}).get("completed_tasks", []))
            if set(affected_tasks) - completed:
                raise TeamError("review can only reopen existing completed TASKs")
            run["remediation_task_ids"] = sorted(set(run.get("remediation_task_ids", [])) | set(affected_tasks))
        state.setdefault("team_review_history", []).append({"review_type": gate, "status": "needs_remediation", "reason": event["reason"], **lock})
        locks.pop(gate)
        pending = set(run.get("remediation_targets", [])) | set(targets)
        run["remediation_targets"] = sorted(pending)
        run["status"] = "needs_remediation"
        activate_remediation(state, run)


def output_identity(run: dict) -> str:
    return stable({"outputs": integrated_outputs(run), "artifacts": {
        key: row.get("accepted_artifacts", []) for key,row in run["work_packages"].items()}})


def activate_remediation(state: dict, run: dict) -> bool:
    targets = run.get("remediation_targets", [])
    if not targets or state.get("team_review_locks"):
        return False
    affected = set(run.get("remediation_task_ids", []))
    if affected:
        goal = state["delivery_goal"]
        completions = goal.setdefault("task_completion_artifacts", {})
        state.setdefault("team_task_rework_history", []).append({
            "source_run_id": run["run_id"], "task_ids": sorted(affected),
            "completion_artifacts": {key: copy.deepcopy(completions.get(key)) for key in affected},
            "reopened_at": now(),
        })
        generations = state.setdefault("team_task_generations", {})
        for task_id in affected:
            generations[task_id] = generations.get(task_id, 0) + 1
            completions.pop(task_id, None)
            for evidence_type in ("task_executed_evidence", "task_prototype_conformance"):
                record = (state.get(evidence_type) or {}).get("records", {}).get(task_id)
                if isinstance(record, dict):
                    record.update(status="stale", stale_reason="team_review_task_rework")
        goal["completed_tasks"] = [key for key in goal.get("completed_tasks", []) if key not in affected]
        remaining = [t["task_id"] for t in goal["planned_tasks"] if t["task_id"] not in set(goal["completed_tasks"])]
        goal.update(status="implementation_in_progress", current_task_cursor=remaining[0], next_action=remaining[0])
        state.update(status="implementation_in_progress", stage="implementation_in_progress", next_gate=remaining[0])
        state.setdefault("implementation", {}).update(current_task=remaining[0], completed_tasks=list(goal["completed_tasks"]))
        state["team_pending_task_repairs"] = sorted(affected)
        for evidence_type in ("executed_browser_evidence", "executed_behavior_evidence", "prototype_production_conformance"):
            record = state.get(evidence_type)
            if isinstance(record, dict) and record.get("status") == "passed":
                record.update(status="stale", stale_reason="team_review_task_rework")
        run.update(status="stale", failure_reason="implementation TASKs reopened by independent review")
    else:
        exhausted = any(run["work_packages"][key]["revision_count"] >= 1 for key in targets)
        for key in targets:
            if exhausted:
                run["work_packages"][key]["status"] = "needs_rework"
            else:
                _new_attempt(run["work_packages"][key], recovery=False)
        run["status"] = "needs_remediation" if exhausted else "running"
    for gate in required_reviews(run):
        review = (state.get("multi_agent_reviews") or {}).get(gate) or {}
        if review.get("team_run_id") == run["run_id"]:
            review.update(status="stale", stale_reason="team_production_remediation")
    run["remediation_targets"] = []
    return True


def accept_review(root: Path, state: dict, gate: str, lock: dict) -> None:
    run = read_run(root, state, lock["run_id"])
    state["multi_agent_reviews"][gate]["team_output_hash"] = output_identity(run)
    if activate_remediation(state, run):
        run["revision"] += 1
        save_run(root, state, run, "team_batch_remediation_prepared")


def contributor_ids(state: dict) -> set:
    return set(state.get("production_contributors", []))


def validate_review_submission(root: Path, state: dict, gate: str, review: dict) -> None:
    if set(review.get("reviewer_agent_ids", [])) & contributor_ids(state):
        raise TeamError("production contributors cannot be independent reviewers")
    if (state.get("production_policy") or {}).get("mode") != "team":
        return
    lock = (state.get("team_review_locks") or {}).get(gate)
    if not lock or lock.get("phase") != "complete":
        raise TeamError("team review requires completed independent/challenge/revision barriers")
    run = read_run(root, state, lock["run_id"])
    check_current(root, state, run)
    if review.get("review_mode", "spawned_subagents") != lock.get("review_mode", "spawned_subagents"):
        raise TeamError("review mode must match the frozen review batch")
    if set(review.get("reviewer_agent_ids", [])) != set(lock["reviewer_agent_ids"]):
        raise TeamError("review identities must match frozen independent seats")
    if review_input_hash(state,gate) != lock["input_hash"]:
        raise TeamError("review input snapshot is stale")
    for path, expected in lock["sources"].items():
        if file_hash(safe(root,path)) != expected:
            raise TeamError("reviewed source changed during frozen review")
    for phase in lock["members"].values():
        for ref in phase.values():
            if file_hash(safe(root,ref["ref"])) != ref["sha256"]:
                raise TeamError("review phase artifact changed")


def required_reviews(run: dict) -> list:
    return {"open_spec_product_surface":["scenario"], "test_design":["test","test_coverage"],
            "delivery_preparation":["test_implementation"] + (["ui_conformance"] if run["project_type"] == "ui" else [])}.get(run["stage"],[])


def _assert_completed_outputs_current(root: Path, run: dict) -> None:
    for row in run["work_packages"].values():
        if row["status"] != "integrated":
            raise TeamError("all production work packages must be integrated")
        for artifact in row.get("accepted_artifacts", []):
            if file_hash(safe(root, artifact["ref"])) != artifact["sha256"]:
                raise TeamError("accepted production artifact changed")
    for path, expected in integrated_outputs(run).items():
        if file_hash(safe(root, path)) != expected:
            raise TeamError("integrated production output changed")


def integrate(root: Path, state: dict, run_id: str, expected_revision: int) -> dict:
    require_team(state)
    run = read_run(root,state,run_id)
    if state.get("team_review_locks"):
        raise TeamError("review snapshot is frozen")
    if type(expected_revision) is not int:
        raise TeamError("integration revision must be an integer")
    prior = next((r for r in run.get("integration_receipts", []) if r.get("source_revision") == expected_revision), None)
    if prior:
        for path, expected in prior["outputs"].items():
            if file_hash(safe(root, path)) != integrated_outputs(run).get(path, expected):
                raise TeamError("integration replay conflicts with current output")
        return run
    if run["revision"] != expected_revision:
        raise TeamError("integration revision conflict")
    if run["status"] in {"completed","paused","cancelled","stale"}:
        raise TeamError("run cannot integrate")
    # Resume a durable intent even if the caller lost the response after partial application.
    intent_path = safe(root, _run_root(state,run_id) + f"/intents/integrate-{expected_revision}.json")
    if intent_path.exists():
        intent = json.loads(intent_path.read_text())
        content = {k:v for k,v in intent.items() if k != "intent_hash"}
        if stable(content) != intent.get("intent_hash") or intent.get("run_sha256") != stable(run):
            raise TeamError("integration intent identity/hash mismatch")
    else:
        check_current(root,state,run)
        ready = {k:w for k,w in run["work_packages"].items() if w["status"] == "ready"}
        if not ready:
            raise TeamError("no ready production results to integrate")
        changes=[]
        snapshots={}
        targets=set()
        for key,row in ready.items():
            verify_result_files(root,row)
            snapshots[key] = [{"artifact": copy.deepcopy(artifact), "content_b64": base64.b64encode(safe(safe(root,row["staging_root"]),artifact["path"]).read_bytes()).decode()}
                              for artifact in row["result"]["artifacts"]]
            for change in row["result"]["changes"]:
                if change["path"] in targets:
                    raise TeamError("conflicting ready patches require serial resolution")
                targets.add(change["path"])
                target=safe(root,change["path"])
                if file_hash(target) != change["base_sha256"]:
                    raise TeamError("target baseline conflict; external edits preserved")
                data = None if change["operation"] == "delete" else safe(safe(root,row["staging_root"]),change["staged_path"]).read_bytes()
                changes.append({**change,"content_b64":base64.b64encode(data).decode() if data is not None else None,
                                "mode": (target.stat().st_mode & 0o777) if target.exists() else 0o644})
        intent={"run_id":run_id,"run_sha256":stable(run),"revision":expected_revision,"packages":list(ready),"changes":changes,"artifact_snapshots":snapshots}
        intent["intent_hash"]=stable(intent)
        atomic_json(intent_path,intent)
    approved_changes = []
    if not isinstance(intent.get("packages"), list) or len(intent["packages"]) != len(set(intent["packages"])):
        raise TeamError("invalid integration package intent")
    for key in intent["packages"]:
        row = run["work_packages"].get(key)
        if not row or row["status"] != "ready":
            raise TeamError("intent references a package not ready for integration")
        approved_changes.extend(row["result"]["changes"])
        snapshots = intent.get("artifact_snapshots", {}).get(key, [])
        if [item.get("artifact") for item in snapshots] != row["result"]["artifacts"]:
            raise TeamError("integration artifact snapshot differs from accepted result")
        for item in snapshots:
            if sha(base64.b64decode(item["content_b64"], validate=True)) != item["artifact"]["sha256"]:
                raise TeamError("durable artifact snapshot hash mismatch")
    if [{k: c.get(k) for k in ("path", "operation", "base_sha256", "result_sha256", "staged_path")} for c in intent["changes"]] != approved_changes:
        raise TeamError("integration intent differs from submitted immutable patches")
    # Preflight the entire set before writing a single target, including recovery.
    expected_outputs={c["path"]:c["result_sha256"] for c in intent["changes"]}
    if scope_hash(state) != run["scope_hash"]:
        raise TeamError("integration scope is stale")
    previous_outputs = integrated_outputs(run)
    for ref in run["input_refs"].values():
        actual=file_hash(safe(root,ref["ref"]))
        allowed={previous_outputs.get(ref["ref"],ref["sha256"])}
        if ref["ref"] in expected_outputs: allowed.add(expected_outputs[ref["ref"]])
        if actual not in allowed: raise TeamError("integration input snapshot is stale")
    for c in intent["changes"]:
        if file_hash(safe(root,c["path"])) not in {c["base_sha256"],c["result_sha256"]}:
            raise TeamError("integration recovery conflict; external edit preserved")
        if c["content_b64"] is not None and sha(base64.b64decode(c["content_b64"],validate=True)) != c["result_sha256"]:
            raise TeamError("integration content hash mismatch")
    for c in intent["changes"]:
        target=safe(root,c["path"])
        if file_hash(target) == c["result_sha256"]: continue
        if c["operation"] == "delete": target.unlink()
        else:
            atomic_bytes(target, base64.b64decode(c["content_b64"]), c["mode"])
    for key in intent["packages"]:
        row=run["work_packages"][key]
        accepted = []
        for index, snapshot in enumerate(intent["artifact_snapshots"][key]):
            artifact = snapshot["artifact"]
            content = base64.b64decode(snapshot["content_b64"], validate=True)
            if sha(content) != artifact["sha256"]:
                raise TeamError("output artifact changed during acceptance")
            relative = _run_root(state, run_id) + f"/accepted/{key}/{row['attempt']}/{index}-{artifact['sha256']}"
            dest = safe(root, relative)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and file_hash(dest) != artifact["sha256"]:
                raise TeamError("accepted artifact identity conflict")
            atomic_bytes(dest, content)
            accepted.append({**artifact, "ref": relative})
        row["accepted_artifacts"] = accepted
        row["status"]="integrated"
        state["production_contributors"]=sorted(contributor_ids(state)|{row["agent_id"]})
    run.setdefault("integration_receipts",[]).append({"intent_path":str(intent_path.relative_to(root)),"intent_hash":intent["intent_hash"],"integrated_at":now(), "source_revision": expected_revision, "outputs": expected_outputs})
    run["status"]="integrated" if all(w["status"]=="integrated" for w in run["work_packages"].values()) else "running"
    run["revision"]+=1
    return save_run(root,state,run,"team_results_integrated")


def finalize(root: Path,state: dict,run_id: str,expected_revision: int) -> dict:
    require_team(state)
    run=read_run(root,state,run_id)
    if run["status"] == "completed":
        receipt = run.get("finalization_receipt") or {}
        if expected_revision in {run["revision"], receipt.get("source_revision")}:
            _assert_completed_outputs_current(root, run)
            return run
    if expected_revision!=run["revision"] or run["status"]!="integrated":
        raise TeamError("finalization requires current integrated run")
    check_current(root,state,run)
    _assert_completed_outputs_current(root, run)
    if state.get("team_review_locks"): raise TeamError("review remains unfinished")
    for gate in required_reviews(run):
        review=(state.get("multi_agent_reviews") or {}).get(gate) or {}
        if review.get("status")!="passed" or review.get("team_run_id")!=run_id or review.get("team_output_hash") != output_identity(run):
            raise TeamError("current independent review required: "+gate)
    if run["stage"]=="implementation_execution":
        from product_delivery_agent.delivery_goal import _validate_task_prototype_conformance, _validate_task_slice_evidence
        task=next((t for t in state["delivery_goal"]["planned_tasks"] if t["task_id"]==run["task_id"]),None)
        if task is None: raise TeamError("current TASK not found")
        _validate_task_prototype_conformance(state,task)
        _validate_task_slice_evidence(state,task)
    run["status"]="completed"
    run["completed_at"]=now()
    run["elapsed_seconds"]=(datetime.fromisoformat(run["completed_at"])-datetime.fromisoformat(run["created_at"])).total_seconds()
    source_revision = expected_revision
    run["revision"]+=1
    run["finalization_receipt"] = {
        "source_revision": source_revision,
        "final_revision": run["revision"],
        "output_identity": output_identity(run),
        "completed_at": run["completed_at"],
    }
    return save_run(root,state,run,"team_run_completed")


def pause_runs(root: Path,state: dict) -> dict:
    for run_id,summary in list(state.get("team_runs",{}).items()):
        if summary["status"] in {"completed","cancelled","stale","paused"}: continue
        run=read_run(root,state,run_id)
        if pending_merge_intent(root, state, run) is not None:
            raise TeamError("cannot pause a run with a pending integration intent")
        for row in run["work_packages"].values():
            if row["status"]=="running":
                row["history"].append({k:copy.deepcopy(v) for k,v in row.items() if k not in {"history","task"}})
                row["attempt"]+=1
                row["status"]="pending"
                row.pop("agent_id",None)
        run["resume_status"]=run["status"]
        run["status"]="paused"
        run["revision"]+=1
        save_run(root,state,run,"team_run_paused")
    return state


def resume_runs(root: Path,state: dict) -> dict:
    for run_id,summary in list(state.get("team_runs",{}).items()):
        if summary["status"]!="paused": continue
        run=read_run(root,state,run_id)
        try:
            check_current(root,state,run)
            run["status"]=run.pop("resume_status","running")
        except TeamError as error:
            run.update(status="stale",failure_reason=str(error))
            locks = state.setdefault("team_review_locks", {})
            for gate in list(locks):
                if locks[gate].get("run_id") == run_id:
                    state.setdefault("team_review_history", []).append({"review_type": gate, "reason": "production_snapshot_stale", **locks.pop(gate)})
        run["revision"]+=1
        save_run(root,state,run,"team_run_resumed")
    return state


def assert_team_closure_ready(state: dict, root: Path | None) -> None:
    runs = state.get("team_runs", {})
    if not any(r.get("stage") == "delivery_preparation" and r.get("status") == "completed" for r in runs.values()):
        raise TeamError("production delivery_preparation must complete before formal closure")
    if state.get("team_review_locks") or any(r.get("status") not in {"completed", "cancelled", "stale"} for r in runs.values()):
        raise TeamError("unfinished production work blocks formal closure")
    if root is None:
        raise TeamError("project_root required for production closure evidence")
    for run_id, summary in runs.items():
        if summary.get("status") != "completed":
            continue
        run = read_run(root, state, run_id)
        _assert_completed_outputs_current(root, run)
