#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_ROOT="$ROOT/plugins/waygate-product-delivery"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
PLUGIN_REGISTRY_JSON="$(mktemp "${TMPDIR:-/tmp}/waygate-plugin-registry.XXXXXX.json")"
trap 'rm -f "$PLUGIN_REGISTRY_JSON"' EXIT

PYTHONPATH="$ROOT/src" python3 "$ROOT/scripts/check_waygate_product_delivery_dependencies.py" \
  --plugin-root "$PLUGIN_ROOT"
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
