"""Versioned role cards and gate profiles for review expert panels.

The catalog is deliberately provider-neutral.  It describes what a reviewer
must do and what evidence it must return; the host still owns model choice,
agent creation, and execution isolation.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


ROLE_CATALOG_VERSION = "1.1.0"
SEAT_PROFILE_VERSION = "1.1.0-seat.1"


class RoleProfileError(ValueError):
    """Raised when a role card, profile, task, or result is invalid."""


ROLE_IDS = (
    "product.intent_reviewer",
    "scenario.journey_reviewer",
    "negative.boundary_reviewer",
    "test.strategy_reviewer",
    "coverage.traceability_reviewer",
    "coverage.assertion_reviewer",
    "test.implementation_reviewer",
    "ui.conformance_reviewer",
)


GATE_PROFILES: dict[str, tuple[str, ...]] = {
    "scenario": (
        "product.intent_reviewer",
        "scenario.journey_reviewer",
        "negative.boundary_reviewer",
    ),
    "test": (
        "test.strategy_reviewer",
        "coverage.assertion_reviewer",
    ),
    "test_coverage": (
        "coverage.traceability_reviewer",
        "coverage.assertion_reviewer",
        "negative.boundary_reviewer",
    ),
    "test_implementation": (
        "test.implementation_reviewer",
        "coverage.assertion_reviewer",
    ),
    "ui_conformance": (
        "ui.conformance_reviewer",
        "scenario.journey_reviewer",
    ),
}

# A seat is the unit dispatched to a real reviewer Agent.  Its role_ids are
# still validated and reported separately so the eight logical responsibilities
# remain traceable without requiring one Agent per responsibility.
SEAT_PROFILES: dict[str, tuple[dict[str, Any], ...]] = {
    "scenario": (
        {"seat_id": "intent_boundary", "display_name": "产品意图与边界", "role_ids": (
            "product.intent_reviewer", "negative.boundary_reviewer",
        )},
        {"seat_id": "journey_interaction", "display_name": "用户旅程与交互", "role_ids": (
            "scenario.journey_reviewer",
        )},
    ),
    "test": (
        {"seat_id": "test_strategy", "display_name": "测试策略", "role_ids": (
            "test.strategy_reviewer",
        )},
        {"seat_id": "assertion_quality", "display_name": "测试断言与假通过", "role_ids": (
            "coverage.assertion_reviewer",
        )},
    ),
    "test_coverage": (
        {"seat_id": "coverage_boundary", "display_name": "覆盖追溯与边界", "role_ids": (
            "coverage.traceability_reviewer", "negative.boundary_reviewer",
        )},
        {"seat_id": "assertion_quality", "display_name": "测试断言与假通过", "role_ids": (
            "coverage.assertion_reviewer",
        )},
    ),
    "test_implementation": (
        {"seat_id": "implementation_evidence", "display_name": "测试实现证据", "role_ids": (
            "test.implementation_reviewer",
        )},
        {"seat_id": "assertion_quality", "display_name": "测试断言与假通过", "role_ids": (
            "coverage.assertion_reviewer",
        )},
    ),
    "ui_conformance": (
        {"seat_id": "ui_conformance", "display_name": "UI 一致性", "role_ids": (
            "ui.conformance_reviewer",
        )},
        {"seat_id": "journey_interaction", "display_name": "用户旅程与交互", "role_ids": (
            "scenario.journey_reviewer",
        )},
    ),
}


_COMMON_FORBIDDEN = [
    "change_scope", "edit_TASK", "write_code", "edit_tests", "update_Goal",
    "close_delivery", "write_canonical_artifact", "expand_input_scope",
    "delegate_review", "override_gate_by_majority",
]
_PEERS = {
    "product.intent_reviewer": ["scenario.journey_reviewer", "negative.boundary_reviewer"],
    "scenario.journey_reviewer": ["product.intent_reviewer", "negative.boundary_reviewer", "ui.conformance_reviewer"],
    "negative.boundary_reviewer": ["product.intent_reviewer", "scenario.journey_reviewer", "coverage.traceability_reviewer", "coverage.assertion_reviewer"],
    "test.strategy_reviewer": ["coverage.assertion_reviewer"],
    "coverage.traceability_reviewer": ["coverage.assertion_reviewer", "negative.boundary_reviewer"],
    "coverage.assertion_reviewer": ["test.strategy_reviewer", "coverage.traceability_reviewer", "negative.boundary_reviewer", "test.implementation_reviewer"],
    "test.implementation_reviewer": ["coverage.assertion_reviewer"],
    "ui.conformance_reviewer": ["scenario.journey_reviewer"],
}
_RESULT_PROPERTIES = {
    **{name: {"type": "string"} for name in (
        "role_id", "role_version", "role_definition_hash", "task_template_hash",
        "task_hash", "input_snapshot_hash", "independent_position",
        "seat_contract_version", "seat_id", "seat_task_hash",
    )},
    "status": {"enum": ["passed", "blocked", "needs_remediation"]},
    "completion_status": {"enum": ["complete", "incomplete"]},
    "identity_kind": {"enum": ["spawned", "simulated"]},
    "agent_id": {"type": ["string", "null"]},
    "spawn_source": {"type": ["string", "null"]},
    "simulated_identity": {"type": ["string", "null"]},
    "checked_items": {"type": "array", "items": {"type": "string"}},
    "check_records": {"type": "array", "items": {
        "type": "object", "required": ["check_id", "outcome", "reason", "evidence_refs"],
        "properties": {"check_id": {"type": "string"}, "reason": {"type": "string"},
                       "outcome": {"enum": ["satisfied", "finding", "blocked", "not_applicable"]},
                       "evidence_refs": {"type": "array", "items": {"type": "string"}}},
    }},
    "completion_evidence": {"type": "object", "additionalProperties": {
        "type": "array", "minItems": 1, "items": {"type": "string"}}},
    "findings": {"type": "array", "items": {
        "type": "object",
        "required": ["finding_id", "kind", "check_id", "subject_ref", "evidence_refs",
                     "impact", "recommendation", "disposition", "rationale"],
        "properties": {
            **{name: {"type": "string"} for name in (
                "finding_id", "check_id", "subject_ref", "impact", "recommendation", "rationale")},
            "kind": {"enum": ["finding", "risk", "unresolved_question", "blocking_finding"]},
            "disposition": {"enum": ["open", "accepted", "rejected"]},
            "evidence_refs": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        },
    }},
    "evidence_refs": {"type": "array", "items": {"type": "string"}},
    "blocking_findings": {"type": "array", "items": {"type": "string"}},
    "unresolved_questions": {"type": "array", "items": {"type": "string"}},
    "write_intents": {"type": "array", "maxItems": 0},
}
_COMMON_OUTPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": sorted(set(_RESULT_PROPERTIES) - {
        "agent_id", "spawn_source", "simulated_identity",
        "seat_contract_version", "seat_id", "seat_task_hash",
    }),
    "properties": _RESULT_PROPERTIES,
}


def _stable_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _definition_hash(card: dict[str, Any]) -> str:
    return _stable_hash({k: v for k, v in card.items()
                         if k not in {"definition_hash", "template_hash", "provenance"}})


def _template_hash(card: dict[str, Any]) -> str:
    return _stable_hash({"task_format": "role-task-v1", "instructions": {
        key: card[key] for key in (
            "role_id", "role_version", "mission", "when_to_invoke", "scope", "non_goals",
            "required_inputs", "optional_inputs", "task_steps", "must_check", "must_not_do",
            "required_capabilities", "permissions", "output_schema", "evidence_requirements",
            "completion_criteria", "escalation_conditions", "peer_challenge_contract", "runtime_policy",
        )}})


def _card(
    *, role_id: str, display_name: str, mission: str, when_to_invoke: str,
    scope: list[str], non_goals: list[str], required_inputs: list[str], optional_inputs: list[str],
    task_steps: list[str], must_check: list[str], must_not_do: list[str],
    required_capabilities: list[str], evidence_requirements: list[str],
    completion_criteria: list[str], escalation_conditions: list[str],
    peer_responses: list[str], quality_rubric: list[str], examples: dict[str, str],
) -> dict[str, Any]:
    card = {
        "role_id": role_id, "role_version": ROLE_CATALOG_VERSION,
        "display_name": display_name, "mission": mission, "when_to_invoke": when_to_invoke,
        "scope": scope, "non_goals": non_goals, "required_inputs": required_inputs,
        "optional_inputs": optional_inputs, "task_steps": task_steps, "must_check": must_check,
        "must_not_do": list(dict.fromkeys(must_not_do + _COMMON_FORBIDDEN)),
        "required_capabilities": required_capabilities,
        "permissions": {"read": ["role_brief", "input_snapshot_refs"],
                        "write": ["member_result_return"], "canonical_write": False},
        "output_schema": copy.deepcopy(_COMMON_OUTPUT_SCHEMA),
        "evidence_requirements": evidence_requirements + [
            "每项检查引用任务内当前材料和具体锚点；快照外材料需先升级 owner，不得自行扩读。",
            "判断、风险和未知项分别报告；无发现也要逐项填写检查依据。",
        ],
        "completion_criteria": completion_criteria,
        "escalation_conditions": escalation_conditions + [
            "必需输入不可读、能力缺失、快照漂移或越权时 blocked；已完成但需修复时 needs_remediation。",
        ],
        "peer_challenge_contract": {
            "can_challenge": _PEERS[role_id],
            "must_respond_to": peer_responses,
            "cannot_adjudicate": ["用户意图变更", "他人专业结论的最终裁决", "确定性门禁豁免", "用户确认或 closure"],
            "escalate_to_owner": escalation_conditions,
            "no_findings": "逐项列出 checked_items、check_records 和证据，不制造争议。",
            "challenge_format": ["target_role", "check_id_or_finding_id", "question", "evidence_refs"],
            "response_format": ["challenge_ref", "position", "evidence_refs", "revision_or_no_change_reason"],
        },
        "quality_rubric": quality_rubric, "examples": examples,
        "runtime_policy": {"timeout_seconds": 600, "max_recovery": 1,
                           "max_revision_rounds": 1, "model_control": "host_managed"},
        "provenance": {"catalog_version": ROLE_CATALOG_VERSION,
                       "source": "waygate-product-delivery-v1.1-review-expert-panel"},
    }
    card["definition_hash"] = _definition_hash(card)
    card["template_hash"] = _template_hash(card)
    return card


_ROLE_CARDS: dict[str, dict[str, Any]] = {
    "product.intent_reviewer": _card(
        role_id="product.intent_reviewer",
        display_name="产品意图评审专家",
        mission="判断交付是否仍表达清晰、可验证的产品意图和边界。",
        when_to_invoke="scenario gate 在产品基线确认前启用。",
        scope=["product_blueprint", "open_spec", "scope", "acceptance"],
        non_goals=["改变产品优先级", "发明未声明的商业目标", "直接批准范围变化"],
        required_inputs=["feature_slug", "open_spec", "product_blueprint", "user_stories", "non_goals"],
        optional_inputs=["prototype_or_behavior_contract", "prior_confirmations"],
        task_steps=[
            "提取目标用户、用户任务、期望结果和非目标。",
            "建立目标—功能—验收标准对应关系。",
            "标出目标遗漏、范围冲突和不支持的推断。",
            "为每个结论绑定原始需求或产品材料证据。",
        ],
        must_check=["intent.target_user", "intent.user_job", "intent.scope", "intent.acceptance"],
        must_not_do=["add_product_goal", "change_priority", "treat_preference_as_blocker"],
        required_capabilities=["read_open_spec", "read_artifact", "structured_output"],
        evidence_requirements=["每个关键目标有功能和验收锚点", "冲突引用具体文档位置"],
        completion_criteria=["每个关键目标有功能和验收锚点", "冲突引用具体文档位置"],
        escalation_conditions=["缺目标证据", "范围与已确认基线冲突", "验收无法描述用户结果"],
        peer_responses=["不重复确认的目标无需阻塞", "意见冲突需引用目标和证据"],
        quality_rubric=["目标与功能必须双向可追溯", "个人偏好不能成为 blocking"],
        examples={
            "pass": "目标—功能—验收矩阵完整，且每个锚点都能回到当前需求材料。",
            "insufficient": "只有价值口号，没有用户结果或验收证据。",
            "scope_violation": "建议引入未声明的商业能力或改变已确认优先级。",
            "false_positive": "把文档出现了‘提升效率’当成目标已被功能和验收覆盖。",
            "must_block": "关键用户目标与当前范围冲突，且没有可引用的裁决或变更记录。",
        },
    ),
    "scenario.journey_reviewer": _card(
        role_id="scenario.journey_reviewer",
        display_name="用户旅程评审专家",
        mission="检查每个用户角色能否从真实入口完成普通、异常和恢复旅程。",
        when_to_invoke="scenario gate 或 UI conformance gate 需要旅程检查时启用。",
        scope=["actors", "entry_paths", "journeys", "states", "exceptions", "recovery"],
        non_goals=["重新设计产品", "只审查理想路径", "以说明文字代替真实交互"],
        required_inputs=["scenario_matrix", "user_stories", "journeys", "acceptance_anchors", "prototype_or_behavior_contract"],
        optional_inputs=["baseline_entry_paths", "browser_evidence"],
        task_steps=[
            "按角色列出普通入口、前置条件和最终结果。",
            "逐项走查异常、取消、重试、恢复和权限不足。",
            "核对 US/J/SC/AC 锚点和状态变化。",
            "将每个缺口绑定到具体 journey、state 或 action。",
        ],
        must_check=["journey.actor", "journey.entry", "journey.happy_path", "journey.exception", "journey.recovery", "journey.permission"],
        must_not_do=["ignore_negative_paths", "redesign_product", "accept_static_explanation_as_interaction"],
        required_capabilities=["read_scenario_matrix", "read_ui_or_behavior_evidence", "structured_output"],
        evidence_requirements=["每个角色和旅程有覆盖结论", "异常/恢复路径有证据"],
        completion_criteria=["每个角色和旅程有覆盖结论", "异常/恢复路径有证据"],
        escalation_conditions=["入口无法到达", "关键状态缺失", "异常后无法恢复", "既有入口被平行页面替换"],
        peer_responses=["其他角色指出路径缺口时必须回应证据", "不可用状态要升级 owner"],
        quality_rubric=["不能以样例旅程代替全量声明旅程", "必须区分产品缺口和证据缺口"],
        examples={
            "pass": "普通、异常和恢复路径均有入口、状态变化和结果证据。",
            "insufficient": "只覆盖 happy path，异常后没有可复现的恢复证据。",
            "scope_violation": "把未批准的新流程当作现有旅程的补救方案。",
            "false_positive": "看到页面展示‘可重试’就认定重试动作和状态恢复已实现。",
            "must_block": "关键角色没有可到达入口，或异常后无法回到声明的最终结果。",
        },
    ),
    "negative.boundary_reviewer": _card(
        role_id="negative.boundary_reviewer",
        display_name="负面边界评审专家",
        mission="识别越界、未支持、越权和高风险行为，保护版本范围。",
        when_to_invoke="scenario 或 test_coverage gate 需要负面边界检查时启用。",
        scope=["non_goals", "permissions", "unsupported_behavior", "failure_boundaries"],
        non_goals=["凭空添加法规要求", "改变权限政策", "把个人风险偏好列为阻塞"],
        required_inputs=["scope", "non_goals", "negative_boundaries", "scenario_matrix", "permission_constraints"],
        optional_inputs=["prior_review_findings"],
        task_steps=[
            "提取明确不支持、未来版本和越权行为。",
            "为每个边界构造触发条件和预期拒绝结果。",
            "检查成功提示是否可能掩盖实际失败。",
            "把边界转成可执行验证建议。",
        ],
        must_check=["boundary.out_of_scope", "boundary.permission", "boundary.invalid_input", "boundary.failure_result"],
        must_not_do=["invent_policy", "expand_scope", "waive_declared_boundary"],
        required_capabilities=["read_scope_artifacts", "read_permission_rules", "structured_output"],
        evidence_requirements=["每个边界有触发、拒绝结果和证据", "未声明规则被标为 question 而非 blocker"],
        completion_criteria=["每个边界有触发、拒绝结果和证据", "未声明规则被标为 question 而非 blocker"],
        escalation_conditions=["越权可达", "未来功能泄漏", "失败被错误地报告为成功"],
        peer_responses=["必须回应其他角色发现的边界冲突", "边界语义缺失时升级 owner"],
        quality_rubric=["只能依据已声明范围和权限", "不得以多数票豁免边界"],
        examples={
            "pass": "每个边界都有触发条件、拒绝结果和验证证据。",
            "insufficient": "只列风险，没有定义系统应拒绝什么或如何验证。",
            "scope_violation": "凭空加入未声明的法规、安全或合规政策。",
            "false_positive": "检测到‘权限不足’文案就认定越权请求确实被拒绝。",
            "must_block": "已声明的越权行为可达，或错误输入被当成成功结果继续处理。",
        },
    ),
    "test.strategy_reviewer": _card(
        role_id="test.strategy_reviewer",
        display_name="测试策略评审专家",
        mission="检查测试层级、环境、数据、依赖和回归范围是否能验证产品风险。",
        when_to_invoke="generic test gate 在测试覆盖计划前启用。",
        scope=["test_layers", "fixtures", "dependencies", "regression", "execution"],
        non_goals=["实现测试代码", "强制所有路径使用 E2E", "删除关键验证以节省成本"],
        required_inputs=["open_spec", "scenario_matrix", "test_obligations", "prototype_or_behavior_contract", "test_strategy"],
        optional_inputs=["architecture_constraints", "known_failure_history"],
        task_steps=[
            "按风险为行为选择 unit/integration/E2E 层级。",
            "检查环境、账号、数据、依赖和清理前置条件。",
            "检查 mock 是否遮蔽了需要验证的真实链路。",
            "确定回归范围和失败定位方式。",
        ],
        must_check=["strategy.layer", "strategy.precondition", "strategy.real_path", "strategy.regression"],
        must_not_do=["write_test_code", "require_e2e_everywhere", "remove_required_coverage"],
        required_capabilities=["read_test_plan", "read_architecture_constraints", "structured_output"],
        evidence_requirements=["每个高风险行为有层级和理由", "执行前置条件明确"],
        completion_criteria=["每个高风险行为有层级和理由", "执行前置条件明确"],
        escalation_conditions=["真实链路被完全 mock", "关键失败路径没有可执行验证", "环境前置不可满足"],
        peer_responses=["必须回应断言专家指出的弱验证", "依赖不确定时升级 owner"],
        quality_rubric=["策略选择必须与风险相关", "不能以测试数量代替策略合理性"],
        examples={
            "pass": "每个高风险行为都有与风险相称的层级、前置条件和回归理由。",
            "insufficient": "只列 unit/integration/E2E 类型，没有环境、数据或依赖条件。",
            "scope_violation": "替实现团队编写测试代码或改变产品行为。",
            "false_positive": "用全量命令成功替代关键链路和失败定位策略。",
            "must_block": "关键真实链路被 mock 掉，导致目标风险没有可执行验证。",
        },
    ),
    "coverage.traceability_reviewer": _card(
        role_id="coverage.traceability_reviewer",
        display_name="覆盖追溯评审专家",
        mission="确保需求承诺、用户旅程、测试任务和测试用例双向闭环。",
        when_to_invoke="test_coverage gate 在实现授权前启用。",
        scope=["US", "J", "SC", "AC", "TASK", "TC", "exemptions"],
        non_goals=["按标题相似认定覆盖", "自行添加豁免", "删除缺失义务"],
        required_inputs=["open_spec", "scenario_matrix", "coverage_audit", "planned_obligations", "task_queue", "test_cases"],
        optional_inputs=["collection_items", "accepted_exemptions"],
        task_steps=[
            "建立 US/J/SC/AC/TASK/TC 双向映射。",
            "逐条检查每项义务是否有测试或有效豁免。",
            "逐项检查集合型数据的 required/covered/assertion。",
            "标出多余测试、断链和未经批准的豁免。",
        ],
        must_check=["traceability.US_to_TC", "traceability.TC_to_AC", "traceability.journey", "traceability.collection", "traceability.exemption"],
        must_not_do=["accept_title_only", "invent_exemption", "merge_unrelated_obligations"],
        required_capabilities=["read_coverage_audit", "read_task_queue", "structured_output"],
        evidence_requirements=["每条义务有明确测试映射或有效豁免（允许多个测试共同覆盖）", "双向链接完整"],
        completion_criteria=["每条义务有明确测试映射或有效豁免（允许多个测试共同覆盖）", "双向链接完整"],
        escalation_conditions=["活跃义务断链", "集合项缺失", "测试无需求依据"],
        peer_responses=["可挑战测试策略的覆盖不足", "必须引用具体 anchor"],
        quality_rubric=["编号连续不等于覆盖", "缺口必须保留而非改名消失"],
        examples={
            "pass": "US/J/SC/AC/TASK/TC 双向追溯完整，集合项逐项有测试或有效豁免。",
            "insufficient": "只有测试编号，没有语义链接或集合项映射。",
            "scope_violation": "把未批准的豁免当成已接受并删除缺失义务。",
            "false_positive": "因编号连续或标题相似就认定需求已覆盖。",
            "must_block": "活跃义务没有明确测试映射、有效豁免或可解释的追溯链。",
        },
    ),
    "coverage.assertion_reviewer": _card(
        role_id="coverage.assertion_reviewer",
        display_name="测试断言评审专家",
        mission="判断测试在错误实现出现时是否真的失败。",
        when_to_invoke="test、test_coverage 或 test_implementation gate 需要断言检查时启用。",
        scope=["actions", "expected_results", "negative_assertions", "false_positive_risks"],
        non_goals=["接受 marker-only/function-name-only/static-panel-only/first-button-only", "只看测试名称", "修改被测代码"],
        required_inputs=["planned_obligations", "test_cases", "action_assertions", "behavior_or_ui_evidence"],
        optional_inputs=["test_source", "execution_evidence"],
        task_steps=[
            "列出每个动作的真实入口和预期结果。",
            "判断错误实现是否仍可能通过当前断言。",
            "检查负面、权限和集合项断言。",
            "提出可区分正确与错误行为的证据目标。",
        ],
        must_check=["assertion.action_entry", "assertion.expected_result", "assertion.failure_condition", "assertion.evidence_target"],
        must_not_do=["accept_static_text_as_success", "accept_marker_only", "rewrite_source_under_review"],
        required_capabilities=["read_test_plan", "read_test_source_when_available", "structured_output"],
        evidence_requirements=["每个关键动作有真实结果断言", "断言目标可从证据验证"],
        completion_criteria=["每个关键动作有真实结果断言", "断言目标可从证据验证"],
        escalation_conditions=["错误实现仍能通过", "断言只验证点击或文案", "证据无法区分正确/错误"],
        peer_responses=["必须回应测试策略的层级选择", "与实现专家共享断言缺口但不替其改代码"],
        quality_rubric=["页面显示成功不等于业务成功", "断言必须绑定结果目标"],
        examples={
            "pass": "错误实现会在真实结果断言处失败，并能提供对应证据目标。",
            "insufficient": "只断言元素存在、点击完成或静态文案出现。",
            "scope_violation": "建议修改产品或测试目标来迁就弱断言。",
            "false_positive": "提交后页面显示‘成功’，但没有验证服务端记录、响应或后续查询。",
            "must_block": "关键动作没有可区分正确与错误实现的真实结果断言。",
        },
    ),
    "test.implementation_reviewer": _card(
        role_id="test.implementation_reviewer",
        display_name="测试实现证据评审专家",
        mission="核验计划测试是否真实实现、执行，并对应当前交付版本。",
        when_to_invoke="test_implementation gate 在实现证据出现后启用。",
        scope=["test_source", "execution_logs", "screenshots", "traces", "test_ids"],
        non_goals=["使用旧版本证据", "用总命令成功替代逐项证据", "把未执行测试标为通过"],
        required_inputs=["planned_obligations", "test_source", "test_code_paths", "execution_evidence", "reviewed_test_ids"],
        optional_inputs=["browser_logs", "screenshots", "traces", "mock_findings"],
        task_steps=[
            "将计划测试逐条映射到实际代码路径。",
            "核对执行记录、版本、环境和结果。",
            "检查日志、截图、trace 是否对应当前测试。",
            "识别跳过项、mock 遮蔽和 supporting-only 证据。",
        ],
        must_check=["implementation.code_path", "implementation.execution_record", "implementation.test_id", "implementation.action_assertion", "implementation.current_version"],
        must_not_do=["use_old_evidence", "accept_aggregate_command_only", "change_test_under_review"],
        required_capabilities=["read_test_source", "read_execution_artifacts", "structured_output"],
        evidence_requirements=["每个计划测试有当前实现路径和执行证据", "证据版本和对象匹配"],
        completion_criteria=["每个计划测试有当前实现路径和执行证据", "证据版本和对象匹配"],
        escalation_conditions=["代码未执行", "证据属于旧版本", "测试被配置排除", "只验证 mock"],
        peer_responses=["必须回应 assertion reviewer 的误报风险", "无法确认版本时升级 owner"],
        quality_rubric=["总命令成功不等于逐项通过", "截图/trace 必须绑定 test ID"],
        examples={
            "pass": "计划、当前代码路径、执行记录和逐项证据全部对应。",
            "insufficient": "只有测试源码，没有当前版本的执行结果或证据路径。",
            "scope_violation": "把 supporting evidence 当成正式闭包证明，或修改被审查测试。",
            "false_positive": "总命令退出码为 0，但计划测试被跳过或没有逐项结果。",
            "must_block": "关键测试未执行、证据属于旧版本，或当前实现路径无法确认。",
        },
    ),
    "ui.conformance_reviewer": _card(
        role_id="ui.conformance_reviewer",
        display_name="UI 一致性评审专家",
        mission="核验生产 UI 是否兑现冻结原型的结构、状态、区域和交互契约。",
        when_to_invoke="ui_conformance gate 在 UI 生产证据形成后启用。",
        scope=["surfaces", "states", "regions", "relationships", "interactions", "allowed_deviations"],
        non_goals=["按审美偏好重设计", "恢复退役像素门槛", "推翻有效用户裁决", "把数据行数变化当结构失败"],
        required_inputs=["prototype_contract", "implementation_baseline", "production_screenshots", "semantic_snapshots", "visual_adjudications"],
        optional_inputs=["browser_traces", "computed_style_fingerprints"],
        task_steps=[
            "逐个 surface/state/viewport 核对区域、层级和顺序。",
            "核对关键交互、可访问语义和旧入口复用。",
            "区分结构/语义/交互失败与允许的数据变化。",
            "只引用当前有效的视觉偏差裁决。",
        ],
        must_check=["ui.surface", "ui.state", "ui.region", "ui.interaction", "ui.legacy_reuse", "ui.allowed_deviation"],
        must_not_do=["redesign_by_preference", "restore_retired_pixel_gate", "ignore_unmapped_regions"],
        required_capabilities=["read_prototype_contract", "read_browser_evidence", "structured_output"],
        evidence_requirements=["每个冻结 UI 单元有结构/交互/偏差结论", "差异绑定生产证据和契约"],
        completion_criteria=["每个冻结 UI 单元有结构/交互/偏差结论", "差异绑定生产证据和契约"],
        escalation_conditions=["缺关键 region", "状态不可达", "交互结果不一致", "未映射区域", "无证据偏差"],
        peer_responses=["可挑战旅程专家的路径缺失", "视觉裁决不能豁免结构或交互失败"],
        quality_rubric=["允许的数据变化不自动成为 blocker", "不得用新设计替代冻结契约"],
        examples={
            "pass": "每个冻结 surface/state/region 都有结构、交互和偏差证据映射。",
            "insufficient": "只看截图外观，没有状态、区域或交互证据。",
            "scope_violation": "按个人审美要求重做 UI，或恢复已退役的像素门槛。",
            "false_positive": "截图看起来相似，就认定旧入口、键盘路径和状态反馈一致。",
            "must_block": "关键区域未映射、状态不可达或核心交互结果与冻结契约不一致。",
        },
    ),
}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _strings(value: Any, label: str, *, empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not empty and not value) or not all(_nonempty(x) for x in value):
        raise RoleProfileError(f"{label} must be a list of nonempty strings")
    return value


def validate_role_card(card: dict[str, Any]) -> None:
    """Reject malformed or altered definitions before creating any member task."""
    if not isinstance(card, dict) or card.get("role_id") not in ROLE_IDS:
        raise RoleProfileError("unknown role_id in role card")
    if card.get("role_version") != ROLE_CATALOG_VERSION:
        raise RoleProfileError("unsupported role_version in the fixed catalog")
    for field in ("role_version", "display_name", "mission", "when_to_invoke"):
        if not _nonempty(card.get(field)):
            raise RoleProfileError(f"role card requires {field}")
    for field in ("scope", "non_goals", "required_inputs", "task_steps", "must_check", "must_not_do",
                  "required_capabilities", "evidence_requirements", "completion_criteria",
                  "escalation_conditions", "quality_rubric"):
        _strings(card.get(field), field)
    _strings(card.get("optional_inputs"), "optional_inputs", empty=True)
    if len(set(card["must_check"])) != len(card["must_check"]):
        raise RoleProfileError("duplicate required check ID")
    if card.get("permissions") != {"read": ["role_brief", "input_snapshot_refs"],
                                   "write": ["member_result_return"], "canonical_write": False}:
        raise RoleProfileError("role permissions must only allow returning member results")
    schema = card.get("output_schema")
    if not isinstance(schema, dict) or schema.get("type") != "object" or not schema.get("required") or not schema.get("properties"):
        raise RoleProfileError("role card requires structured output_schema")
    peer = card.get("peer_challenge_contract")
    if not isinstance(peer, dict):
        raise RoleProfileError("peer_challenge_contract must be an object")
    for field in ("can_challenge", "must_respond_to", "cannot_adjudicate", "escalate_to_owner",
                  "challenge_format", "response_format"):
        _strings(peer.get(field), "peer_challenge_contract." + field)
    if set(peer["can_challenge"]) - set(ROLE_IDS) or not _nonempty(peer.get("no_findings")):
        raise RoleProfileError("peer_challenge_contract has invalid targets or no-findings rule")
    examples = card.get("examples")
    if not isinstance(examples, dict) or set(examples) != {
        "pass", "insufficient", "scope_violation", "false_positive", "must_block"
    } or not all(_nonempty(value) for value in examples.values()):
        raise RoleProfileError("role examples must cover all five quality cases")
    if card.get("runtime_policy") != {"timeout_seconds": 600, "max_recovery": 1,
                                     "max_revision_rounds": 1, "model_control": "host_managed"}:
        raise RoleProfileError("invalid runtime_policy")
    if card.get("definition_hash") != _definition_hash(card) or card.get("template_hash") != _template_hash(card):
        raise RoleProfileError("role definition or template hash is stale")


def get_role_card(role_id: str) -> dict[str, Any]:
    """Return an independently mutable, validated role definition."""
    if not isinstance(role_id, str) or role_id not in _ROLE_CARDS:
        raise RoleProfileError(f"unknown role_id: {role_id}")
    card = copy.deepcopy(_ROLE_CARDS[role_id])
    validate_role_card(card)
    return card


def get_gate_profile(review_type: str) -> tuple[str, ...]:
    if not isinstance(review_type, str) or review_type not in GATE_PROFILES:
        raise RoleProfileError(f"unknown review_type: {review_type}")
    return GATE_PROFILES[review_type]


def get_gate_seat_profile(review_type: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(review_type, str) or review_type not in SEAT_PROFILES:
        raise RoleProfileError(f"unknown review_type: {review_type}")
    seats = tuple(copy.deepcopy(row) for row in SEAT_PROFILES[review_type])
    role_ids = [role_id for seat in seats for role_id in seat["role_ids"]]
    if len(seats) != 2 or set(role_ids) != set(get_gate_profile(review_type)) or len(role_ids) != len(set(role_ids)):
        raise RoleProfileError(f"invalid fixed seat profile for {review_type}")
    return seats


def build_role_task(
    review_type: str,
    role_id: str,
    context: dict[str, Any],
    *,
    seat_id: str | None = None,
    seat_role_ids: tuple[str, ...] | list[str] | None = None,
    seat_display_name: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic, minimal brief. The workflow verifies file contents."""
    profile = get_gate_profile(review_type)
    if role_id not in profile:
        raise RoleProfileError(f"role {role_id} is not part of review_type {review_type}")
    if not isinstance(context, dict):
        raise RoleProfileError("role task context must be an object")
    for field in ("delivery_id", "feature_slug", "input_snapshot_hash"):
        if not _nonempty(context.get(field)):
            raise RoleProfileError(f"{field} is required")
    branch = context.get("project_type")
    if branch not in ("ui", "non_ui") or (review_type == "ui_conformance" and branch != "ui"):
        raise RoleProfileError("invalid project_type for this review type")
    refs = context.get("input_refs")
    if not isinstance(refs, dict):
        raise RoleProfileError("input_refs must map logical inputs to bound files")
    card = get_role_card(role_id)
    required = [key for key in card["required_inputs"] if key != "feature_slug"]
    if review_type == "test_implementation" and role_id == "coverage.assertion_reviewer":
        required += ["test_source", "execution_evidence"]
    if review_type == "ui_conformance" and role_id == "scenario.journey_reviewer":
        required += ["browser_evidence"]
    missing = set(required) - set(refs)
    if missing:
        raise RoleProfileError("missing required inputs: " + ", ".join(sorted(missing)))
    selected = {}
    for key in sorted(set(required) | (set(card["optional_inputs"]) & set(refs))):
        ref = refs[key]
        if not isinstance(ref, dict) or not _nonempty(ref.get("ref")):
            raise RoleProfileError(f"input ref {key} requires a file ref")
        digest = ref.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or set(digest) - set("0123456789abcdef"):
            raise RoleProfileError(f"input ref {key} requires lowercase sha256")
        if ref.get("project_type", "shared") not in ("shared", branch):
            raise RoleProfileError(f"input ref {key} belongs to the wrong project branch")
        selected[key] = {"ref": ref["ref"], "sha256": digest,
                         "project_type": ref.get("project_type", "shared")}
    task = {key: copy.deepcopy(card[key]) for key in (
        "role_id", "role_version", "display_name", "mission", "when_to_invoke", "scope", "non_goals",
        "task_steps", "must_check", "must_not_do", "required_capabilities", "permissions",
        "evidence_requirements", "completion_criteria", "escalation_conditions",
        "peer_challenge_contract", "output_schema", "runtime_policy",
    )}
    task.update({key: context[key] for key in ("feature_slug", "delivery_id", "project_type", "input_snapshot_hash")})
    task.update(review_type=review_type, role_definition_hash=card["definition_hash"],
                task_template_hash=card["template_hash"], required_inputs=required,
                input_refs=selected)
    effective_seat_id = seat_id or context.get("seat_id")
    effective_seat_roles = tuple(seat_role_ids or context.get("seat_role_ids") or ())
    if effective_seat_id:
        if role_id not in effective_seat_roles:
            raise RoleProfileError("role is not part of the declared reviewer seat")
        task.update({
            "seat_contract_version": SEAT_PROFILE_VERSION,
            "seat_id": effective_seat_id,
            "seat_display_name": seat_display_name or context.get("seat_display_name") or effective_seat_id,
            "seat_role_ids": list(effective_seat_roles),
        })
        if context.get("seat_task_hash"):
            task["seat_task_hash"] = context["seat_task_hash"]
    task["peer_challenge_contract"]["can_challenge"] = [
        peer for peer in task["peer_challenge_contract"]["can_challenge"] if peer in profile
    ]
    task["task_hash"] = _stable_hash(task)
    return task


