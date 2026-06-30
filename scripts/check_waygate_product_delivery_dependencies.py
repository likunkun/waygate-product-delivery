#!/usr/bin/env python3
"""Check local skills required by the Waygate Product Delivery plugin."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from product_delivery_agent.skill_gates import FILE_SKILLS, STAGE_SKILLS


PLUGIN_SKILL_NAME = "waygate-product-delivery"
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
    args = parser.parse_args(argv)

    result = check_dependencies(plugin_root=args.plugin_root)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_human_result(result)
    return 0 if result["passed"] else 1


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


if __name__ == "__main__":
    raise SystemExit(main())
