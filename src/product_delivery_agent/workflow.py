"""Local workflow prototype for product delivery mode."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from product_delivery_agent.artifact_protocol import (
    ARTIFACT_ROOT,
    CORE_ARTIFACTS,
    initialize_workspace,
    load_state,
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
from product_delivery_agent.coverage_audit import (
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
    GatekeeperError,
    assert_pre_closure_ready,
    assert_pre_handoff_ready,
    derive_blockers,
    render_closure_validator_result,
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

    def start(self, *, feature_slug: str | None = None) -> dict[str, Any]:
        state = initialize_workspace(self.project_root)
        state["active"] = True
        state["paused"] = False
        state["intervention_enabled"] = True
        state["stage"] = "product_blueprint"
        state["activation_source"] = "waygate-product-delivery"
        state["feature_slug"] = feature_slug
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
        }
        state["ui_prototype"] = {
            "generated": False,
            "reviewed_by_agent": False,
            "confirmed_by_user": False,
            "confirmation_source": None,
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
        state["closure_validation"] = {
            "status": "not_run",
            "errors": [],
        }
        state["user_confirmations"] = {}
        state["pending_confirmations"] = {}
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

    def record_scenario_matrix(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        state = self._require_started()
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
        state = self._require_started()
        validate_multi_agent_review(review_type, review)
        review_mode = review.get("review_mode", "spawned_subagents")
        if (
            review_mode == "role_simulation"
            and "role_simulation_review_acceptance"
            not in state.get("user_confirmations", {})
        ):
            raise ReviewGateError(
                "role_simulation review requires separate user acceptance"
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
        }
        self._remove_blockers(state, f"multi_agent_{review_type}_review")
        state["stage"] = f"multi_agent_{review_type}_review_passed"
        state["next_gate"] = (
            "user_confirmed_freeze"
            if review_type == "scenario"
            else "codex_goal_handoff"
        )
        return write_state(self.project_root, state)

    def record_implementation_launch_authorization(
        self,
        *,
        user_message: str,
        scope: str,
        verification_commands: list[str] | None = None,
        planned_tasks: list[dict[str, Any]] | None = None,
        prohibited_work: list[str] | None = None,
    ) -> dict[str, Any]:
        """Record user authorization to start implementation for this package."""
        state = self._require_started()
        if "确认按当前交付包开始实现" not in user_message:
            raise ConfirmationError(
                "implementation launch requires exact user authorization phrase"
            )
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

        confirmation = {
            "confirmation_id": "CONF-implementation_launch_authorization",
            "target": "implementation_launch_authorization",
            "artifact_path": ".product-delivery/artifacts/implementation-launch-authorization.md",
            "artifact_version": package["launch_package_hash"],
            "artifact_hash": package["launch_package_hash"],
            "confirmed_by": "user",
            "confirmation_source": "chat_user_reply",
            "confirmed_at": self._timestamp_from_state(state),
            "decision": "approved",
            "user_message": user_message,
            "nonce": package["nonce"],
        }
        confirmations_dir = (
            self.project_root / ARTIFACT_ROOT / "artifacts" / "user-confirmations"
        )
        confirmations_dir.mkdir(parents=True, exist_ok=True)
        launch_path = (
            self.project_root
            / ARTIFACT_ROOT
            / "artifacts"
            / "implementation-launch-authorization.md"
        )
        launch_path.write_text(
            self._render_implementation_launch_authorization(package, confirmation),
            encoding="utf-8",
        )
        confirmation_path = confirmations_dir / "implementation_launch_authorization.md"
        confirmation_path.write_text(
            render_user_confirmation(confirmation),
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
            "confirmation_artifact_path": (
                "artifacts/user-confirmations/implementation_launch_authorization.md"
            ),
            "authorized_at": confirmation["confirmed_at"],
        }
        state.setdefault("user_confirmations", {})
        state["user_confirmations"]["implementation_launch_authorization"] = {
            **confirmation,
            "confirmation_artifact_path": (
                "artifacts/user-confirmations/implementation_launch_authorization.md"
            ),
        }
        state["stage"] = "implementation_launch_authorized"
        state["next_gate"] = "codex_goal_handoff"
        return write_state(self.project_root, state)

    def record_user_confirmation(
        self,
        confirmation: dict[str, Any],
    ) -> dict[str, Any]:
        state = self._require_started()
        validate_user_confirmation(confirmation)
        target = confirmation["target"]
        if target == "open_spec_freeze":
            review = state.get("multi_agent_reviews", {}).get("scenario", {})
            if review.get("status") != "passed":
                raise WorkflowError("multi-agent scenario review is required before freeze")

        confirmations_dir = (
            self.project_root / ARTIFACT_ROOT / "artifacts" / "user-confirmations"
        )
        confirmations_dir.mkdir(parents=True, exist_ok=True)
        confirmation_path = confirmations_dir / f"{target}.md"
        confirmation_path.write_text(
            render_user_confirmation(confirmation),
            encoding="utf-8",
        )

        artifact_path = f"artifacts/user-confirmations/{target}.md"
        state.setdefault("user_confirmations", {})
        state["user_confirmations"][target] = {
            **confirmation,
            "confirmation_artifact_path": artifact_path,
        }
        if target == "open_spec_freeze":
            state["open_spec_freeze"] = {
                "approved_by_user": True,
                "approved_at": confirmation["confirmed_at"],
                "confirmation_artifact_path": artifact_path,
            }
            state["freeze"] = {
                **state.get("freeze", {}),
                "frozen": True,
            }
            self._remove_blockers(state, "user_confirmed_freeze")
            state["stage"] = "open_spec_user_confirmed_freeze"
            state["next_gate"] = "ui_or_non_ui_confirmation"
        elif target == "planned_e2e_obligations":
            state.setdefault("planned_e2e_obligations", {})
            state["planned_e2e_obligations"]["accepted_by_user"] = True
            self._remove_blockers(state, "planned_e2e_user_confirmation")
            state["stage"] = "planned_e2e_user_confirmed"
        else:
            state["stage"] = f"{target}_user_confirmed"
        return write_state(self.project_root, state)

    def status(self) -> dict[str, Any]:
        state = self._state()
        if not state:
            state = initialize_workspace(self.project_root)
        else:
            state = write_state(self.project_root, state)
        return state

    def pause(self) -> dict[str, Any]:
        state = self._require_started()
        state["paused"] = True
        state["intervention_enabled"] = False
        return write_state(self.project_root, state)

    def resume(self) -> dict[str, Any]:
        state = self._require_started()
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
        return write_state(self.project_root, state)

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

        missing = validate_ui_prototype_review(review)
        if missing:
            raise WorkflowError(
                "missing UI prototype review fields: " + ", ".join(missing)
            )

        artifacts_dir = self.project_root / ARTIFACT_ROOT / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        review_path = artifacts_dir / CORE_ARTIFACTS["ui_prototype_review"]
        review_path.write_text(render_ui_prototype_review(review), encoding="utf-8")
        artifact_hash = self._artifact_hash(review["prototype_path"])
        revision_number = (
            int(state.get("ui_prototype", {}).get("revision_number") or 0) + 1
        )
        prototype_revision = f"prototype-revision-{revision_number:03d}"
        pending_confirmation = self._build_pending_confirmation(
            target="ui_prototype",
            artifact_path=review["prototype_path"],
            artifact_hash=artifact_hash,
            artifact_version=prototype_revision,
            prototype_revision=prototype_revision,
            state=state,
        )

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
            "review_artifact_path": f"artifacts/{CORE_ARTIFACTS['ui_prototype_review']}",
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
            "revision_number": revision_number,
            "confirmation_status": "pending_user_confirmation",
            "pending_confirmation_nonce": pending_confirmation["nonce"],
            "confirmation_source": None,
        }
        state.setdefault("pending_confirmations", {})
        state["pending_confirmations"]["ui_prototype"] = pending_confirmation
        state.setdefault("user_confirmations", {}).pop("ui_prototype", None)
        self._add_blockers(state, "ui_html_prototype_confirmation")
        state.setdefault("handoff_inputs", {})
        state["handoff_inputs"]["ui_prototype_limitations"] = list(
            review["limitations"]
        )
        state.setdefault("closure_inputs", {})
        state["closure_inputs"]["ui_prototype_limitations"] = list(
            review["limitations"]
        )
        state["stage"] = "ui_prototype_review_ready"
        state["next_gate"] = "ui_prototype_review_confirmation"
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
        self._add_blockers(state, "ui_html_prototype_confirmation")
        state["stage"] = "ui_prototype_changes_requested"
        state["next_gate"] = "ui_prototype_revision_review"
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
        state["stage"] = "non_ui_behavior_contract_ready"
        state["next_gate"] = "non_ui_behavior_contract_confirmation"
        return write_state(self.project_root, state)

    def record_test_coverage_audit(
        self,
        rows: list[dict[str, Any]],
        *,
        negative_guard_records: list[str] | None = None,
    ) -> dict[str, Any]:
        state = self._require_started()
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
        state.setdefault("handoff_inputs", {})
        state["handoff_inputs"]["coverage_matrix_range"] = audit["matrix_range"]
        state["handoff_inputs"]["latest_test_case"] = audit["latest_test_case"]
        state.setdefault("closure_inputs", {})
        state["closure_inputs"]["coverage_matrix_range"] = audit["matrix_range"]
        state["closure_inputs"]["latest_test_case"] = audit["latest_test_case"]
        state["stage"] = "test_coverage_audit_ready"
        state["next_gate"] = "codex_goal_handoff"
        return write_state(self.project_root, state)

    def record_planned_e2e_obligations(
        self,
        obligations: list[dict[str, Any]],
        *,
        exemptions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        state = self._require_started()
        planned = build_planned_e2e_obligations(obligations, exemptions)

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
        state["executed_browser_evidence"] = {
            "status": "missing",
            "records": [],
        }
        self._add_blockers(state, "planned_e2e_user_confirmation", "executed_browser_evidence")
        self._remove_blockers(state, "planned_e2e_obligations")
        state["stage"] = "planned_e2e_obligations_ready"
        state["next_gate"] = "planned_e2e_user_confirmation"
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
        self._remove_blockers(state, "executed_browser_evidence")
        state["stage"] = "executed_browser_evidence_passed"
        state["next_gate"] = "feature_closure_after_implementation"
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
        assert_pre_handoff_ready(
            state,
            self.project_root,
            launch_package_hash=package["launch_package_hash"],
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
            "completed_tasks": [],
        }
        state["codex_goal_prompt"] = handoff["codex_goal_prompt"]
        state["freeze"] = {
            "frozen": True,
            "scope_version": state.get("freeze", {}).get("scope_version") or "v1",
        }
        state["stage"] = "codex_goal_handoff_ready"
        state["status"] = "implementation_goal_active"
        state["next_gate"] = delivery_goal["current_task_cursor"]
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

    def record_post_freeze_change(
        self,
        *,
        change_type: str,
        description: str,
        cr_id: str,
    ) -> dict[str, Any]:
        state = self._require_started()
        state.setdefault("change_requests", [])
        state["change_requests"].append(
            {
                "cr_id": cr_id,
                "change_type": change_type,
                "description": description,
                "status": "recorded",
            }
        )
        if change_type == "scope_change":
            state["freeze"] = {
                **state.get("freeze", {}),
                "frozen": False,
            }
            state["stage"] = "version_scope_confirmation"
            state["next_gate"] = "version_scope"
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

    def _state(self) -> dict[str, Any]:
        return load_state(self.project_root, fallback_state=self.fallback_state)

    def _require_started(self) -> dict[str, Any]:
        state = self._state()
        if not state.get("active"):
            raise WorkflowError("workflow is not active; run start first")
        return state

    def _missing_required_confirmations(self, state: dict[str, Any]) -> list[str]:
        required = ["product_brief", "version_scope"]
        if state.get("project_type") == "ui":
            required.append("ui_prototype_review")
        elif state.get("project_type") == "non_ui":
            required.append("non_ui_behavior_contract")
        else:
            required.append("project_type")

        confirmation_points = state.get("confirmation_points", {})
        missing = []
        for artifact_name in required:
            if artifact_name == "project_type":
                missing.append(artifact_name)
                continue
            if not confirmation_points.get(artifact_name, {}).get("confirmed"):
                missing.append(artifact_name)
        return missing

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

    @staticmethod
    def _stable_hash(value: Any) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _render_implementation_launch_authorization(
        package: dict[str, Any],
        confirmation: dict[str, Any],
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
            f"Confirmed At: {confirmation['confirmed_at']}",
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
        lines.extend(["", "## User Message", confirmation["user_message"], ""])
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
            ).encode("utf-8")
        ).hexdigest()[:16]
        return {
            "confirmation_id": f"PENDING-{target}",
            "target": target,
            "artifact_path": artifact_path,
            "artifact_version": artifact_version,
            "artifact_hash": artifact_hash,
            "prototype_revision": prototype_revision,
            "nonce": nonce,
            "created_at": self._timestamp_from_state(state),
            "status": "pending",
        }

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
        return str(state.get("updated_at") or "not-recorded")

    @staticmethod
    def _render_planned_e2e_obligations(planned: dict[str, Any]) -> str:
        lines = ["# Planned E2E Obligations", "", "Status: Accepted", ""]
        lines.extend(["## Obligations"])
        for obligation in planned["obligations"]:
            lines.append(
                "- {test_id} covers {scenario_id} with {test_layer}".format(
                    **obligation
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
                "- {test_id}: {evidence_path} ({evidence_sha256})".format(**record)
            )
        lines.append("")
        return "\n".join(lines)
