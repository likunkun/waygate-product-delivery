import tempfile
import unittest
from pathlib import Path

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
    def test_record_user_confirmation_rejects_non_delivery_user_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = ProductDeliveryWorkflow(Path(tmp))
            workflow.start(execution_mode="automatic",
                multi_agent_mode="spawned_subagents_authorized")

            with self.assertRaises(WorkflowError) as caught:
                workflow.record_user_confirmation(
                    confirmation("implementation_launch_authorization")
                )

            self.assertIn("not a user confirmation gate", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
