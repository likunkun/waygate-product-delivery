"""The map is a portable document, including when its input contains markup."""
import importlib.util
import json
import unittest
from html.parser import HTMLParser


MODEL = {
    "schema_version": "v1", "delivery_id": "delivery-demo", "feature_slug": "report",
    "title": "报告交付", "objective": "让用户导出可核验的报告", "current_version": "v1.2",
    "generated_at": "2026-10-06T10:00:00+08:00", "source_revision": "a" * 64,
    "enabled": True, "settings_source": "delivery_override",
    "versions": [{"id": "v1.1", "title": "历史归档"}, {"id": "v1.2", "title": "本次交付"}, {"id": "v1.3", "title": "批量导出"}],
    "goals": [{"id": "g1", "title": "可信报告", "description": "报告内容可追溯"}],
    "components": [
        {"id": "writer", "title": "报告编辑器", "description": "组织报告内容", "capability_ids": ["draft"], "version_ids": ["v1.2"], "current": True},
        {"id": "exporter", "title": "导出服务", "description": "生成最终文件", "capability_ids": ["export"], "version_ids": ["v1.2"]},
        {"id": "archive", "title": "历史归档", "description": "已交付的历史版本", "capability_ids": ["history"], "version_ids": ["v1.1"]},
    ],
    "capabilities": [
        {"id": "draft", "title": "编辑报告内容", "description": "内容变更即时保存", "component_ids": ["writer"], "version_ids": ["v1.2"], "goal_ids": ["g1"], "task_ids": ["task-1"], "status": "working", "current": True, "milestones": {"produced": True, "integrated": False, "verified": False, "reviewed": False, "delivered": False}, "gaps": ["尚缺保存失败恢复验证"], "sources": [{"path": "src/report.py", "sha256": "b" * 64, "status": "current"}]},
        {"id": "export", "title": "导出 PDF", "description": "生成可下载文件", "component_ids": ["exporter"], "version_ids": ["v1.2"], "status": "planned", "milestones": {}, "gaps": ["尚未实现"]},
        {"id": "history", "title": "检索历史报告", "component_ids": ["archive"], "version_ids": ["v1.1"], "status": "delivered", "milestones": {"produced": True, "integrated": True, "verified": True, "reviewed": True, "delivered": True}},
    ],
    "edges": [{"from": "writer", "to": "exporter", "kind": "interface", "label": "报告内容接口"}, {"from": "exporter", "to": "archive", "kind": "dependency", "label": "依赖归档索引"}],
    "current_work": {"task_id": "task-1", "title": "补齐保存失败恢复", "description": "验证中断后的内容恢复", "why": "避免编辑内容丢失", "unlocks": ["报告内容可进入集成"], "owner": "coordinator", "blockers": [], "next_action": "运行恢复场景"},
    "tasks": [{"task_id": "task-1", "title": "补齐保存失败恢复", "status": "working", "verification": "重启后内容完整"}],
    "stages": [{"id": "requirements", "title": "需求", "status": "complete"}, {"id": "design", "title": "设计", "status": "complete"}, {"id": "build", "title": "实现", "status": "current"}, {"id": "verify", "title": "验证", "status": "pending"}, {"id": "review", "title": "评审", "status": "pending"}, {"id": "delivery", "title": "交付", "status": "pending"}],
    "remaining": [{"id": "gap-1", "title": "失败恢复验证", "reason": "异常路径证据未齐", "next_action": "运行恢复场景"}],
    "changes": [{"id": "change-1", "kind": "scope", "title": "增加断点恢复", "reason": "避免内容丢失", "impact": "编辑器", "next_action": "补齐验证", "comparison": "initial", "affected_ids": ["draft"], "before": "手动保存", "after": "自动保存并恢复", "before_detail": {"id": "draft", "description": "手动保存报告"}, "after_detail": {"id": "draft", "description": "自动保存报告并支持中断恢复"}}],
    "history": [{"revision": 2, "generated_at": "2026-10-06", "summary": "纳入恢复场景", "baseline_status": "approved"}],
    "baseline": {"initial_revision": 1, "approved_revision": 2, "history_complete": True},
    "counts": {"current_capabilities": 2, "verified_capabilities": 0},
}

