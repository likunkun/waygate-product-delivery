// Reusable fail-closed Waygate Playwright adapter harness.
//
// Copy this file into the target project. Pass a project module with
// `--project-module <path>`. That module must export:
//
//   async function capture({ browser, plan, outputDir, writeArtifact }) {
//     return {
//       source_identity, build_identity, deployment_identity,
//       environment_identity, collector_identity, actor_identities,
//       data_state_identity, units, journey_segments
//     };
//   }
//
// Each unit and journey row must follow ui-capture-manifest.json. Use
// writeArtifact("name.ext", bytesOrText) for every referenced artifact; it
// returns the project-relative {path, sha256}. A formal closure capture should
// cover plan.required_units, not only plan.units. The project module owns
// authentication, deterministic data setup, route/interaction execution,
// task and production semantic snapshots, style/geometry extraction, trace
// capture, and API probing. Keep semantic_snapshot only as the compatibility
// reference; formal projections consume task_semantic_snapshot and
// production_semantic_snapshot separately.
// Never return passed/status verdicts: canonical Waygate validators decide gates.
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

function failClosed(message) {
  throw new Error(`Waygate capture rejected: ${message}`);
}

function requiredEnvironment(name) {
  const value = process.env[name];
  if (!value) failClosed(`missing ${name}`);
  return value;
}

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) failClosed(`missing ${name}`);
  return process.argv[index + 1];
}

function rejectVerdicts(value, location = '$') {
  const forbidden = new Set([
    'status', 'passed', 'gate_status', 'closure_status', 'authoritative_verdict',
  ]);
  if (Array.isArray(value)) {
    value.forEach((item, index) => rejectVerdicts(item, `${location}[${index}]`));
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value)) {
    if (forbidden.has(key)) failClosed(`authoritative verdict at ${location}.${key}`);
    rejectVerdicts(child, `${location}.${key}`);
  }
}

const projectRoot = process.cwd();
const planPath = requiredEnvironment('WAYGATE_CAPTURE_PLAN');
const outputDir = path.resolve(requiredEnvironment('WAYGATE_CAPTURE_OUTPUT_DIR'));
const captureRunRef = requiredEnvironment('WAYGATE_CAPTURE_RUN_ID');
const projectModulePath = path.resolve(argument('--project-module'));
const plan = JSON.parse(await fs.readFile(planPath, 'utf8'));
if (plan.schema_version !== 'capture-plan-v1' || !plan.plan_id) {
  failClosed('capture plan schema or plan_id is invalid');
}
if (!outputDir.startsWith(`${projectRoot}${path.sep}`)) {
  failClosed('output directory must be below the project root');
}
if (!projectModulePath.startsWith(`${projectRoot}${path.sep}`)) {
  failClosed('project module must be below the project root');
}
await fs.mkdir(outputDir, { recursive: true });
if ((await fs.readdir(outputDir)).length !== 0) {
  failClosed('output directory must be empty');
}

async function writeArtifact(relativeName, content) {
  if (!relativeName || path.isAbsolute(relativeName) || relativeName.split(path.sep).includes('..')) {
    failClosed(`unsafe artifact name: ${relativeName}`);
  }
  const target = path.resolve(outputDir, relativeName);
  if (!target.startsWith(`${outputDir}${path.sep}`)) {
    failClosed(`artifact escapes output directory: ${relativeName}`);
  }
  const bytes = Buffer.isBuffer(content) ? content : Buffer.from(String(content));
  await fs.mkdir(path.dirname(target), { recursive: true });
  await fs.writeFile(target, bytes);
  return {
    path: path.relative(projectRoot, target),
    sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
  };
}

const projectModule = await import(pathToFileURL(projectModulePath).href);
if (typeof projectModule.capture !== 'function') {
  failClosed('project module must export async capture(context)');
}

const browser = await chromium.launch();
try {
  const facts = await projectModule.capture({
    browser,
    plan,
    outputDir,
    writeArtifact,
    // Formal standard and strict captures must eventually cover this full set.
    requiredUnits: plan.required_units ?? [],
    selectedUnits: plan.units ?? [],
    journeys: plan.journeys ?? [],
  });
  if (!facts || typeof facts !== 'object') failClosed('capture() returned no facts');
  rejectVerdicts(facts);
  const manifest = {
    schema_version: 'capture-run-v1',
    capture_run_ref: captureRunRef,
    plan_id: plan.plan_id,
    purpose: plan.purpose,
    profile: plan.resolved_profile,
    closure_valid: plan.closure_valid,
    source_identity: facts.source_identity,
    build_identity: facts.build_identity,
    deployment_identity: facts.deployment_identity,
    environment_identity: facts.environment_identity,
    collector_identity: facts.collector_identity,
    actor_identities: facts.actor_identities,
    data_state_identity: facts.data_state_identity,
    units: facts.units,
    journey_segments: facts.journey_segments,
  };
  await fs.writeFile(
    path.join(outputDir, 'capture-manifest.json'),
    `${JSON.stringify(manifest, null, 2)}
`,
    { flag: 'wx' },
  );
} finally {
  await browser.close();
}
