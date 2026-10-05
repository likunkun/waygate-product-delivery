#!/usr/bin/env python3
"""Render five illustrative timepoints; never writes any delivery state.

These are explicitly labelled UX examples, not executed delivery evidence.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from product_delivery_agent.progress_map_html import render_progress_map


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO / "docs/examples/progress-map")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    base = {
        "schema_version": "v1", "delivery_id": "illustrative-report-delivery", "feature_slug": "report-example",
        "title": "报表交付 · 五个时点演示", "objective": "管理员从现有入口导出真实数据，失败时能恢复并看见原因。",
        "current_version": "v1.2", "enabled": True, "settings_source": "delivery_override", "production_mode": "team", "project_type": "ui",
        "warnings": ["这是展示地图表达方式的演示数据，不是实际交付、批准或验收记录。"],
        "success_criteria": ["管理员可下载完整报表", "权限不足时明确拒绝", "失败后可安全重试且不会重复生成"],
        "versions": [{"id": "v1.1", "title": "已有报表入口"}, {"id": "v1.2", "title": "本次：导出与恢复"}, {"id": "v1.3", "title": "以后：定时生成"}],
        "goals": [{"id": "G1", "title": "可靠导出", "description": "完成正常操作，解释并恢复失败"}],
        "components": [{"id": "web", "title": "报表工作台", "description": "用户发起导出，查看结果与恢复入口", "goal_ids": ["G1"], "version_ids": ["v1.2"], "capability_ids": ["export-ui"]},
                       {"id": "api", "title": "导出服务", "description": "校验权限，读取真实数据，生成文件", "goal_ids": ["G1"], "version_ids": ["v1.2"], "capability_ids": ["export-api"]},
                       {"id": "schedule", "title": "定时任务", "description": "下一版本建设，不属于当前遗漏", "goal_ids": ["G1"], "version_ids": ["v1.3"], "capability_ids": ["scheduled"]}],
        "edges": [{"from": "web", "to": "api", "kind": "interface", "label": "提交导出与读取结果"}, {"from": "api", "to": "schedule", "kind": "dependency", "label": "未来复用导出能力"}],
        "capabilities": [{"id": "export-ui", "title": "发起并下载报表", "description": "从已有入口选择范围并下载结果", "goal_ids": ["G1"], "component_ids": ["web"], "version_ids": ["v1.2"], "task_ids": ["TASK-001"], "status": "planned", "milestones": {}},
                         {"id": "export-api", "title": "鉴权并生成报表", "description": "拒绝越权请求，并生成真实数据文件", "goal_ids": ["G1"], "component_ids": ["api"], "version_ids": ["v1.2"], "task_ids": ["TASK-001"], "status": "planned", "milestones": {}},
                         {"id": "scheduled", "title": "按日自动生成", "description": "以后建设，不计入本次缺口", "goal_ids": ["G1"], "component_ids": ["schedule"], "version_ids": ["v1.3"], "task_ids": [], "status": "planned", "milestones": {}}],
        "tasks": [{"task_id": "TASK-001", "title": "完成管理员导出旅程", "description": "前后端贯通当前旅程", "status": "planned", "verification": "真实用户发起导出并检查文件内容", "owner": "主线程"}],
        "current_work": {"title": "明确导出边界", "description": "先确认管理员与普通成员的行为区别", "why": "避免实现出没有明确用户边界的导出功能", "owner": "产品与架构专家", "next_action": "确认产品基线", "blockers": ["等待产品基线确认"], "unlocks": ["详细测试设计"]},
        "stages": [{"id": name, "title": title, "status": "pending"} for name, title in [("product", "产品定义"), ("architecture", "架构与版本"), ("spec", "规格与产品表面"), ("test", "测试设计"), ("implementation", "实现执行"), ("delivery", "交付准备")]],
        "remaining": [{"id": "export-ui", "title": "完整导出旅程", "reason": "尚未实现并验证", "next_action": "确认范围后设计测试并执行 TASK-001"}],
        "changes": [], "history": [], "baseline": {"initial_revision": 1, "approved_revision": None, "history_complete": True},
        "counts": {"current_capabilities": 2, "verified_capabilities": 0}, "closure": {"status": "not_run"},
    }
    titles = ["原计划", "实现中", "评审发现遗漏", "批准变更", "修复验收"]
    files = []
    model = copy.deepcopy(base)
    for index, title in enumerate(titles, 1):
        model["title"] = f"报表交付 · {title}（演示）"
        model["generated_at"] = f"2026-10-06T{9 + index:02d}:00:00+08:00"
        model["history"].append({"revision": index, "generated_at": model["generated_at"], "summary": title + "（示例记录）", "baseline_status": "approved" if index >= 4 else "draft"})
        model["stages"][0]["status"] = "completed"
        model["stages"][1]["status"] = "current" if index == 1 else "completed"
        if index >= 2:
            for row in model["stages"][2:4]:
                row["status"] = "completed"
            model["stages"][4]["status"] = "current"
            model["current_work"].update(title="完成管理员导出旅程", task_id="TASK-001", description="当前 TASK 内的前后端工作包并行，随后整合验证", why="服务可靠导出目标；接口已明确，先贯通普通使用路径", owner="前端与后端专家", blockers=[], next_action="整合并运行真实导出验证", unlocks=["失败恢复测试", "独立实现评审"], work_packages=[{"id": "WP-web", "status": "running", "agent_id": "前端专家", "role_ids": ["前端实现"]}, {"id": "WP-api", "status": "running", "agent_id": "后端专家", "role_ids": ["后端实现"]}])
            model["tasks"][0]["status"] = "working"
            model["components"][0]["current"] = True
            model["capabilities"][0].update(current=True, status="working")
        if index == 3:
            model["changes"].append({"id": "gap-retry", "kind": "review_gap", "title": "原计划未覆盖超时后的重试", "reason": "独立评审发现用户无法判断请求是否完成", "impact": "可能重复生成报表，或让用户反复等待", "owner": "主线程与测试设计专家", "next_action": "确认是否将恢复体验纳入本版本，补齐测试义务", "before": "只定义成功导出", "after": "拟加入超时提示与安全重试", "affected_ids": ["export-ui", "export-api"]})
            model["remaining"].append({"id": "retry", "title": "重试行为待决定", "reason": "评审发现范围遗漏；当前尚未批准新增行为", "next_action": "沿用产品与测试覆盖变更确认"})
            model["current_work"].update(title="核实失败恢复范围", why="这是有来源的评审补漏，当前需明确是否纳入版本", blockers=["等待范围与测试覆盖确认"], owner="主线程", next_action="展示变更前后供确认")
        if index == 4:
            model["baseline"]["approved_revision"] = 4
            model["changes"][0].update(kind="approved_change", title="恢复体验已纳入本版本（演示批准）", reason="示例中用户批准超时提示和幂等重试", next_action="补充失败恢复测试并修复当前 TASK", after="已纳入超时提示与安全重试")
            model["capabilities"].insert(2, {"id": "retry", "title": "超时提示与安全重试", "description": "新增能力有明确批准来源，并保留与原计划的差异", "goal_ids": ["G1"], "component_ids": ["web"], "version_ids": ["v1.2"], "task_ids": ["TASK-001"], "status": "working", "current": True, "milestones": {}, "gaps": ["需验证重复请求不生成重复文件"], "scenarios": [{"scenario_id": "SC-retry", "role": "管理员", "user_story": "导出超时后能安全恢复", "journey": "导出失败与恢复", "path_type": "visible_exception"}], "obligations": [{"obligation_id": "OBL-retry", "scenario_id": "SC-retry", "test_id": "TC-retry", "semantic_assertions": ["超时显示可执行的恢复动作", "重复请求返回同一份结果"], "coverage_items": ["超时提示", "幂等重试"], "status": "pending"}]})
            model["counts"]["current_capabilities"] = 3
            model["current_work"].update(title="实现已批准的恢复行为", why="补齐同一导出目标的异常路径，变更已解释并批准", blockers=[], next_action="先验证失败测试，再完成修复", owner="前后端与测试专家")
        if index == 5:
            for component in model["components"]:
                component["current"] = False
            for cap in model["capabilities"]:
                if "v1.2" in cap["version_ids"]:
                    cap.update(status="reviewed", current=False, milestones={"produced": True, "integrated": True, "verified": True, "reviewed": True, "delivered": False}, gaps=["尚需正式闭包"])
                    for obligation in cap.get("obligations", []):
                        obligation["status"] = "verified"
            model["counts"]["verified_capabilities"] = 3
            model["tasks"][0]["status"] = "verified"
            model["stages"][4]["status"] = "completed"
            model["stages"][5]["status"] = "current"
            model["current_work"].update(title="整理交付证据", description="示例中的正常与异常路径已验证并完成独立评审", why="修复验收完成后仍需正式交付闭包", owner="交付证据专家", next_action="通过既有 canonical closure 完成交付", work_packages=[], unlocks=["正式交付"])
            model["remaining"] = [{"id": "closure", "title": "正式交付闭包", "reason": "已验证和已评审仍不等于正式交付", "next_action": "运行 canonical closure"}]
        model["source_revision"] = hashlib.sha256(json.dumps(model, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        filename = f"{index:02d}.html"
        (args.output_dir / filename).write_text(render_progress_map(model, live=False), encoding="utf-8")
        files.append((filename, title))
    links = "".join(f'<li><a href="{filename}">{title}</a></li>' for filename, title in files)
    (args.output_dir / "index.html").write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>产品交付地图示例</title><style>body{font:18px/1.8 sans-serif;max-width:760px;margin:8vh auto;padding:24px;color:#183149;background:#f3f7fb}a{color:#255d94}li{padding:8px}</style><h1>同一交付的五个时点</h1><p>用于查看地图的信息表达。全部为演示数据，不是实际交付或批准证据；页面可离线打开。</p><ol>' + links + '</ol></html>', encoding="utf-8")
    print(args.output_dir / "index.html")


if __name__ == "__main__":
    main()