MODEL["capabilities"][0].update(
    scenarios=[
        {"scenario_id": "scenario-recovery", "role": "报告编辑者", "user_story": "恢复未保存的报告内容", "journey": "编辑 → 中断 → 重新打开 → 恢复内容", "path_type": "exception"},
        {"scenario_id": "scenario-unmapped", "role": "报告编辑者", "user_story": "恢复失败时保留草稿", "journey": "恢复失败 → 查看草稿", "path_type": "exception"},
    ],
    obligations=[
        {"obligation_id": "obligation-recovery", "scenario_id": "scenario-recovery", "test_id": "test-report-recovery", "user_story": "恢复未保存的报告内容", "journey": "编辑 → 中断 → 恢复", "semantic_assertions": ["恢复后的正文与中断前一致"], "coverage_items": ["异常路径：中断恢复"], "status": "pending"},
        {"obligation_id": "obligation-empty", "scenario_id": "scenario-recovery", "test_id": "test-empty-recovery", "semantic_assertions": ["空草稿不触发覆盖"], "coverage_items": [], "status": "missing"},
        {"obligation_id": "obligation-save", "scenario_id": "scenario-recovery", "test_id": "test-save", "status": "verified"},
    ],
)
MODEL["capabilities"][0]["sources"][0]["included"] = False
MODEL["capabilities"][0]["sources"].append({"path": "tests/recovery.json", "sha256": "c" * 64, "status": "stale", "included": False, "error": "文件内容与登记哈希不一致"})


class Document(HTMLParser):
    def __init__(self, value):
        super().__init__()
        self.tags = []
        self.data = []
        self.payload = ""
        self.in_payload = False
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        self.in_payload = tag == "script" and attrs.get("id") == "progress-map-data"

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_payload = False

    def handle_data(self, value):
        self.data.append(value)
        if self.in_payload:
            self.payload += value


class ProgressMapHTMLTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec("product_delivery_agent.progress_map_html")
        self.assertIsNotNone(spec, "The portable progress-map renderer is not implemented")
        from product_delivery_agent.progress_map_html import render_progress_map
        self.render = render_progress_map

    def test_untrusted_markup_cannot_break_out_of_data_or_title(self):
        hostile = '</script><script>window.pwned=true</script><img src=x onerror=alert(1)>\u2028\u2029 & "'
        page = self.render({**MODEL, "title": hostile, "objective": hostile})
        doc = Document(page)
        self.assertEqual(json.loads(doc.payload)["model"]["objective"], hostile)
        self.assertEqual(sum(tag == "script" for tag, _ in doc.tags), 2)
        self.assertFalse(any(tag == "img" for tag, _ in doc.tags))
        self.assertNotIn("\u2028", doc.payload)
        self.assertNotIn("\u2029", doc.payload)

    def test_document_needs_no_network_assets(self):
        doc = Document(self.render(MODEL))
        for tag, attrs in doc.tags:
            self.assertNotIn("src", attrs)
            if tag == "link":
                self.assertNotIn("href", attrs)
        self.assertTrue(any(tag == "html" and attrs.get("lang") == "zh-CN" for tag, attrs in doc.tags))
        self.assertTrue(any(tag == "meta" and attrs.get("name") == "viewport" for tag, attrs in doc.tags))

    def test_live_and_snapshot_refresh_modes_are_explicit(self):
        live = json.loads(Document(self.render(MODEL)).payload)
        snapshot = json.loads(Document(self.render(MODEL, live=False)).payload)
        self.assertTrue(live["live"])
        self.assertFalse(snapshot["live"])

    def test_disabled_setting_wins_over_requested_live_refresh(self):
        for model, enabled in ((MODEL, False), ({**MODEL, "enabled": False}, True)):
            with self.subTest(enabled=enabled):
                doc = Document(self.render(model, live=True, enabled=enabled))
                payload = json.loads(doc.payload)
                self.assertFalse(payload["enabled"])
                self.assertFalse(payload["live"])

    def test_minimal_model_is_a_valid_portable_document(self):
        doc = Document(self.render({}, live=False))
        self.assertEqual(json.loads(doc.payload)["model"], {})
        self.assertTrue(any(tag == "main" for tag, _ in doc.tags))


if __name__ == "__main__":
    unittest.main()
