# V1.0 Codex Plugin Packaging - 06 Test Cases

| Field | Value |
| --- | --- |
| Version | V1.0 |
| Author | Codex |
| Date | 2026-06-22 |
| Status | Draft |

## Revision History

| Revision | Date | Author | Summary | Related CR |
| --- | --- | --- | --- | --- |
| REV-20260622-01 | 2026-06-22 | Codex | Initial Open Spec package for V1.0 Codex Plugin Packaging. | CR-001 |
| REV-20260622-02 | 2026-06-22 | Codex | Add V0.10 Feature Closure packaging checks. | CR-001 |
| REV-20260622-03 | 2026-06-22 | Codex | Add asset-level package checks and lifecycle safety tests. | CR-001 |
| REV-20260622-04 | 2026-06-22 | Codex | Tighten manifest requirement and add runtime read-only boundary verification. | CR-001 |
| REV-20260622-05 | 2026-06-22 | Codex | Record runtime unit tests, full-suite evidence, and plugin validator evidence. | CR-001 |


## Test Strategy

Current tests include runtime unit coverage for repo-local plugin package generation plus full-suite regression and plugin manifest validation.
Lifecycle install/start/stop/upgrade execution against a real Codex installation remains a future integration verification obligation.

## Test Cases

| TC | Layer | Scope | Steps | Expected Result |
| --- | --- | --- | --- | --- |
| TC-V100-001 | Unit | Plugin manifest | Run `tests/test_plugin_packaging.py::PluginPackagingTests.test_package_creates_valid_plugin_manifest` and verify `.codex-plugin/plugin.json` contains valid name, version, skills path, interface metadata, and no unsupported `hooks` field. | FR-001 and TASK-001 are covered. |
| TC-V100-002 | Unit | Packaged runtime assets | Run `tests/test_plugin_packaging.py::PluginPackagingTests.test_package_includes_runtime_assets_and_v0_10_closure_assets` and verify packaged skill, hooks docs, templates, validation scripts, lifecycle policy, upgrade policy, and read-only policy are generated. | FR-001, NFR-003, and TASK-001 are covered. |
| TC-V100-003 | Unit | Marketplace config | Run `tests/test_plugin_packaging.py::PluginPackagingTests.test_repo_marketplace_config_points_to_local_plugin` and verify `.agents/plugins/marketplace.json` points to `./plugins/product-delivery-agent` with `AVAILABLE` and `ON_INSTALL`. | FR-002 and TASK-002 are covered. |
| TC-V100-004 | Unit plus future integration | Dormant install and project activation | Run `tests/test_plugin_packaging.py::PluginPackagingTests.test_lifecycle_is_dormant_by_default_and_start_stop_scoped`; future integration must install plugin locally and verify `start` activates only the current project. | FR-003, NFR-001, and TASK-003 are covered. |
| TC-V100-005 | Unit plus future integration | Stop preservation | Run lifecycle policy unit coverage for `stop`; future integration must run `stop` and verify plugin intervention exits while existing `.product-delivery/` artifacts remain. | FR-004, NFR-002, and TASK-003 are covered. |
| TC-V100-006 | Unit plus future integration | Upgrade retention | Run `tests/test_plugin_packaging.py::PluginPackagingTests.test_upgrade_policy_preserves_product_delivery_artifacts`; future integration must upgrade the plugin and verify existing `.product-delivery/` artifacts survive unchanged. | FR-005, NFR-002, and TASK-004 are covered. |
| TC-V100-007 | Unit | Closure artifact template | Run packaged asset unit coverage and verify V0.10 closure artifact template is packaged with artifact root, artifact generation command, and E2E evidence path metadata fields. | FR-006, NFR-003, and TASK-005 are covered. |
| TC-V100-008 | Unit | Coverage matrix template | Run packaged asset unit coverage and verify coverage matrix template is packaged. | FR-007, NFR-003, and TASK-006 are covered. |
| TC-V100-009 | Unit | Negative scope guard checklist | Run packaged asset unit coverage and verify negative scope guard checklist is packaged. | FR-007, NFR-003, and TASK-006 are covered. |
| TC-V100-010 | Unit | Formal gate validator | Run packaged asset unit coverage and verify `validate-closure-artifact.py` plus formal gate validation plan are packaged. | FR-008, NFR-003, and TASK-007 are covered. |
| TC-V100-011 | Unit | V0.10 dependency | Run packaged asset unit coverage and verify V0.10 closure template, coverage matrix template, and negative scope guard checklist are present as pre-packaging dependency assets. | FR-009, NFR-003, and TASK-008 are covered. |
| TC-V100-012 | Unit | Waygate/controller read-only boundary | Run `tests/test_plugin_packaging.py::PluginPackagingTests.test_waygate_controller_boundary_is_read_only` and verify plugin packaging policy forbids direct Waygate/controller state mutation. | NFR-001, NFR-002, and TASK-001..TASK-008 are covered. |
| TC-V100-013 | Future implementation verification | Runtime read-only boundary | Run install, `start`, `stop`, and upgrade flows while monitoring Waygate/controller files or state APIs; verify no direct mutation occurs and any controller evidence is read-only. | NFR-001, NFR-002, and TASK-003..TASK-004 are covered. |

