import tempfile
import unittest
from pathlib import Path

from product_delivery_agent.confirmation_policy import (
    confirmed_user_confirmation_targets,
)
from product_delivery_agent.workflow import ProductDeliveryWorkflow, WorkflowError


def confirmation(target):
    return {
        "confirmation_id": f"CONF-{target}",
        "target": target,
        "artifact_path": f".product-delivery/artifacts/{target}.md",
        "artifact_version": "v1",
        "confirmed_by": "user",
        "confirmation_source": "chat_user_reply",
        "confirmed_at": "2026-07-04T00:00:00+00:00",
        "decision": "approved",
        "user_message": "确认",
    }


class ConfirmationPolicyTests(unittest.TestCase):
    def test_modern_delivery_reports_only_two_formal_confirmation_targets(self):
        state = {
            "user_confirmations": {
                "product_baseline": {"decision": "approved"},
                "open_spec_freeze": {"decision": "approved"},
                "ui_prototype": {"decision": "approved"},
                "test_coverage_plan": {"decision": "approved"},
                "planned_e2e_obligations": {"decision": "approved"},
            },
            "ui_prototype": {"confirmed_by_user": True},
        }

        self.assertEqual(
            confirmed_user_confirmation_targets(state),
            ["product_baseline", "test_coverage_plan"],
        )

    def test_record_user_confirmation_rejects_non_delivery_user_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(
                multi_agent_mode="spawned_subagents_authorized")

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_user_confirmation(
                    confirmation("implementation_launch_authorization")
                )

            self.assertIn("not a user confirmation gate", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
