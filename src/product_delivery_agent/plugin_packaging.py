"""Codex plugin package assembly helpers."""

from __future__ import annotations

import json
import shutil
import tarfile
from pathlib import Path
from typing import Any

from product_delivery_agent.gatekeeper import (
    CANONICAL_SCHEMA_VERSION,
    CANONICAL_VALIDATOR,
    PLUGIN_VERSION,
)
from product_delivery_agent.skill_gates import FILE_SKILLS, STAGE_SKILLS

PLUGIN_NAME = "waygate-product-delivery"
LEGACY_PLUGIN_NAMES = ("product-delivery-agent",)


def package_codex_plugin(repo_root: str | Path) -> dict[str, Path]:
    """Create a repo-local Codex plugin package for the product workflow."""
    root = Path(repo_root)
    _remove_legacy_plugin_packages(root)
    plugin_root = root / "plugins" / PLUGIN_NAME
    manifest_dir = plugin_root / ".codex-plugin"
    skills_dir = plugin_root / "skills" / PLUGIN_NAME
    hooks_dir = plugin_root / "hooks"
    templates_dir = plugin_root / "templates"
    scripts_dir = plugin_root / "scripts"
    policies_dir = plugin_root / "policies"
    runtime_dir = plugin_root / "runtime" / "product_delivery_agent"

    for directory in (
        manifest_dir,
        skills_dir,
        hooks_dir,
        templates_dir,
        scripts_dir,
        policies_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    _copy_runtime_package(runtime_dir)

    _write_json(manifest_dir / "plugin.json", _plugin_manifest())
    (skills_dir / "SKILL.md").write_text(_skill_markdown(), encoding="utf-8")
    (hooks_dir / "README.md").write_text(_hooks_readme(), encoding="utf-8")
    _write_templates(templates_dir)
    validator_path = scripts_dir / "validate-closure-artifact.py"
    validator_path.write_text(
        _validation_script(),
        encoding="utf-8",
    )
    validator_path.chmod(0o755)
    (scripts_dir / "formal-gate-validation-plan.md").write_text(
        _formal_gate_plan(),
        encoding="utf-8",
    )
    _write_json(policies_dir / "lifecycle.json", _lifecycle_policy())
    (policies_dir / "upgrade-retention.md").write_text(
        _upgrade_policy(),
        encoding="utf-8",
    )
    (policies_dir / "waygate-controller-readonly.md").write_text(
        _readonly_policy(),
        encoding="utf-8",
    )
    marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(marketplace_path, _marketplace())
    return {
        "plugin_root": plugin_root,
        "manifest_path": manifest_dir / "plugin.json",
        "marketplace_path": marketplace_path,
    }


def build_codex_plugin_distribution(repo_root: str | Path) -> Path:
    """Build a compressed distribution archive for the installable plugin."""
    root = Path(repo_root)
    package = package_codex_plugin(root)
    plugin_root = package["plugin_root"]
    dist_dir = root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    archive_path = dist_dir / f"{PLUGIN_NAME}-{PLUGIN_VERSION}.tar.gz"
    if archive_path.exists():
        archive_path.unlink()
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(plugin_root, arcname=PLUGIN_NAME)
        archive.add(package["marketplace_path"], arcname=".agents/plugins/marketplace.json")
    return archive_path


def _plugin_manifest() -> dict[str, Any]:
    return {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": "Codex-native product delivery workflow plugin.",
        "author": {
            "name": "Waygate Product Delivery Maintainers",
            "email": "maintainers@example.com",
            "url": "https://example.com/waygate-product-delivery",
        },
        "homepage": "https://example.com/waygate-product-delivery",
        "repository": "https://example.com/waygate-product-delivery.git",
        "license": "MIT",
        "keywords": [
            "product-delivery",
            "open-spec",
            "codex",
            "feature-closure",
        ],
        "skills": "./skills/",
        "interface": {
            "displayName": "Waygate Product Delivery",
            "shortDescription": "Waygate-guided product delivery workflow for Codex.",
            "longDescription": (
                "A dormant-by-default workflow plugin for product briefs, "
                "scope confirmation, UI/non-UI gates, coverage audit, "
                "Codex handoff, and feature closure evidence."
            ),
            "developerName": "Waygate Product Delivery Maintainers",
            "category": "Productivity",
            "capabilities": ["Write", "Review"],
            "websiteURL": "https://example.com/waygate-product-delivery",
            "privacyPolicyURL": "https://example.com/privacy",
            "termsOfServiceURL": "https://example.com/terms",
            "defaultPrompt": [
                "启动交付",
                "启动交付，多 Agent 模式",
                "启动交付，允许降级评审",
                "查看状态",
                "验证闭包",
                "停止交付",
            ],
            "brandColor": "#2563EB",
        },
    }


def _marketplace() -> dict[str, Any]:
    return {
        "name": "repo-local",
        "interface": {
            "displayName": "Repo Local",
        },
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {
                    "source": "local",
                    "path": f"./plugins/{PLUGIN_NAME}",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }
        ],
    }


