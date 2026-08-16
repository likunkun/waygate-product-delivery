# Waygate Product Delivery 1.0.30 Design

Version 1.0.30 adds execution-review batching and exceptional UI pixel adjudication. Test implementation and UI conformance reviewers share one frozen snapshot, complete discovery before mutation, freeze a deduplicated finding set, batch-remediate it, and re-review once.

The existing 2% critical-region and 5% full-surface pixel thresholds remain automatic targets. A stable pixel-only failure starts two distinct remediation rounds. Only after both fail does the workflow create a pending user decision; an explicit user may adjudicate earlier. Accepted deviations are canonical, task-bound, invalidated by identity changes, and must be cited by final UI conformance review. Non-pixel failures remain fail-closed. Closure schema remains v0.11.
