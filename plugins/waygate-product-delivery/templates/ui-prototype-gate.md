# UI Prototype Gate

- UI projects require a local 1:1 HTML prototype for the current feature.
- Expected path: `docs/prototypes/<feature-slug>-prototype.html`.
- Alternative path: `.product-delivery/artifacts/<feature-slug>-prototype.html`.
- Use `ui-ux-pro-max` for prototype review and `webapp-testing` for browser verification.
- Record `ui_change_type`: `incremental_existing_surface`, `new_surface_in_existing_product`, `greenfield_ui`, or `non_ui`.
- Incremental existing-surface UI must include `baseline_feature_slug`, `baseline_surface_paths`, `baseline_user_journey`, `continuity_mapping`, and `prototype_delta_summary`.
- New surfaces must include meaningful `new_surface_justification`; the exception is confirmed as part of `product_baseline`, not through a third confirmation.
- After generating the prototype, call `record_ui_prototype_design_bundle()` before product/scenario review.
- `clean_surface` must bind the product HTML, prototype contract, clean PNGs, semantic snapshot, and browser checks for every required state and viewport.
- `product_context_contract` must positively cover `global_shell`, `navigation`, `visual_language`, `information_density`, `component_system`, and `responsive_behavior`.
- Review annotations belong in an independent `review_annotation_set`; the clean product page must not load review assets, overlays, annotation scripts, or an annotation query mode.
- Product guidance is allowed only as declared `intended_product_ui_callouts` bound to requirements, scenarios, triggers, lifecycle, and a contract region.
- The `prototype_design_integrity` gate verifies these objective facts. Multi-Agent review judges whether the baseline is representative, globally coherent, and justified; it cannot override a failed gate.
- Product/scenario review must pass before `prepare_product_baseline_confirmation()`.
- Product baseline preparation must present only the clean product surface and clean screenshots, never the review annotation artifact.
- Detailed test design is blocked until `confirm_product_baseline()` records the requirements-and-surface baseline.
