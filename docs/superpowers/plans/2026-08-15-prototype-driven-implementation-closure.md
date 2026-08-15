# V1.0.28 Prototype-Driven Implementation Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every new UI implementation task consume and prove conformance to the confirmed prototype baseline before it can complete.

**Architecture:** Add a focused `implementation_baseline` domain module for immutable baseline, visual-policy, PNG comparison, task-binding, and task-conformance logic. Integrate it at product confirmation, launch-package generation, prompt rendering, and task completion while retaining existing final production conformance and grandfathering old confirmed UI deliveries.

**Tech Stack:** Python 3 standard library, unittest, existing Product Delivery JSON/hash protocols, existing PNG and semantic evidence artifacts.

---

### Task 1: Freeze implementation baseline domain

**Files:**
- Create: `src/product_delivery_agent/implementation_baseline.py`
- Create: `tests/test_prototype_implementation_closure_v1028.py`

- [ ] **Step 1: Write failing baseline and visual-policy tests**

```python
def test_builds_units_from_confirmed_bundle_runtime_checks(self):
    baseline = build_implementation_baseline(root, bundle, contract, visual_policy=None)
    self.assertEqual(baseline["status"], "ready")
    self.assertEqual(baseline["units"][0]["surface_id"], "series-management")
    self.assertEqual(baseline["visual_policy"]["critical_region_max_diff_ratio"], 0.02)

def test_policy_rejects_relaxed_thresholds_and_unknown_mask_regions(self):
    with self.assertRaises(ImplementationBaselineError):
        normalize_visual_policy({"full_surface_max_diff_ratio": 0.08}, contract)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `PYTHONPATH=src python3 -m unittest tests/test_prototype_implementation_closure_v1028.py -v`

Expected: import failure for `product_delivery_agent.implementation_baseline`.

- [ ] **Step 3: Implement canonical policy and baseline builders**

Implement `ImplementationBaselineError`, `normalize_visual_policy(policy, prototype_contract)`, and `build_implementation_baseline(project_root, canonical_bundle, prototype_contract, visual_policy=None)` as the public domain interfaces. Both builder functions return canonical dictionaries and raise `ImplementationBaselineError` for schema, reference, artifact, or policy failures.

Load the already-validated prototype semantic snapshot to attach prototype region bounds. Match contract requirements to `clean_surface.runtime_checks` and `artifact_metadata.clean_screenshots` by surface/state/viewport. Return `baseline_sha256` over the canonical body.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `PYTHONPATH=src python3 -m unittest tests/test_prototype_implementation_closure_v1028.py -v`

Expected: baseline-domain tests pass.

### Task 2: Bind the baseline to product confirmation and invalidation

**Files:**
- Modify: `src/product_delivery_agent/gatekeeper.py`
- Modify: `src/product_delivery_agent/workflow.py`
- Test: `tests/test_prototype_implementation_closure_v1028.py`

- [ ] **Step 1: Write failing workflow lifecycle tests**

```python
def test_new_ui_confirmation_writes_implementation_baseline(self):
    state = confirm_product_baseline(ready_ui_workflow(root))
    self.assertEqual(state["implementation_baseline"]["status"], "ready")
    self.assertTrue((root / ".product-delivery/artifacts/implementation-baseline.json").is_file())

def test_non_ui_and_confirmed_legacy_ui_are_not_forced_into_new_policy(self):
    self.assertEqual(non_ui_state["implementation_baseline_policy"]["status"], "not_applicable")
    self.assertFalse(implementation_baseline_required(legacy_confirmed_ui_state))
```

- [ ] **Step 2: Run lifecycle tests and verify RED**

Expected: missing policy/baseline state and workflow API.

- [ ] **Step 3: Implement lifecycle integration**

Add `implementation_baseline_policy` for new deliveries when project type is selected. Add `record_implementation_visual_policy(policy)` before product confirmation, include it in `surface_input_hash`, and write the canonical baseline during `confirm_product_baseline`. Add a helper that loads the artifact and verifies its hash before use. Product-domain invalidation must mark the baseline stale and clear task conformance; review-domain-only changes must not.

- [ ] **Step 4: Run lifecycle tests and existing confirmation/prototype suites**

Run: `PYTHONPATH=src python3 -m unittest tests/test_prototype_implementation_closure_v1028.py tests/test_layered_confirmation_v1021.py tests/test_prototype_design_workflow_v1023.py -v`

Expected: all selected tests pass.

### Task 3: Require UI task bindings and generate focused prompts

**Files:**
- Modify: `src/product_delivery_agent/delivery_goal.py`
- Modify: `src/product_delivery_agent/handoff.py`
- Modify: `src/product_delivery_agent/workflow.py`
- Test: `tests/test_prototype_implementation_closure_v1028.py`

- [ ] **Step 1: Write failing task-schema and prompt tests**

```python
def test_new_ui_explicit_task_without_binding_blocks_launch(self):
    with self.assertRaisesRegex(WorkflowError, "prototype_bindings"):
        workflow.record_implementation_launch_authorization(
            scope="Implement UI", verification_commands=["pytest"], planned_tasks=[generic_task]
        )

def test_current_task_prompt_contains_only_bound_units(self):
    prompt = state["current_task_prompt"]
    self.assertIn("series-management", prompt)
    self.assertNotIn("unrelated-settings-surface", prompt)
