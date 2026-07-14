"""Local workflow prototype for product delivery mode."""

from __future__ import annotations

import json
import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from product_delivery_agent.artifact_protocol import (
    AUTHORIZED_REVIEW_TYPES,
    ARTIFACT_ROOT,
    CORE_ARTIFACTS,
    initialize_workspace,
    load_state,
    new_delivery_state,
    write_state,
)
from product_delivery_agent.closure import (
    ClosureGateError,
    render_feature_closure,
    validate_feature_closure,
)
from product_delivery_agent.confirmation import (
    ConfirmationError,
    render_user_confirmation,
    validate_confirmation_message,
    validate_user_confirmation,
)
from product_delivery_agent.confirmation_policy import (
    is_recordable_user_confirmation_target,
)
from product_delivery_agent.coverage_audit import (
    build_prototype_production_conformance,
    build_executed_browser_evidence,
    build_planned_e2e_obligations,
    build_coverage_audit,
    render_coverage_audit,
)
from product_delivery_agent.delivery_goal import (
    DeliveryGoalError,
    assert_goal_can_stop as assert_delivery_goal_can_stop,
    build_delivery_goal,
    derive_remaining_tasks as derive_goal_remaining_tasks,
    mark_goal_closure_failed,
    mark_goal_complete,
    normalize_planned_tasks,
    planned_tasks_from_coverage,
    record_task_completion as record_delivery_task_completion,
    render_implementation_goal,
    render_stop_guard_result,
    render_task_queue,
)
from product_delivery_agent.gatekeeper import (
    CANONICAL_SCHEMA_VERSION,
    CANONICAL_VALIDATOR,
    PLUGIN_VERSION,
    TERMINAL_STATUSES,
    GatekeeperError,
    assert_pre_closure_ready,
    assert_pre_handoff_ready,
    derive_blockers,
    product_baseline_hash,
    requirements_e2e_confirmation_hash,
    render_closure_validator_result,
    review_input_hash,
    stable_state_hash,
    surface_input_hash,
    test_coverage_plan_hash,
    test_coverage_user_semantics_hash,
)
from product_delivery_agent.handoff import (
    build_codex_goal_handoff,
    render_handoff_document,
)
from product_delivery_agent.non_ui_behavior import (
    render_non_ui_behavior_contract,
    validate_non_ui_behavior_contract,
)
from product_delivery_agent.review_gates import (
    ReviewGateError,
    render_multi_agent_review,
    validate_multi_agent_review,
)
from product_delivery_agent.scenario_matrix import (
    render_scenario_matrix,
    validate_scenario_matrix,
)
from product_delivery_agent.skill_gates import (
    SkillGateError,
    required_skills_for_stage,
    validate_skill_gate,
)
from product_delivery_agent.transition_journal import append_transition
from product_delivery_agent.ui_prototype import (
    UIPrototypeError,
    build_prototype_contract,
    render_ui_prototype_review,
    validate_ui_prototype_review,
)


class WorkflowError(RuntimeError):
    """Raised when a workflow transition is not allowed."""


