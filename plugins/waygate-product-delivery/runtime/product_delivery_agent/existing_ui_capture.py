"""Capture existing UI evidence from a project's Playwright Page.

Projects own authentication and fixture setup. The helper has no Playwright
dependency until a caller supplies a Page from their browser runner.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from product_delivery_agent.evidence_artifacts import sha256_file
from product_delivery_agent.existing_ui import CAPTURE_SCHEMA


_DOM_INVENTORY = r"""({ regions, controls, dynamicRegions, repeatedControls }) => {
  const controlSelector = 'a[href],button,input:not([type=hidden]),select,textarea,summary,' +
    '[role=button],[role=link],[role=checkbox],[role=radio],[role=switch],[role=tab],' +
    '[role=combobox],[role=slider],[role=menuitem],[contenteditable=true]';
  const selected = new Map([[document.body, {id: 'product-root', kind: 'region'}]]);
  const select = (id, selector, kind) => {
    const nodes = document.querySelectorAll(selector);
    if (nodes.length !== 1) throw Error(`${id} must identify exactly one rendered node`);
    if (selected.has(nodes[0])) throw Error(`${id} duplicates an existing node`);
    selected.set(nodes[0], {id, kind});
  };
  for (const [id, selector] of Object.entries(regions)) select(id, selector, 'region');
  for (const [id, selector] of Object.entries(controls)) select(id, selector, 'control');
  const role = node => node.getAttribute('role') || ({
    A: 'link', BUTTON: 'button', NAV: 'navigation', MAIN: 'main', HEADER: 'banner',
    FOOTER: 'contentinfo', ASIDE: 'complementary', SELECT: 'combobox',
    INPUT: ({checkbox: 'checkbox', radio: 'radio', range: 'slider', search: 'searchbox',
      submit: 'button', button: 'button'})[node.type] || 'textbox', TEXTAREA: 'textbox',
  })[node.tagName] || (node.matches(controlSelector) ? 'button' : 'region');
  const visible = node => {
    const style = getComputedStyle(node), box = node.getBoundingClientRect();
    return box.width > 0 && box.height > 0 && !['hidden', 'collapse'].includes(style.visibility)
      && !node.closest('[inert],[aria-hidden=true]');
  };
  const name = node => {
    const labels = node.getAttribute('aria-labelledby');
    const refs = labels?.split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' ');
    return (refs?.trim() || node.getAttribute('aria-label') ||
      Array.from(node.labels || []).map(label => label.textContent).join(' ') ||
      (node.tagName === 'INPUT' && ['button', 'submit'].includes(node.type) ? node.value : '') ||
      (node.matches(controlSelector) ? node.innerText : '') || node.getAttribute('title') || '')
      .replace(/\s+/g, ' ').trim();
  };
  const regionNodes = [...selected].filter(([, v]) => v.kind === 'region').map(([node]) => node);
  const matches = [...document.querySelectorAll(controlSelector)].filter(node =>
    visible(node) && regionNodes.some(region => region.contains(node)));
  const counts = new Map();
  const parent = node => {
    for (let p = node.parentElement; p; p = p.parentElement) if (selected.has(p)) return selected.get(p).id;
    return null;
  };
  for (const node of matches) {
    if (selected.has(node)) continue;
    // Repeated data rows share interactive patterns. Compare their control types
    // within the explicitly marked region, without comparing counts or item titles.
    const repeated = regionNodes.some(r => dynamicRegions.includes(selected.get(r).id) && r.contains(node))
      && Object.entries(repeatedControls).find(([, selector]) => node.matches(selector));
    const fingerprint = `${parent(node) || 'root'}/${role(node)}/${repeated ? repeated[0] : name(node)}`;
    const count = (counts.get(fingerprint) || 0) + 1;
    counts.set(fingerprint, count);
    if (repeated && count > 1) continue;
    selected.set(node, {id: `control/${fingerprint}/${count}`, kind: 'control', dynamicItem: Boolean(repeated)});
  }
  return [...selected].sort(([a], [b]) => a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1)
    .map(([node, entry]) => {
      const style = getComputedStyle(node);
      const dynamicText = entry.kind === 'region' && dynamicRegions.includes(entry.id);
      return {id: entry.id, kind: entry.kind, parent_id: parent(node), role: role(node),
        name: dynamicText || entry.dynamicItem ? '' : name(node), dynamic_text: dynamicText,
        visible: visible(node), enabled: !node.matches(':disabled') && !node.closest('[aria-disabled=true]'),
        layout: `${style.display}/${style.position}`};
    });
}"""


def _safe_url(url: str, *, keep_fragment: bool = False) -> str:
    uri = urlsplit(url)
    if uri.username or uri.password:
        raise ValueError("capture URLs may not include credentials")
    return urlunsplit((uri.scheme, uri.netloc, uri.path, "", uri.fragment if keep_fragment else ""))


def observe_action(page, *, action_id, control_id, control_selector,
                   outcome_selector, outcome_text, route_for_url=None, perform=None):
    """Click the real control and record an observed visible outcome and route."""
    if route_for_url is None:
        def route_for_url(url):
            return urlsplit(url).path or "/"

    before = route_for_url(page.url)
    control = page.locator(control_selector)
    if perform is None:
        control.click()
    else:
        perform(control)
    result = page.locator(outcome_selector)
    result.wait_for(state="visible")
    observed = " ".join(result.inner_text().split())
    if observed != outcome_text:
        raise ValueError(f"unexpected browser outcome for {action_id}")
    return {"id": action_id, "control_id": control_id, "before_route": before,
            "after_route": route_for_url(page.url), "outcome": observed}


def capture_unit(page, *, project_root, screenshot_path, surface_id, state_id,
                 viewport, actor_role, actor_marker, context_id, state_marker, actions,
                 regions, controls=None, dynamic_regions=(), repeated_controls=None, prototype_route=None,
                 baseline_unit=None):
    """Capture the DOM and screenshot after the caller follows the ordinary journey."""
    page.locator(actor_marker).wait_for(state="visible")
    page.locator(state_marker).wait_for(state="visible")
    if not actions or not regions or set(dynamic_regions) - set(regions):
        raise ValueError("capture requires journey observations and explicit existing regions")
    region_ids = set(regions) | set(controls or {})
    if "product-root" in region_ids or len(region_ids) != len(regions) + len(controls or {}):
        raise ValueError("regions and controls require distinct IDs other than product-root")
    root = Path(project_root).resolve()
    output = (root / screenshot_path).resolve()
    relative = output.relative_to(root / ".product-delivery" / "artifacts")
    if not relative or output.suffix != ".png":
        raise ValueError("capture screenshot must be a PNG under .product-delivery/artifacts")
    actual_url = _safe_url(page.url, keep_fragment=baseline_unit is not None)
    elements = page.evaluate(_DOM_INVENTORY, {
        "regions": regions, "controls": controls or {}, "dynamicRegions": list(dynamic_regions),
        "repeatedControls": repeated_controls or {},
    })
    dimensions = page.evaluate("() => ({width: innerWidth, height: innerHeight})")
    output.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output), scale="css", full_page=False, animations="disabled")
    if actual_url != _safe_url(page.url, keep_fragment=baseline_unit is not None):
        raise ValueError("page navigated during the browser capture")
    capture = {
        "surface_id": surface_id, "state_id": state_id, "viewport": viewport,
        "actor_role": actor_role, "context_id": context_id, "actual_url": actual_url,
        "route": prototype_route or urlsplit(actual_url).path or "/",
        "entry_route": actions[0]["before_route"], "actions": actions, "elements": elements,
        "screenshot": {"path": output.relative_to(root).as_posix(), "sha256": sha256_file(output)},
        **dimensions,
    }
    if baseline_unit is not None:
        capture["baseline_unit"] = list(baseline_unit)
    return capture


def write_capture(path, *, observations, browser_engine, build_id=None, origin=None,
                  baseline_path=None, prototype_path=None):
    """Write one capture manifest. Save the product manifest before designing."""
    product_fields = (build_id, origin)
    prototype_fields = (baseline_path, prototype_path)
    baseline = all(value is not None for value in product_fields)
    candidate = all(value is not None for value in prototype_fields)
    if not (baseline and not any(prototype_fields) or candidate and not any(product_fields)):
        raise ValueError("provide the product build and origin or the product capture and prototype")
    identity = {"origin": origin, "build_id": build_id} if baseline else {
        "baseline_sha256": sha256_file(Path(baseline_path)),
        "prototype_sha256": sha256_file(Path(prototype_path)),
    }
    manifest = {
        "schema_version": CAPTURE_SCHEMA,
        "source": "product_runtime" if baseline else "interactive_prototype",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "browser_engine": browser_engine, "observations": observations, **identity,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
