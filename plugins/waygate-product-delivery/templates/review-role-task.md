# Review Role Task

Generate with `workflow.prepare_review_role_tasks(review_type, input_refs)`; dispatch each reviewer seat from its matching `dispatch_briefs` entry using its canonical agent_spawn_name and full dispatch_message. Preserve the complete seat brief: its `role_tasks` and frozen `role_cards`, including each card's quality rubric and five examples. Submit the returned role_context/review_seats/role_tasks/review_briefs/dispatch_briefs with role_results through the existing review gate. Never hand-author hashes.

Review Type:
Role:
Role Version:
Seat Contract Version: 1.1.0-seat.1
Seat ID:
Seat Display Name:
Seat Role IDs:
Review Brief (required): complete generated entry for this seat
Frozen Role Cards (required): original role_cards payload
Quality Rubric (required): role_cards[].quality_rubric
Examples (required): role_cards[].examples with pass, insufficient, scope_violation, false_positive, must_block
Mission:
Current Delivery:
Feature Slug:
Project Type: ui | non_ui
Input Snapshot Hash:
Role Definition Hash:
Task Template Hash:
Task Hash:
Seat Task Hash:
Required Inputs:
Task Steps:
Required Checks:
Forbidden Actions:
Permissions: read bound inputs; return result only
Evidence Rules:
Completion Criteria:
Output Schema:
Escalation Rules:
Peer Challenge Target:
Time Limit: 600 seconds

Return check_records and completion_evidence even with no findings. Missing inputs/capabilities must be reported as blocked. Timing, retries and isolation are enforced by the host; this template is not a scheduler.
