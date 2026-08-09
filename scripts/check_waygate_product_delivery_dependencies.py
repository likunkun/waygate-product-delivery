#!/usr/bin/env python3
"""Check local skills required by the Waygate Product Delivery plugin."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from product_delivery_agent.skill_gates import FILE_SKILLS, STAGE_SKILLS


PLUGIN_SKILL_NAME = "waygate-product-delivery"
PLUGIN_MARKETPLACE = "repo-local"
WAYGATE_PLUGIN_ID = f"{PLUGIN_SKILL_NAME}@{PLUGIN_MARKETPLACE}"
LEGACY_PLUGIN_NAMES = ("product-delivery-agent",)
OPTIONAL_FILE_SKILLS = tuple(dict.fromkeys(FILE_SKILLS.values()))


def _flatten_requirements(requirements: Iterable[str]) -> list[str]:
    flattened: list[str] = []
    for requirement in requirements:
        for alternative in requirement.split("|"):
            if alternative not in flattened:
                flattened.append(alternative)
    return flattened


REQUIRED_SKILL_REQUIREMENTS = tuple(
    dict.fromkeys(
        requirement
        for requirements in STAGE_SKILLS.values()
        for requirement in requirements
    )
)
REQUIRED_SKILL_NAMES = tuple(_flatten_requirements(REQUIRED_SKILL_REQUIREMENTS))


def check_plugin_selection(
    *,
    codex_home: str | Path,
    installed_plugins: dict[str, object] | None = None,
) -> dict[str, object]:
    """Verify that Waygate is the only installed product-delivery plugin.

    The config, Codex cache, and installed-plugin registry are intentionally
    checked together.  A stale cache is sufficient to make the selection
    unsafe, even if a UI listing no longer exposes the old plugin.
    """
    codex_path = Path(codex_home).expanduser()
    config_plugins = _configured_plugins(codex_path / "config.toml")
    relevant_config_ids = sorted(
        plugin_id
        for plugin_id in config_plugins
        if _is_product_delivery_plugin_id(plugin_id)
    )
    enabled_plugin_ids = sorted(
        plugin_id
        for plugin_id in relevant_config_ids
        if config_plugins[plugin_id].get("enabled") is True
    )
    legacy_config_plugin_ids = sorted(
        plugin_id
        for plugin_id in relevant_config_ids
        if _plugin_name(plugin_id) in LEGACY_PLUGIN_NAMES
    )
    legacy_enabled_plugin_ids = sorted(
        plugin_id
        for plugin_id in enabled_plugin_ids
        if _plugin_name(plugin_id) in LEGACY_PLUGIN_NAMES
    )
    cache_root = codex_path / "plugins" / "cache"
    legacy_cache_paths = sorted(
        str(path)
        for legacy_name in LEGACY_PLUGIN_NAMES
        for path in cache_root.glob(f"*/{legacy_name}")
        if path.is_dir()
    )

    registry_entries = _installed_plugin_entries(installed_plugins)
    legacy_registry_plugin_ids = sorted(
        entry["plugin_id"]
        for entry in registry_entries
        if entry["name"] in LEGACY_PLUGIN_NAMES
    )
    waygate_registry_plugin_ids = sorted(
        entry["plugin_id"]
        for entry in registry_entries
        if entry["plugin_id"] == WAYGATE_PLUGIN_ID
        and entry["installed"] is True
        and entry["enabled"] is True
    )
    waygate_registry_versions = sorted(
        str(entry["version"])
        for entry in registry_entries
        if entry["plugin_id"] == WAYGATE_PLUGIN_ID
        and entry["installed"] is True
        and entry["enabled"] is True
        and isinstance(entry["version"], str)
    )

    registry_supplied = installed_plugins is not None
    passed = (
        enabled_plugin_ids == [WAYGATE_PLUGIN_ID]
        and not legacy_config_plugin_ids
        and not legacy_cache_paths
        and not legacy_registry_plugin_ids
        and (
            not registry_supplied
            or waygate_registry_plugin_ids == [WAYGATE_PLUGIN_ID]
        )
    )
    return {
        "passed": passed,
        "enabled_plugin_ids": enabled_plugin_ids,
        "legacy_config_plugin_ids": legacy_config_plugin_ids,
        "legacy_enabled_plugin_ids": legacy_enabled_plugin_ids,
        "legacy_cache_paths": legacy_cache_paths,
        "legacy_registry_plugin_ids": legacy_registry_plugin_ids,
        "waygate_registry_plugin_ids": waygate_registry_plugin_ids,
        "waygate_registry_versions": waygate_registry_versions,
        "registry_supplied": registry_supplied,
    }


def _configured_plugins(config_path: Path) -> dict[str, dict[str, object]]:
    if not config_path.is_file():
        return {}
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    plugins = payload.get("plugins") if isinstance(payload, dict) else None
    if not isinstance(plugins, dict):
        return {}
    return {
        str(plugin_id): value
        for plugin_id, value in plugins.items()
        if isinstance(value, dict)
    }


def _installed_plugin_entries(
    installed_plugins: dict[str, object] | None,
) -> list[dict[str, object]]:
    if not isinstance(installed_plugins, dict):
        return []
    installed = installed_plugins.get("installed")
    if not isinstance(installed, list):
        return []
    entries: list[dict[str, object]] = []
    for item in installed:
        if not isinstance(item, dict):
            continue
        plugin_id = item.get("pluginId")
        name = item.get("name")
        if not isinstance(plugin_id, str) or not isinstance(name, str):
            continue
        if not _is_product_delivery_plugin_id(plugin_id):
            continue
        entries.append(
            {
                "plugin_id": plugin_id,
                "name": name,
                "installed": item.get("installed") is True,
                "enabled": item.get("enabled") is True,
                "version": item.get("version"),
            }
        )
    return entries


def _plugin_name(plugin_id: str) -> str:
    return plugin_id.split("@", 1)[0]


def _is_product_delivery_plugin_id(plugin_id: str) -> bool:
    return _plugin_name(plugin_id) in {PLUGIN_SKILL_NAME, *LEGACY_PLUGIN_NAMES}


def check_dependencies(
    *,
    plugin_root: str | Path,
    codex_home: str | Path | None = None,
    agents_home: str | Path | None = None,
) -> dict[str, object]:
    """Return dependency check details for required and optional skills."""
    plugin_path = Path(plugin_root)
    codex_path = Path(codex_home or os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    agents_path = Path(agents_home or os.environ.get("AGENTS_HOME", "~/.agents")).expanduser()

    required_results = [
        check_requirement(
            requirement,
            plugin_root=plugin_path,
            codex_home=codex_path,
            agents_home=agents_path,
        )
        for requirement in REQUIRED_SKILL_REQUIREMENTS
    ]
    optional_results = [
        check_requirement(
            skill,
            plugin_root=plugin_path,
            codex_home=codex_path,
            agents_home=agents_path,
        )
        for skill in OPTIONAL_FILE_SKILLS
    ]

    missing_required = [
        result["requirement"] for result in required_results if not result["satisfied"]
    ]
    missing_optional = [
        result["requirement"] for result in optional_results if not result["satisfied"]
    ]

    return {
        "passed": not missing_required,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "required": required_results,
        "optional": optional_results,
    }


def check_requirement(
    requirement: str,
    *,
    plugin_root: str | Path,
    codex_home: str | Path,
    agents_home: str | Path,
) -> dict[str, object]:
    """Check a single requirement, including one-of alternatives."""
    alternatives = requirement.split("|")
    checked = []
    for skill_name in alternatives:
        candidates = candidate_skill_paths(
            skill_name,
            plugin_root=Path(plugin_root),
            codex_home=Path(codex_home),
            agents_home=Path(agents_home),
        )
        for candidate in candidates:
            checked.append(str(candidate))
            if candidate.is_file():
                return {
                    "requirement": requirement,
                    "satisfied": True,
                    "matched": skill_name,
                    "path": str(candidate),
                    "checked": checked,
                }
    return {
        "requirement": requirement,
        "satisfied": False,
        "matched": None,
        "path": None,
        "checked": checked,
    }


def candidate_skill_paths(
    skill_name: str,
    *,
    plugin_root: Path,
    codex_home: Path,
    agents_home: Path,
) -> list[Path]:
    """Return possible SKILL.md locations for a named skill."""
    if skill_name == PLUGIN_SKILL_NAME:
        return [plugin_root / "skills" / PLUGIN_SKILL_NAME / "SKILL.md"]
    if skill_name.startswith("superpowers:"):
        bare_name = skill_name.split(":", 1)[1]
        return [
            codex_home / "superpowers" / "skills" / bare_name / "SKILL.md",
            agents_home / "skills" / bare_name / "SKILL.md",
        ]
    return [
        codex_home / "skills" / skill_name / "SKILL.md",
        agents_home / "skills" / skill_name / "SKILL.md",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Waygate Product Delivery local skill dependencies.",
    )
    parser.add_argument(
        "--plugin-root",
        default=str(REPO_ROOT / "plugins" / "waygate-product-delivery"),
        help="Path to the generated waygate-product-delivery plugin root.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )
    parser.add_argument(
        "--codex-home",
        default=os.environ.get("CODEX_HOME", "~/.codex"),
        help="Codex home used to inspect config and plugin cache.",
    )
    parser.add_argument(
        "--installed-plugins-json",
        help="Path to `codex plugin list --json` output for registry checks.",
    )
    parser.add_argument(
        "--legacy-present",
        action="store_true",
        help="Exit 0 only when legacy product-delivery installation evidence exists.",
    )
    parser.add_argument(
        "--assert-plugin-selection",
        action="store_true",
        help="Fail unless only enabled Waygate repo-local product-delivery remains.",
    )
    args = parser.parse_args(argv)

    if args.legacy_present and args.assert_plugin_selection:
        parser.error("--legacy-present and --assert-plugin-selection are mutually exclusive")

    installed_plugins = _load_installed_plugins(args.installed_plugins_json)
    if args.legacy_present or args.assert_plugin_selection:
        selection = check_plugin_selection(
            codex_home=args.codex_home,
            installed_plugins=installed_plugins,
        )
        legacy_present = bool(
            selection["legacy_config_plugin_ids"]
            or selection["legacy_cache_paths"]
            or selection["legacy_registry_plugin_ids"]
        )
        if args.json:
            print(json.dumps(selection, indent=2, sort_keys=True))
        else:
            _print_plugin_selection(selection)
        if args.legacy_present:
            return 0 if legacy_present else 1
        return 0 if selection["passed"] else 1

    result = check_dependencies(plugin_root=args.plugin_root)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_human_result(result)
    return 0 if result["passed"] else 1


def _load_installed_plugins(path: str | None) -> dict[str, object] | None:
    if path is None:
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise SystemExit(f"invalid installed plugin registry JSON: {path}")
    if not isinstance(payload, dict):
        raise SystemExit(f"installed plugin registry must be a JSON object: {path}")
    return payload


def _print_human_result(result: dict[str, object]) -> None:
    missing_required = result["missing_required"]
    missing_optional = result["missing_optional"]
    if missing_required:
        print("missing_required:")
        for requirement in missing_required:
            print(f"- {requirement}")
    else:
        print("missing_required: []")

    if missing_optional:
        print("missing_optional:")
        for requirement in missing_optional:
            print(f"- {requirement}")
    else:
        print("missing_optional: []")

    print("dependency_check=" + ("passed" if result["passed"] else "failed"))


def _print_plugin_selection(result: dict[str, object]) -> None:
    print("enabled_product_delivery_plugins:")
    for plugin_id in result["enabled_plugin_ids"]:
        print(f"- {plugin_id}")
    print("legacy_config_plugin_ids:")
    for plugin_id in result["legacy_config_plugin_ids"]:
        print(f"- {plugin_id}")
    print("legacy_cache_paths:")
    for path in result["legacy_cache_paths"]:
        print(f"- {path}")
    print("legacy_registry_plugin_ids:")
    for plugin_id in result["legacy_registry_plugin_ids"]:
        print(f"- {plugin_id}")
    print("waygate_enabled_versions:")
    for version in result["waygate_registry_versions"]:
        print(f"- {version}")
    print("plugin_selection=" + ("passed" if result["passed"] else "failed"))


if __name__ == "__main__":
    raise SystemExit(main())
