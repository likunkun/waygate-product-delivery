# Findings
- Existing linked worktree forlorn-wasp; no CodeGraph index.
- V1.1 review validators hard-code review roles, readonly permissions and 600 seconds. Production needs separate validators.
- state_write_lock protects canonical mutations; use _write_state_locked inside it.
- Host Goal observations must not be consumed repeatedly for internal calls.
- TeamRun outcomes never substitute for existing canonical gate/evidence APIs.
- Non-UI closure required a first-class `record_executed_behavior_evidence()` API; using only `record_task_executed_evidence()` left the final `executed_behavior_evidence` blocker unresolved.
- The native release exercise confirmed that UI browser evidence and non-UI CLI behavior evidence reach separate canonical state keys and artifact reports; non-UI records use their own command/output/trace contract and hash real files.
