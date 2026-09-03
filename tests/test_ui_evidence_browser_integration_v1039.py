import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from product_delivery_agent.coverage_audit import build_executed_browser_evidence
from product_delivery_agent.ui_evidence import (
    append_performance_event,
    browser_records_from_capture_runs,
    build_capture_plan,
    build_closure_manifest,
    ingest_capture_run,
    performance_report,
    production_conformance_payload_from_capture_runs,
    run_capture_adapter,
    task_conformance_payload_from_capture_runs,
    unit_records_from_capture_runs,
)


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/health"):
            self._json({"service": "fixture-api"})
            return
        if self.path.startswith("/api/items"):
            self._json({"items": ["alpha", "beta"]})
            return
        if self.path.startswith("/api/identity"):
            role = "admin" if "admin" in self.path else "teacher"
            self._json(
                {
                    "role": role,
                    "user_id": f"{role}-1",
                    "session_id": f"session-{role}",
                }
            )
            return
        state = "detail" if "state=detail" in self.path else "default"
        body = f"""<!doctype html><html><body>
        <main aria-label="Dashboard {state}" data-state="{state}">
          <h1>Dashboard {state}</h1><button>Refresh items</button><p id="items">loading</p>
        </main><script>fetch('/api/items').then(r => r.json()).then(v =>
          document.querySelector('#items').textContent = v.items.join(','));</script>
        </body></html>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return

    def _json(self, value):
        body = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@unittest.skipUnless(
    os.environ.get("WAYGATE_RUN_BROWSER_INTEGRATION") == "1",
    "set WAYGATE_RUN_BROWSER_INTEGRATION=1 after installing project-owned Playwright",
)
class UIEvidenceBrowserIntegrationV1039Tests(unittest.TestCase):
    def test_one_real_browser_launch_feeds_all_projection_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                origin = f"http://127.0.0.1:{server.server_port}"
                units = [
                    {
                        "surface_id": "dashboard",
                        "state_id": state,
                        "viewport_class": viewport,
                    }
                    for state in ("default", "detail")
                    for viewport in ("desktop", "mobile")
                ]
                plan = build_capture_plan(
                    delivery_id="delivery-browser-integration",
                    feature_slug="v1039-browser-integration",
                    purpose="closure",
                    requested_profile="strict",
                    risk_facts={"impact_known": False, "risk_tags": ["authorization"]},
                    units=units,
                    journeys=[
                        {"obligation_id": "OBL-TEACHER", "test_id": "TC-TEACHER"},
                        {"obligation_id": "OBL-ADMIN", "test_id": "TC-ADMIN"},
                    ],
                )
                plan["fixture_origin"] = origin
                plan_path = root / "capture-plan.json"
                plan_path.write_text(json.dumps(plan), encoding="utf-8")
                adapter = root / "capture-adapter.cjs"
                adapter.write_text(_ADAPTER, encoding="utf-8")
                staging = root / ".product-delivery" / "staging" / "browser-run"
                manifest_path = run_capture_adapter(
                    project_root=root,
                    plan_path=plan_path,
                    adapter_executable="node",
                    adapter_args=[str(adapter)],
                    output_dir=staging,
                )
                delivery = (
                    root
                    / ".product-delivery"
                    / "deliveries"
                    / "v1039-browser-integration"
                    / "delivery-browser-integration"
                )
                ingested = ingest_capture_run(root, delivery, plan, manifest_path)
                append_performance_event(delivery, ingested["performance_event"])
                capture_ids = [ingested["capture_id"]]
                browser = browser_records_from_capture_runs(delivery, capture_ids)
                self.assertEqual(len(browser), 2)
                self.assertEqual(
                    {record["primary_actor_role"] for record in browser},
                    {"teacher", "admin"},
                )
                self.assertEqual(
                    build_executed_browser_evidence(root, browser)["status"],
                    "passed",
                )
                self.assertEqual(len(unit_records_from_capture_runs(delivery, capture_ids)), 4)
                task_payload = task_conformance_payload_from_capture_runs(
                    delivery,
                    capture_ids,
                    implementation_baseline={"baseline_sha256": "baseline-fixture"},
                    planned_task={
                        "planned_task_hash": "task-fixture",
                        "prototype_bindings": [
                            {
                                "surface_id": "dashboard",
                                "state_id": "default",
                                "viewport_classes": ["desktop", "mobile"],
                            }
                        ],
                    },
                )
                self.assertEqual(len(task_payload["records"]), 2)
                production_payload = production_conformance_payload_from_capture_runs(
                    delivery,
                    capture_ids,
                    canonical_prototype={"prototype_revision": "fixture-r1"},
                    prototype_contract={"contract_sha256": "contract-fixture"},
                )
                self.assertEqual(len(production_payload["records"]), 4)
                closure = build_closure_manifest(
                    delivery,
                    capture_run_ids=capture_ids,
                    required_units=units,
                    required_journeys=plan["journeys"],
                    profile="strict",
                    registry_root_sha256=ingested["registry_root_sha256"],
                )
                self.assertEqual(len(closure["covered_units"]), 4)
                report = performance_report(delivery)
                self.assertEqual(report["browser_launches"], 1)
                self.assertGreaterEqual(report["raw_artifacts"], report["unique_artifacts"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


_ADAPTER = r"""
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { chromium } = require('playwright');