def _write_templates(templates_dir: Path) -> None:
    templates = {
        "product-brief.md": "# Product Brief\n\nStatus: Draft\n",
        "version-scope.md": "# Version Scope\n\nStatus: Draft\n",
        "ui-prototype-review.md": "# UI Prototype Review\n\nStatus: Draft\n",
        "non-ui-behavior-contract.md": "# Non-UI Behavior Contract\n\nStatus: Draft\n",
        "test-coverage-audit.md": "# Test Coverage Audit\n\nStatus: Draft\n",
        "handoff.md": "# Codex Goal Handoff\n\nStatus: Draft\n",
        "closure-artifact-template.json": json.dumps(
            {
                "status": "passed",
                "passed": True,
                "canonical_validator": CANONICAL_VALIDATOR,
                "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
                "plugin_version": PLUGIN_VERSION,
                "closure_flag": "version-feature-closure-passed",
                "latest_test_case": "TC-V008-001",
                "matrix_range": "TC-V008-001..TC-V008-001",
                "e2e_covered_tc": [],
                "covered_user_stories": [],
                "covered_journeys": [],
                "artifact_root": ".product-delivery/artifacts",
                "artifact_generation_command": "product-delivery formal-closure",
                "e2e_evidence_paths": [],
                "full_stack_browser_evidence": {
                    "required_for_ui_journeys": True,
                    "evidence_strength": "full_stack_browser_e2e",
                    "role_accurate_required": True,
                    "ordinary_path_required": True,
                    "independent_execution_segments_required": True,
                    "probe_artifact_paths": [],
                    "actor_identity_evidence": [],
                    "execution_segment_ids": [],
                    "business_api_mock_findings": [],
                },
                "prototype_conformance": {
                    "prototype_revision": "",
                    "prototype_sha256": "",
                    "prototype_contract_sha256": "",
                    "prototype_screenshot_set_sha256": "",
                    "conformance_evidence_sha256": "",
                    "conformance_artifact_sha256": "",
                    "ui_conformance_review_sha256": "",
                    "covered_surface_ids": [],
                    "covered_region_ids": [],
                },
                "high_risk_gate_subresults": {},
                "negative_scope_guard_result": "passed",
                "required_commands": [
                    {
                        "command": "PYTHONPATH=src python3 -m unittest discover -s tests",
                        "exit_code": 0,
                        "output": "Ran tests successfully",
                    }
                ],
                "supporting_validators": [
                    {
                        "name": "target-specific validator",
                        "status": "supporting_only",
                        "result_artifact": "",
                    }
                ],
                "secret_values_recorded": False,
                "controller_session_modified": False,
                "created_fake_controller_state": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "coverage-matrix-template.json": json.dumps(
            {
                "matrix_range": "TC-V008-001..TC-V008-001",
                "latest_test_case": "TC-V008-001",
                "rows": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "negative-scope-guard-checklist.md": (
            "# Negative Scope Guard Checklist\n\n"
            "- Confirm out-of-scope navigation is absent.\n"
            "- Confirm future-version actions are absent.\n"
            "- Confirm unsupported behavior is rejected.\n"
        ),
        "startup-checklist.md": (
            "# Product Delivery Startup Checklist\n\n"
            "- Invoke `superpowers:using-superpowers` before any task action.\n"
            "- Invoke `planning-with-files` and run its session catchup.\n"
            "- Read or create `task_plan.md`, `findings.md`, and `progress.md`.\n"
            "- Create or recover `.product-delivery/state.json`.\n"
            "- Record the current feature slug and blocked gates in state.\n"
            "- Plain startup enters `authorization_pending` and asks for a mode immediately.\n"
            "- `启动交付，多 Agent 模式` authorizes spawned subagents for structured review gates in the current delivery.\n"
        ),
        "required-skills-checklist.md": _required_skills_checklist(),
        "open-spec-gate.md": (
            "# Open Spec Gate\n\n"
            "- The current feature must have `docs/open-spec/<feature-slug>/`.\n"
            "- The package must contain `00-change-request.md` through `08-stage-handoff.md`.\n"
            "- Older feature packages do not satisfy the current feature gate.\n"
            "- Implementation is blocked until this gate passes.\n"
        ),
        "ui-prototype-gate.md": (
            "# UI Prototype Gate\n\n"
            "- UI projects require a local 1:1 HTML prototype for the current feature.\n"
            "- Expected path: `docs/prototypes/<feature-slug>-prototype.html`.\n"
            "- Alternative path: `.product-delivery/artifacts/<feature-slug>-prototype.html`.\n"
            "- Use `ui-ux-pro-max` for prototype review and `webapp-testing` for browser verification.\n"
            "- Record `ui_change_type`: `incremental_existing_surface`, "
            "`new_surface_in_existing_product`, `greenfield_ui`, or `non_ui`.\n"
            "- Incremental existing-surface UI must include `baseline_feature_slug`, "
            "`baseline_surface_paths`, `baseline_user_journey`, `continuity_mapping`, "
            "and `prototype_delta_summary`.\n"
            "- New surfaces must include meaningful `new_surface_justification` and "
            "explicit user confirmation; generic justifications do not satisfy this gate.\n"
            "- Implementation is blocked until the user explicitly confirms the prototype through `confirm_ui_prototype`.\n"
        ),
        "ui-prototype-contract.json": json.dumps(
            {
                "contract_version": "v1",
                "prototype_screenshot_paths": [],
                "surfaces": [
                    {
                        "surface_id": "",
                        "route": "",
                        "state_id": "",
                        "required_viewports": ["desktop"],
                        "critical_regions": [],
                        "critical_relationships": [],
                        "critical_interactions": [],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "prototype-production-conformance.md": (
            "# Prototype Production Conformance\n\n"
            "- status: draft\n"
            "- prototype_revision:\n"
            "- prototype_contract_hash:\n"
            "- evidence_sha256:\n"
            "- covered_surface_ids: []\n"
            "- covered_state_ids: []\n"
            "- covered_region_ids: []\n\n"
            "Each record binds a current full-stack Browser E2E segment, viewport PNG, "
            "controlled semantic snapshot, production route/component provenance, "
            "and complete observations.\n"
        ),
        "scope-scenario-matrix.md": (
            "# Scope Scenario Matrix\n\n"
            "`scope` means version boundary and scenario mapping. It does not mean "
            "a monitored sample run had a demand-boundary-control failure.\n\n"
            "| Scenario | Role | Story | Journey ID | Journey | Acceptance Anchors | Path | Risk | Blocking | Review | Boundary | Planned Behavior Evidence / Tests |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        ),
        "multi-agent-scenario-review.md": (
            "# Multi-Agent Scenario Review\n\n"
            "- review_type: scenario\n"
            "- review_mode: spawned_subagents | role_simulation | blocked_with_reason\n"
            "- role_simulation_user_accepted: false\n"
            "- status: draft\n"
            "- reviewers: product intent, UI/UX scenario, negative boundary\n"
            "- independent_positions: []\n"
            "- cross_challenges: []\n"
            "- revisions: []\n"
            "- final_adjudication:\n"
            "- baseline_inheritance_review: {}\n"
            "- ui_continuity_findings: []\n"
            "- blocking_findings: []\n"
            "\nFor incremental existing-surface UI, `baseline_inheritance_review` must prove "
            "the scenario inherits the previous real entry path and does not replace it "
            "with a parallel page.\n"
        ),
        "multi-agent-test-review.md": (
            "# Multi-Agent Test Review\n\n"
            "- review_type: test\n"
            "- review_mode: spawned_subagents | role_simulation | blocked_with_reason\n"
            "- role_simulation_user_accepted: false\n"
            "- status: draft\n"
            "- reviewers: test strategy, UI E2E, negative boundary\n"
            "- independent_positions: []\n"
            "- cross_challenges: []\n"
            "- revisions: []\n"
            "- final_adjudication:\n"
            "- blocking_findings: []\n"
        ),
        "multi-agent-test-coverage-review.md": (
            "# Multi-Agent Test Coverage Review\n\n"
            "- review_type: test_coverage\n"
            "- review_mode: spawned_subagents | role_simulation | blocked_with_reason\n"
            "- status: draft\n"
            "- traceability_reviewed: [US, J, SC, AC, TASK, TC]\n"
            "- coverage_gaps: []\n"
            "- title_overbreadth_findings: []\n"
            "- missing_executable_assertions: []\n"
            "- false_positive_risks: []\n\n"
            "- role_journey_coverage: []\n"
            "- ordinary_path_coverage: []\n"
            "- scenario_granularity_findings: []\n\n"
            "## Collection Coverage\n\n"
            "| collection_id | required_items | covered_items | item_level_assertions |\n"
            "| --- | --- | --- | --- |\n\n"
            "This gate reviews test case coverage range before implementation. "
            "It must prove every UI journey has the required actor role, ordinary entry path, "
            "and scenario granularity before implementation starts. "
            "Scenario review, prototype review, and generic test review cannot replace it.\n"
        ),
        "multi-agent-test-implementation-review.md": (
            "# Multi-Agent Test Implementation Review\n\n"
            "- review_type: test_implementation\n"
            "- review_mode: spawned_subagents | role_simulation | blocked_with_reason\n"
            "- status: draft\n"
            "- actual_test_code_paths: []\n"
            "- execution_evidence_paths: []\n"
            "- reviewed_test_ids: []\n"
            "- verified_action_assertions: []\n"
            "- false_positive_risks: []\n"
            "- supporting_evidence_only: []\n"
            "- business_api_mock_findings: []\n\n"
            "- actor_role_findings: []\n"
            "- evidence_distribution_findings: []\n"
            "- annotation_only_findings: []\n"
            "- ordinary_path_findings: []\n\n"
            "This gate reviews the actual test code, Playwright/browser scripts, "
            "logs, screenshots, and traces after implementation. Marker existence, "
            "function-name checks, static explanation panels, and first-button-only "
            "checks are false-positive risks. Business API route mocks must be "
            "recorded as structured findings and cannot close UI journey coverage "
            "unless a structured exemption explicitly allows closure. The review must "
            "cover every planned test id and every planned action assertion, not a sample.\n"
        ),
        "multi-agent-ui-conformance-review.md": (
            "# Multi-Agent UI Conformance Review\n\n"
            "- review_type: ui_conformance\n"
            "- review_mode: spawned_subagents | role_simulation | blocked_with_reason\n"
            "- status: draft\n"
            "- reviewed_surface_ids: []\n"
            "- reviewed_state_ids: []\n"
            "- reviewed_region_ids: []\n"
            "- structural_findings: []\n"
            "- visual_findings: []\n"
            "- interaction_findings: []\n"
            "- legacy_reuse_findings: []\n"
            "- unmapped_regions: []\n"
            "- blocking_findings: []\n\n"
            "Review every frozen surface, state, region, relationship, and interaction "
            "against production PNG and controlled semantic snapshot evidence.\n"
        ),
        "user-confirmation.md": (
            "# User Confirmation\n\n"
            "- confirmation_id:\n"
            "- target:\n"
            "- artifact_path:\n"
            "- artifact_version:\n"
            "- artifact_hash:\n"
            "- confirmed_by: user\n"
            "- confirmation_source: chat_user_reply\n"
            "- confirmed_at:\n"
            "- decision: approved\n"
            "- user_message:\n"
        ),
        "planned-e2e-obligations.md": (
            "# Planned E2E Obligations\n\n"
            "- feature_slug:\n"
            "- artifact_version:\n"
            "- generated_at:\n\n"
            "| obligation_id | scenario_id | test_id | user_story | journey | required_actor_roles | path_kind | ordinary_entry_path | data_state_contract | baseline_entry_path | visible_exception | test_layer | semantic_assertions | coverage_items | action_assertions | false_positive_guards | exemption_status |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        ),
        "executed-browser-evidence.md": (
            "# Executed Browser Evidence\n\n"
            "- feature_slug:\n"
            "- artifact_version:\n"
            "- generated_at:\n\n"
            "| test_id | obligation_id | evidence_strength | primary_actor_role | executed_actor_roles | ordinary_path_observed | execution_segment_id | test_title_or_step | acceptance_url | api_health_url | api_health_identity | business_api_requests | mocked_routes | evidence_path | evidence_sha256 | probe_artifact_path | probe_artifact_sha256 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        ),
        "closure-validator-result.md": (
            "# Closure Validator Result\n\n"
            "- status: not_run\n"
            "- validator: product_delivery_agent.finalization\n"
            "- canonical_schema_version: v0.11\n"
            f"- plugin_version: {PLUGIN_VERSION}\n"
            "- feature_slug:\n"
            "- errors: []\n"
        ),
        "implementation-goal.md": (
            "# Implementation Goal\n\n"
            "- status: active\n"
            "- objective:\n"
            "- current_task_cursor:\n\n"
            "## Stop Rules\n\n"
            "- 不要在 TASK 未完成时停止。\n"
            "- closure validator 未通过时不要 complete goal。\n"
            "- closure 失败时 goal 保持 active，下一步是修复 closure evidence。\n"
        ),
        "implementation-launch-authorization.md": (
            "# Implementation Launch Authorization\n\n"
            "- status: draft\n"
            "- feature_slug:\n"
            "- launch_package_hash:\n"
            "- nonce:\n"
            "- authorization_source: runtime_auto\n"
            "- authorized_by: runtime\n"
            "- review_modes:\n"
            "- prototype_hash:\n"
            "- planned_e2e_hash:\n"
            "- task_queue_hash:\n"
            "- required_commands_hash:\n\n"
            "Only canonical runtime implementation_launch_authorization can enter "
            "implementation. This is an internal evidence artifact, not a user "
            "confirmation gate.\n"
        ),
        "task-queue.md": (
            "# Task Queue\n\n"
            "| task_id | title | verification | status |\n"
            "| --- | --- | --- | --- |\n"
        ),
        "stop-guard-result.md": (
            "# Stop Guard Result\n\n"
            "- status: not_run\n"
            "- reason:\n"
            "- remaining_tasks:\n"
            "  - None\n"
        ),
    }
    for filename, content in templates.items():
        (templates_dir / filename).write_text(content, encoding="utf-8")


def _skill_markdown() -> str:
    return (
        "---\n"
        f"name: {PLUGIN_NAME}\n"
        "description: Codex-native product delivery workflow.\n"
        "---\n\n"
        "# Product Delivery Agent\n\n"
        "默认休眠。说 `启动交付` 激活当前项目的产品交付模式，并立即进入 "
        "`authorization_pending` 等待模式选择；说 `启动交付，多 Agent 模式` "
        "显式授权当前 delivery 在结构化 review gate 自动启动 2–3 个独立 subagents；"
        "只有在真实 subagents 不可用时，才使用 `启动交付，允许降级评审` "
        "显式允许 role_simulation 弱证据；"
        "说 `停止交付` 或使用 `stop` 退出干预。底层命令仍保留 "
        "`start` / `stop`。\n\n"
        "## Active Mode Hard Rules\n\n"
        "启动后必须创建或恢复 `.product-delivery/state.json`，并把它作为当前项目的权威状态。"
        "聊天总结、旧版本文档和 `progress.md` 都不能替代 gate evidence。\n\n"
        "active mode 下必须先使用这些 baseline skills："
        "`superpowers:using-superpowers`、`planning-with-files`、`waygate-product-delivery`。"
        "`planning-with-files` 必须执行 session catchup，并读取或创建 "
        "`task_plan.md`、`findings.md`、`progress.md`。\n\n"
        "## Blocking Gates\n\n"
        "禁止实现，直到以下门禁全部满足：\n\n"
        "1. 当前 feature slug 已写入 `.product-delivery/state.json`。\n"
        "2. 当前 feature 已使用 `open-spec` 生成 `docs/open-spec/<feature-slug>/`，"
        "包含 `00-change-request.md` 到 `08-stage-handoff.md`。\n"
        "3. 项目类型已经确认。UI 项目必须进入本地 1:1 HTML 原型 gate；"
        "非 UI 项目必须进入 behavior contract gate。\n"
        "4. UI 项目必须使用 `ui-ux-pro-max` 评审原型，并使用 `webapp-testing` "
        "做浏览器验证；没有当前 feature 的 HTML 原型确认前禁止实现。\n"
        "5. 测试覆盖审计必须使用 `test-strategy` 或 `testing-strategy`。\n"
        "6. closure 必须使用 `open-spec-feature-closure` 和 "
        "`superpowers:verification-before-completion`。\n\n"
        "禁止实现的条件：未完成 combined requirements freeze + planned E2E 确认、"
        "未确认 prototype、未冻结 planned E2E obligations、或 closure validator 未通过。"
        "实现前只能冻结 planned E2E，真实 browser evidence 必须在实现后落盘并校验。\n\n"
        "V1.0.3 强制两道状态机出口：pre-handoff gate 和 pre-closure gate。"
        "pre-handoff 通过前禁止开始实现；pre-closure 和 closure validator "
        "通过前禁止声明完成。\n\n"
        "UI 项目未显式确认本地 1:1 HTML prototype 前禁止实现。"
        "截图、Playwright evidence、static review 只能作为辅助证据，不能替代用户确认；"
        "必须通过 `confirm_ui_prototype` 写入 `ui_prototype.confirmed_by_user=true` "
        "和 user confirmation artifact。prototype 每次修订后都必须重新确认；"
        "用户反馈导致 prototype 文件、截图或 review evidence 变化时，旧 confirmation 自动失效。"
        "`confirm_ui_prototype` 只能确认当前 pending confirmation 的 artifact hash、"
        "prototype revision 和 nonce；裸 `继续` 不能替代当前版本确认。\n\n"
        "V1.0.14 起，UI prototype review 必须声明 `ui_change_type`。"
        "默认增量 UI 是 `incremental_existing_surface`，必须记录上一版 feature、"
        "baseline surface paths、baseline user journey、continuity mapping 和 prototype delta summary。"
        "增量 UI 不得用独立工作台或平行新页面替代上一版真实主路径。"
        "`new_surface_in_existing_product` 和 `greenfield_ui` 只有在记录有意义的 "
        "`new_surface_justification` 且有显式用户确认时才允许作为例外。"
        "用户反馈或已有 prototype revision 后，旧 prototype confirmation、scenario/test review、"
        "planned E2E confirmation 和实现授权必须 stale；重新 review 前不得进入实现。\n\n"
        "多 agent scenario/test review 必须落成结构化 artifact，包含 independent positions、"
        "cross challenges、revisions、final adjudication 和 blocking findings。"
        "session log、Open Spec 摘要、quick review 不能替代这些 artifact。\n\n"
        "planned E2E、executed browser evidence、coverage audit 和 closure artifact "
        "必须按 `scenario_id`、`obligation_id`、`test_id`、user story、journey 对账；"
        "UI planned E2E obligation 必须记录 `baseline_entry_path`，测试必须从上一版真实入口进入；"
        "supporting evidence 不能替代 UI journey browser E2E。"
        "V1.0.13 起，UI journey closure 只接受 `full_stack_browser_e2e`。"
        "`mocked_api_browser_e2e` 和 `static_or_prototype_browser_check` 只能作为 supporting evidence，"
        "除非有结构化豁免允许 closure。executed browser evidence 必须记录 acceptance URL、"
        "API health identity、network probe artifact、business API request summary 和 `mocked_routes`；"
        "未豁免 business API mock 必须阻塞 closure。\n\n"
        "V1.0.15 起，UI journey closure 还必须是 role-accurate、ordinary-path、"
        "independently verifiable evidence。UI planned E2E obligation 必须记录 "
        "`required_actor_roles`、`path_kind`、`ordinary_entry_path` 和 `data_state_contract`。"
        "executed browser evidence 必须记录 `executed_actor_roles`、`primary_actor_role`、"
        "`actor_identity_evidence`、`ordinary_path_observed`、`execution_segment_id` 和 "
        "`test_title_or_step`。Teacher 主路径不能由 admin browser E2E 关闭；"
        "主路径、可见异常和权限拒绝必须有可定位、可失败的独立 execution segment。"
        "API/Go/Vitest 等 supporting evidence 可以证明后端行为，但不能替代 "
        "role-accurate Browser E2E。\n\n"
        "V1.0.16 起，prototype confirmation 必须冻结 canonical `prototype_contract`、"
        "prototype HTML hash 和 prototype PNG screenshot set hash。实现与 full-stack Browser E2E "
        "完成后，必须调用 `record_prototype_production_conformance`，为每个冻结 surface/state/viewport "
        "记录 production PNG、controlled semantic snapshot、region/relationship/interaction observation "
        "和 execution segment 绑定，并声明 production route/component provenance。"
        "`.txt`、HTML、JSON、伪 PNG、路径逃逸或被修改的证据必须 fail closed。"
        "formal closure 前还必须有独立 `ui_conformance` multi-agent review，完整覆盖所有冻结 region；"
        "`test_implementation` 不能替代它。closure schema `v0.11` 必须绑定 prototype、contract、"
        "production conformance 和 UI conformance review hashes。\n\n"
        "用户面对的确认只保留两次：`ui_prototype` 原型确认，以及 "
        "combined requirements freeze + planned E2E coverage 确认。后者必须一次写入 "
        "`open_spec_freeze` 需求范围和 `planned_e2e_obligations` 测试用例覆盖情况"
        "两个 canonical state fact；legacy 单独记录 API 只用于兼容旧调用。"
        "`handoff`、coverage/review 接受、`implementation_launch_authorization`、"
        "closure 等都是内部 evidence/gate；满足条件后必须自动推进，"
        "不得要求额外用户确认。\n\n"
        "V1.0.9 起，测试审查拆成两个不可互相替代的 gate。"
        "实现授权前必须通过 `multi_agent_test_coverage_review`，评审对象是测试用例覆盖范围，"
        "必须检查 `US/J/SC/AC/TASK/TC` 映射，并把集合型场景展开到 item-level coverage。"
        "例如二级工作台 tab、三级详情入口、人员维护、模板、Agent 规则、绑定、供应商、"
        "白名单、告警忽略等，必须看到每一项的 action assertion。"
        "实现和 E2E 运行后、formal closure 前必须通过 `multi_agent_test_implementation_review`，"
        "评审对象是真实测试代码、Playwright/browser 脚本、执行日志、截图和 trace。"
        "`marker exists`、函数名存在、静态说明面板、只点第一个按钮，都必须标记为 false-positive risk。"
        "如果发现 Playwright、MSW、service worker、fetch/XHR patch 或 fixture server mock 了当前 journey "
        "依赖的 business API，却仍声称覆盖 UI journey，必须作为 blocking finding，"
        "并记录在 `business_api_mock_findings`。"
        "V1.0.15 起，`multi_agent_test_coverage_review` 必须记录 "
        "`role_journey_coverage`、`ordinary_path_coverage` 和 `scenario_granularity_findings`；"
        "`multi_agent_test_implementation_review` 必须记录 `actor_role_findings`、"
        "`evidence_distribution_findings`、`annotation_only_findings` 和 `ordinary_path_findings`。"
        "`reviewed_test_ids` 必须覆盖 planned test IDs，`verified_action_assertions` "
        "必须覆盖每个 planned coverage item，不能只抽样代表项或只靠 annotation 关闭场景。"
        "如果发现 coverage gap，必须先补 RED test 让当前浅实现失败，再继续修 UI 或 E2E。\n\n"
        "## Main Flow Continuation\n\n"
        "active mode 下每次准备 final summary、普通 stop guard 或交付总结前，"
        "必须先运行 Product Delivery continuation guard，并以 `.product-delivery/state.json` "
        "推导 `must_continue`、`wait_for_user`、`blocked`、`complete`。"
        "当结果是 `must_continue` 时，说明主流程已有 next gate 或 remaining TASK，"
        "如果没有 pending user confirmation、需求澄清、外部环境阻塞或连续失败阻塞，"
        "就必须继续推进下一 gate，不要用聊天总结结束当前交付主流程。\n\n"
        "`wait_for_user` 只允许用于真实用户输入点：当前 prototype 确认、"
        "combined requirements freeze + planned E2E coverage 确认、必要需求澄清、"
        "用户主动暂停或停止。"
        "`blocked` 必须说明 blocker；如果 blocker 是 `canonical_closure_plugin_version`，"
        "下一步是使用当前 installed packaged `product_delivery_agent.finalization` "
        "重新生成 canonical closure，或在启动新 feature 前显式清理/迁移旧状态。"
        "`complete` 只有在 canonical closure、feature closure 和 delivery goal 都满足当前插件规则时才成立。\n\n"
        "## Goal-Driven Closure\n\n"
        "pre-handoff 通过后必须创建 Product Delivery implementation delivery goal，"
        "目标覆盖完整 planned TASK queue、executed E2E evidence 和 formal closure。"
        "不要在 TASK 未完成时停止；每次准备停止或总结前必须检查 remaining TASK。"
        "如果还有 TASK 且没有用户确认、外部环境阻塞或连续失败阻塞，就继续执行下一 TASK。"
        "closure validator 未通过时不要 complete goal，closure 失败时 goal 保持 active，"
        "下一步必须修复 closure evidence。`progress.md` 和聊天总结不能替代 delivery goal status。\n\n"
        "final summary、stop、goal complete 前必须运行 `validate-closure-artifact.py "
        "--project-root <repo> --closure-artifact <path>`。该脚本必须非 0 fail closed，"
        "并写入 `.product-delivery/artifacts/closure-validator-result.md`。"
        "V1.0.8 起，只有调用 installed packaged `product_delivery_agent.finalization` 并写入 "
        "`closure_validation.validator=product_delivery_agent.finalization`、"
        f"`canonical_schema_version=v0.11`、`plugin_version={PLUGIN_VERSION}`、"
        "`closure_artifact_sha256`、`transition_journal` closure event 的结果才是 Product Delivery closure truth。"
        "target-specific validator、repo-local `scripts/verify/validate-closure-artifact.py`、"
        "Open Spec closure claim、聊天总结和 `progress.md` 只能作为 supporting evidence，"
        "不能解除 closure blocker。"
        "任何 closure-like 状态，包括 `closed_local_product_delivery`、`blocking_gates.closure=true`、"
        "`implementation.current_task=COMPLETE` 或 `delivery_goal.status=complete`，"
        "都必须同时满足 `closure_validation.status=passed`、`feature_closure.status=passed`、"
        "`delivery_goal.status=complete`；UI 项目还必须满足 `executed_browser_evidence.status=passed`。"
        "missing goal 在 handoff 后、implementation 中或 closure-like 状态下必须阻塞。\n\n"
        "V1.0.8 起，critical transitions 必须写入 hash-linked `transition_journal`。"
        "handoff、TASK completion、executed browser evidence、closure validation、goal complete "
        "都必须来自 canonical runtime API；手写 `.product-delivery/state.json`、批量补 TASK JSON、"
        "旧 feature closure result 或 docs 领先状态必须 fail closed。\n\n"
        "multi-agent review 必须记录 `review_mode`。`spawned_subagents` 是强证据；"
        "它只在 `execution_authorization` 对 `authorization_scope=current_delivery` 有效时可接受。"
        "授权只覆盖 scenario、test、test_coverage、test_implementation、ui_conformance "
        "结构化 review gate，不授权普通实现、文件读取或串行修复自动并行。"
        "`role_simulation` 是弱证据，"
        "只有使用 `启动交付，允许降级评审` 后才允许；"
        "`blocked_with_reason` 不能通过 handoff。\n\n"
        "进入实现前必须记录 canonical `implementation_launch_authorization`，"
        "但它是 runtime 自动授权 artifact，不是用户确认 gate。"
        "授权必须绑定当前 `feature_slug`、review mode、prototype hash、planned E2E、"
        "TASK queue、required commands 和 nonce/hash。scope、TASK、review mode、prototype "
        "或 planned E2E 改变后必须自动刷新授权并继续 handoff。\n\n"
        "custom artifact 可以作为 supporting evidence，但不能授权实现。"
        "自定义 `*-pre-handoff-gate.json`、Open Spec 总结、task artifact、prototype screenshot "
        "或磁盘 E2E JSON 都不能替代 canonical handoff、delivery goal、"
        "implementation launch authorization、executed browser evidence 或 closure validation。\n\n"
        "V1.0.18 起，如果当前 authorized launch package 与旧 `delivery_goal` 的 "
        "`launch_package_hash` 不一致，必须调用 canonical "
        "`recover_stale_launch_package()`；runtime 会归档旧 implementation package、写入 "
        "`implementation_package_superseded` transition，并仅按完全一致的 "
        "`planned_task_hash` 复用 TASK completion。禁止手改 state 或只删除 stale blocker。\n\n"
        "其他技能只能辅助，不能替代 Product Delivery 主流程。项目 `AGENTS.md`、"
        "Waygate/controller 规则仍要遵守，但不得绕过 Product Delivery 的 Open Spec、"
        "UI/非 UI gate、测试覆盖和 closure evidence。\n\n"
        "## Current Feature Evidence\n\n"
        "检查 Open Spec 或原型时必须按当前 feature slug 匹配。旧版本 "
        "`docs/open-spec/`、旧 prototype、聊天总结、`progress.md` 都不能替代当前 feature gate evidence。\n"
    )


def _required_skills_checklist() -> str:
    lines = [
        "# Required Skills Checklist",
        "",
        "| Gate | Required skills |",
        "| --- | --- |",
    ]
    for stage, requirements in STAGE_SKILLS.items():
        formatted = ", ".join(_format_skill_requirement(requirement) for requirement in requirements)
        lines.append(f"| {stage} | {formatted} |")
    optional = ", ".join(f"`{skill}`" for skill in dict.fromkeys(FILE_SKILLS.values()))
    lines.extend(
        [
            f"| file_specific_optional | {optional} |",
            "",
            "Installation checks fail closed for required skills and warn for file-specific optional skills.",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_skill_requirement(requirement: str) -> str:
    alternatives = requirement.split("|")
    if len(alternatives) == 1:
        return f"`{alternatives[0]}`"
    return " or ".join(f"`{alternative}`" for alternative in alternatives)


def _hooks_readme() -> str:
    return (
        "# Hooks\n\n"
        "V1.0 packages hook assets for future binding. Hook behavior must "
        "remain silent while inactive and must read `.product-delivery/state.json` "
        "as the source of truth when active.\n"
    )


def _validation_script() -> str:
    return (
        "#!/usr/bin/env python3\n"
        "\"\"\"Validate and record Product Delivery formal closure.\"\"\"\n\n"
        "from pathlib import Path\n"
        "import sys\n\n"
        "RUNTIME_DIR = Path(__file__).resolve().parents[1] / 'runtime'\n"
        "sys.path.insert(0, str(RUNTIME_DIR))\n\n"
        "# Canonical validator identity: product_delivery_agent.finalization\n"
        "from product_delivery_agent.finalization import run_finalize_cli\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(run_finalize_cli())\n"
    )


def _formal_gate_plan() -> str:
    return (
        "# Formal Gate Validation Plan\n\n"
        "- Read V0.11 handoff and prototype-conformance expectations from local state.\n"
        "- Validate closure artifact fields with `validate_feature_closure`.\n"
        "- Require command output evidence for all handoff-required commands.\n"
        "- Reject summary-only closure evidence.\n"
    )


def _lifecycle_policy() -> dict[str, Any]:
    return {
        "dormant_by_default": True,
        "activation_command": "start",
        "deactivation_command": "stop",
        "current_project_only": True,
        "artifact_root": ".product-delivery/",
    }


def _upgrade_policy() -> str:
    return (
        "# Upgrade Retention Policy\n\n"
        "Plugin upgrades must not delete `.product-delivery/` artifacts, "
        "state, templates, handoff files, or closure evidence. Migrations "
        "must be additive or provide an explicit rollback path.\n"
    )


def _readonly_policy() -> str:
    return (
        "# Waygate And Controller Read-Only Boundary\n\n"
        "Packaged workflow assets may read external Waygate/controller evidence "
        "when explicitly supplied, but the boundary is read-only and they "
        "must not mutate Waygate state, "
        "controller session files, or acceptance artifacts.\n"
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _copy_runtime_package(runtime_dir: Path) -> None:
    source_dir = Path(__file__).resolve().parent
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    shutil.copytree(
        source_dir,
        runtime_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def _remove_legacy_plugin_packages(root: Path) -> None:
    plugins_dir = root / "plugins"
    for plugin_name in LEGACY_PLUGIN_NAMES:
        plugin_root = plugins_dir / plugin_name
        manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if manifest.get("name") == plugin_name:
            shutil.rmtree(plugin_root)
