# V1.0.39 Test Cases

Status: passed

| ID | Trace | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-039-001 | FR-001, AC-001 | Build one capture plan and run one adapter for multiple projections | Adapter invocation count is one |
| TC-039-002 | FR-001, NFR-003 | Re-ingest byte-identical capture | Idempotent, no duplicate authority |
| TC-039-003 | FR-001, NFR-003 | Reuse capture ID with changed manifest | Rejected |
| TC-039-004 | FR-002, AC-005 | Omit build/deployment/environment identity | Formal ingestion rejected |
| TC-039-005 | FR-002, AC-005 | Reference path or symlink outside staging root | Rejected |
| TC-039-006 | FR-004, NFR-001 | Raw capture includes self-reported passed status | Verdict rejected; validators decide independently |
| TC-039-007 | FR-005, AC-002 | Use iteration capture for TASK completion or closure | Rejected |
| TC-039-008 | FR-006, AC-003 | Unknown impact requests auto profile | Resolves strict |
| TC-039-009 | FR-006, AC-003 | Auth/global-shell/new-route change | Resolves strict |
| TC-039-010 | FR-006 | User requests standard downgrade | Rejected; strict upgrade accepted |
| TC-039-011 | FR-007, AC-004 | Reuse registered capture facts from another build | Rejected |
| TC-039-012 | FR-007, AC-004 | Reuse identical capture in same build | Accepted without re-running adapter |
| TC-039-013 | FR-008, AC-006 | Aggregate complete TASK slice union | Final Browser E2E projection generated |
| TC-039-014 | FR-008, AC-006 | Missing slice obligation or contract unit | Final manifest rejected |
| TC-039-015 | FR-009 | Reuse same prototype PNG across comparisons | Decoded once per process identity |
| TC-039-016 | FR-009 | Passing visual comparison | Ratio retained; heatmap omitted by default |
| TC-039-017 | FR-009 | Failing visual comparison | Diff artifact generated and bound |
| TC-039-018 | FR-010, AC-007 | Both batch review payloads valid | Two typed artifacts committed atomically |
| TC-039-019 | FR-010, AC-007 | One batch review payload invalid | Neither review recorded as passed |
| TC-039-020 | FR-011 | Record and report performance events | Counters/timings emitted, gates unchanged |
| TC-039-021 | FR-012, AC-005 | Non-empty console/network errors without exemption | Rejected |
| TC-039-022 | FR-012, AC-005 | Weak actor identity or wrong role | Rejected |
| TC-039-023 | FR-012, AC-005 | Request count differs from probe | Rejected |
| TC-039-024 | FR-012, AC-005 | Prototype origin used as production origin | Rejected |
| TC-039-025 | FR-012, AC-005 | Screenshot/semantic/trace/probe use different capture IDs | Rejected |
| TC-039-026 | FR-012, AC-005 | Business API mocked without exemption | Rejected |
| TC-039-027 | FR-013, AC-008 | Packaged capture CLI runs adapter with spaced arguments | Exact argv passed once without shell |
| TC-039-028 | NFR-004 | Non-UI delivery follows existing evidence path | Behavior unchanged |
| TC-039-029 | NFR-004 | Existing lifecycle and confirmation tests | No interface regression |
| TC-039-030 | NFR-004, AC-008 | Installed package without source PYTHONPATH | Capture/report/closure CLI smoke passes |
| TC-039-031 | FR-006, AC-003 | Build a strict closure manifest from a standard capture | Rejected; matching strict capture succeeds |
| TC-039-032 | FR-002, FR-004, AC-005 | Re-hash a manifest after forging execution identity | Deterministic capture replay rejects it |
| TC-039-033 | FR-008, AC-006 | Forge a Browser projection field while retaining capture ID | Closure replay rejects it |
| TC-039-034 | FR-008, AC-006 | Forge a production-conformance field while retaining capture ID | Closure replay rejects it |
| TC-039-035 | FR-006, AC-003 | Prepare strict after ingesting standard, then reuse the old capture | Current strict-plan binding rejects it |
| TC-039-036 | FR-012, AC-005 | Bind a formal unit to prototype origin instead of deployment origin | Ingestion rejects it |

## Browser Integration Fixture

A temporary local app exposes two states, two viewports, one actor identity, `/api/health`, and one business endpoint. Its adapter generates screenshot, semantic, trace, console/network, and probe facts in one run. Negative variants inject console failure, wrong actor, mocked business API, stale build, and missing viewport.

## Release Commands

- Focused V1.0.39 tests and security negatives.
- `PYTHONPATH=src python3 -m unittest discover -s tests`.
- Source and packaged-runtime Python compilation.
- Skill quick validation and plugin validation.
- Distribution content and installed CLI smoke.
- `git diff --check`.

## Executed Result

- Fresh source suite: 573 tests in 179.182 seconds, 0 failures, 1 default browser skip.
- Focused UI/closure/security suite: 104 tests in 49.842 seconds, 0 failures, 1 default browser skip.
- Real Chromium fixture: 1 test in 1.643 seconds from source and 1 test in 1.196 seconds from the installed cache; each sample reported one browser launch.
- Installed runtime: 51 UI/closure tests in 35.214 seconds, 0 failures, with source runtime absent from `PYTHONPATH`.
- Compile, source/package byte comparison, Skill validation, plugin validation, adapter syntax, dependency selection, dist inspection, and `git diff --check` all exited 0.
- These are single-run measured samples, not P90 claims.
