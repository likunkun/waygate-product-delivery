# Waygate Product Delivery Installation

## Deliverable Shape

The installable Codex plugin is:

```text
plugins/waygate-product-delivery/
```

The distributable archive is:

```text
dist/waygate-product-delivery-<version>.tar.gz
```

The runtime package inside the plugin remains `runtime/product_delivery_agent/`.
That is an internal Python import path, not the Codex plugin name.

## Build Package

From this repository root:

```bash
python3 scripts/package_waygate_product_delivery.py
```

This regenerates:

- `plugins/waygate-product-delivery/`
- `.agents/plugins/marketplace.json`
- `dist/waygate-product-delivery-<version>.tar.gz`

## Install Or Update Locally

Use the automated install script:

```bash
bash scripts/install_waygate_product_delivery.sh
```

The script runs:

1. package regeneration;
2. plugin validation;
3. Codex cachebuster update;
4. `codex plugin add waygate-product-delivery@repo-local`.

After installation, start a new Codex thread so Codex loads the updated plugin.

## Manual Install

If you need to run the steps manually:

```bash
python3 scripts/package_waygate_product_delivery.py
python3 /home/lichangkun/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/waygate-product-delivery
python3 /home/lichangkun/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py plugins/waygate-product-delivery
codex plugin add waygate-product-delivery@repo-local
```

## Smoke Test

Run the packaged validator without source `PYTHONPATH`:

```bash
env -u PYTHONPATH PYTHONNOUSERSITE=1 \
  python3 plugins/waygate-product-delivery/scripts/validate-closure-artifact.py --help
```

For the installed cache, replace the script path with:

```text
~/.codex/plugins/cache/repo-local/waygate-product-delivery/<installed-version>/scripts/validate-closure-artifact.py
```
