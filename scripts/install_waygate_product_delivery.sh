#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_ROOT="$ROOT/plugins/waygate-product-delivery"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
PLUGIN_REGISTRY_JSON="$(mktemp "${TMPDIR:-/tmp}/waygate-plugin-registry.XXXXXX.json")"
trap 'rm -f "$PLUGIN_REGISTRY_JSON"' EXIT

PYTHONPATH="$ROOT/src" python3 "$ROOT/scripts/check_waygate_product_delivery_dependencies.py" \
  --plugin-root "$PLUGIN_ROOT"
WAYGATE_INSTALL_PROJECT="${WAYGATE_INSTALL_PROJECT:-$PWD}" \
  PYTHONPATH="$ROOT/src" python3 -c 'import os; from product_delivery_agent.ui_visual_loop import assert_no_capture_backed_delivery; assert_no_capture_backed_delivery(os.environ["WAYGATE_INSTALL_PROJECT"])'
PYTHONPATH="$ROOT/src" python3 "$ROOT/scripts/package_waygate_product_delivery.py" >/dev/null
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" "$PLUGIN_ROOT"
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py" "$PLUGIN_ROOT"

codex plugin list --json >"$PLUGIN_REGISTRY_JSON"
if PYTHONPATH="$ROOT/src" python3 "$ROOT/scripts/check_waygate_product_delivery_dependencies.py" \
  --codex-home "$CODEX_HOME_DIR" \
  --installed-plugins-json "$PLUGIN_REGISTRY_JSON" \
  --legacy-present >/dev/null; then
  codex plugin remove product-delivery-agent@repo-local
fi

codex plugin add waygate-product-delivery@repo-local
codex plugin list --json >"$PLUGIN_REGISTRY_JSON"
PYTHONPATH="$ROOT/src" python3 "$ROOT/scripts/check_waygate_product_delivery_dependencies.py" \
  --codex-home "$CODEX_HOME_DIR" \
  --installed-plugins-json "$PLUGIN_REGISTRY_JSON" \
  --assert-plugin-selection

echo "Installed the unique enabled Waygate product-delivery plugin."
echo "Start a new Codex thread before testing the updated plugin."