const plan = JSON.parse(fs.readFileSync(process.env.WAYGATE_CAPTURE_PLAN, 'utf8'));
const outputDir = process.env.WAYGATE_CAPTURE_OUTPUT_DIR;
const root = process.cwd();
const rel = p => path.relative(root, p).replaceAll(path.sep, '/');
const write = (name, data) => {
  const target = path.join(outputDir, name);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, data);
  return { path: rel(target), sha256: crypto.createHash('sha256').update(fs.readFileSync(target)).digest('hex') };
};
const stable = value => crypto.createHash('sha256').update(JSON.stringify(value, Object.keys(value).sort())).digest('hex');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const actors = [];
  const segments = [];
  for (const role of ['teacher', 'admin']) {
    const response = await fetch(`${plan.fixture_origin}/api/identity?role=${role}`);
    const identity = await response.json();
    const backendHash = crypto.createHash('sha256').update(JSON.stringify(identity, Object.keys(identity).sort())).digest('hex');
    actors.push({ ...identity, backend_identity_sha256: backendHash });
  }
  const units = [];
  for (let index = 0; index < plan.required_units.length; index++) {
    const unit = plan.required_units[index];
    const role = index < 2 ? 'teacher' : 'admin';
    const segmentId = `${role}-dashboard`;
    const viewport = unit.viewport_class === 'mobile' ? { width: 390, height: 844 } : { width: 1280, height: 720 };
    const page = await browser.newPage({ viewport });
    const consoleErrors = [];
    const networkErrors = [];
    page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
    page.on('requestfailed', request => networkErrors.push(request.url()));
    await page.goto(`${plan.fixture_origin}/dashboard?state=${unit.state_id}`);
    await page.waitForSelector('#items:not(:empty)');
    const png = await page.screenshot();
    const screenshot = write(`unit-${index}.png`, png);
    const base = {
      surface_id: unit.surface_id, state_id: unit.state_id, route: '/dashboard',
      viewport: { class: unit.viewport_class, width: viewport.width, height: viewport.height },
      regions: [], relationships: [], interactions: [], execution_segment_id: segmentId,
      acceptance_url: `${plan.fixture_origin}/dashboard?state=${unit.state_id}`,
    };
    const taskSnapshot = write(`unit-${index}-task.json`, JSON.stringify({ ...base, schema_version: 'task-production-semantic-snapshot-v1' }));
    const productionSnapshot = write(`unit-${index}-production.json`, JSON.stringify({ ...base, schema_version: 'ui-semantic-surface-v1', production_route: '/dashboard' }));
    units.push({
      ...unit, route: '/dashboard', origin: plan.fixture_origin,
      acceptance_url: base.acceptance_url, execution_segment_id: segmentId, dpr: 1,
      console_errors: consoleErrors, network_errors: networkErrors, error_exemptions: [],
      screenshot, semantic_snapshot: productionSnapshot,
      task_semantic_snapshot: taskSnapshot, production_semantic_snapshot: productionSnapshot,
      computed_style: { comparisons: [] },
      production_component_refs: [{ path: 'capture-adapter.cjs', kind: 'integration_fixture', note: 'Owns the fixture surface' }],
      region_results: [], relationship_results: [], interaction_results: [],
    });
    await page.close();
  }
  for (const [index, role] of ['teacher', 'admin'].entries()) {
    const actor = actors[index];
    const obligation = plan.journeys[index];
    const acceptanceUrl = `${plan.fixture_origin}/dashboard?state=${index ? 'detail' : 'default'}`;
    const healthUrl = `${plan.fixture_origin}/api/health`;
    const probe = {
      capture_run_ref: process.env.WAYGATE_CAPTURE_RUN_ID,
      acceptance_url: acceptanceUrl, api_health_url: healthUrl, api_health_identity: 'fixture-api',
      health_response_status: 200, health_response_content_type: 'application/json',
      health_response_body_sample: '{"service":"fixture-api"}', actor_identity_response: {
        role: actor.role, user_id: actor.user_id, session_id: actor.session_id,
      },
      business_api_requests: [{ method: 'GET', url: `${plan.fixture_origin}/api/items`, status: 200, source: 'network' }],
    };
    const probeRef = write(`journey-${index}-probe.json`, JSON.stringify(probe));
    const traceRef = write(`journey-${index}-trace.zip`, `trace-${role}`);
    const screenshotRef = units[index * 2].screenshot;
    const evidenceRef = write(
      `journey-${index}-evidence.json`,
      JSON.stringify({ observed: true, role }),
    );
    const segmentId = `${role}-dashboard`;
    const segmentMetadata = write(
      `journey-${index}-segment.json`,
      JSON.stringify({
        schema_version: 'ui-journey-segment-metadata-v1',
        capture_run_ref: process.env.WAYGATE_CAPTURE_RUN_ID,
        execution_segment_id: segmentId,
        actor_identity_sha256: crypto.createHash('sha256').update(JSON.stringify(actor, Object.keys(actor).sort())).digest('hex'),
        screenshot_sha256: screenshotRef.sha256,
        trace_sha256: traceRef.sha256,
        evidence_sha256: evidenceRef.sha256,
        probe_sha256: probeRef.sha256,
      }),
    );
    segments.push({
      ...obligation, scenario_id: `SC-${role.toUpperCase()}`, user_story: `US-${role.toUpperCase()}`,
      journey: `${role} opens dashboard`, command: 'node capture-adapter.cjs', exit_code: 0,
      trace: traceRef, screenshot: screenshotRef,
      evidence: evidenceRef, probe: probeRef, segment_metadata: segmentMetadata,
      semantic_assertions: ['dashboard and business items are visible'], evidence_strength: 'full_stack_browser_e2e',
      acceptance_url: acceptanceUrl, api_health_url: healthUrl, api_health_identity: 'fixture-api',
      mocked_routes: [], console_errors: [], network_errors: [], executed_actor_roles: [role],
      primary_actor_role: role, actor_identity_evidence: actor, ordinary_path_observed: true,
      execution_segment_id: segmentId, test_title_or_step: `${role} opens dashboard`,
    });
  }
  await browser.close();
  const manifest = {
    schema_version: 'capture-run-v1', plan_id: plan.plan_id,
    capture_run_ref: process.env.WAYGATE_CAPTURE_RUN_ID,
    purpose: plan.purpose, profile: plan.resolved_profile, closure_valid: plan.closure_valid,
    source_identity: { tree_sha256: '1'.repeat(64), commit_sha: 'integration-commit' },
    build_identity: { build_digest: 'integration-build' },
    deployment_identity: { deployment_id: 'integration-deploy', origin: plan.fixture_origin, api_origin: plan.fixture_origin },
    environment_identity: { environment_id: 'integration', feature_flags_sha256: '2'.repeat(64), locale: 'en-US', timezone: 'UTC', reduced_motion: false },
    collector_identity: { name: 'playwright-integration', version: '1', browser_name: 'chromium', browser_version: 'project-owned', validator_version: '1.0.39' },
    actor_identities: actors, data_state_identity: { seed_id: 'integration-seed', version: '1' },
    units, journey_segments: segments,
  };
  fs.writeFileSync(path.join(outputDir, 'capture-manifest.json'), JSON.stringify(manifest, null, 2));
})().catch(error => { console.error(error); process.exit(1); });
"""


if __name__ == "__main__":
    unittest.main()