def build_gate_tasks(review_type: str, context: dict[str, Any]) -> dict[str, Any]:
    """Build the two dispatch seats and their flattened logical role tasks."""
    seats = get_gate_seat_profile(review_type)
    role_tasks: list[dict[str, Any]] = []
    review_seats: list[dict[str, Any]] = []
    for seat in seats:
        base_tasks = [
            build_role_task(
                review_type,
                role_id,
                context,
                seat_id=seat["seat_id"],
                seat_role_ids=tuple(seat["role_ids"]),
                seat_display_name=seat["display_name"],
            )
            for role_id in seat["role_ids"]
        ]
        seat_task_hash = _stable_hash({
            "seat_contract_version": SEAT_PROFILE_VERSION,
            "seat_id": seat["seat_id"],
            "role_ids": list(seat["role_ids"]),
            "role_task_hashes": [task["task_hash"] for task in base_tasks],
        })
        final_tasks: list[dict[str, Any]] = []
        for task in base_tasks:
            task["seat_task_hash"] = seat_task_hash
            task.pop("task_hash", None)
            task["task_hash"] = _stable_hash(task)
            final_tasks.append(task)
        role_tasks.extend(final_tasks)
        review_seats.append({
            "seat_contract_version": SEAT_PROFILE_VERSION,
            "seat_id": seat["seat_id"],
            "display_name": seat["display_name"],
            "role_ids": list(seat["role_ids"]),
            "role_task_hashes": {task["role_id"]: task["task_hash"] for task in final_tasks},
            "seat_task_hash": seat_task_hash,
        })
    return {
        "seat_contract_version": SEAT_PROFILE_VERSION,
        "review_seats": review_seats,
        "role_tasks": role_tasks,
    }


