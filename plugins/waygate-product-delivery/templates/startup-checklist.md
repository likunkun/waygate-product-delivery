# Product Delivery Startup Checklist

- Invoke `superpowers:using-superpowers` before any task action.
- Invoke `planning-with-files` and run its session catchup.
- Read or create `task_plan.md`, `findings.md`, and `progress.md`.
- Create or recover `.product-delivery/state.json`.
- Call `inspect_startup_request(feature_slug=...)` before startup; a new feature never reuses a previous delivery authorization.
- For an active pre-v1.0.22 state with `execution_model_policy`, call `retire_model_execution_policy()`; do not edit state or restart the delivery.
- Record the current feature slug and blocked gates in state.
- Plain startup enters `multi_agent_mode_selection` and asks for the review mode immediately.
- `启动交付，多 Agent 模式` authorizes spawned subagents for structured review gates in the current delivery.
- `启动交付，允许降级评审` explicitly allows structured role simulation when subagents are unavailable.
- Draft Open Spec, scenario matrix, and the UI prototype or non-UI behavior contract before asking for product confirmation.
- Run product/scenario review, then call `prepare_product_baseline_confirmation()` and `confirm_product_baseline()`.
- Do not generate detailed test cases, planned E2E, or coverage audit before `product_baseline` is confirmed.
- After the baseline is confirmed, create planned E2E and coverage evidence, run test/test-coverage reviews, then call `prepare_test_coverage_confirmation()` and `confirm_test_coverage_plan()`.
