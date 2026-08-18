"""Tests for delivery-scoped artifact storage and identity isolation."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product_delivery_agent.artifact_store import (
    ArtifactStoreError,
    ARTIFACT_ROOT,
    compat_artifacts_dir,
    current_pointer_path,
    delivery_artifacts_dir,
    delivery_dir,
    detect_legacy_layout,
    freeze_delivery,
    legacy_unbound_dir,
    load_current_pointer,
    load_manifest,
    migrate_legacy_layout,
    validate_current_artifact_identity,
    write_artifact,
    write_artifact_bytes,
    write_current_pointer,
)

from product_delivery_agent.gatekeeper import derive_blockers

from product_delivery_agent.workflow import ProductDeliveryWorkflow


class ArtifactStoreWriteTests(unittest.TestCase):
    def test_write_artifact_creates_canonical_manifest_and_compat_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = write_artifact(
                root,
                "v0-5-5-flow-preview",
                "abc123",
                "handoff",
                "handoff.md",
                "# Codex Goal Handoff\n\nStatus: Frozen\n",
            )
            # canonical file exists
            canonical = (
                delivery_artifacts_dir(root, "v0-5-5-flow-preview", "abc123")
                / "handoff.md"
            )
            self.assertTrue(canonical.is_file())
            # identity header injected
            content = canonical.read_text("utf-8")
            self.assertIn("Delivery ID: abc123", content)
            self.assertIn("Feature Slug: v0-5-5-flow-preview", content)
            # manifest has the artifact
            manifest = load_manifest(root, "v0-5-5-flow-preview", "abc123")
            self.assertIn("handoff", manifest["artifacts"])
            self.assertEqual(
                manifest["artifacts"]["handoff"]["sha256"],
                result["sha256"],
            )
            # current.json pointer exists
            pointer = load_current_pointer(root)
            self.assertEqual(pointer["feature_slug"], "v0-5-5-flow-preview")
            self.assertEqual(pointer["delivery_id"], "abc123")
            # compat mirror exists with matching content
            compat = compat_artifacts_dir(root) / "handoff.md"
            self.assertTrue(compat.is_file())
            self.assertEqual(compat.read_text("utf-8"), content)

    def test_write_artifact_bytes_works_for_binary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
            write_artifact_bytes(
                root,
                "feature-a",
                "del-1",
                "screenshot",
                "prototype.png",
                data,
            )
            canonical = (
                delivery_artifacts_dir(root, "feature-a", "del-1")
                / "prototype.png"
            )
            self.assertTrue(canonical.is_file())
            self.assertEqual(canonical.read_bytes(), data)

    def test_write_artifact_requires_feature_and_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ArtifactStoreError):
                write_artifact(tmp, "", "x", "t", "f.md", "")

    def test_current_symlink_best_effort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(
                root, "f", "d", "handoff", "handoff.md", "# H\n"
            )
            link = root / ARTIFACT_ROOT / "current"
            if link.is_symlink():
                target = os.readlink(link)
                self.assertIn("deliveries/f/d", target)


    def test_frozen_delivery_rejects_later_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, "f", "d", "handoff", "handoff.md", "# First\n")
            freeze_delivery(root, "f", "d")
            with self.assertRaises(ArtifactStoreError):
                write_artifact(root, "f", "d", "handoff", "handoff.md", "# Changed\n")


    def test_symlink_failure_is_recorded_but_pointer_remains_authoritative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(Path, "symlink_to", side_effect=OSError("unsupported")):
                write_artifact(root, "f", "d", "handoff", "handoff.md", "# H\n")
            pointer = load_current_pointer(root)
            self.assertEqual(pointer["symlink_status"], "unsupported")
            self.assertEqual(pointer["delivery_id"], "d")

class ArtifactStoreIdentityTests(unittest.TestCase):
    def test_validate_identity_passes_when_pointer_matches_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = ProductDeliveryWorkflow(root)
            state = workflow.start(
                feature_slug="f",
                multi_agent_mode="spawned_subagents_authorized",
            )
            write_artifact(
                root,
                "f",
                state["delivery_id"],
                "handoff",
                "handoff.md",
                "# H\n",
            )
            # Persist artifact_refs/transition-equivalent state refresh.
            from product_delivery_agent.artifact_protocol import write_state
            write_state(root, state)
            blockers = validate_current_artifact_identity(root, state)
            self.assertEqual(blockers, [])

    def test_validate_identity_detects_stale_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, "v0-5", "old-id", "handoff", "handoff.md", "# H\n")
            state = {"feature_slug": "v0-5-5", "delivery_id": "new-id"}
            blockers = validate_current_artifact_identity(root, state)
            self.assertIn("stale_current_artifact_owner", blockers)
            self.assertIn("artifact_identity_mismatch", blockers)

    def test_validate_identity_detects_tampered_compat_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, "f", "d", "handoff", "handoff.md", "# H\n")
            compat = compat_artifacts_dir(root) / "handoff.md"
            compat.write_text("# TAMPERED\n", encoding="utf-8")
            state = {"feature_slug": "f", "delivery_id": "d"}
            blockers = validate_current_artifact_identity(root, state)
            self.assertIn("stale_compat_mirror:handoff", blockers)


    def test_validate_identity_detects_manifest_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, "f", "d", "handoff", "handoff.md", "# H\n")
            manifest_file = delivery_dir(root, "f", "d") / "manifest.json"
            payload = json.loads(manifest_file.read_text("utf-8"))
            payload["tampered"] = True
            manifest_file.write_text(json.dumps(payload), encoding="utf-8")
            blockers = validate_current_artifact_identity(
                root, {"feature_slug": "f", "delivery_id": "d"}
            )
            self.assertIn("artifact_identity_mismatch", blockers)


    def test_gatekeeper_fails_closed_when_compatibility_view_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, "f", "d", "handoff", "handoff.md", "# H\n")
            (compat_artifacts_dir(root) / "handoff.md").write_text(
                "# old owner\n", encoding="utf-8"
            )
            state = {
                "feature_slug": "f",
                "delivery_id": "d",
                "multi_agent_policy": {"execution_authorization": "authorized"},
            }
            blockers = derive_blockers(state, root)
            self.assertIn("artifact_identity_mismatch", blockers)

    def test_switching_current_delivery_archives_old_compatibility_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, "v0-5", "old", "handoff", "handoff.md", "# V0.5\n")
            write_artifact(root, "v0-5-5", "new", "handoff", "handoff.md", "# V0.5.5\n")
            archived = (
                root / ARTIFACT_ROOT / "history" / "old" / "compat-artifacts" / "handoff.md"
            )
            self.assertTrue(archived.is_file())
            self.assertIn("V0.5", archived.read_text("utf-8"))
            current = compat_artifacts_dir(root) / "handoff.md"
            self.assertIn("V0.5.5", current.read_text("utf-8"))

class ArtifactStoreFreezeTests(unittest.TestCase):
    def test_freeze_marks_manifest_archived_without_deleting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_artifact(root, "f", "d", "handoff", "handoff.md", "# H\n")
            result = freeze_delivery(root, "f", "d")
            self.assertTrue(result["frozen"])
            manifest = load_manifest(root, "f", "d")
            self.assertEqual(
                manifest["artifacts"]["handoff"]["artifact_status"],
                "archived",
            )
            # file still exists
            canonical = delivery_artifacts_dir(root, "f", "d") / "handoff.md"
            self.assertTrue(canonical.is_file())


class LegacyMigrationTests(unittest.TestCase):
    def test_detect_legacy_layout_reports_flat_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flat = root / ARTIFACT_ROOT / "artifacts"
            flat.mkdir(parents=True)
            (flat / "handoff.md").write_text("# old\n", encoding="utf-8")
            result = detect_legacy_layout(root)
            self.assertTrue(result["migration_required"])
            self.assertIn("handoff.md", result["legacy_files"])

    def test_migrate_copies_referenced_files_and_unbound_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flat = root / ARTIFACT_ROOT / "artifacts"
            flat.mkdir(parents=True)
            (flat / "handoff.md").write_text("# old handoff\n", encoding="utf-8")
            (flat / "mystery-file.md").write_text("# ??\n", encoding="utf-8")
            state = {
                "feature_slug": "f",
                "delivery_id": "d",
                "artifact_paths": {"handoff": "artifacts/handoff.md"},
            }
            result = migrate_legacy_layout(root, state)
            self.assertTrue(result["migrated"])
            self.assertIn("handoff.md", result["copied"])
            self.assertIn("mystery-file.md", result["unbound"])
            # original files NOT deleted
            self.assertTrue((flat / "handoff.md").is_file())
            self.assertTrue((flat / "mystery-file.md").is_file())
            # canonical copy exists
            canonical = delivery_artifacts_dir(root, "f", "d") / "handoff.md"
            self.assertTrue(canonical.is_file())
            # unbound file exists
            unbound_dir = legacy_unbound_dir(root)
            unbound_files = list(unbound_dir.rglob("mystery-file.md"))
            self.assertEqual(len(unbound_files), 1)

    def test_migrate_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flat = root / ARTIFACT_ROOT / "artifacts"
            flat.mkdir(parents=True)
            (flat / "handoff.md").write_text("# old\n", encoding="utf-8")
            state = {
                "feature_slug": "f",
                "delivery_id": "d",
                "artifact_paths": {"handoff": "artifacts/handoff.md"},
            }
            migrate_legacy_layout(root, state)
            result2 = migrate_legacy_layout(root, state)
            self.assertEqual(result2["copied"], [])

    def test_v05_evidence_survives_v055_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # V0.5 writes its handoff
            write_artifact(
                root, "v0-5", "id-v05", "handoff", "handoff.md", "# V0.5\n"
            )
            v05_content = (
                delivery_artifacts_dir(root, "v0-5", "id-v05")
                / "handoff.md"
            ).read_text("utf-8")

            # V0.5 is frozen
            freeze_delivery(root, "v0-5", "id-v05")

            # V0.5.5 writes its own handoff
            write_artifact(
                root, "v0-5-5", "id-v055", "handoff", "handoff.md", "# V0.5.5\n"
            )

            # V0.5 evidence is untouched
            v05_again = (
                delivery_artifacts_dir(root, "v0-5", "id-v05")
                / "handoff.md"
            ).read_text("utf-8")
            self.assertEqual(v05_content, v05_again)
            # current pointer now points to V0.5.5
            pointer = load_current_pointer(root)
            self.assertEqual(pointer["feature_slug"], "v0-5-5")
            self.assertEqual(pointer["delivery_id"], "id-v055")


if __name__ == "__main__":
    unittest.main()
