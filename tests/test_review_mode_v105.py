import unittest
import tempfile
from pathlib import Path

from product_delivery_agent.review_gates import ReviewGateError, validate_multi_agent_review
from product_delivery_agent.workflow import ProductDeliveryWorkflow


def review_payload(**overrides):
    payload = {
        "review_id": "MR-SCENARIO-001",
        "review_type": "scenario",
        "status": "passed",
        "review_mode": "spawned_subagents",
        "reviewers": ["agent-a", "agent-b"],
        "artifact_version": "scenario-review-v1",
        "independent_positions": ["A: no blocker", "B: no blocker"],
        "cross_challenges": ["A challenged B on E2E journey coverage"],
        "revisions": ["Added journey coverage"],
        "final_adjudication": "passed",
        "conclusions": ["scenario review passed"],
        "accepted_suggestions": ["add mobile journey"],
        "rejected_suggestions": [],
        "unresolved_questions": [],
        "blocking_findings": [],
    }
    payload.update(overrides)
    return payload


class ReviewModeV105Tests(unittest.TestCase):
    def test_role_simulation_requires_explicit_user_acceptance(self):
        review = review_payload(review_mode="role_simulation")

        with self.assertRaises(ReviewGateError) as caught:
            validate_multi_agent_review("scenario", review)

        self.assertIn("role_simulation", str(caught.exception))
        self.assertIn("user acceptance", str(caught.exception))

    def test_role_simulation_with_user_acceptance_is_valid_but_marked_weaker(self):
        review = review_payload(
            review_mode="role_simulation",
            role_simulation_user_accepted=True,
        )

        validate_multi_agent_review("scenario", review)

    def test_unknown_review_mode_is_rejected(self):
        review = review_payload(review_mode="quick_summary")

        with self.assertRaises(ReviewGateError) as caught:
            validate_multi_agent_review("scenario", review)

        self.assertIn("review_mode", str(caught.exception))

    def test_workflow_rejects_role_simulation_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start()

            with self.assertRaises(ReviewGateError) as caught:
                workflow.record_multi_agent_review(
                    "scenario",
                    review_payload(
                        review_mode="role_simulation",
                        role_simulation_user_accepted=True,
                    ),
                )

            self.assertIn("spawned_subagents_required", str(caught.exception))

    def test_workflow_accepts_role_simulation_when_degradation_is_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(allow_review_degradation=True)

            state = workflow.record_multi_agent_review(
                "scenario",
                review_payload(
                    review_mode="role_simulation",
                    role_simulation_user_accepted=True,
                ),
            )

            self.assertEqual(
                state["multi_agent_reviews"]["scenario"]["review_mode"],
                "role_simulation",
            )
            self.assertNotIn(
                "role_simulation_review_acceptance",
                state["user_confirmations"],
            )


if __name__ == "__main__":
    unittest.main()
