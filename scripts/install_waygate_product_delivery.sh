#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_ROOT="$ROOT/plugins/waygate-product-delivery"

PYTHONPATH="$ROOT/src" python3 "$ROOT/scripts/check_waygate_product_delivery_dependencies.py" \
  --plugin-root "$PLUGIN_ROOT"
PYTHONPATH="$ROOT/src" python3 "$ROOT/scripts/package_waygate_product_delivery.py" >/dev/null
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" "$PLUGIN_ROOT"
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py" "$PLUGIN_ROOT"
codex plugin add waygate-product-delivery@repo-local

echo "Installed waygate-product-delivery@repo-local"
echo "Start a new Codex thread before testing the updated plugin."