def _schema_check(value: Any, schema: dict[str, Any], path: str = "result") -> None:
    """Validate the small JSON-schema subset used by the fixed output contracts."""
    types = {"object": dict, "array": list, "string": str, "null": type(None)}
    required_type = schema.get("type")
    if required_type:
        names = required_type if isinstance(required_type, list) else [required_type]
        if not any(isinstance(value, types[name]) for name in names):
            raise RoleProfileError(f"{path} has wrong type")
    if "enum" in schema and value not in schema["enum"]:
        raise RoleProfileError(f"{path} has invalid value")
    if isinstance(value, dict):
        if set(schema.get("required", [])) - set(value):
            raise RoleProfileError(f"{path} is missing required fields")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        if extra is False and set(value) - set(properties):
            raise RoleProfileError(f"{path} contains fields outside the output contract")
        for key, item in value.items():
            if key in properties:
                _schema_check(item, properties[key], path + "." + key)
            elif isinstance(extra, dict):
                _schema_check(item, extra, path + "." + key)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            raise RoleProfileError(f"{path} has invalid length")
        for index, item in enumerate(value):
            if "items" in schema:
                _schema_check(item, schema["items"], f"{path}[{index}]")


def _evidence(refs: Any, allowed: set[str], *, empty: bool = False) -> None:
    for ref in _strings(refs, "evidence_refs", empty=empty):
        if ref not in allowed and ref.partition("#")[0] not in allowed:
            raise RoleProfileError("evidence ref is outside the bound task inputs")


