#!/usr/bin/env python3
"""Exercise the self-contained map through file://, with no application server."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/progress-map-browser"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    spec = importlib.util.find_spec("product_delivery_agent.progress_map_html")
    assert spec is not None, "The portable progress-map renderer is not implemented"
    from product_delivery_agent.progress_map_html import render_progress_map
    from playwright.sync_api import sync_playwright

    fixture_spec = importlib.util.spec_from_file_location("map_fixture", root / "tests/test_progress_map_html.py")
    fixture = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture)
    model = fixture.MODEL
    args.output_dir.mkdir(parents=True, exist_ok=True)
    offline = args.output_dir / "snapshot.html"
    live = args.output_dir / "live.html"
    disabled = args.output_dir / "disabled.html"
    hostile = args.output_dir / "untrusted.html"
    disabled_empty = args.output_dir / "disabled-empty.html"
    offline.write_text(render_progress_map(model, live=False), encoding="utf-8")
    live.write_text(render_progress_map(model), encoding="utf-8")
    disabled.write_text(render_progress_map(model, enabled=False), encoding="utf-8")
    disabled_empty.write_text(render_progress_map({"delivery_id": "empty-delivery", "generated_at": "2026-10-06T11:00:00+08:00", "settings_source": "project_default"}, enabled=False), encoding="utf-8")
    attack = '</script><img src=x onerror="window.pwned=true"><script>window.pwned=true</script>'
    hostile.write_text(render_progress_map({**model, "title": attack, "objective": attack, "components": [{**model["components"][0], "title": attack}]}, live=False), encoding="utf-8")
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
        errors = []
        remote = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: remote.append(request.url) if request.url.startswith(("https://", "http://")) else None)
        page.goto(offline.as_uri(), wait_until="networkidle")
        assert page.locator("#settings-source").inner_text() == "设置来源：本次交付设置"
        assert "v1.3" in page.locator("#roadmap-versions").inner_text()
        assert "批量导出" in page.locator("#roadmap-versions").inner_text()
        assert page.locator(".component").count() == 3
        assert page.locator("#stages li").count() == 6
        assert page.locator("#connectors path.edge").count() == 2
        assert "报告内容接口" in page.locator("#connectors").text_content()
        overlap = page.evaluate("""() => [...document.querySelectorAll('#connectors text')].filter(label => {
          const a = label.getBoundingClientRect();
          return [...document.querySelectorAll('.component')].some(component => {
            const b = component.getBoundingClientRect();
            return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
          });
        }).map(label => label.textContent)""")
        assert not overlap, f"Connector labels overlap components: {overlap}"
        page.screenshot(path=str(args.output_dir / "desktop.png"), full_page=True)
        checks.append("architecture, six stages, SVG interfaces and dependencies")

        page.get_by_role("button", name="仅看本版本", exact=True).click()
        assert page.locator(".component").count() == 2
        page.get_by_role("button", name="定位当前任务", exact=True).click()
        assert page.locator('[data-capability="draft"] button').first.get_attribute("aria-expanded") == "true"
        detail = page.locator('[data-capability="draft"] .capability-detail')
        assert "src/report.py" in detail.inner_text()
        assert "文件已核对" in detail.inner_text()
        assert "证据状态：当前阶段" not in detail.inner_text()
        assert "尚缺保存失败恢复验证" in detail.inner_text()
        assert detail.locator('[data-milestone="produced"]').get_attribute("data-complete") == "true"
        assert detail.locator('[data-milestone="verified"]').get_attribute("data-complete") == "false"
        assert "重启后内容完整" in detail.inner_text()
        checks.append("version filter, current-task focus, evidence and independent milestones")
        assert detail.locator('[data-scenario="scenario-recovery"]').count() == 1
        scenario = detail.locator('[data-scenario="scenario-recovery"]')
        assert "报告编辑者" in scenario.inner_text()
        assert "编辑 → 中断 → 重新打开 → 恢复内容" in scenario.inner_text()
        assert "异常路径" in scenario.inner_text()
        pending = scenario.locator('[data-obligation="obligation-recovery"]')
        assert "test-report-recovery" in pending.inner_text()
        assert "待验证" in pending.inner_text()
        assert "恢复后的正文与中断前一致" in pending.inner_text()
        assert "异常路径：中断恢复" in pending.inner_text()
        assert "测试义务未被任务覆盖" in scenario.locator('[data-obligation="obligation-empty"]').inner_text()
        assert "已验证" in scenario.locator('[data-obligation="obligation-save"]').inner_text()
        assert "场景缺少测试义务" in detail.locator('[data-scenario="scenario-unmapped"]').inner_text()
        assert "文件内容与登记哈希不一致" in detail.inner_text()
        assert "附件未嵌入此 HTML" in detail.inner_text()
        current_source = detail.locator('.source[data-status="current"]')
        assert "文件已核对" in current_source.inner_text()
        assert "附件未嵌入此 HTML" in current_source.inner_text()
        assert current_source.locator(".source-error").count() == 0
        page.screenshot(path=str(args.output_dir / "scenario-trace.png"), full_page=True)
        checks.append("scenario-to-test obligations, semantic assertions, missing/pending/verified distinction and stale source diagnostics")

        page.get_by_role("button", name="剩余差距", exact=True).click()
        assert page.locator("#remaining-view").is_visible()
        assert "失败恢复验证" in page.locator("#remaining-view").inner_text()
        page.get_by_role("button", name="查看变更", exact=True).click()
        assert "增加断点恢复" in page.locator("#changes-view").inner_text()
        assert "纳入恢复场景" in page.locator("#changes-view").inner_text()
        page.get_by_text("查看变更前后详情", exact=True).click()
        assert "手动保存报告" in page.locator(".change-before").inner_text()
        assert "自动保存报告并支持中断恢复" in page.locator(".change-after").inner_text()
        assert "相对初始基线" in page.locator("#changes-view").inner_text()
        page.screenshot(path=str(args.output_dir / "changes.png"), full_page=True)
        page.reload(wait_until="networkidle")
        assert page.locator("#changes-view").is_visible()
        assert page.get_by_role("button", name="仅看本版本", exact=True).get_attribute("aria-pressed") == "true"
        page.get_by_role("button", name="架构地图", exact=True).click()
        assert page.locator('[data-capability="draft"] button').first.get_attribute("aria-expanded") == "true"
        page.evaluate("window.scrollTo(0, 300)")
        page.wait_for_timeout(100)
        page.reload(wait_until="networkidle")
        assert page.evaluate("window.scrollY") > 100
        checks.append("remaining gaps, change history, filter/selection/view/scroll persistence")

        page.get_by_role("button", name="架构地图", exact=True).focus()
        page.keyboard.press("Enter")
        page.get_by_role("button", name="定位当前任务", exact=True).focus()
        page.keyboard.press("Enter")
        page.wait_for_function("document.activeElement.closest('[data-capability]')?.dataset.capability === 'draft'")
        checks.append("keyboard navigation and focus")

        for width in (375, 768, 1024):
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_timeout(100)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"horizontal overflow at {width}"
            assert page.locator("#current-work").is_visible()
        page.set_viewport_size({"width": 375, "height": 900})
        page.screenshot(path=str(args.output_dir / "mobile.png"), full_page=True)
        checks.append("mobile and tablet layouts without horizontal page overflow")

        page.goto(hostile.as_uri(), wait_until="networkidle")
        assert page.locator("h1").inner_text() == attack
        assert page.evaluate("window.pwned === undefined")
        assert page.locator("img").count() == 0
        checks.append("untrusted HTML remains text in title, objective and map nodes")

        page.clock.install()
        page.goto(disabled.as_uri(), wait_until="networkidle")
        assert page.locator("#disabled-message").is_visible()
        assert "自动更新已关闭" in page.locator("#disabled-message").inner_text()
        assert "2026-10-06T10:00:00+08:00" in page.locator("body").inner_text()
        assert "delivery-demo" in page.locator("body").inner_text()
        page.get_by_role("button", name="架构地图", exact=True).click()
        assert page.locator(".component").count() == 2
        page.get_by_role("button", name="查看变更", exact=True).click()
        assert "纳入恢复场景" in page.locator("#changes-view").inner_text()
        page.clock.fast_forward(60_000)
        assert "_map_refresh" not in page.url
        page.goto(disabled_empty.as_uri(), wait_until="networkidle")
        assert "empty-delivery" in page.locator("body").inner_text()
        assert "2026-10-06T11:00:00+08:00" in page.locator("body").inner_text()
        assert page.locator("#settings-source").inner_text() == "设置来源：项目默认设置"
        assert page.locator("#disabled-message").is_visible()
        page.goto(offline.as_uri(), wait_until="networkidle")
        page.clock.fast_forward(60_000)
        assert "_map_refresh" not in page.url
        checks.append("disabled maps retain content, history, identity and data time; disabled/snapshot do not refresh")

        page.goto(live.as_uri(), wait_until="networkidle")
        assert page.locator(".live-indicator").inner_text() == "实时地图 · 每 1 分钟更新"
        page.get_by_role("button", name="查看变更", exact=True).click()
        live.write_text(render_progress_map({**model, "title": "报告交付已更新"}), encoding="utf-8")
        page.clock.fast_forward(5_000)
        assert "_map_refresh" not in page.url
        assert page.locator("h1").inner_text() == model["title"]
        page.clock.fast_forward(55_000)
        page.wait_for_url("**?_map_refresh=*", timeout=5000, wait_until="networkidle")
        assert page.locator("h1").inner_text() == "报告交付已更新"
        assert page.locator("#changes-view").is_visible()
        assert page.get_by_role("button", name="仅看本版本", exact=True).get_attribute("aria-pressed") == "true"
        checks.append("live file stays unchanged after five seconds and refreshes at one minute with cachebuster and retained state")
        assert not remote, remote
        assert not errors, errors
        browser.close()

    report = {"result": "pass", "transport": "file://", "checks": checks, "console_errors": errors, "network_requests": remote}
    (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
