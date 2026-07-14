# UI Prototype Gate

- UI projects require a local 1:1 HTML prototype for the current feature.
- Expected path: `docs/prototypes/<feature-slug>-prototype.html`.
- Alternative path: `.product-delivery/artifacts/<feature-slug>-prototype.html`.
- Use `ui-ux-pro-max` for prototype review and `webapp-testing` for browser verification.
- Record `ui_change_type`: `incremental_existing_surface`, `new_surface_in_existing_product`, `greenfield_ui`, or `non_ui`.
- Incremental existing-surface UI must include `baseline_feature_slug`, `baseline_surface_paths`, `baseline_user_journey`, `continuity_mapping`, and `prototype_delta_summary`.
- New surfaces must include meaningful `new_surface_justification`; the exception is confirmed as part of `product_baseline`, not through a third confirmation.
- Product/scenario review must pass before `prepare_product_baseline_confirmation()`.
- Detailed test design is blocked until `confirm_product_baseline()` records the requirements-and-surface baseline.