## Coverage Matrix

| Requirement | NFR | TASK | TC | Evidence Type | Package Or Lifecycle Obligation |
| --- | --- | --- | --- | --- | --- |
| FR-001 | NFR-003 | TASK-001 | TC-V100-001, TC-V100-002 | Unit + plugin validator | `.codex-plugin/plugin.json` plus skill/hooks/templates/validation scripts |
| FR-002 | NFR-001 | TASK-002 | TC-V100-003 | Unit | Repo marketplace configuration |
| FR-003 | NFR-001 | TASK-003 | TC-V100-004 | Unit + future install verification | Dormant-by-default install and current-project `start` |
| FR-004 | NFR-002 | TASK-003 | TC-V100-005 | Unit + future lifecycle verification | `stop` exits intervention and preserves artifacts |
| FR-005 | NFR-002 | TASK-004 | TC-V100-006 | Unit + future upgrade verification | Upgrade preserves `.product-delivery/` |
| FR-006 | NFR-003 | TASK-005 | TC-V100-007 | Unit | Closure artifact template packaged with artifact metadata fields |
| FR-007 | NFR-003 | TASK-006 | TC-V100-008, TC-V100-009 | Unit | Coverage matrix template and negative scope guard checklist packaged |
| FR-008 | NFR-003 | TASK-007 | TC-V100-010 | Unit | Formal gate validation script and planning asset present |
| FR-009 | NFR-003 | TASK-008 | TC-V100-011 | Unit | V0.10 pre-packaging dependency |
| NFR-001 | NFR-001 | TASK-001, TASK-002, TASK-003 | TC-V100-004, TC-V100-012, TC-V100-013 | Unit + future lifecycle verification | No behavior change before explicit `start`; controller state read-only |
| NFR-002 | NFR-002 | TASK-003, TASK-004 | TC-V100-005, TC-V100-006, TC-V100-012, TC-V100-013 | Unit + future lifecycle verification | Artifact retention and no controller mutation |

## Feature Closure Package Checks

- Continuous range: `TC-V100-001..TC-V100-013`.
- Required V0.10 assets: closure artifact template with artifact metadata fields, coverage matrix template, negative scope guard checklist, and formal gate validation script planning item or asset.
- Required package assets: `.codex-plugin/plugin.json`, packaged skill, hooks, templates, validation scripts, and repo marketplace configuration.
- Lifecycle checks remain dormant-by-default with explicit `start` and `stop`.
- `start` activates only the current project, `stop` preserves artifacts, upgrades preserve `.product-delivery/`, and both document review and future runtime verification must prove Waygate/controller state remains read-only.

## Execution Record

- Runtime unit evidence: `PYTHONPATH=src python3 -m unittest tests/test_plugin_packaging.py` passes 6 tests.
- Full-suite evidence: `PYTHONPATH=src python3 -m unittest discover -s tests` passes 69 tests.
- Compile evidence: `python3 -m py_compile src/product_delivery_agent/*.py` exits 0.
- Plugin validator evidence: `python3 <plugin-creator>/scripts/validate_plugin.py plugins/product-delivery-agent` reports plugin validation passed.
- Future evidence: live Codex install/start/stop/upgrade monitoring for TC-V100-013.

## Information Gaps

| Level | Item | Impact | Disposition |
| --- | --- | --- | --- |
| Blocker | None | No blocker prevents this documentation package. | Proceed |
| Assumption | Roadmap version labels are planning labels, not release promises. | May be revisited in later version packages. | Recorded |
| Assumption | Live Codex install/start/stop/upgrade verification is outside this repo-local package generation run. | May be revisited in later version packages. | Recorded |
| Nice-to-know | Future public marketplace publication and hook installation mechanics remain deferred unless a later version explicitly scopes them. | No current blocker. | Track in later Open Spec packages |