```

- [ ] **Step 2: Run tests and verify RED**

Expected: generic UI task is accepted and no current-task prompt exists.

- [ ] **Step 3: Extend normalized task schema and handoff rendering**

Normalize `ui_impact`, `ui_impact_reason`, and `prototype_bindings` into `planned_task_hash`. Validate binding references against the current implementation baseline. Coverage-derived UI tasks bind all baseline units; explicit queues must declare their bindings. Extend the Goal prompt with immutable prototype authority rules and baseline identity. Add `render_current_task_prompt(task, baseline)` and persist `artifacts/current-task-prompt.md` at handoff.

- [ ] **Step 4: Run prompt/task tests and handoff regression suites**

Run: `PYTHONPATH=src python3 -m unittest tests/test_prototype_implementation_closure_v1028.py tests/test_codex_goal_handoff.py tests/test_delivery_goal_task_queue.py tests/test_goal_driven_closure_v104.py -v`

Expected: all selected tests pass.

### Task 4: Validate task-level semantic and visual conformance

**Files:**
- Modify: `src/product_delivery_agent/implementation_baseline.py`
- Modify: `src/product_delivery_agent/workflow.py`
- Modify: `src/product_delivery_agent/delivery_goal.py`
- Test: `tests/test_prototype_implementation_closure_v1028.py`

- [ ] **Step 1: Write failing conformance tests**

Cover a passing record plus independent failures for route, region hierarchy/order, interaction coverage, computed style, geometry, critical-region pixel ratio, full-surface pixel ratio, missing evidence, and `environment_status=inconclusive`. Also prove that functional verification success cannot complete a prototype-bound task without passed conformance.

- [ ] **Step 2: Run tests and verify RED**

Expected: missing `record_task_prototype_conformance` and completion guard.

- [ ] **Step 3: Implement PNG comparison and task conformance**

Implement standard-library decoding for non-interlaced 8-bit RGB/RGBA PNGs with filters 0-4. Compare channel deltas using the frozen pixel threshold, calculate full-surface and region ratios, compare normalized geometry, and validate fixed computed-style maps. Add `build_task_prototype_conformance(project_root, payload, *, implementation_baseline, planned_task)` to the domain module and `ProductDeliveryWorkflow.record_task_prototype_conformance(task_id, payload)` to the workflow facade. The domain function returns canonical pass/fail/inconclusive evidence; the workflow method persists it and updates the transition journal.

Persist pass/fail/inconclusive artifacts and a canonical journal transition. Require a current `passed` record with matching baseline/task hashes before `record_task_completion`. Regenerate the current-task prompt for the next cursor.

- [ ] **Step 4: Run conformance and completion regression tests**

Run: `PYTHONPATH=src python3 -m unittest tests/test_prototype_implementation_closure_v1028.py tests/test_prototype_production_conformance_v1016.py tests/test_goal_driven_closure_v104.py tests/test_canonical_launch_v106.py -v`

Expected: all selected tests pass.

### Task 5: Prove staleness, compatibility, and launch binding

**Files:**
- Modify: `src/product_delivery_agent/workflow.py`
- Modify: `src/product_delivery_agent/gatekeeper.py`
- Test: `tests/test_prototype_implementation_closure_v1028.py`

- [ ] **Step 1: Write failing staleness tests**

Prove that baseline hash and task binding changes alter the launch hash, old task conformance cannot complete a changed task, product-domain changes stale all implementation evidence, annotation-only changes preserve it, and a reopened grandfathered UI delivery upgrades to required policy.

- [ ] **Step 2: Run tests and verify RED**

- [ ] **Step 3: Implement launch-package binding and compatibility helpers**

Include `implementation_baseline_sha256` in `_build_launch_package`. Extend invalidation and reusable-completion logic to honor baseline/task-conformance identities. Keep non-UI and untouched grandfathered UI paths byte-compatible with current task behavior.

- [ ] **Step 4: Run launch, invalidation, and compatibility suites**

Run: `PYTHONPATH=src python3 -m unittest tests/test_prototype_implementation_closure_v1028.py tests/test_launch_package_supersession_v1018.py tests/test_prototype_design_workflow_v1023.py tests/test_canonical_launch_v106.py -v`

Expected: all selected tests pass.

### Task 6: Package and release V1.0.28

**Files:**
- Modify: `src/product_delivery_agent/gatekeeper.py`
- Modify: `src/product_delivery_agent/plugin_packaging.py`
- Regenerate: `plugins/waygate-product-delivery/`
- Modify: release/docs indexes as required by existing packaging tests
- Test: `tests/test_plugin_packaging.py`

- [ ] **Step 1: Write failing packaging/version assertions**

Require manifest/runtime version `1.0.28`, the new implementation-baseline module in packaged runtime, V1.0.28 skill rules, and exact source/runtime parity.

- [ ] **Step 2: Run packaging tests and verify RED**

Run: `PYTHONPATH=src python3 -m unittest tests/test_plugin_packaging.py -v`

Expected: version/content assertions fail against `1.0.27`.

- [ ] **Step 3: Update version and regenerate package**

Set `PLUGIN_VERSION = "1.0.28"`, document the new hard rules in generated skill text, run `package_codex_plugin(repo_root)`, and refresh the manifest cachebuster using the existing release convention. Keep canonical closure schema at `v0.11`.

- [ ] **Step 4: Run full verification**

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src plugins/waygate-product-delivery/runtime
python3 plugins/waygate-product-delivery/scripts/validate-closure-artifact.py --help
git diff --check
```

Expected: all tests pass, compilation succeeds, validator help exits zero, and diff check is clean.

- [ ] **Step 5: Commit implementation**

Commit runtime/tests, then generated package/version/docs as reviewable commits. Do not commit `.codegraph`, caches, distributions, or temporary evidence.