class ProductDeliveryWorkflow:
    """Small runtime facade for the V0.3 local workflow prototype."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        fallback_state: dict[str, Any] | None = None,
    ) -> None:
        self.project_root = Path(project_root)
        self.fallback_state = fallback_state

    def inspect_startup_request(
        self,
        *,
        feature_slug: str | None = None,
    ) -> dict[str, Any]:
        """Inspect whether startup creates, resumes, or conflicts with a delivery."""
        state = load_state(self.project_root, fallback_state=self.fallback_state)
        raw_state = self._load_raw_state()
        if not state:
            action = "new_delivery_required"
        else:
            current_feature = state.get("feature_slug")
            terminal = state.get("status") in TERMINAL_STATUSES or (
                raw_state.get("status") in TERMINAL_STATUSES
            )
            same_feature = feature_slug is None or feature_slug == current_feature
            if state.get("active") and not terminal and same_feature:
                action = "resume_current_delivery"
            elif state.get("active") and not terminal and not same_feature:
                action = "blocked_by_active_delivery"
            else:
                action = "new_delivery_required"
        policy = (state.get("multi_agent_policy") or {}) if state else {}
        reusable = (
            action == "resume_current_delivery"
            and policy.get("execution_authorization")
            in {"authorized", "degradation_authorized"}
            and policy.get("authorization_delivery_id") == state.get("delivery_id")
            and policy.get("authorization_feature_slug") == state.get("feature_slug")
        )
        return {
            "action": action,
            "requested_feature_slug": feature_slug,
            "current_feature_slug": state.get("feature_slug") if state else None,
            "current_delivery_id": state.get("delivery_id") if state else None,
            "review_mode_selection_required": not reusable,
            "mode_selection_required": not reusable,
            "review_authorization_reusable": reusable,
            "authorization_reusable": reusable,
        }

    def start(
        self,
        *,
        feature_slug: str | None = None,
        allow_review_degradation: bool = False,
        multi_agent_mode: str | None = None,
        **deprecated_options: Any,
    ) -> dict[str, Any]:
        if deprecated_options:
            model_options = {
                "execution_mode",
                "model_profile_overrides",
            }
            if model_options.intersection(deprecated_options):
                self._raise_model_orchestration_retired()
            raise WorkflowError(
                "unsupported startup options: "
                + ", ".join(sorted(deprecated_options))
            )
        if allow_review_degradation:
            if multi_agent_mode not in {None, "role_simulation_allowed"}:
                raise WorkflowError(
                    "allow_review_degradation conflicts with multi_agent_mode"
                )
            multi_agent_mode = "role_simulation_allowed"
        if multi_agent_mode not in {
            None,
            "spawned_subagents_authorized",
            "role_simulation_allowed",
        }:
            raise WorkflowError("unsupported multi_agent_mode")

        existing_state = load_state(
            self.project_root,
            fallback_state=self.fallback_state,
        )
        raw_existing_state = self._load_raw_state()
        startup = self.inspect_startup_request(feature_slug=feature_slug)
        if startup["action"] == "blocked_by_active_delivery":
            raise WorkflowError(
                "a different active delivery already exists; close or stop it before starting another feature"
            )
        if startup["action"] == "resume_current_delivery":
            if multi_agent_mode is not None or allow_review_degradation:
                raise WorkflowError(
                    "current delivery is already active; use authorize_multi_agent_mode instead of start"
                )
            return write_state(self.project_root, existing_state)

        initialize_workspace(self.project_root)
        state = new_delivery_state()
        state["active"] = True
        state["paused"] = False
        state["intervention_enabled"] = True
        state["stage"] = "product_blueprint"
        state["activation_source"] = "waygate-product-delivery"
        state["feature_slug"] = feature_slug
        previous_delivery = self._archive_previous_delivery(
            raw_existing_state
            if raw_existing_state.get("status") in TERMINAL_STATUSES
            else existing_state
        )
        if previous_delivery:
            state["previous_delivery"] = previous_delivery
        state["open_spec_draft_ready"] = False
        state["scenario_matrix_draft_ready"] = False
        state["open_spec_freeze"] = {
            "approved_by_user": False,
            "approved_at": None,
            "confirmation_artifact_path": None,
        }
        state["multi_agent_reviews"] = {
            "scenario": {
                "status": "missing",
                "artifact": None,
            },
            "test": {
                "status": "missing",
                "artifact": None,
            },
            "test_coverage": {
                "status": "missing",
                "artifact": None,
            },
            "test_implementation": {
                "status": "missing",
                "artifact": None,
            },
            "ui_conformance": {
                "status": "missing",
                "artifact": None,
            },
        }
        state["multi_agent_policy"] = self._multi_agent_policy(
            multi_agent_mode,
            authorization_source="startup_command" if multi_agent_mode else None,
            delivery_id=state["delivery_id"],
            feature_slug=feature_slug,
        )
        state["ui_prototype"] = {
            "generated": False,
            "reviewed_by_agent": False,
            "confirmed_by_user": False,
            "confirmation_source": None,
        }
        state["prototype_contract"] = {"status": "missing"}
        state["prototype_production_conformance"] = {
            "status": "missing",
            "records": [],
        }
        state["planned_e2e_obligations"] = {
            "accepted": False,
            "accepted_by_user": False,
            "obligations": [],
            "exemptions": [],
        }
        state["executed_browser_evidence"] = {
            "status": "missing",
            "records": [],
        }
        state["executed_behavior_evidence"] = {
            "status": "missing",
            "records": [],
        }
        state["closure_validation"] = {
            "status": "not_run",
            "errors": [],
        }
        state["user_confirmations"] = {}
        state["pending_confirmations"] = {}
        state["confirmation_readiness"] = {
            "product_baseline": "draft",
            "test_coverage_plan": "blocked_on_product_baseline",
        }
        state["user_change_requests"] = []
        state["pending_user_decisions"] = {}
        if multi_agent_mode is None:
            state["pending_user_decisions"]["multi_agent_mode"] = {
                "status": "pending",
                "reason": "select multi-Agent review execution mode",
            }
            state["next_gate"] = "multi_agent_mode_selection"
        state["delivery_goal"] = None
        state["required_skill_gates"] = {
            "active_mode_startup": required_skills_for_stage("active_mode_startup"),
            "open_spec_planning": required_skills_for_stage("open_spec_planning"),
        }
        state["blocked_until"] = [
            "planning_files_ready",
            "open_spec_current_feature",
            "project_type_decision",
        ]
        state["required_artifacts"] = []
        if feature_slug:
            state["required_artifacts"].append(f"docs/open-spec/{feature_slug}/")
        return write_state(self.project_root, state)



    def authorize_multi_agent_mode(
        self,
        mode: str,
        user_message: str,
    ) -> dict[str, Any]:
        state = self._require_started(allow_pending_authorization=True)
        if mode not in {
            "spawned_subagents_authorized",
            "role_simulation_allowed",
        }:
            raise WorkflowError("unsupported multi_agent_mode")
        if not isinstance(user_message, str) or not user_message.strip():
            raise WorkflowError("user_message is required for mode authorization")
        expected_message = {
            "spawned_subagents_authorized": "启动交付，多 Agent 模式",
            "role_simulation_allowed": "启动交付，允许降级评审",
        }[mode]
        if user_message.strip() != expected_message:
            raise WorkflowError("user_message does not match multi_agent_mode")
        current_authorization = (state.get("multi_agent_policy") or {}).get(
            "execution_authorization"
        )
        if current_authorization not in {
            "pending",
            "legacy_unverified",
            "invalidated",
        }:
            raise WorkflowError("multi-Agent mode is already authorized")

        self._mark_reviews_stale(
            state,
            tuple(AUTHORIZED_REVIEW_TYPES),
            reason="multi_agent_mode_authorized",
        )
        self._invalidate_requirements_e2e_confirmation(
            state,
            reason="multi_agent_mode_authorized",
            invalidate_open_spec=True,
            invalidate_planned_e2e=True,
        )
        self._invalidate_launch_authorization(
            state,
            reason="multi_agent_mode_authorized",
        )
        state["multi_agent_policy"] = self._multi_agent_policy(
            mode,
            authorization_source="user_mode_selection",
            delivery_id=state.get("delivery_id"),
            feature_slug=state.get("feature_slug"),
        )
        state["multi_agent_policy"]["authorization_user_message"] = (
            user_message.strip()
        )
        state.setdefault("pending_user_decisions", {}).pop("multi_agent_mode", None)
        self._refresh_startup_gate(state)
        return write_state(self.project_root, state)







    def record_scenario_matrix(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        state = self._require_started()
        if self._product_baseline_is_confirmed(state) and not self._has_user_change_authorization(
            state, "product_baseline"
        ):
            raise WorkflowError(
                "confirmed product baseline requires user change authorization"
            )
        validate_scenario_matrix(rows)

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        matrix_path = artifacts_dir / "scope-scenario-matrix.md"
        matrix_path.write_text(render_scenario_matrix(rows), encoding="utf-8")

        state["open_spec_draft_ready"] = True
        state["scenario_matrix_draft_ready"] = True
        state["scenario_matrix"] = {
            "draft_ready": True,
            "rows": [dict(row) for row in rows],
            "artifact_path": "artifacts/scope-scenario-matrix.md",
        }
        self._mark_reviews_stale(
            state,
            ("scenario", "test", "test_coverage"),
            reason="scenario_matrix_changed",
        )
        self._invalidate_requirements_e2e_confirmation(
            state,
            reason="scenario_matrix_changed",
            invalidate_open_spec=True,
            invalidate_planned_e2e=True,
        )
        self._invalidate_launch_authorization(
            state,
            reason="scenario_matrix_changed",
        )
        self._remove_blockers(state, "open_spec_current_feature")
        self._add_blockers(
            state,
            "multi_agent_scenario_review",
            "user_confirmed_freeze",
        )
        state["stage"] = "scenario_matrix_draft_ready"
        state["next_gate"] = "multi_agent_scenario_review"
        return write_state(self.project_root, state)

    def record_multi_agent_review(
        self,
        review_type: str,
        review: dict[str, Any],
    ) -> dict[str, Any]:
        state = self._require_started(allow_pending_authorization=True)
        if review_type == "scenario":
            if state.get("project_type") == "ui" and not state.get(
                "ui_prototype", {}
            ).get("generated"):
                raise ReviewGateError(
                    "UI prototype draft is required before scenario review"
                )
            if state.get("project_type") == "non_ui" and not state.get(
                "non_ui_behavior_contract"
            ):
                raise ReviewGateError(
                    "non-UI behavior contract is required before scenario review"
                )
        if review_type in {"test", "test_coverage"}:
            self._require_product_baseline_confirmed(state)
        ui_change_type = None
        if review_type == "scenario" and state.get("project_type") == "ui":
            ui_change_type = (
                state.get("ui_prototype_review", {}).get("ui_change_type")
                or state.get("ui_prototype", {}).get("ui_change_type")
            )
        validate_multi_agent_review(
            review_type,
            review,
            ui_change_type=ui_change_type,
            planned_obligations=list(
                (state.get("planned_e2e_obligations") or {}).get("obligations", [])
            ),
            executed_records=list(
                (state.get("executed_browser_evidence") or {}).get("records", [])
                if state.get("project_type") == "ui"
                else (state.get("executed_behavior_evidence") or {}).get("records", [])
            ),
            prototype_contract=(
                state.get("prototype_contract") or {}
                if review_type == "ui_conformance"
                else None
            ),
        )
        review_mode = review.get("review_mode", "spawned_subagents")
        policy = state.get("multi_agent_policy", {})
        policy_mode = policy.get("mode", "authorization_pending")
        execution_authorization = policy.get("execution_authorization")
        authorized_review_types = policy.get("authorized_review_types") or []
        if review_mode == "spawned_subagents" and (
            execution_authorization != "authorized"
            or policy.get("authorization_scope") != "current_delivery"
            or not policy.get("authorization_source")
            or review_type not in authorized_review_types
        ):
            raise ReviewGateError(
                "spawned_subagents review requires explicit execution authorization for the current delivery"
            )
        if review_mode == "spawned_subagents":
            self._validate_spawned_reviewer_agents(review)
        if review_mode == "role_simulation" and (
            policy_mode != "role_simulation_allowed"
            or execution_authorization != "degradation_authorized"
            or policy.get("authorization_scope") != "current_delivery"
            or not policy.get("authorization_source")
            or review_type not in authorized_review_types
        ):
            raise ReviewGateError(
                f"role_simulation review rejected by {policy_mode} policy"
            )
        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_name = f"multi-agent-{review_type}-review.md"
        review_path = artifacts_dir / artifact_name
        review_path.write_text(render_multi_agent_review(review), encoding="utf-8")

        state.setdefault("multi_agent_reviews", {})
        state["multi_agent_reviews"][review_type] = {
            "status": "passed",
            "artifact": f"artifacts/{artifact_name}",
            "review_id": review["review_id"],
            "artifact_version": review["artifact_version"],
            "review_mode": review_mode,
            "reviewer_agent_ids": list(review.get("reviewer_agent_ids") or []),
            "reviewer_spawn_source": review.get("reviewer_spawn_source"),
            "input_snapshot_hash": review_input_hash(state, review_type),
        }
        self._remove_blockers(
            state,
            f"multi_agent_{review_type}_review",
            f"stale_multi_agent_{review_type}_review",
        )
        state["stage"] = f"multi_agent_{review_type}_review_passed"
        next_gates = {
            "scenario": "product_baseline_confirmation_preparation",
            "test": "multi_agent_test_coverage_review",
            "test_coverage": "multi_agent_test_review",
            "test_implementation": "feature_closure_after_implementation",
            "ui_conformance": "multi_agent_test_implementation_review",
        }
        next_gate = next_gates.get(review_type, "codex_goal_handoff")
        if review_type in {"test", "test_coverage"}:
            required_reviews = ("test", "test_coverage")
            reviews_current = all(
                state.get("multi_agent_reviews", {}).get(required, {}).get("status")
                == "passed"
                and state.get("multi_agent_reviews", {})
                .get(required, {})
                .get("input_snapshot_hash")
                == review_input_hash(state, required)
                for required in required_reviews
            )
            if reviews_current:
                next_gate = (
                    "implementation_launch_authorization"
                    if self._test_coverage_plan_is_user_confirmed(state)
                    else "test_coverage_confirmation_preparation"
                )
        if state.get("project_type") == "ui" and review_type == "test_implementation":
            conformance = state.get("prototype_production_conformance") or {}
            ui_review = (state.get("multi_agent_reviews") or {}).get(
                "ui_conformance"
            ) or {}
            if conformance.get("status") != "passed":
                next_gate = "prototype_production_conformance"
            elif ui_review.get("status") != "passed":
                next_gate = "multi_agent_ui_conformance_review"
        if review_type == "ui_conformance":
            test_review = (state.get("multi_agent_reviews") or {}).get(
                "test_implementation"
            ) or {}
            if test_review.get("status") == "passed":
                next_gate = "feature_closure_after_implementation"
        state["next_gate"] = next_gate
        return write_state(self.project_root, state)

    def record_implementation_launch_authorization(
        self,
        *,
        scope: str,
        verification_commands: list[str] | None = None,
        planned_tasks: list[dict[str, Any]] | None = None,
        prohibited_work: list[str] | None = None,
        user_message: str | None = None,
    ) -> dict[str, Any]:
        """Record runtime authorization to start implementation for this package."""
        state = self._require_started()
        task_queue = list(planned_tasks or planned_tasks_from_coverage(state))
        package = self._build_launch_package(
            state,
            scope=scope,
            verification_commands=verification_commands,
            prohibited_work=prohibited_work,
            planned_tasks=task_queue,
        )
        blockers = [
            blocker
            for blocker in derive_blockers(
                state,
                self.project_root,
                launch_package_hash=package["launch_package_hash"],
            )
            if blocker != "implementation_launch_authorization"
            and blocker != "stale_implementation_launch_authorization"
        ]
        if blockers:
            raise WorkflowError(
                "implementation launch blocked: " + ", ".join(sorted(blockers))
            )

        state = self._record_runtime_launch_authorization(
            state,
            package,
            scope=scope,
            user_message=user_message,
        )
        state["stage"] = "implementation_launch_authorized"
        state["next_gate"] = "codex_goal_handoff"
        return write_state(self.project_root, state)

    def record_user_confirmation(
        self,
        confirmation: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_started()
        validate_user_confirmation(confirmation)
        target = confirmation["target"]
        if not is_recordable_user_confirmation_target(target):
            raise WorkflowError(f"{target} is not a user confirmation gate")
        if target == "open_spec_freeze":
            raise WorkflowError(
                "use prepare_product_baseline_confirmation and "
                "confirm_product_baseline for modern deliveries"
            )
        raise WorkflowError(
            "use prepare_test_coverage_confirmation and "
            "confirm_test_coverage_plan for modern deliveries"
        )

    def prepare_product_baseline_confirmation(self) -> dict[str, Any]:
        """Create the single requirements-and-surface confirmation request."""
        state = self._require_started()
        project_type = state.get("project_type")
        if project_type not in {"ui", "non_ui"}:
            raise WorkflowError("project type is required before product baseline")
        review = state.get("multi_agent_reviews", {}).get("scenario", {})
        if review.get("status") != "passed" or review.get(
            "input_snapshot_hash"
        ) != review_input_hash(state, "scenario"):
            raise WorkflowError(
                "current multi-agent scenario review is required before product baseline confirmation"
            )
        if project_type == "ui":
            ui = state.get("ui_prototype") or {}
            if not ui.get("generated") or not ui.get("reviewed_by_agent"):
                raise WorkflowError("current UI prototype draft is required")
            artifact_path = str(ui.get("prototype_path") or "")
            surface_artifact_hash = str(ui.get("artifact_hash") or "")
            prototype_revision = str(ui.get("prototype_revision") or "")
            contract_hash = str(ui.get("prototype_contract_hash") or "")
            screenshot_hash = str(ui.get("prototype_screenshot_set_hash") or "")
        else:
            contract = state.get("non_ui_behavior_contract") or {}
            if not contract:
                raise WorkflowError("current non-UI behavior contract is required")
            artifact_path = str(contract.get("contract_artifact_path") or "")
            surface_artifact_hash = str(contract.get("artifact_hash") or "")
            prototype_revision = "non-ui-behavior-contract"
            contract_hash = None
            screenshot_hash = None
        baseline_hash = product_baseline_hash(state)
        pending = self._build_pending_confirmation(
            target="product_baseline",
            artifact_path=artifact_path,
            artifact_hash=baseline_hash,
            artifact_version=f"product-baseline-{baseline_hash[:12]}",
            prototype_revision=prototype_revision,
            state=state,
            prototype_contract_hash=contract_hash,
            prototype_screenshot_set_hash=screenshot_hash,
        )
        pending["surface_artifact_hash"] = surface_artifact_hash
        pending["surface_hash"] = surface_input_hash(state)
        state.setdefault("pending_confirmations", {}).pop("ui_prototype", None)
        state["pending_confirmations"]["product_baseline"] = pending
        state.setdefault("confirmation_readiness", {})[
            "product_baseline"
        ] = "ready_for_user"
        state["stage"] = "product_baseline_confirmation_ready"
        state["next_gate"] = "product_baseline_user_confirmation"
        return write_state(self.project_root, state)

    def confirm_product_baseline(
        self,
        user_message: str,
        nonce: str,
        *,
        agent_explicitly_asked: bool = False,
    ) -> dict[str, Any]:
        """Confirm requirement scope and the final UI/non-UI surface together."""
        state = self._require_started()
        pending = state.get("pending_confirmations", {}).get("product_baseline")
        if not pending:
            raise ConfirmationError("pending product baseline confirmation is required")
        if nonce != pending.get("nonce"):
            raise ConfirmationError("current product baseline confirmation nonce is required")
        current_baseline_hash = product_baseline_hash(state)
        if pending.get("artifact_hash") != current_baseline_hash:
            raise ConfirmationError("product baseline changed after confirmation preparation")
        validate_confirmation_message(
            user_message,
            agent_explicitly_asked=agent_explicitly_asked,
        )
        project_type = state.get("project_type")
        if project_type == "ui":
            ui = state.get("ui_prototype") or {}
            current_artifact_hash = self._artifact_hash(
                str(ui.get("prototype_path") or ""), require_exists=True
            )
            if current_artifact_hash != pending.get("surface_artifact_hash"):
                raise ConfirmationError("prototype changed after confirmation preparation")
            try:
                current_contract = build_prototype_contract(
                    self.project_root,
                    state.get("prototype_contract") or {},
                )
            except UIPrototypeError as cause:
                raise ConfirmationError(str(cause)) from cause
            if current_contract.get("contract_sha256") != pending.get(
                "prototype_contract_hash"
            ):
                raise ConfirmationError("prototype contract changed after preparation")
            if current_contract.get("prototype_screenshot_set_sha256") != pending.get(
                "prototype_screenshot_set_hash"
            ):
                raise ConfirmationError("prototype screenshots changed after preparation")
        elif project_type != "non_ui":
            raise WorkflowError("project type is required before product baseline")

        confirmation = {
            "confirmation_id": "CONF-product_baseline",
            "target": "product_baseline",
            "artifact_path": pending["artifact_path"],
            "artifact_version": pending["artifact_version"],
            "artifact_hash": pending["artifact_hash"],
            "surface_hash": pending["surface_hash"],
            "nonce": pending["nonce"],
            "confirmed_by": "user",
            "confirmation_source": "chat_user_reply",
            "confirmed_at": self._timestamp_from_state(state),
            "decision": "approved",
            "user_message": user_message,
        }
        if project_type == "ui":
            confirmation.update(
                {
                    "prototype_revision": pending["prototype_revision"],
                    "prototype_contract_hash": pending[
                        "prototype_contract_hash"
                    ],
                    "prototype_screenshot_set_hash": pending[
                        "prototype_screenshot_set_hash"
                    ],
                }
            )
        artifact_name = f"product-baseline-{pending['nonce']}.md"
        relative_artifact_path = f"artifacts/user-confirmations/{artifact_name}"
        confirmations_dir = (
            self.project_root / ARTIFACT_ROOT / "artifacts" / "user-confirmations"
        )
        confirmations_dir.mkdir(parents=True, exist_ok=True)
        (confirmations_dir / artifact_name).write_text(
            render_user_confirmation(confirmation), encoding="utf-8"
        )
        logical = {
            **confirmation,
            "confirmation_artifact_path": relative_artifact_path,
        }
        confirmations = state.setdefault("user_confirmations", {})
        confirmations["product_baseline"] = logical
        confirmations["open_spec_freeze"] = {
            **logical,
            "target": "open_spec_freeze",
        }
        state["open_spec_freeze"] = {
            "approved_by_user": True,
            "approved_at": confirmation["confirmed_at"],
            "confirmation_artifact_path": relative_artifact_path,
            "product_baseline_hash": pending["artifact_hash"],
        }
        state["freeze"] = {
            **state.get("freeze", {}),
            "frozen": True,
        }
        if project_type == "ui":
            ui_confirmation = {
                **logical,
                "target": "ui_prototype",
                "artifact_path": state["ui_prototype"]["prototype_path"],
                "artifact_hash": pending["surface_artifact_hash"],
            }
            confirmations["ui_prototype"] = ui_confirmation
            state["ui_prototype"] = {
                **state["ui_prototype"],
                "confirmed_by_user": True,
                "confirmation_status": "confirmed",
                "pending_confirmation_nonce": None,
                "confirmation_source": "chat_user_reply",
                "confirmation_artifact_path": relative_artifact_path,
            }
        else:
            contract_confirmation = {
                **logical,
                "target": "non_ui_behavior_contract",
                "artifact_hash": pending["surface_hash"],
            }
            confirmations["non_ui_behavior_contract"] = contract_confirmation
            state["non_ui_behavior_contract"] = {
                **state["non_ui_behavior_contract"],
                "confirmed_by_user": True,
                "confirmation_status": "confirmed",
                "confirmation_artifact_path": relative_artifact_path,
            }
        state.setdefault("pending_confirmations", {}).pop("product_baseline", None)
        state.setdefault("confirmation_readiness", {})[
            "product_baseline"
        ] = "confirmed"
        state["confirmation_readiness"][
            "test_coverage_plan"
        ] = "internal_review_pending"
        self._close_user_change_authorizations(state, "product_baseline")
        self._remove_blockers(
            state,
            "user_confirmed_freeze",
            "product_baseline_user_confirmation",
            "ui_html_prototype_confirmation",
            "ui_prototype_user_confirmation",
            "non_ui_behavior_contract_confirmation",
        )
        state["stage"] = "product_baseline_user_confirmed"
        state["next_gate"] = "planned_e2e_obligations"
        return write_state(self.project_root, state)

    def prepare_test_coverage_confirmation(self) -> dict[str, Any]:
        """Create the reviewed planned-E2E confirmation request."""
        state = self._require_started()
        self._require_product_baseline_confirmed(state)
        planned = state.get("planned_e2e_obligations") or {}
        if not planned.get("accepted") or not planned.get("obligations"):
            raise WorkflowError("planned E2E obligations are required")
        if not state.get("test_coverage_audit", {}).get("passed"):
            raise WorkflowError("passed test coverage audit is required")
        for review_type in ("test_coverage", "test"):
            review = state.get("multi_agent_reviews", {}).get(review_type, {})
            if review.get("status") != "passed" or review.get(
                "input_snapshot_hash"
            ) != review_input_hash(state, review_type):
                raise WorkflowError(
                    f"current multi-agent {review_type} review is required"
                )
        plan_hash = test_coverage_plan_hash(state)
        pending = self._build_pending_confirmation(
            target="test_coverage_plan",
            artifact_path=str(planned.get("artifact_path") or ""),
            artifact_hash=plan_hash,
            artifact_version=f"test-coverage-plan-{plan_hash[:12]}",
            prototype_revision="test-coverage-plan",
            state=state,
        )
        pending["user_semantics_hash"] = test_coverage_user_semantics_hash(state)
        pending["product_baseline_hash"] = product_baseline_hash(state)
        state.setdefault("pending_confirmations", {})[
            "test_coverage_plan"
        ] = pending
        state.setdefault("confirmation_readiness", {})[
            "test_coverage_plan"
        ] = "ready_for_user"
        state["stage"] = "test_coverage_confirmation_ready"
        state["next_gate"] = "test_coverage_plan_user_confirmation"
        return write_state(self.project_root, state)

    def confirm_test_coverage_plan(
        self,
        user_message: str,
        nonce: str,
        *,
        agent_explicitly_asked: bool = False,
    ) -> dict[str, Any]:
        """Confirm planned E2E and coverage without re-confirming product scope."""
        state = self._require_started()
        self._require_product_baseline_confirmed(state)
        pending = state.get("pending_confirmations", {}).get("test_coverage_plan")
        if not pending:
            raise ConfirmationError("pending test coverage confirmation is required")
        if nonce != pending.get("nonce"):
            raise ConfirmationError("current test coverage confirmation nonce is required")
        if pending.get("artifact_hash") != test_coverage_plan_hash(state):
            raise ConfirmationError("test coverage plan changed after preparation")
        validate_confirmation_message(
            user_message,
            agent_explicitly_asked=agent_explicitly_asked,
        )
        confirmation = {
            "confirmation_id": "CONF-test_coverage_plan",
            "target": "test_coverage_plan",
            "artifact_path": pending["artifact_path"],
            "artifact_version": pending["artifact_version"],
            "artifact_hash": pending["artifact_hash"],
            "user_semantics_hash": pending["user_semantics_hash"],
            "product_baseline_hash": pending["product_baseline_hash"],
            "nonce": pending["nonce"],
            "confirmed_by": "user",
            "confirmation_source": "chat_user_reply",
            "confirmed_at": self._timestamp_from_state(state),
            "decision": "approved",
            "user_message": user_message,
        }
        artifact_name = f"test-coverage-plan-{pending['nonce']}.md"
        relative_artifact_path = f"artifacts/user-confirmations/{artifact_name}"
        confirmations_dir = (
            self.project_root / ARTIFACT_ROOT / "artifacts" / "user-confirmations"
        )
        confirmations_dir.mkdir(parents=True, exist_ok=True)
        (confirmations_dir / artifact_name).write_text(
            render_user_confirmation(confirmation), encoding="utf-8"
        )
        logical = {
            **confirmation,
            "confirmation_artifact_path": relative_artifact_path,
        }
        confirmations = state.setdefault("user_confirmations", {})
        confirmations["test_coverage_plan"] = logical
        confirmations["planned_e2e_obligations"] = {
            **logical,
            "target": "planned_e2e_obligations",
        }
        state.setdefault("planned_e2e_obligations", {})[
            "accepted_by_user"
        ] = True
        state["planned_e2e_obligations"][
            "confirmation_artifact_path"
        ] = relative_artifact_path
        state["planned_e2e_obligations"][
            "confirmation_user_semantics_hash"
        ] = pending["user_semantics_hash"]
        state.setdefault("pending_confirmations", {}).pop(
            "test_coverage_plan", None
        )
        state.setdefault("confirmation_readiness", {})[
            "test_coverage_plan"
        ] = "confirmed"
        self._close_user_change_authorizations(state, "test_coverage_plan")
        self._remove_blockers(
            state,
            "planned_e2e_user_confirmation",
            "test_coverage_plan_user_confirmation",
            "stale_requirements_e2e_confirmation",
        )
        state["stage"] = "test_coverage_plan_user_confirmed"
        state["next_gate"] = "implementation_launch_authorization"
        return write_state(self.project_root, state)

    def confirm_requirements_and_e2e_plan(
        self,
        user_message: str,
        *,
        agent_explicitly_asked: bool = False,
    ) -> dict[str, Any]:
        """Compatibility entry for the v1.0.21 test coverage confirmation."""
        state = self._require_started()
        pending = state.get("pending_confirmations", {}).get("test_coverage_plan")
        if not pending:
            raise WorkflowError(
                "prepare_test_coverage_confirmation is required before confirmation"
            )
        return self.confirm_test_coverage_plan(
            user_message,
            str(pending.get("nonce") or ""),
            agent_explicitly_asked=agent_explicitly_asked,
        )

    def status(self) -> dict[str, Any]:
        state = self._state()
        if not state:
            state = initialize_workspace(self.project_root)
        else:
            state = write_state(self.project_root, state)
        return state

    def pause(self) -> dict[str, Any]:
        state = self._require_started(allow_pending_authorization=True)
        state["paused"] = True
        state["intervention_enabled"] = False
        return write_state(self.project_root, state)

    def resume(self) -> dict[str, Any]:
        state = self._require_started(allow_pending_authorization=True)
        state["paused"] = False
        state["intervention_enabled"] = True
        return write_state(self.project_root, state)

    def stop(self) -> dict[str, Any]:
        state = self._state()
        if not state:
            state = initialize_workspace(self.project_root)
        elif state.get("delivery_goal") or state.get("handoff"):
            self.assert_goal_can_stop()
            state = self._state()
        state["active"] = False
        state["paused"] = False
        state["intervention_enabled"] = False
        policy = state.setdefault("multi_agent_policy", {})
        policy["execution_authorization"] = "invalidated"
        policy["authorized_review_types"] = []
        state.setdefault("pending_user_decisions", {}).pop("multi_agent_mode", None)
        return write_state(self.project_root, state)

    @staticmethod
    def _multi_agent_policy(
        mode: str | None,
        *,
        authorization_source: str | None,
        delivery_id: str | None,
        feature_slug: str | None,
    ) -> dict[str, Any]:
        if mode == "spawned_subagents_authorized":
            return {
                "mode": "spawned_subagents_required",
                "evidence_requirement": "spawned_subagents",
                "execution_authorization": "authorized",
                "authorization_scope": "current_delivery",
                "authorization_source": authorization_source,
                "authorization_delivery_id": delivery_id,
                "authorization_feature_slug": feature_slug,
                "authorized_review_types": list(AUTHORIZED_REVIEW_TYPES),
            }
        if mode == "role_simulation_allowed":
            return {
                "mode": "role_simulation_allowed",
                "evidence_requirement": "structured_role_simulation",
                "execution_authorization": "degradation_authorized",
                "authorization_scope": "current_delivery",
                "authorization_source": authorization_source,
                "authorization_delivery_id": delivery_id,
                "authorization_feature_slug": feature_slug,
                "authorized_review_types": list(AUTHORIZED_REVIEW_TYPES),
            }
        return {
            "mode": "authorization_pending",
            "evidence_requirement": "mode_selection_required",
            "execution_authorization": "pending",
            "authorization_scope": "current_delivery",
            "authorization_source": None,
            "authorization_delivery_id": delivery_id,
            "authorization_feature_slug": feature_slug,
            "authorized_review_types": [],
        }



    @staticmethod
    def _refresh_startup_gate(state: dict[str, Any]) -> None:
        decisions = state.setdefault("pending_user_decisions", {})
        startup_decisions = {"multi_agent_mode"}.intersection(decisions)
        if startup_decisions:
            state["next_gate"] = "startup_mode_selection"
        elif state.get("next_gate") in {
            None,
            "startup_mode_selection",
            "multi_agent_mode_selection",
        }:
            state["next_gate"] = "product_blueprint"

    def select_project_type(self, project_type: str) -> dict[str, Any]:
        if project_type not in {"ui", "non_ui"}:
            raise WorkflowError("project_type must be 'ui' or 'non_ui'")

        state = self._require_started()
        state["project_type"] = project_type
        blocked_until = list(state.get("blocked_until", []))
        blocked_until = [
            blocker for blocker in blocked_until if blocker != "project_type_decision"
        ]
        required_artifacts = list(state.get("required_artifacts", []))
        feature_slug = state.get("feature_slug")
        if project_type == "ui":
            state["stage"] = "ui_prototype_confirmation"
            state["next_gate"] = "ui_prototype_review"
            if "ui_html_prototype_confirmation" not in blocked_until:
                blocked_until.append("ui_html_prototype_confirmation")
            if feature_slug:
                prototype_path = f"docs/prototypes/{feature_slug}-prototype.html"
                if prototype_path not in required_artifacts:
                    required_artifacts.append(prototype_path)
        else:
            state["stage"] = "non_ui_behavior_contract_confirmation"
            state["next_gate"] = "non_ui_behavior_contract"
            if "non_ui_behavior_contract_confirmation" not in blocked_until:
                blocked_until.append("non_ui_behavior_contract_confirmation")
            contract_path = (
                ".product-delivery/artifacts/non-ui-behavior-contract.md"
            )
            if contract_path not in required_artifacts:
                required_artifacts.append(contract_path)
        state["blocked_until"] = blocked_until
        state["required_artifacts"] = required_artifacts
        return write_state(self.project_root, state)

    def confirm(self, artifact_name: str) -> dict[str, Any]:
        if artifact_name not in CORE_ARTIFACTS:
            raise WorkflowError(f"unknown confirmation point: {artifact_name}")

        state = self._require_started()
        if artifact_name == "ui_prototype_review" and state.get("project_type") == "ui":
            state["stage"] = "ui_prototype_review_ready"
            state["next_gate"] = "ui_prototype_review_confirmation"
            return write_state(self.project_root, state)
        state["confirmation_points"][artifact_name]["confirmed"] = True
        return write_state(self.project_root, state)

    def record_skill_use(
        self,
        stage: str,
        used_skills: list[str],
        *,
        file_paths: list[str | Path] | None = None,
    ) -> dict[str, Any]:
        state = self._require_started()
        result = validate_skill_gate(stage, used_skills, file_paths=file_paths)
        if not result.passed:
            raise SkillGateError(
                "missing required skills for "
                + stage
                + ": "
                + ", ".join(result.missing_skills)
            )
        state.setdefault("skill_records", {})
        state["skill_records"][stage] = result.as_dict()
        return write_state(self.project_root, state)

    def record_ui_prototype_review(self, review: dict[str, Any]) -> dict[str, Any]:
        state = self._require_started()
        if state.get("project_type") != "ui":
            raise WorkflowError("UI prototype review is only available for UI projects")
        if state.get("ui_prototype", {}).get("confirmed_by_user") and not self._has_user_change_authorization(
            state, "product_baseline"
        ):
            raise WorkflowError(
                "confirmed product surface requires user change authorization"
            )

        missing = validate_ui_prototype_review(review)
        if missing:
            raise WorkflowError(
                "missing UI prototype review fields: " + ", ".join(missing)
            )
        try:
            prototype_contract = build_prototype_contract(
                self.project_root,
                review.get("prototype_contract") or {},
            )
        except UIPrototypeError as cause:
            raise WorkflowError(str(cause)) from cause

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        review_path = artifacts_dir / CORE_ARTIFACTS["ui_prototype_review"]
        review_path.write_text(render_ui_prototype_review(review), encoding="utf-8")
        artifact_hash = self._artifact_hash(review["prototype_path"])
        revision_number = (
            int(state.get("ui_prototype", {}).get("revision_number") or 0) + 1
        )
        prototype_revision = f"prototype-revision-{revision_number:03d}"

        state["ui_prototype_review"] = {
            "prototype_path": review["prototype_path"],
            "pages": list(review["pages"]),
            "states": list(review["states"]),
            "journeys": list(review["journeys"]),
            "taxonomy": {
                key: list(value)
                for key, value in review["taxonomy"].items()
            },
            "limitations": list(review["limitations"]),
            "ui_change_type": review.get("ui_change_type"),
            "baseline_feature_slug": review.get("baseline_feature_slug"),
            "baseline_surface_paths": list(review.get("baseline_surface_paths", [])),
            "baseline_user_journey": review.get("baseline_user_journey"),
            "continuity_mapping": list(review.get("continuity_mapping", [])),
            "prototype_delta_summary": list(review.get("prototype_delta_summary", [])),
            "new_surface_justification": review.get("new_surface_justification"),
            "review_artifact_path": f"artifacts/{CORE_ARTIFACTS['ui_prototype_review']}",
            "prototype_contract_hash": prototype_contract["contract_sha256"],
        }
        contract_path = artifacts_dir / "ui-prototype-contract.json"
        contract_path.write_text(
            json.dumps(prototype_contract, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        state["prototype_contract"] = {
            **prototype_contract,
            "artifact_path": "artifacts/ui-prototype-contract.json",
            "artifact_sha256": self._artifact_hash(str(contract_path)),
        }
        state["downstream_inputs"] = {
            "browser_e2e_candidates": list(review["browser_e2e_candidates"]),
            "negative_scope_guard_candidates": list(
                review["negative_scope_guard_candidates"]
            ),
        }
        state["prototype_limitations"] = list(review["limitations"])
        state["ui_prototype"] = {
            "generated": True,
            "reviewed_by_agent": True,
            "confirmed_by_user": False,
            "prototype_path": review["prototype_path"],
            "artifact_hash": artifact_hash,
            "artifact_version": prototype_revision,
            "prototype_revision": prototype_revision,
            "prototype_contract_hash": prototype_contract["contract_sha256"],
            "prototype_screenshot_set_hash": prototype_contract[
                "prototype_screenshot_set_sha256"
            ],
            "revision_number": revision_number,
            "ui_change_type": review.get("ui_change_type"),
            "baseline_feature_slug": review.get("baseline_feature_slug"),
            "baseline_surface_paths": list(review.get("baseline_surface_paths", [])),
            "baseline_user_journey": review.get("baseline_user_journey"),
            "confirmation_status": "draft_internal_review",
            "pending_confirmation_nonce": None,
            "confirmation_source": None,
        }
        state.setdefault("pending_confirmations", {}).pop("ui_prototype", None)
        state["pending_confirmations"].pop("product_baseline", None)
        state.setdefault("user_confirmations", {}).pop("ui_prototype", None)
        self._mark_reviews_stale(
            state,
            ("scenario", "test", "test_coverage", "test_implementation", "ui_conformance"),
            reason="ui_prototype_changed",
        )
        self._invalidate_prototype_production_conformance(
            state,
            reason="ui_prototype_changed",
        )
        if self._has_user_change_authorization(state, "product_baseline"):
            self._invalidate_requirements_e2e_confirmation(
                state,
                reason="ui_prototype_changed",
                invalidate_open_spec=True,
                invalidate_planned_e2e=True,
            )
        self._invalidate_launch_authorization(
            state,
            reason="ui_prototype_changed",
        )
        self._add_blockers(
            state,
            "multi_agent_scenario_review",
            "product_baseline_user_confirmation",
        )
        state.setdefault("handoff_inputs", {})
        state["handoff_inputs"]["ui_prototype_limitations"] = list(
            review["limitations"]
        )
        state.setdefault("closure_inputs", {})
        state["closure_inputs"]["ui_prototype_limitations"] = list(
            review["limitations"]
        )
        state.setdefault("confirmation_readiness", {})[
            "product_baseline"
        ] = "internal_review_pending"
        state["stage"] = "ui_prototype_review_ready"
        state["next_gate"] = "multi_agent_scenario_review"
        return write_state(self.project_root, state)

    def confirm_ui_prototype(
        self,
        user_message: str,
        prototype_path: str,
        *,
        agent_explicitly_asked: bool = False,
        nonce: str | None = None,
    ) -> dict[str, Any]:
        state = self._require_started()
        if state.get("project_type") != "ui":
            raise WorkflowError("UI prototype confirmation is only available for UI projects")
        pending = state.get("pending_confirmations", {}).get("ui_prototype")
        if not pending:
            raise ConfirmationError("pending UI prototype confirmation is required")
        if nonce != pending.get("nonce"):
            raise ConfirmationError("current UI prototype confirmation nonce is required")
        if pending.get("artifact_path") != prototype_path:
            raise ConfirmationError("confirmation prototype path does not match pending artifact")
        current_hash = self._artifact_hash(prototype_path, require_exists=True)
        if current_hash != pending.get("artifact_hash"):
            raise ConfirmationError("prototype artifact changed after pending confirmation")
        try:
            current_contract = build_prototype_contract(
                self.project_root,
                state.get("prototype_contract") or {},
            )
        except UIPrototypeError as cause:
            raise ConfirmationError(str(cause)) from cause
        if current_contract.get("contract_sha256") != pending.get(
            "prototype_contract_hash"
        ):
            raise ConfirmationError("prototype contract changed after pending confirmation")
        if current_contract.get("prototype_screenshot_set_sha256") != pending.get(
            "prototype_screenshot_set_hash"
        ):
            raise ConfirmationError("prototype screenshot set changed after pending confirmation")
        validate_confirmation_message(
            user_message,
            agent_explicitly_asked=agent_explicitly_asked,
        )

        confirmation = {
            "confirmation_id": "CONF-ui_prototype",
            "target": "ui_prototype",
            "artifact_path": prototype_path,
            "artifact_version": pending["artifact_version"],
            "artifact_hash": pending["artifact_hash"],
            "prototype_revision": pending["prototype_revision"],
            "prototype_contract_hash": pending["prototype_contract_hash"],
            "prototype_screenshot_set_hash": pending[
                "prototype_screenshot_set_hash"
            ],
            "nonce": pending["nonce"],
            "confirmed_by": "user",
            "confirmation_source": "chat_user_reply",
            "confirmed_at": self._timestamp_from_state(state),
            "decision": "approved",
            "user_message": user_message,
        }
        confirmations_dir = (
            self.project_root / ARTIFACT_ROOT / "artifacts" / "user-confirmations"
        )
        confirmations_dir.mkdir(parents=True, exist_ok=True)
        confirmation_path = confirmations_dir / "ui_prototype.md"
        confirmation_path.write_text(
            render_user_confirmation(confirmation),
            encoding="utf-8",
        )

        state["ui_prototype"] = {
            **state.get("ui_prototype", {}),
            "generated": True,
            "reviewed_by_agent": bool(
                state.get("ui_prototype", {}).get("reviewed_by_agent", True)
            ),
            "confirmed_by_user": True,
            "prototype_path": prototype_path,
            "artifact_hash": pending["artifact_hash"],
            "artifact_version": pending["artifact_version"],
            "prototype_revision": pending["prototype_revision"],
            "prototype_contract_hash": pending["prototype_contract_hash"],
            "prototype_screenshot_set_hash": pending[
                "prototype_screenshot_set_hash"
            ],
            "revision_number": state.get("ui_prototype", {}).get("revision_number"),
            "confirmation_status": "confirmed",
            "pending_confirmation_nonce": None,
            "confirmation_source": "chat_user_reply",
            "confirmation_artifact_path": (
                "artifacts/user-confirmations/ui_prototype.md"
            ),
        }
        state.setdefault("pending_confirmations", {}).pop("ui_prototype", None)
        state.setdefault("user_confirmations", {})
        state["user_confirmations"]["ui_prototype"] = {
            **confirmation,
            "confirmation_artifact_path": (
                "artifacts/user-confirmations/ui_prototype.md"
            ),
        }
        if "ui_prototype_review" in state.get("confirmation_points", {}):
            state["confirmation_points"]["ui_prototype_review"]["confirmed"] = True
        self._remove_blockers(state, "ui_html_prototype_confirmation")
        state["stage"] = "ui_prototype_user_confirmed"
        state["next_gate"] = "planned_e2e_obligations"
        return write_state(self.project_root, state)

    def record_ui_prototype_feedback(
        self,
        user_message: str,
        prototype_path: str,
    ) -> dict[str, Any]:
        state = self._require_started()
        if state.get("project_type") != "ui":
            raise WorkflowError("UI prototype feedback is only available for UI projects")
        if not user_message.strip():
            raise WorkflowError("UI prototype feedback message is required")
        self._register_user_change_request(
            state,
            targets=["product_baseline"],
            user_message=user_message,
        )
        state.setdefault("ui_prototype_feedback", [])
        state["ui_prototype_feedback"].append(
            {
                "prototype_path": prototype_path,
                "user_message": user_message,
                "recorded_at": self._timestamp_from_state(state),
                "status": "changes_requested",
            }
        )
        state["ui_prototype"] = {
            **state.get("ui_prototype", {}),
            "generated": True,
            "reviewed_by_agent": bool(
                state.get("ui_prototype", {}).get("reviewed_by_agent")
            ),
            "confirmed_by_user": False,
            "prototype_path": prototype_path,
            "confirmation_status": "changes_requested",
            "confirmation_source": None,
            "confirmation_artifact_path": None,
        }
        state.setdefault("user_confirmations", {}).pop("ui_prototype", None)
        state.setdefault("pending_confirmations", {}).pop("ui_prototype", None)
        state["pending_confirmations"].pop("product_baseline", None)
        self._mark_reviews_stale(
            state,
            ("scenario", "test", "test_coverage", "test_implementation", "ui_conformance"),
            reason="ui_prototype_feedback",
        )
        self._invalidate_prototype_production_conformance(
            state,
            reason="ui_prototype_feedback",
        )
        self._invalidate_requirements_e2e_confirmation(
            state,
            reason="ui_prototype_feedback",
            invalidate_open_spec=True,
            invalidate_planned_e2e=True,
        )
        self._invalidate_launch_authorization(
            state,
            reason="ui_prototype_feedback",
        )
        self._add_blockers(state, "ui_html_prototype_confirmation")
        state["stage"] = "ui_prototype_changes_requested"
        state["next_gate"] = "ui_prototype_revision_review"
        return write_state(self.project_root, state)

    def record_user_requested_change(
        self,
        *,
        targets: list[str],
        user_message: str,
    ) -> dict[str, Any]:
        """Authorize revision of an already confirmed product or test baseline."""
        state = self._require_started()
        if not user_message.strip():
            raise WorkflowError("user-requested change message is required")
        allowed = {"product_baseline", "test_coverage_plan"}
        requested = sorted({str(target) for target in targets})
        if not requested or any(target not in allowed for target in requested):
            raise WorkflowError(
                "change targets must be product_baseline or test_coverage_plan"
            )
        self._register_user_change_request(
            state,
            targets=requested,
            user_message=user_message,
        )
        if "product_baseline" in requested:
            self._mark_reviews_stale(
                state,
                ("scenario", "test", "test_coverage"),
                reason="user_requested_product_baseline_change",
            )
            self._invalidate_requirements_e2e_confirmation(
                state,
                reason="user_requested_product_baseline_change",
                invalidate_open_spec=True,
                invalidate_planned_e2e=True,
            )
            self._invalidate_launch_authorization(
                state,
                reason="user_requested_product_baseline_change",
            )
            state["stage"] = "product_baseline_revision"
            state["next_gate"] = "product_blueprint"
        else:
            self._mark_reviews_stale(
                state,
                ("test", "test_coverage"),
                reason="user_requested_test_coverage_change",
            )
            self._invalidate_requirements_e2e_confirmation(
                state,
                reason="user_requested_test_coverage_change",
                invalidate_open_spec=False,
                invalidate_planned_e2e=True,
            )
            self._invalidate_launch_authorization(
                state,
                reason="user_requested_test_coverage_change",
            )
            state["stage"] = "test_coverage_plan_revision"
            state["next_gate"] = "planned_e2e_obligations"
        return write_state(self.project_root, state)

    def record_non_ui_behavior_contract(
        self,
        contract: dict[str, Any],
    ) -> dict[str, Any]:
        state = self._require_started()
        if state.get("project_type") != "non_ui":
            raise WorkflowError(
                "Non-UI behavior contract is only available for non-UI projects"
            )
        if self._product_baseline_is_confirmed(state) and not self._has_user_change_authorization(
            state, "product_baseline"
        ):
            raise WorkflowError(
                "confirmed product behavior contract requires user change authorization"
            )

        missing = validate_non_ui_behavior_contract(contract)
        if missing:
            raise WorkflowError(
                "missing non-UI behavior contract fields: " + ", ".join(missing)
            )

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        contract_path = artifacts_dir / CORE_ARTIFACTS["non_ui_behavior_contract"]
        contract_path.write_text(
            render_non_ui_behavior_contract(contract),
            encoding="utf-8",
        )
        artifact_hash = self._artifact_hash(str(contract_path))

        state["non_ui_behavior_contract"] = {
            "contract_name": contract["contract_name"],
            "entry_points": list(contract["entry_points"]),
            "inputs": list(contract["inputs"]),
            "outputs": list(contract["outputs"]),
            "taxonomy": {
                key: list(value)
                for key, value in contract["taxonomy"].items()
            },
            "behavior_paths": list(contract["behavior_paths"]),
            "negative_boundary_records": list(contract["negative_boundary_records"]),
            "limitations": list(contract["limitations"]),
            "contract_artifact_path": (
                f"artifacts/{CORE_ARTIFACTS['non_ui_behavior_contract']}"
            ),
            "artifact_hash": artifact_hash,
            "confirmed_by_user": False,
            "confirmation_status": "draft_internal_review",
        }
        state["downstream_inputs"] = {
            "behavior_evidence_candidates": list(contract["behavior_paths"]),
            "negative_boundary_candidates": list(
                contract["negative_boundary_records"]
            ),
        }
        state["behavior_contract_limitations"] = list(contract["limitations"])
        state.setdefault("handoff_inputs", {})
        state["handoff_inputs"]["non_ui_behavior_limitations"] = list(
            contract["limitations"]
        )
        state.setdefault("closure_inputs", {})
        state["closure_inputs"]["non_ui_behavior_limitations"] = list(
            contract["limitations"]
        )
        state.setdefault("pending_confirmations", {}).pop("product_baseline", None)
        self._mark_reviews_stale(
            state,
            ("scenario", "test", "test_coverage", "test_implementation"),
            reason="non_ui_behavior_contract_changed",
        )
        if self._has_user_change_authorization(state, "product_baseline"):
            self._invalidate_requirements_e2e_confirmation(
                state,
                reason="non_ui_behavior_contract_changed",
                invalidate_open_spec=True,
                invalidate_planned_e2e=True,
            )
        self._add_blockers(
            state,
            "multi_agent_scenario_review",
            "product_baseline_user_confirmation",
        )
        state.setdefault("confirmation_readiness", {})[
            "product_baseline"
        ] = "internal_review_pending"
        state["stage"] = "non_ui_behavior_contract_ready"
        state["next_gate"] = "multi_agent_scenario_review"
        return write_state(self.project_root, state)

    def record_test_coverage_audit(
        self,
        rows: list[dict[str, Any]],
        *,
        negative_guard_records: list[str] | None = None,
    ) -> dict[str, Any]:
        state = self._require_started()
        self._require_product_baseline_confirmed(state)
        project_type = state.get("project_type")
        inherited_limitations = []
        if project_type == "ui":
            inherited_limitations = list(state.get("prototype_limitations", []))
        elif project_type == "non_ui":
            inherited_limitations = list(
                state.get("behavior_contract_limitations", [])
            )

        audit = build_coverage_audit(
            project_type=project_type,
            rows=rows,
            downstream_inputs=state.get("downstream_inputs", {}),
            inherited_limitations=inherited_limitations,
            negative_guard_records=negative_guard_records,
        )
        candidate_state = {
            **state,
            "test_coverage_audit": {
                **audit,
                "audit_artifact_path": (
                    f"artifacts/{CORE_ARTIFACTS['test_coverage_audit']}"
                ),
            },
        }
        if self._test_coverage_change_requires_user_authorization(
            state, candidate_state
        ):
            raise WorkflowError(
                "confirmed test coverage semantics require user change authorization"
            )

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        audit_path = artifacts_dir / CORE_ARTIFACTS["test_coverage_audit"]
        audit_path.write_text(render_coverage_audit(audit), encoding="utf-8")

        state["test_coverage_audit"] = {
            **audit,
            "audit_artifact_path": (
                f"artifacts/{CORE_ARTIFACTS['test_coverage_audit']}"
            ),
        }
        self._mark_reviews_stale(
            state,
            ("test", "test_coverage"),
            reason="test_coverage_audit_changed",
        )
        if self._has_snapshot_bound_requirements_e2e_confirmation(
            state
        ) and not self._test_coverage_plan_is_user_confirmed(state):
            self._invalidate_requirements_e2e_confirmation(
                state,
                reason="test_coverage_audit_changed",
                invalidate_open_spec=False,
                invalidate_planned_e2e=True,
            )
        self._invalidate_launch_authorization(
            state,
            reason="test_coverage_audit_changed",
        )
        state.setdefault("handoff_inputs", {})
        state["handoff_inputs"]["coverage_matrix_range"] = audit["matrix_range"]
        state["handoff_inputs"]["latest_test_case"] = audit["latest_test_case"]
        state.setdefault("closure_inputs", {})
        state["closure_inputs"]["coverage_matrix_range"] = audit["matrix_range"]
        state["closure_inputs"]["latest_test_case"] = audit["latest_test_case"]
        state["stage"] = "test_coverage_audit_ready"
        state["next_gate"] = "multi_agent_test_coverage_review"
        return write_state(self.project_root, state)

    def record_planned_e2e_obligations(
        self,
        obligations: list[dict[str, Any]],
        *,
        exemptions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        state = self._require_started()
        self._require_product_baseline_confirmed(state)
        existing_test_confirmation = dict(
            state.get("user_confirmations", {}).get("test_coverage_plan") or {}
        )
        planned = build_planned_e2e_obligations(
            obligations,
            exemptions,
            project_type=state.get("project_type") or "ui",
        )
        candidate_state = {
            **state,
            "planned_e2e_obligations": {
                **planned,
                "artifact_path": "artifacts/planned-e2e-obligations.md",
            },
        }
        if self._test_coverage_change_requires_user_authorization(
            state, candidate_state
        ):
            raise WorkflowError(
                "confirmed test coverage semantics require user change authorization"
            )

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        planned_path = artifacts_dir / "planned-e2e-obligations.md"
        planned_path.write_text(
            self._render_planned_e2e_obligations(planned),
            encoding="utf-8",
        )

        state["planned_e2e_obligations"] = {
            **planned,
            "artifact_path": "artifacts/planned-e2e-obligations.md",
        }
        self._mark_reviews_stale(
            state,
            ("test", "test_coverage"),
            reason="planned_e2e_changed",
        )
        if existing_test_confirmation and self._test_coverage_plan_is_user_confirmed(
            state
        ):
            state["planned_e2e_obligations"].update(
                {
                    "accepted_by_user": True,
                    "confirmation_artifact_path": existing_test_confirmation.get(
                        "confirmation_artifact_path"
                    ),
                    "confirmation_user_semantics_hash": existing_test_confirmation.get(
                        "user_semantics_hash"
                    ),
                }
            )
            self._remove_blockers(
                state,
                "planned_e2e_user_confirmation",
                "test_coverage_plan_user_confirmation",
            )
        elif existing_test_confirmation or state.get(
            "confirmation_readiness", {}
        ).get("test_coverage_plan") == "revision_pending":
            self._invalidate_requirements_e2e_confirmation(
                state,
                reason="planned_e2e_changed",
                invalidate_open_spec=False,
                invalidate_planned_e2e=True,
            )
        else:
            state["planned_e2e_obligations"]["accepted_by_user"] = False
            state.setdefault("confirmation_readiness", {})[
                "test_coverage_plan"
            ] = "internal_review_pending"
            self._add_blockers(
                state,
                "planned_e2e_user_confirmation",
                "test_coverage_plan_user_confirmation",
            )
        self._invalidate_launch_authorization(
            state,
            reason="planned_e2e_changed",
        )
        if state.get("project_type") == "non_ui":
            state["executed_behavior_evidence"] = {
                "status": "missing",
                "records": [],
            }
            self._remove_blockers(state, "executed_browser_evidence")
            self._add_blockers(state, "executed_behavior_evidence")
        else:
            state["executed_browser_evidence"] = {
                "status": "missing",
                "records": [],
            }
            self._remove_blockers(state, "executed_behavior_evidence")
            self._add_blockers(state, "executed_browser_evidence")
        if not state["planned_e2e_obligations"].get("accepted_by_user"):
            self._add_blockers(
                state,
                "planned_e2e_user_confirmation",
                "test_coverage_plan_user_confirmation",
            )
        self._remove_blockers(state, "planned_e2e_obligations")
        state["stage"] = "planned_e2e_obligations_ready"
        state["next_gate"] = "multi_agent_test_coverage_review"
        return write_state(self.project_root, state)

    def record_executed_browser_evidence(
        self,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        state = self._require_started()
        planned = state.get("planned_e2e_obligations", {})
        evidence = build_executed_browser_evidence(
            self.project_root,
            records,
            planned_obligations=list(planned.get("obligations", [])),
            exemptions=list(planned.get("exemptions", [])),
        )

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = artifacts_dir / "executed-browser-evidence.md"
        evidence_path.write_text(
            self._render_executed_browser_evidence(evidence),
            encoding="utf-8",
        )

        state["executed_browser_evidence"] = {
            **evidence,
            "artifact_path": "artifacts/executed-browser-evidence.md",
        }
        state = append_transition(
            state,
            "executed_browser_evidence_recorded",
            feature_slug=state.get("feature_slug"),
            runtime_version=PLUGIN_VERSION,
            input_artifact_hashes={
                record["evidence_path"]: record["evidence_sha256"]
                for record in evidence.get("records", [])
            },
            output_artifact_hashes={
                "artifacts/executed-browser-evidence.md": self._artifact_hash(
                    str(evidence_path)
                )
            },
            metadata={
                "record_count": len(evidence.get("records", [])),
            },
        )
        self._mark_reviews_stale(
            state,
            ("test_implementation", "ui_conformance"),
            reason="executed_browser_evidence_changed",
        )
        self._invalidate_prototype_production_conformance(
            state,
            reason="executed_browser_evidence_changed",
        )
        self._remove_blockers(state, "executed_browser_evidence")
        state["stage"] = "executed_browser_evidence_passed"
        state["next_gate"] = "multi_agent_test_implementation_review"
        return write_state(self.project_root, state)

    def record_prototype_production_conformance(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Record production UI conformance against the confirmed prototype."""
        state = self._require_started()
        if state.get("project_type") != "ui":
            raise WorkflowError("prototype production conformance is only available for UI projects")
        if not (state.get("ui_prototype") or {}).get("confirmed_by_user"):
            raise WorkflowError("confirmed UI prototype is required before conformance")
        implementation = state.get("implementation") or {}
        if implementation.get("current_task") not in {"COMPLETE", "TASKS_COMPLETE"}:
            raise WorkflowError("implementation tasks must be complete before conformance")
        if (state.get("executed_browser_evidence") or {}).get("status") != "passed":
            raise WorkflowError("executed browser evidence must pass before conformance")
        try:
            evidence = build_prototype_production_conformance(
                self.project_root,
                payload,
                canonical_prototype=state.get("ui_prototype") or {},
                prototype_contract=state.get("prototype_contract") or {},
                executed_browser_evidence=state.get("executed_browser_evidence") or {},
            )
        except Exception as cause:
            raise WorkflowError(str(cause)) from cause

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        json_path = artifacts_dir / "prototype-production-conformance.json"
        json_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        markdown_path = artifacts_dir / "prototype-production-conformance.md"
        markdown_path.write_text(
            self._render_prototype_production_conformance(evidence),
            encoding="utf-8",
        )
        state["prototype_production_conformance"] = {
            **evidence,
            "artifact_path": "artifacts/prototype-production-conformance.json",
            "artifact_sha256": self._artifact_hash(str(json_path)),
            "report_path": "artifacts/prototype-production-conformance.md",
        }
        state = append_transition(
            state,
            "prototype_production_conformance_recorded",
            feature_slug=state.get("feature_slug"),
            runtime_version=PLUGIN_VERSION,
            input_artifact_hashes={
                "prototype_contract": evidence["prototype_contract_hash"],
                "executed_browser_evidence": stable_state_hash(
                    state.get("executed_browser_evidence") or {}
                ),
            },
            output_artifact_hashes={
                "artifacts/prototype-production-conformance.json": state[
                    "prototype_production_conformance"
                ]["artifact_sha256"]
            },
            metadata={"record_count": len(evidence.get("records", []))},
        )
        self._mark_reviews_stale(
            state,
            ("ui_conformance",),
            reason="prototype_production_conformance_changed",
        )
        self._remove_blockers(state, "prototype_production_conformance")
        self._add_blockers(state, "multi_agent_ui_conformance_review")
        state["stage"] = "prototype_production_conformance_passed"
        state["next_gate"] = "multi_agent_ui_conformance_review"
        return write_state(self.project_root, state)

    def generate_codex_goal_handoff(
        self,
        *,
        scope: str,
        non_goals: list[str] | None = None,
        verification_commands: list[str] | None = None,
        prohibited_work: list[str] | None = None,
        planned_tasks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        state = self._require_started()
        task_queue = list(planned_tasks or planned_tasks_from_coverage(state))
        if not task_queue:
            assert_pre_handoff_ready(
                state,
                self.project_root,
                launch_package_hash="missing-launch-package",
            )
        package = self._build_launch_package(
            state,
            scope=scope,
            verification_commands=verification_commands,
            prohibited_work=prohibited_work,
            planned_tasks=task_queue,
        )
        auth_ignored_blockers = [
            blocker
            for blocker in derive_blockers(
                state,
                self.project_root,
                launch_package_hash=package["launch_package_hash"],
            )
            if blocker != "implementation_launch_authorization"
            and blocker != "stale_implementation_launch_authorization"
        ]
        if auth_ignored_blockers:
            raise GatekeeperError(
                "pre-handoff gate blocked: "
                + ", ".join(sorted(auth_ignored_blockers))
            )
        delivery_goal = build_delivery_goal(
            feature_slug=state.get("feature_slug"),
            scope=scope,
            planned_tasks=task_queue,
            created_at=self._timestamp_from_state(state),
        )
        handoff = build_codex_goal_handoff(
            state,
            scope=scope,
            non_goals=non_goals,
            verification_commands=verification_commands,
            prohibited_work=prohibited_work,
            planned_tasks=list(delivery_goal["planned_tasks"]),
        )
        state = self._record_runtime_launch_authorization(
            state,
            package,
            scope=scope,
        )
        previous_goal = dict(state.get("delivery_goal") or {})
        previous_hash = previous_goal.get("launch_package_hash")
        if previous_hash and previous_hash != package["launch_package_hash"]:
            reusable_completions = self._matching_task_completions(
                previous_goal,
                delivery_goal,
            )
            self._supersede_active_implementation_package(
                state,
                reason="launch_package_hash_changed",
                replacement_launch_package_hash=package["launch_package_hash"],
                reused_task_ids=sorted(reusable_completions),
            )
            delivery_goal = self._apply_reused_task_completions(
                delivery_goal,
                reusable_completions,
            )
        assert_pre_handoff_ready(
            state,
            self.project_root,
            launch_package_hash=package["launch_package_hash"],
        )

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        handoff_path = artifacts_dir / CORE_ARTIFACTS["handoff"]
        goal_path = artifacts_dir / "codex-goal-prompt.md"
        implementation_goal_path = artifacts_dir / "implementation-goal.md"
        task_queue_path = artifacts_dir / "task-queue.md"
        handoff_path.write_text(render_handoff_document(handoff), encoding="utf-8")
        goal_path.write_text(handoff["codex_goal_prompt"], encoding="utf-8")
        implementation_goal_path.write_text(
            render_implementation_goal(delivery_goal),
            encoding="utf-8",
        )
        task_queue_path.write_text(render_task_queue(delivery_goal), encoding="utf-8")

        state["handoff"] = {
            **handoff,
            "handoff_artifact_path": f"artifacts/{CORE_ARTIFACTS['handoff']}",
            "codex_goal_prompt_path": "artifacts/codex-goal-prompt.md",
            "implementation_goal_path": "artifacts/implementation-goal.md",
            "task_queue_path": "artifacts/task-queue.md",
        }
        state["delivery_goal"] = {
            **delivery_goal,
            "feature_slug": state.get("feature_slug"),
            "launch_package_hash": package["launch_package_hash"],
            "implementation_goal_path": "artifacts/implementation-goal.md",
            "task_queue_path": "artifacts/task-queue.md",
        }
        state["implementation"] = {
            "current_task": delivery_goal["current_task_cursor"],
            "completed_tasks": list(delivery_goal["completed_tasks"]),
        }
        state["codex_goal_prompt"] = handoff["codex_goal_prompt"]
        state["freeze"] = {
            "frozen": True,
            "scope_version": state.get("freeze", {}).get("scope_version") or "v1",
        }
        if delivery_goal["status"] == "implementation_tasks_complete":
            state["stage"] = "implementation_tasks_complete"
            state["status"] = "implementation_tasks_complete"
        elif delivery_goal["completed_tasks"]:
            state["stage"] = "implementation_in_progress"
            state["status"] = "implementation_in_progress"
        else:
            state["stage"] = "codex_goal_handoff_ready"
            state["status"] = "implementation_goal_active"
        state["next_gate"] = delivery_goal["current_task_cursor"]
        if delivery_goal["current_task_cursor"] is None:
            state["next_gate"] = delivery_goal["next_action"]
        state = append_transition(
            state,
            "handoff_generated",
            feature_slug=state.get("feature_slug"),
            runtime_version=PLUGIN_VERSION,
            input_artifact_hashes={
                "launch_package": package["launch_package_hash"],
            },
            output_artifact_hashes={
                f"artifacts/{CORE_ARTIFACTS['handoff']}": self._artifact_hash(
                    str(handoff_path)
                ),
                "artifacts/codex-goal-prompt.md": self._artifact_hash(
                    str(goal_path)
                ),
                "artifacts/implementation-goal.md": self._artifact_hash(
                    str(implementation_goal_path)
                ),
                "artifacts/task-queue.md": self._artifact_hash(str(task_queue_path)),
            },
            metadata={
                "launch_package_hash": package["launch_package_hash"],
                "task_count": len(delivery_goal["planned_tasks"]),
            },
        )
        return write_state(self.project_root, state)

    def recover_stale_launch_package(
        self,
        *,
        scope: str,
        non_goals: list[str] | None = None,
        verification_commands: list[str] | None = None,
        prohibited_work: list[str] | None = None,
        planned_tasks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Canonically replace an implementation package bound to an old launch hash."""
        state = self._require_started()
        task_queue = list(planned_tasks or planned_tasks_from_coverage(state))
        package = self._build_launch_package(
            state,
            scope=scope,
            verification_commands=verification_commands,
            prohibited_work=prohibited_work,
            planned_tasks=task_queue,
        )
        authorization = state.get("implementation_launch_authorization") or {}
        blockers = [
            blocker
            for blocker in derive_blockers(
                state,
                self.project_root,
                launch_package_hash=package["launch_package_hash"],
            )
            if blocker != "stale_implementation_launch_authorization"
        ]
        if blockers:
            raise WorkflowError(
                "launch package recovery blocked: " + ", ".join(sorted(blockers))
            )
        if authorization.get("status") != "authorized" or authorization.get(
            "launch_package_hash"
        ) != package["launch_package_hash"]:
            raise WorkflowError(
                "current launch package must be authorized before recovery"
            )
        goal = state.get("delivery_goal") or {}
        if goal.get("launch_package_hash") == package["launch_package_hash"]:
            return state
        return self.generate_codex_goal_handoff(
            scope=scope,
            non_goals=non_goals,
            verification_commands=verification_commands,
            prohibited_work=prohibited_work,
            planned_tasks=task_queue,
        )

    def derive_remaining_tasks(self) -> list[dict[str, Any]]:
        state = self._require_started()
        return derive_goal_remaining_tasks(state)

    def record_task_completion(
        self,
        task_id: str,
        *,
        artifact: dict[str, Any],
    ) -> dict[str, Any]:
        state = self._require_started()
        try:
            next_state = record_delivery_task_completion(
                state,
                task_id,
                artifact,
                completed_at=self._timestamp_from_state(state),
            )
        except DeliveryGoalError as error:
            raise WorkflowError(str(error)) from error
        goal = next_state.get("delivery_goal", {})
        next_state["implementation"] = {
            "current_task": goal.get("current_task_cursor") or "TASKS_COMPLETE",
            "completed_tasks": list(goal.get("completed_tasks", [])),
        }
        next_state = append_transition(
            next_state,
            "task_completed",
            feature_slug=next_state.get("feature_slug"),
            runtime_version=PLUGIN_VERSION,
            input_artifact_hashes={
                "planned_task": artifact["planned_task_hash"],
            },
            output_artifact_hashes={
                artifact["artifact_path"]: artifact["artifact_sha256"],
            },
            metadata={
                "task_id": task_id,
                "verification_command": artifact["verification_command"],
                "verification_exit_code": artifact["verification_exit_code"],
            },
        )
        return write_state(self.project_root, next_state)

    def assert_goal_can_stop(self) -> dict[str, Any]:
        state = self._require_started()
        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = assert_delivery_goal_can_stop(state)
        except DeliveryGoalError as error:
            stop_result = {
                "status": "blocked",
                "reason": str(error),
                "remaining_tasks": [
                    task["task_id"] for task in derive_goal_remaining_tasks(state)
                ],
            }
            (artifacts_dir / "stop-guard-result.md").write_text(
                render_stop_guard_result(stop_result),
                encoding="utf-8",
            )
            state["stop_guard"] = stop_result
            write_state(self.project_root, state)
            raise WorkflowError(str(error)) from error

        (artifacts_dir / "stop-guard-result.md").write_text(
            render_stop_guard_result(result),
            encoding="utf-8",
        )
        state["stop_guard"] = result
        return write_state(self.project_root, state)

    def retire_model_execution_policy(self) -> dict[str, Any]:
        """Archive and remove plugin-managed model execution from an active delivery."""
        state = self._require_started(allow_pending_authorization=True)
        changed = False
        policy = state.pop("execution_model_policy", None)
        if isinstance(policy, dict) and policy:
            policy_hash = self._stable_hash(policy)
            history = state.setdefault("retired_model_execution_policies", [])
            if not any(
                record.get("policy_sha256") == policy_hash
                for record in history
                if isinstance(record, dict)
            ):
                history.append(
                    {
                        "policy_sha256": policy_hash,
                        "policy": policy,
                        "retired_at": self._timestamp_from_state(state),
                        "retirement_reason": (
                            "model orchestration transferred to the Codex host"
                        ),
                    }
                )
            changed = True

        pending_decisions = state.setdefault("pending_user_decisions", {})
        for decision in ("execution_mode", "main_thread_model"):
            if decision in pending_decisions:
                pending_decisions.pop(decision, None)
                changed = True

        obsolete_blockers = {
            "execution_mode",
            "main_thread_model",
            "host_capabilities_pending",
            "host_model_capabilities_pending",
            "host_model_control_unavailable",
            "legacy_unverified_model_execution",
            "pending_stage_agent_spawn",
            "stage_agent_model_mismatch",
            "unverified_stage_agent_model",
            "verify_stage_agent_model_execution",
            "pending_user_confirmation",
            "planned_e2e_user_confirmation",
            "ui_html_prototype_confirmation",
            "ui_prototype_user_confirmation",
            "user_confirmed_freeze",
        }
        blocked_until = list(state.get("blocked_until", []))
        filtered_blockers = [
            blocker for blocker in blocked_until if blocker not in obsolete_blockers
        ]
        if filtered_blockers != blocked_until:
            state["blocked_until"] = filtered_blockers
            changed = True
        blocking_gates = state.setdefault("blocking_gates", {})
        for blocker in obsolete_blockers:
            if blocker in blocking_gates:
                blocking_gates.pop(blocker, None)
                changed = True

        ui = state.get("ui_prototype")
        if isinstance(ui, dict) and (
            ui.get("confirmation_status") == "pending_user_confirmation"
            or ui.get("pending_confirmation_nonce")
        ):
            ui["confirmation_status"] = "superseded_by_product_baseline"
            ui.pop("pending_confirmation_nonce", None)
            changed = True

        if state.get("next_gate") in {
            "startup_mode_selection",
            "execution_mode_selection",
            "host_model_capabilities",
            "verify_stage_agent_model_execution",
        }:
            policy = state.get("multi_agent_policy") or {}
            if policy.get("execution_authorization") in {
                "authorized",
                "degradation_authorized",
            }:
                state["next_gate"] = "multi_agent_scenario_review"
            else:
                state["next_gate"] = "multi_agent_mode_selection"
            changed = True

        if not changed:
            return state
        return write_state(self.project_root, state)

    def authorize_execution_mode(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self._raise_model_orchestration_retired()

    def request_execution_mode_switch(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        self._raise_model_orchestration_retired()

    def begin_execution_stage(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self._raise_model_orchestration_retired()

    def bind_execution_stage_agent(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        self._raise_model_orchestration_retired()

    def record_host_model_capabilities(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        self._raise_model_orchestration_retired()

    def save_model_profiles(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self._raise_model_orchestration_retired()

    def record_post_freeze_change(
        self,
        *,
        change_type: str,
        description: str,
        cr_id: str,
    ) -> dict[str, Any]:
        state = self._require_started()
        authorization_target = None
        if change_type == "scope_change":
            authorization_target = "product_baseline"
        elif change_type == "test_gap":
            authorization_target = "test_coverage_plan"
        elif change_type == "acceptance_feedback":
            if self._has_user_change_authorization(state, "product_baseline"):
                authorization_target = "product_baseline"
            elif self._has_user_change_authorization(state, "test_coverage_plan"):
                authorization_target = "test_coverage_plan"
        if authorization_target is None or not self._has_user_change_authorization(
            state, authorization_target
        ):
            raise WorkflowError(
                "post-freeze change requires explicit user change authorization"
            )
        state.setdefault("change_requests", [])
        state["change_requests"].append(
            {
                "cr_id": cr_id,
                "change_type": change_type,
                "description": description,
                "status": "recorded",
            }
        )
        if authorization_target == "product_baseline":
            state["freeze"] = {
                **state.get("freeze", {}),
                "frozen": False,
            }
            self._mark_reviews_stale(
                state,
                ("scenario", "test", "test_coverage"),
                reason=f"post_freeze_{change_type}",
            )
            self._invalidate_requirements_e2e_confirmation(
                state,
                reason=f"post_freeze_{change_type}",
                invalidate_open_spec=True,
                invalidate_planned_e2e=True,
            )
            self._invalidate_launch_authorization(
                state,
                reason=f"post_freeze_{change_type}",
            )
            self._supersede_active_implementation_package(
                state,
                reason=f"post_freeze_{change_type}",
            )
            state["stage"] = "product_baseline_revision"
            state["status"] = "scope_revision"
            state["next_gate"] = "product_blueprint"
        elif authorization_target == "test_coverage_plan":
            self._mark_reviews_stale(
                state,
                ("test", "test_coverage"),
                reason=f"post_freeze_{change_type}",
            )
            self._invalidate_requirements_e2e_confirmation(
                state,
                reason=f"post_freeze_{change_type}",
                invalidate_open_spec=False,
                invalidate_planned_e2e=True,
            )
            self._invalidate_launch_authorization(
                state,
                reason=f"post_freeze_{change_type}",
            )
            self._supersede_active_implementation_package(
                state,
                reason=f"post_freeze_{change_type}",
            )
            state["stage"] = "planned_e2e_obligations_revision"
            state["status"] = "coverage_revision"
            state["next_gate"] = "planned_e2e_obligations"
        self._close_user_change_authorizations(state, authorization_target)
        return write_state(self.project_root, state)

    def record_superseded_closure(
        self,
        *,
        closure_id: str,
        triggering_cr: str,
        reason: str,
    ) -> dict[str, Any]:
        state = self._require_started()
        state.setdefault("superseded_closures", [])
        state["superseded_closures"].append(
            {
                "closure_id": closure_id,
                "triggering_cr": triggering_cr,
                "reason": reason,
                "status": "superseded",
            }
        )
        return write_state(self.project_root, state)

    def record_feature_closure(
        self,
        closure_artifact: dict[str, Any],
        *,
        source_artifact_path: str | None = None,
        source_artifact_sha256: str | None = None,
    ) -> dict[str, Any]:
        state = self._require_started()
        handoff = state.get("handoff", {})
        try:
            remaining_tasks = derive_goal_remaining_tasks(state)
            if remaining_tasks:
                raise DeliveryGoalError(
                    "closure cannot run while TASKs remain: "
                    + ", ".join(task["task_id"] for task in remaining_tasks)
                )
            closure = validate_feature_closure(
                closure_artifact,
                expected_matrix_range=handoff.get("matrix_range", ""),
                expected_latest_test_case=handoff.get("latest_test_case", ""),
                required_commands=list(handoff.get("required_commands", [])),
                project_root=self.project_root,
            )
            assert_pre_closure_ready(state, closure, self.project_root)
        except (ClosureGateError, GatekeeperError, DeliveryGoalError) as error:
            state["closure_validation"] = {
                "status": "closure_failed",
                "errors": [str(error)],
            }
            state["blocking_gates"] = {
                **state.get("blocking_gates", {}),
                "closure": False,
            }
            state = mark_goal_closure_failed(state)
            state.pop("status", None)
            state["stage"] = "closure_failed"
            state["next_gate"] = "feature_closure_after_implementation"
            self._write_closure_validator_result("closure_failed", [str(error)])
            write_state(self.project_root, state)
            raise

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        closure_path = artifacts_dir / "feature-closure.md"
        closure_path.write_text(render_feature_closure(closure), encoding="utf-8")
        canonical_hash = source_artifact_sha256 or self._stable_hash(closure_artifact)
        canonical_source = source_artifact_path or "inline:record_feature_closure"

        state["feature_closure"] = {
            **closure,
            "closure_artifact_path": "artifacts/feature-closure.md",
            "source_artifact_path": canonical_source,
            "source_artifact_sha256": canonical_hash,
        }
        state["closure_validation"] = {
            "status": "passed",
            "errors": [],
            "validator": CANONICAL_VALIDATOR,
            "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
            "plugin_version": PLUGIN_VERSION,
            "feature_slug": state.get("feature_slug"),
            "closure_artifact_sha256": canonical_hash,
            "result_artifact": ".product-delivery/artifacts/closure-validator-result.md",
        }
        self._write_closure_validator_result("passed", [])
        try:
            state = mark_goal_complete(
                state,
                completed_at=self._timestamp_from_state(state),
            )
        except DeliveryGoalError as error:
            state = mark_goal_closure_failed(state)
            state["closure_validation"] = {
                "status": "closure_failed",
                "errors": [str(error)],
            }
            state.pop("status", None)
            state["stage"] = "closure_failed"
            state["next_gate"] = "feature_closure_after_implementation"
            self._write_closure_validator_result("closure_failed", [str(error)])
            write_state(self.project_root, state)
            raise WorkflowError(str(error)) from error
        state["implementation"] = {
            "current_task": "COMPLETE",
            "completed_tasks": list(state.get("delivery_goal", {}).get("completed_tasks", [])),
        }
        state = append_transition(
            state,
            "closure_validated",
            feature_slug=state.get("feature_slug"),
            runtime_version=PLUGIN_VERSION,
            input_artifact_hashes={
                canonical_source: canonical_hash,
            },
            output_artifact_hashes={
                "artifacts/feature-closure.md": self._artifact_hash(str(closure_path)),
                "artifacts/closure-validator-result.md": self._artifact_hash(
                    str(artifacts_dir / "closure-validator-result.md")
                ),
            },
            metadata={
                "validator": CANONICAL_VALIDATOR,
                "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
            },
        )
        state = append_transition(
            state,
            "goal_completed",
            feature_slug=state.get("feature_slug"),
            runtime_version=PLUGIN_VERSION,
            input_artifact_hashes={
                "closure_artifact": canonical_hash,
            },
            output_artifact_hashes={},
            metadata={
                "delivery_goal_status": state.get("delivery_goal", {}).get("status"),
            },
        )
        state["status"] = "closed"
        state["stage"] = "feature_closure_passed"
        state["next_gate"] = "plugin_packaging"
        return write_state(self.project_root, state)

    def prepare_audit_and_handoff_drafts(self) -> dict[str, Any]:
        state = self._require_started()
        missing = self._missing_required_confirmations(state)
        if missing:
            raise WorkflowError(
                "missing required confirmations before audit and handoff: "
                + ", ".join(missing)
            )

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._write_artifact_if_missing(
            artifacts_dir / CORE_ARTIFACTS["test_coverage_audit"],
            "# Test Coverage Audit\n\nStatus: Draft\n\n",
        )
        self._write_artifact_if_missing(
            artifacts_dir / CORE_ARTIFACTS["handoff"],
            "# Codex Goal Handoff Draft\n\nStatus: Draft\n\n",
        )

        state["stage"] = "handoff_draft_ready"
        state["next_gate"] = "test_coverage_audit"
        return write_state(self.project_root, state)

    def _archive_previous_delivery(
        self,
        state: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not state or not any(
            state.get(key) for key in ("feature_slug", "status", "activation_source")
        ):
            return None
        state_hash = stable_state_hash(state)
        delivery_id = str(state.get("delivery_id") or f"legacy-{state_hash[:16]}")
        archive_dir = self.project_root / ARTIFACT_ROOT / "history" / delivery_id
        archive_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = archive_dir / "state.json"
        if not snapshot_path.exists():
            snapshot_path.write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return {
            "delivery_id": delivery_id,
            "feature_slug": state.get("feature_slug"),
            "status": state.get("status"),
            "state_sha256": state_hash,
            "state_snapshot_path": str(snapshot_path.relative_to(self.project_root)),
            "archived_at": self._timestamp_from_state(state),
        }

    def _load_raw_state(self) -> dict[str, Any]:
        state_path = self.project_root / ARTIFACT_ROOT / "state.json"
        if not state_path.is_file():
            return {}
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _state(self) -> dict[str, Any]:
        return load_state(self.project_root, fallback_state=self.fallback_state)

    def _require_started(
        self,
        *,
        allow_pending_authorization: bool = False,
    ) -> dict[str, Any]:
        state = self._state()
        if not state.get("active"):
            raise WorkflowError("workflow is not active; run start first")
        if self._load_raw_state().get("status") not in TERMINAL_STATUSES:
            self._require_current_delivery_authorization(state)
        execution_authorization = (state.get("multi_agent_policy") or {}).get(
            "execution_authorization"
        )
        if not allow_pending_authorization and execution_authorization in {
            "pending",
            "legacy_unverified",
            "invalidated",
        }:
            raise WorkflowError(
                "multi-Agent mode authorization is required before workflow progress"
            )
        return state

    @staticmethod
    def _require_current_delivery_authorization(state: dict[str, Any]) -> None:
        if state.get("status") in TERMINAL_STATUSES:
            return
        policy = state.get("multi_agent_policy") or {}
        if policy.get("execution_authorization") not in {
            "authorized",
            "degradation_authorized",
        }:
            return
        if (
            policy.get("authorization_delivery_id") != state.get("delivery_id")
            or policy.get("authorization_feature_slug") != state.get("feature_slug")
        ):
            raise WorkflowError("authorization is not bound to the current delivery")

    @staticmethod
    def _validate_spawned_reviewer_agents(review: dict[str, Any]) -> None:
        reviewer_ids = review.get("reviewer_agent_ids")
        reviewers = review.get("reviewers") or []
        if (
            not isinstance(reviewer_ids, list)
            or len(reviewer_ids) != len(reviewers)
            or not 2 <= len(reviewer_ids) <= 3
            or not all(
                isinstance(agent_id, str) and agent_id.strip()
                for agent_id in reviewer_ids
            )
        ):
            raise ReviewGateError(
                "spawned_subagents review requires 2-3 reviewer_agent_ids matching reviewers"
            )
        if len(set(reviewer_ids)) != len(reviewer_ids):
            raise ReviewGateError("reviewer_agent_ids must be unique")
        spawn_source = review.get("reviewer_spawn_source")
        if not isinstance(spawn_source, str) or not spawn_source.strip():
            raise ReviewGateError("reviewer_spawn_source is required")




    def _missing_required_confirmations(self, state: dict[str, Any]) -> list[str]:
        missing = []
        user_confirmations = state.get("user_confirmations", {})
        if not self._product_baseline_is_confirmed(state):
            missing.append("product_baseline")

        if state.get("project_type") == "ui":
            ui = state.get("ui_prototype", {})
            if (
                not ui.get("confirmed_by_user")
                or "ui_prototype" not in user_confirmations
            ):
                missing.append("ui_prototype")
        elif state.get("project_type") == "non_ui":
            contract = state.get("non_ui_behavior_contract") or {}
            if not contract.get("confirmed_by_user"):
                missing.append("non_ui_behavior_contract")
        else:
            missing.append("project_type")
        return missing

    @staticmethod
    def _product_baseline_is_confirmed(state: dict[str, Any]) -> bool:
        confirmation = (state.get("user_confirmations") or {}).get(
            "product_baseline"
        ) or {}
        return bool(confirmation) and confirmation.get(
            "artifact_hash"
        ) == product_baseline_hash(state)

    def _require_product_baseline_confirmed(self, state: dict[str, Any]) -> None:
        if not self._product_baseline_is_confirmed(state):
            raise WorkflowError(
                "product baseline confirmation is required before test planning"
            )

    @staticmethod
    def _test_coverage_plan_is_user_confirmed(state: dict[str, Any]) -> bool:
        confirmation = state.get("user_confirmations", {}).get(
            "test_coverage_plan"
        ) or {}
        return bool(confirmation) and confirmation.get(
            "user_semantics_hash"
        ) == test_coverage_user_semantics_hash(state)

    def _test_coverage_change_requires_user_authorization(
        self,
        state: dict[str, Any],
        candidate_state: dict[str, Any],
    ) -> bool:
        if self._has_user_change_authorization(state, "test_coverage_plan"):
            return False
        confirmation = state.get("user_confirmations", {}).get(
            "test_coverage_plan"
        ) or {}
        if confirmation:
            return confirmation.get(
                "user_semantics_hash"
            ) != test_coverage_user_semantics_hash(candidate_state)
        return (
            state.get("confirmation_readiness", {}).get("test_coverage_plan")
            == "revision_pending"
        )

    @staticmethod
    def _has_user_change_authorization(
        state: dict[str, Any], target: str
    ) -> bool:
        return any(
            request.get("status") == "authorized"
            and target in (request.get("targets") or [])
            for request in state.get("user_change_requests", [])
        )

    def _register_user_change_request(
        self,
        state: dict[str, Any],
        *,
        targets: list[str],
        user_message: str,
    ) -> None:
        request_hash = stable_state_hash(
            {
                "targets": sorted(targets),
                "user_message": user_message.strip(),
                "feature_slug": state.get("feature_slug"),
                "delivery_id": state.get("delivery_id"),
            }
        )
        state.setdefault("user_change_requests", []).append(
            {
                "request_id": f"UCR-{request_hash[:16]}",
                "targets": sorted(targets),
                "user_message": user_message.strip(),
                "status": "authorized",
                "recorded_at": self._timestamp_from_state(state),
            }
        )

    def _close_user_change_authorizations(
        self, state: dict[str, Any], target: str
    ) -> None:
        closed_at = self._timestamp_from_state(state)
        for request in state.get("user_change_requests", []):
            if request.get("status") == "authorized" and target in (
                request.get("targets") or []
            ):
                request["status"] = "consumed"
                request["consumed_at"] = closed_at

    @staticmethod
    def _write_artifact_if_missing(path: Path, content: str) -> None:
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    def _write_closure_validator_result(
        self,
        status: str,
        errors: list[str],
    ) -> None:
        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "closure-validator-result.md").write_text(
            render_closure_validator_result(
                status,
                errors,
                feature_slug=self._state().get("feature_slug"),
            ),
            encoding="utf-8",
        )

    def _build_launch_package(
        self,
        state: dict[str, Any],
        *,
        scope: str,
        verification_commands: list[str] | None,
        prohibited_work: list[str] | None,
        planned_tasks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        task_queue = normalize_planned_tasks(planned_tasks)
        required_commands = list(verification_commands or [])
        review_modes = {
            review_type: review.get("review_mode", "spawned_subagents")
            for review_type, review in state.get("multi_agent_reviews", {}).items()
            if review.get("status") == "passed"
        }
        ui_prototype = state.get("ui_prototype", {})
        planned = state.get("planned_e2e_obligations", {})
        task_queue_hash = self._stable_hash(task_queue)
        required_commands_hash = self._stable_hash(required_commands)
        planned_e2e_hash = self._stable_hash(
            {
                "obligations": planned.get("obligations", []),
                "exemptions": planned.get("exemptions", []),
                "accepted": planned.get("accepted"),
                "accepted_by_user": planned.get("accepted_by_user"),
            }
        )
        package = {
            "feature_slug": state.get("feature_slug"),
            "scope": scope,
            "review_modes": review_modes,
            "prototype_hash": ui_prototype.get("artifact_hash"),
            "prototype_revision": ui_prototype.get("prototype_revision"),
            "planned_e2e_hash": planned_e2e_hash,
            "task_queue": task_queue,
            "task_queue_hash": task_queue_hash,
            "required_commands": required_commands,
            "required_commands_hash": required_commands_hash,
            "prohibited_work": list(prohibited_work or []),
        }
        package_hash = self._stable_hash(package)
        return {
            **package,
            "launch_package_hash": package_hash,
            "nonce": f"launch-{package_hash[:16]}",
        }

    def _record_runtime_launch_authorization(
        self,
        state: dict[str, Any],
        package: dict[str, Any],
        *,
        scope: str,
        user_message: str | None = None,
    ) -> dict[str, Any]:
        authorization = {
            "authorization_id": "AUTH-implementation_launch_authorization",
            "target": "implementation_launch_authorization",
            "artifact_path": ".product-delivery/artifacts/implementation-launch-authorization.md",
            "artifact_version": package["launch_package_hash"],
            "artifact_hash": package["launch_package_hash"],
            "authorized_by": "runtime",
            "authorization_source": "runtime_auto",
            "authorized_at": self._timestamp_from_state(state),
            "decision": "authorized",
            "user_message": user_message
            or "Runtime auto-authorization after required user confirmation gates passed.",
            "nonce": package["nonce"],
        }
        launch_path = (
            self.project_root
            / ARTIFACT_ROOT
            / "artifacts"
            / "implementation-launch-authorization.md"
        )
        launch_path.parent.mkdir(parents=True, exist_ok=True)
        launch_path.write_text(
            self._render_implementation_launch_authorization(
                package,
                authorization,
            ),
            encoding="utf-8",
        )

        state["implementation_launch_authorization"] = {
            "status": "authorized",
            "feature_slug": state.get("feature_slug"),
            "launch_package_hash": package["launch_package_hash"],
            "nonce": package["nonce"],
            "scope": scope,
            "review_modes": package["review_modes"],
            "prototype_hash": package["prototype_hash"],
            "planned_e2e_hash": package["planned_e2e_hash"],
            "task_queue_hash": package["task_queue_hash"],
            "required_commands_hash": package["required_commands_hash"],
            "authorization_artifact_path": (
                "artifacts/implementation-launch-authorization.md"
            ),
            "authorization_source": authorization["authorization_source"],
            "authorized_by": authorization["authorized_by"],
            "authorized_at": authorization["authorized_at"],
        }
        state.setdefault("user_confirmations", {}).pop(
            "implementation_launch_authorization",
            None,
        )
        state.setdefault("pending_confirmations", {}).pop(
            "implementation_launch_authorization",
            None,
        )
        return state

    def _mark_reviews_stale(
        self,
        state: dict[str, Any],
        review_types: tuple[str, ...],
        *,
        reason: str,
    ) -> None:
        reviews = state.setdefault("multi_agent_reviews", {})
        stale_records = state.setdefault("stale_multi_agent_reviews", [])
        stale_at = self._timestamp_from_state(state)
        for review_type in review_types:
            review = reviews.get(review_type, {})
            if review.get("status") not in {"passed", "stale"}:
                continue
            if review.get("status") == "passed":
                stale_records.append(
                    {
                        **review,
                        "review_type": review_type,
                        "stale_reason": reason,
                        "stale_at": stale_at,
                    }
                )
            reviews[review_type] = {
                **review,
                "status": "stale",
                "stale_reason": reason,
                "stale_at": stale_at,
            }
            self._add_blockers(state, f"stale_multi_agent_{review_type}_review")

    def _invalidate_prototype_production_conformance(
        self,
        state: dict[str, Any],
        *,
        reason: str,
    ) -> None:
        conformance = state.get("prototype_production_conformance")
        if not isinstance(conformance, dict) or conformance.get("status") not in {
            "passed",
            "stale",
        }:
            return
        state["prototype_production_conformance"] = {
            **conformance,
            "status": "stale",
            "stale_reason": reason,
            "stale_at": self._timestamp_from_state(state),
        }
        self._add_blockers(state, "prototype_production_conformance")

    def _invalidate_requirements_e2e_confirmation(
        self,
        state: dict[str, Any],
        *,
        reason: str,
        invalidate_open_spec: bool,
        invalidate_planned_e2e: bool,
    ) -> None:
        confirmations = state.setdefault("user_confirmations", {})
        targets: list[str] = []
        if invalidate_open_spec:
            targets.extend(["product_baseline", "open_spec_freeze"])
            if state.get("project_type") == "ui":
                targets.append("ui_prototype")
            elif state.get("project_type") == "non_ui":
                targets.append("non_ui_behavior_contract")
        if invalidate_planned_e2e:
            targets.extend(["test_coverage_plan", "planned_e2e_obligations"])
        targets = list(dict.fromkeys(targets))
        existing = [confirmations.get(target) for target in targets]
        stale = [confirmation for confirmation in existing if confirmation]
        if stale:
            state.setdefault("stale_user_confirmations", []).append(
                {
                    "targets": targets,
                    "reason": reason,
                    "stale_at": self._timestamp_from_state(state),
                    "records": stale,
                }
            )
        if invalidate_open_spec:
            for target in (
                "product_baseline",
                "open_spec_freeze",
                "ui_prototype",
                "non_ui_behavior_contract",
            ):
                confirmations.pop(target, None)
            state["open_spec_freeze"] = {
                **state.get("open_spec_freeze", {}),
                "approved_by_user": False,
                "approved_at": None,
                "confirmation_artifact_path": None,
                "stale_reason": reason,
            }
            if state.get("project_type") == "ui":
                state["ui_prototype"] = {
                    **state.get("ui_prototype", {}),
                    "confirmed_by_user": False,
                    "confirmation_status": "changes_requested",
                    "confirmation_source": None,
                    "confirmation_artifact_path": None,
                }
            elif state.get("project_type") == "non_ui":
                state["non_ui_behavior_contract"] = {
                    **state.get("non_ui_behavior_contract", {}),
                    "confirmed_by_user": False,
                    "confirmation_status": "changes_requested",
                    "confirmation_artifact_path": None,
                }
            state.setdefault("confirmation_readiness", {})[
                "product_baseline"
            ] = "revision_pending"
            self._add_blockers(
                state,
                "user_confirmed_freeze",
                "product_baseline_user_confirmation",
            )
        if invalidate_planned_e2e:
            confirmations.pop("test_coverage_plan", None)
            confirmations.pop("planned_e2e_obligations", None)
            planned = state.setdefault("planned_e2e_obligations", {})
            planned["accepted_by_user"] = False
            planned.pop("confirmation_artifact_path", None)
            planned.pop("confirmation_snapshot_hash", None)
            planned.pop("confirmation_user_semantics_hash", None)
            state.setdefault("confirmation_readiness", {})[
                "test_coverage_plan"
            ] = "revision_pending"
            self._add_blockers(
                state,
                "planned_e2e_user_confirmation",
                "test_coverage_plan_user_confirmation",
            )

    @staticmethod
    def _expand_shared_requirements_e2e_targets(
        confirmations: dict[str, Any],
        targets: list[str],
    ) -> list[str]:
        expanded = list(targets)
        logical_targets = ("open_spec_freeze", "planned_e2e_obligations")
        selected_records = [
            confirmations.get(target)
            for target in targets
            if isinstance(confirmations.get(target), dict)
        ]
        shared_paths = {
            record.get("confirmation_artifact_path")
            for record in selected_records
            if record.get("shared_confirmation_target") == "requirements_e2e_plan"
            or record.get("snapshot_hash")
        }
        if not shared_paths:
            return expanded
        for logical_target in logical_targets:
            record = confirmations.get(logical_target)
            if (
                isinstance(record, dict)
                and record.get("confirmation_artifact_path") in shared_paths
                and logical_target not in expanded
            ):
                expanded.append(logical_target)
        return expanded

    @staticmethod
    def _has_snapshot_bound_requirements_e2e_confirmation(
        state: dict[str, Any],
    ) -> bool:
        confirmations = state.get("user_confirmations") or {}
        for target in (
            "test_coverage_plan",
            "open_spec_freeze",
            "planned_e2e_obligations",
        ):
            record = confirmations.get(target)
            if isinstance(record, dict) and (
                record.get("snapshot_hash") or record.get("user_semantics_hash")
            ):
                return True
        return False

    def _invalidate_launch_authorization(
        self,
        state: dict[str, Any],
        *,
        reason: str,
    ) -> None:
        authorization = state.get("implementation_launch_authorization")
        if not isinstance(authorization, dict) or not authorization:
            return
        state.setdefault("stale_implementation_launch_authorizations", []).append(
            {
                **authorization,
                "stale_reason": reason,
                "stale_at": self._timestamp_from_state(state),
            }
        )
        state["implementation_launch_authorization"] = {
            **authorization,
            "status": "stale",
            "stale_reason": reason,
        }
        self._add_blockers(state, "stale_implementation_launch_authorization")

    def _supersede_active_implementation_package(
        self,
        state: dict[str, Any],
        *,
        reason: str,
        replacement_launch_package_hash: str | None = None,
        reused_task_ids: list[str] | None = None,
    ) -> None:
        package_keys = (
            "handoff",
            "delivery_goal",
            "implementation",
            "codex_goal_prompt",
        )
        if not any(state.get(key) for key in package_keys):
            return
        old_goal = dict(state.get("delivery_goal") or {})
        archived = {
            "reason": reason,
            "superseded_at": self._timestamp_from_state(state),
            "replacement_launch_package_hash": replacement_launch_package_hash,
            "reused_task_ids": list(reused_task_ids or []),
            "task_completion_binding": {
                "completed_tasks": list(old_goal.get("completed_tasks", [])),
                "task_completion_artifacts": dict(
                    old_goal.get("task_completion_artifacts", {})
                ),
                "planned_task_hashes": {
                    task.get("task_id"): task.get("planned_task_hash")
                    for task in old_goal.get("planned_tasks", [])
                },
            },
            **{key: state.get(key) for key in package_keys if state.get(key)},
        }
        state.setdefault("superseded_implementation_packages", []).append(archived)
        for key in package_keys:
            state.pop(key, None)
        self._remove_blockers(state, "stale_implementation_launch_authorization")
        state["protocol_errors"] = [
            error
            for error in state.get("protocol_errors", [])
            if error != "stale_implementation_launch_authorization"
        ]
        state["status"] = "implementation_launch_authorized"
        state["stage"] = "implementation_launch_authorized"
        state["next_gate"] = "codex_goal_handoff"
        if replacement_launch_package_hash:
            next_state = append_transition(
                state,
                "implementation_package_superseded",
                feature_slug=state.get("feature_slug"),
                runtime_version=PLUGIN_VERSION,
                input_artifact_hashes={
                    "previous_launch_package": str(
                        old_goal.get("launch_package_hash") or "missing"
                    ),
                    "replacement_launch_package": replacement_launch_package_hash,
                },
                metadata={
                    "reason": reason,
                    "reused_task_ids": list(reused_task_ids or []),
                },
            )
            state.clear()
            state.update(next_state)

    @staticmethod
    def _matching_task_completions(
        previous_goal: dict[str, Any],
        next_goal: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        previous_tasks = {
            task.get("task_id"): task
            for task in previous_goal.get("planned_tasks", [])
        }
        artifacts = previous_goal.get("task_completion_artifacts") or {}
        matches = {}
        for task in next_goal.get("planned_tasks", []):
            task_id = task.get("task_id")
            previous = previous_tasks.get(task_id) or {}
            artifact = artifacts.get(task_id)
            if (
                artifact
                and task.get("planned_task_hash")
                and task.get("planned_task_hash") == previous.get("planned_task_hash")
                and artifact.get("planned_task_hash") == task.get("planned_task_hash")
            ):
                matches[str(task_id)] = dict(artifact)
        return matches

    @staticmethod
    def _apply_reused_task_completions(
        goal: dict[str, Any],
        completions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        next_goal = dict(goal)
        ordered_ids = [task["task_id"] for task in next_goal["planned_tasks"]]
        completed = [task_id for task_id in ordered_ids if task_id in completions]
        next_goal["completed_tasks"] = completed
        if completed:
            next_goal["task_completion_artifacts"] = {
                task_id: completions[task_id] for task_id in completed
            }
        remaining = [task_id for task_id in ordered_ids if task_id not in completions]
        if remaining:
            next_goal["status"] = (
                "implementation_in_progress" if completed else "active"
            )
            next_goal["current_task_cursor"] = remaining[0]
            next_goal["next_action"] = remaining[0]
        else:
            next_goal["status"] = "implementation_tasks_complete"
            next_goal["current_task_cursor"] = None
            next_goal["next_action"] = "record_executed_evidence_and_closure"
        return next_goal

    @staticmethod
    def _stable_hash(value: Any) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _render_implementation_launch_authorization(
        package: dict[str, Any],
        authorization: dict[str, Any],
    ) -> str:
        lines = [
            "# Implementation Launch Authorization",
            "",
            f"Status: authorized",
            f"Feature Slug: {package['feature_slug']}",
            f"Launch Package Hash: {package['launch_package_hash']}",
            f"Nonce: {package['nonce']}",
            f"Scope: {package['scope']}",
            f"Prototype Hash: {package.get('prototype_hash')}",
            f"Planned E2E Hash: {package['planned_e2e_hash']}",
            f"Task Queue Hash: {package['task_queue_hash']}",
            f"Required Commands Hash: {package['required_commands_hash']}",
            f"Authorization Source: {authorization['authorization_source']}",
            f"Authorized By: {authorization['authorized_by']}",
            f"Authorized At: {authorization['authorized_at']}",
            "",
            "## Review Modes",
        ]
        if package["review_modes"]:
            lines.extend(
                f"- {review_type}: {mode}"
                for review_type, mode in sorted(package["review_modes"].items())
            )
        else:
            lines.append("- None")
        lines.extend(["", "## Task Queue"])
        lines.extend(f"- {task['task_id']}: {task['title']}" for task in package["task_queue"])
        lines.extend(["", "## Authorization Note", authorization["user_message"], ""])
        return "\n".join(lines)

    def _artifact_hash(
        self,
        artifact_path: str,
        *,
        require_exists: bool = False,
    ) -> str:
        path = Path(artifact_path)
        if not path.is_absolute():
            path = self.project_root / path
        if not path.is_file():
            if require_exists:
                raise ConfirmationError(
                    f"prototype artifact does not exist: {artifact_path}"
                )
            return hashlib.sha256(
                f"missing:{artifact_path}".encode("utf-8")
            ).hexdigest()
        digest = hashlib.sha256()
        with path.open("rb") as artifact_file:
            for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _build_pending_confirmation(
        self,
        *,
        target: str,
        artifact_path: str,
        artifact_hash: str,
        artifact_version: str,
        prototype_revision: str,
        state: dict[str, Any],
        prototype_contract_hash: str | None = None,
        prototype_screenshot_set_hash: str | None = None,
    ) -> dict[str, Any]:
        nonce = hashlib.sha256(
            (
                target
                + ":"
                + artifact_path
                + ":"
                + artifact_hash
                + ":"
                + artifact_version
                + ":"
                + str(prototype_contract_hash or "")
                + ":"
                + str(prototype_screenshot_set_hash or "")
            ).encode("utf-8")
        ).hexdigest()[:16]
        return {
            "confirmation_id": f"PENDING-{target}",
            "target": target,
            "artifact_path": artifact_path,
            "artifact_version": artifact_version,
            "artifact_hash": artifact_hash,
            "prototype_revision": prototype_revision,
            "prototype_contract_hash": prototype_contract_hash,
            "prototype_screenshot_set_hash": prototype_screenshot_set_hash,
            "nonce": nonce,
            "created_at": self._timestamp_from_state(state),
            "status": "pending",
        }

    @staticmethod
    def _render_prototype_production_conformance(evidence: dict[str, Any]) -> str:
        lines = [
            "# Prototype Production Conformance",
            "",
            f"Status: {evidence.get('status')}",
            f"Prototype Revision: {evidence.get('prototype_revision')}",
            f"Prototype Contract Hash: {evidence.get('prototype_contract_hash')}",
            "",
            "## Covered Surfaces",
        ]
        lines.extend(f"- {item}" for item in evidence.get("covered_surface_ids", []))
        lines.extend(["", "## Covered Regions"])
        lines.extend(f"- {item}" for item in evidence.get("covered_region_ids", []))
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _add_blockers(state: dict[str, Any], *blockers: str) -> None:
        blocked_until = list(state.get("blocked_until", []))
        for blocker in blockers:
            if blocker not in blocked_until:
                blocked_until.append(blocker)
        state["blocked_until"] = blocked_until

    @staticmethod
    def _remove_blockers(state: dict[str, Any], *blockers: str) -> None:
        remove = set(blockers)
        state["blocked_until"] = [
            blocker for blocker in state.get("blocked_until", []) if blocker not in remove
        ]

    @staticmethod
    def _timestamp_from_state(state: dict[str, Any]) -> str:
        del state
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _raise_model_orchestration_retired() -> None:
        raise WorkflowError(
            "model orchestration has been retired to the Codex host"
        )

    @staticmethod
    def _render_planned_e2e_obligations(planned: dict[str, Any]) -> str:
        lines = [
            "# Planned E2E Obligations",
            "",
            "Status: Accepted",
            "User Accepted: False",
            "",
            "## Obligations",
            "",
            "| Test | Scenario | User Story | Journey | Baseline Entry | AC | TASK | Layer | Assertions | Actions | False-Positive Guards |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for obligation in planned["obligations"]:
            lines.append(
                "| {test_id} | {scenario_id} | {user_story} | {journey} | "
                "{baseline_entry_path} | {ac} | {task} | {test_layer} | "
                "{semantic_assertions} | {actions} | "
                "{false_positive_guards} |".format(
                    test_id=obligation["test_id"],
                    scenario_id=obligation["scenario_id"],
                    user_story=obligation["user_story"],
                    journey=obligation["journey"],
                    baseline_entry_path=obligation.get("baseline_entry_path", ""),
                    ac=obligation.get("acceptance_criteria", ""),
                    task=obligation.get("task", ""),
                    test_layer=obligation["test_layer"],
                    semantic_assertions="<br>".join(
                        obligation.get("semantic_assertions", [])
                    ),
                    actions="<br>".join(
                        "{action_entry} -> {assertion_target} ({semantic_depth})".format(
                            **assertion
                        )
                        for assertion in obligation.get("action_assertions", [])
                    ),
                    false_positive_guards="<br>".join(
                        obligation.get("false_positive_guards", [])
                    ),
                )
            )
        lines.extend(["", "## Exemptions"])
        for exemption in planned["exemptions"]:
            lines.append(
                "- {exemption_id} for {object_id}: {reason}".format(**exemption)
            )
        if not planned["exemptions"]:
            lines.append("- None")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_executed_browser_evidence(evidence: dict[str, Any]) -> str:
        lines = ["# Executed Browser Evidence", "", "Status: Passed", ""]
        for record in evidence["records"]:
            lines.append(
                (
                    "- {test_id}: {evidence_strength} "
                    "{evidence_path} ({evidence_sha256}); "
                    "probe={probe_artifact_path} ({probe_artifact_sha256}); "
                    "business_api_requests={business_api_request_count}"
                ).format(
                    business_api_request_count=record.get(
                        "probe_artifact_summary", {}
                    ).get("business_api_request_count", 0),
                    **record,
                )
            )
        lines.append("")
        return "\n".join(lines)