def validate_role_result(review_type: str, result: dict[str, Any], *,
                         expected_snapshot_hash: str,
                         expected_task: dict[str, Any] | None = None) -> None:
    """Validate member evidence; a valid blocked result still cannot pass a gate."""
    if not isinstance(result, dict) or not isinstance(expected_task, dict):
        raise RoleProfileError("role result and bound expected task are required")
    role_id = result.get("role_id")
    if not isinstance(role_id, str) or role_id not in get_gate_profile(review_type):
        raise RoleProfileError("role result does not match the gate profile")
    card = get_role_card(role_id)
    task = build_role_task(review_type, role_id, expected_task)
    if expected_task != task:
        raise RoleProfileError("expected task content or hash is stale")
    _schema_check(result, card["output_schema"])
    for field in ("role_id", "role_version", "role_definition_hash", "task_template_hash", "task_hash"):
        if result.get(field) != task[field]:
            raise RoleProfileError(f"{field} does not match the role task")
    if task.get("seat_id"):
        for field in ("seat_contract_version", "seat_id", "seat_task_hash"):
            if result.get(field) != task.get(field):
                raise RoleProfileError(f"{field} does not match the reviewer seat")
    if task["input_snapshot_hash"] != expected_snapshot_hash or result.get("input_snapshot_hash") != expected_snapshot_hash:
        raise RoleProfileError("input_snapshot_hash does not match the current snapshot")
    if not _nonempty(result["independent_position"]):
        raise RoleProfileError("independent_position is required")
    if result["identity_kind"] == "spawned":
        if not _nonempty(result.get("agent_id")) or not _nonempty(result.get("spawn_source")) or result.get("simulated_identity") is not None:
            raise RoleProfileError("spawned identity requires agent_id and spawn_source only")
    elif not _nonempty(result.get("simulated_identity")) or result.get("agent_id") is not None or result.get("spawn_source") is not None:
        raise RoleProfileError("simulated identity cannot claim real spawn identity")
    blocked = result["status"] == "blocked"
    complete = result["completion_status"] == "complete"
    if not blocked and not complete:
        raise RoleProfileError("completion_status must be complete for finished reviews")
    if blocked and (complete or not result["unresolved_questions"]):
        raise RoleProfileError("blocked result must be incomplete with a reason")
    _strings(result["unresolved_questions"], "unresolved_questions", empty=True)
    allowed = {ref["ref"] for ref in task["input_refs"].values()}
    _evidence(result["evidence_refs"], allowed, empty=blocked)
    required_checks = set(task["must_check"])
    checked = _strings(result["checked_items"], "checked_items", empty=blocked)
    if len(set(checked)) != len(checked) or set(checked) - required_checks or (complete and set(checked) != required_checks):
        raise RoleProfileError("checked_items must cover exactly the required checks")
    records = result["check_records"]
    check_ids = [row["check_id"] for row in records]
    if len(set(check_ids)) != len(check_ids) or set(check_ids) != set(checked):
        raise RoleProfileError("check_records must match checked_items exactly")
    for row in records:
        if not _nonempty(row["reason"]):
            raise RoleProfileError("each check requires its reason")
        _evidence(row["evidence_refs"], allowed, empty=blocked and row["outcome"] == "blocked")
        if result["status"] == "passed" and row["outcome"] not in {"satisfied", "not_applicable"}:
            raise RoleProfileError("passed result cannot contain failed or blocked checks")
    completion = result["completion_evidence"]
    criteria = set(task["completion_criteria"])
    if set(completion) - criteria or (complete and set(completion) != criteria):
        raise RoleProfileError("completion_evidence must cover the completion criteria")
    for refs in completion.values():
        _evidence(refs, allowed)
    findings = result["findings"]
    ids: set[str] = set()
    blockers: set[str] = set()
    for finding in findings:
        for field in ("finding_id", "subject_ref", "impact", "recommendation", "rationale"):
            if not _nonempty(finding[field]):
                raise RoleProfileError(f"finding requires {field}")
        if finding["finding_id"] in ids or finding["check_id"] not in required_checks:
            raise RoleProfileError("finding ID is duplicated or check_id is unknown")
        ids.add(finding["finding_id"])
        _evidence(finding["evidence_refs"], allowed)
        unresolved = finding["disposition"] != "rejected"
        if finding["kind"] == "blocking_finding" and unresolved:
            blockers.add(finding["finding_id"])
        if result["status"] == "passed" and finding["kind"] == "unresolved_question" and unresolved:
            raise RoleProfileError("passed result cannot leave unresolved questions")
        if result["status"] == "passed" and unresolved and finding["kind"] in {"finding", "blocking_finding"}:
            raise RoleProfileError("passed result cannot hide remediation findings")
    blocking_ids = _strings(result["blocking_findings"], "blocking_findings", empty=True)
    if set(blocking_ids) != blockers or len(set(blocking_ids)) != len(blocking_ids):
        raise RoleProfileError("blocking_findings must list exactly the unresolved blockers")
    if result["status"] == "passed" and blockers:
        raise RoleProfileError("passed result cannot contain blocking findings")
    # The host must enforce timing/isolation; no JSON claim proves those facts.


