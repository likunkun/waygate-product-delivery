"""Public production-mode controls preserve explicit authority and existing flow."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.control import ControlError, dispatch, validate_request
from product_delivery_agent.workflow import ProductDeliveryWorkflow


class TeamControlTests(unittest.TestCase):
    def test_team_start_and_review_selection_are_independent(self):
        request = validate_request({"schema_version": "v1", "action": "start", "feature_slug": "v12", "production_mode_if_created": "team"})
        self.assertEqual(request["production_mode_if_created"], "team")
        self.assertEqual(request["review_mode_if_created"], "pending_selection")

    def test_old_start_defaults_to_coordinator(self):
        request = validate_request({"schema_version": "v1", "action": "start", "feature_slug": "v12"})
        self.assertEqual(request["production_mode_if_created"], "coordinator")

    def test_invalid_production_mode_is_rejected(self):
        for value in ("automatic", None, [], True):
            with self.subTest(value=value), self.assertRaises(ControlError):
                validate_request({"schema_version": "v1", "action": "start", "feature_slug": "v12", "production_mode_if_created": value})

    def test_mode_change_requires_exact_delivery(self):
        with self.assertRaises(ControlError):
            validate_request({"schema_version": "v1", "action": "set_production_mode", "mode": "team"})

    def test_start_and_resume_retain_original_mode(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_THREAD_ID": "owner"}):
            request = {"schema_version": "v1", "action": "start", "feature_slug": "v12", "user_request": "Build a report exporter", "production_mode_if_created": "team"}
            first = dispatch(tmp, request)
            second = dispatch(tmp, {**request, "production_mode_if_created": "coordinator"})
            self.assertEqual(first["production_mode"], "team")
            self.assertEqual(second["production_mode"], "team")
            self.assertEqual(first["delivery_id"], second["delivery_id"])
            self.assertEqual(first["result"], "input_enrichment_required")

    def test_mode_switch_dry_run_leaves_state_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_THREAD_ID": "owner"}):
            wf = ProductDeliveryWorkflow(tmp)
            state = wf.start(feature_slug="v12", multi_agent_mode="spawned_subagents_authorized")
            path = Path(tmp) / ".product-delivery/state.json"
            before = path.read_bytes()
            request = {"schema_version": "v1", "action": "set_production_mode", "mode": "team", "delivery_id": state["delivery_id"]}
            result = dispatch(tmp, {**request, "dry_run": True})
            self.assertEqual(result["result"], "dry_run")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(dispatch(tmp, request)["production_mode"], "team")


if __name__ == "__main__":
    unittest.main()