def validate_role_results(review_type: str, results: list[dict[str, Any]], *,
                          expected_snapshot_hash: str,
                          expected_tasks: list[dict[str, Any]] | None = None) -> None:
    required = set(get_gate_profile(review_type))
    if not isinstance(results, list) or not isinstance(expected_tasks, list):
        raise RoleProfileError("role results and expected tasks must be lists")
    if any(not isinstance(task, dict) or not isinstance(task.get("role_id"), str) for task in expected_tasks):
        raise RoleProfileError("expected tasks must have valid role IDs")
    tasks = {task["role_id"]: task for task in expected_tasks}
    if set(tasks) != required or len(expected_tasks) != len(required):
        raise RoleProfileError("expected tasks do not match the gate profile")
    seen: set[str] = set()
    spawned: set[str] = set()
    simulated: set[str] = set()
    seat_mode = any(task.get("seat_id") for task in expected_tasks)
    seat_agents: dict[str, str] = {}
    for result in results:
        role = result.get("role_id") if isinstance(result, dict) else None
        if not isinstance(role, str) or role not in required or role in seen:
            raise RoleProfileError("unknown or duplicate role result")
        seen.add(role)
        validate_role_result(review_type, result, expected_snapshot_hash=expected_snapshot_hash,
                             expected_task=tasks[role])
        identities = spawned if result["identity_kind"] == "spawned" else simulated
        identity = result.get("agent_id") if result["identity_kind"] == "spawned" else result["simulated_identity"]
        if seat_mode:
            seat_id = tasks[role]["seat_id"]
            previous = seat_agents.get(seat_id)
            if previous is not None and previous != identity:
                raise RoleProfileError("roles in one reviewer seat must share an identity")
            seat_agents[seat_id] = identity
        elif identity in identities:
            raise RoleProfileError("duplicate member identity")
        identities.add(identity)
    if seat_mode:
        expected_seats = {task["seat_id"] for task in expected_tasks}
        if set(seat_agents) != expected_seats or len(seat_agents) != len(set(seat_agents.values())):
            raise RoleProfileError("each reviewer seat requires one distinct identity")
    if seen != required:
        raise RoleProfileError("missing required role results: " + ", ".join(sorted(required - seen)))
