"""Startup and delivery-readiness guards for active product delivery mode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from product_delivery_agent.artifact_protocol import ARTIFACT_ROOT

OPEN_SPEC_STAGE_FILES = [
    "00-change-request.md",
    "01-requirements.md",
    "02-specification.md",
    "03-technical-solution.md",
    "04-storage-design.md",
    "05-development-plan.md",
    "06-test-cases.md",
    "07-release-retrospective.md",
    "08-stage-handoff.md",
]

PLANNING_FILES = ["task_plan.md", "findings.md", "progress.md"]


@dataclass(frozen=True)
class GuardResult:
    """Result for a startup or delivery-readiness check."""

    passed: bool
    missing_items: list[str]


def detect_project_type(project_root: str | Path) -> str:
    """Infer whether a project has UI surfaces that require prototype gating."""
    root = Path(project_root)
    ui_markers = [
        "index.html",
        "app.js",
        "app.jsx",
        "app.tsx",
        "main.jsx",
        "main.tsx",
        "page.tsx",
        "layout.tsx",
    ]
    for marker in ui_markers:
        if any(root.rglob(marker)):
            return "ui"

    ui_directories = [
        "web",
        "frontend",
        "components",
        "pages",
        "app",
        "assets",
    ]
    for directory in ui_directories:
        if any(path.is_dir() for path in root.rglob(directory)):
            return "ui"
    return "non_ui"


def validate_planning_files(
    project_root: str | Path,
    feature_slug: str,
) -> GuardResult:
    """Ensure planning-with-files artifacts exist and reference this feature."""
    root = Path(project_root)
    missing: list[str] = []
    for filename in PLANNING_FILES:
        path = root / filename
        if not path.is_file():
            missing.append(filename)
            continue
        content = path.read_text(encoding="utf-8")
        if feature_slug not in content:
            missing.append(f"{filename} missing feature slug {feature_slug}")
    return GuardResult(passed=not missing, missing_items=missing)


def validate_current_open_spec(
    project_root: str | Path,
    feature_slug: str,
) -> GuardResult:
    """Ensure the current feature owns a full Open Spec package."""
    package = Path(project_root) / "docs" / "open-spec" / feature_slug
    missing: list[str] = []
    if not package.is_dir():
        missing.append(f"docs/open-spec/{feature_slug}/")
        return GuardResult(passed=False, missing_items=missing)

    for filename in OPEN_SPEC_STAGE_FILES:
        if not (package / filename).is_file():
            missing.append(f"docs/open-spec/{feature_slug}/{filename}")
    return GuardResult(passed=not missing, missing_items=missing)


def validate_required_delivery_gates(
    project_root: str | Path,
    feature_slug: str,
    project_type: str,
) -> GuardResult:
    """Validate all startup gates required before implementation may begin."""
    root = Path(project_root)
    missing: list[str] = []
    missing.extend(validate_planning_files(root, feature_slug).missing_items)
    missing.extend(validate_current_open_spec(root, feature_slug).missing_items)

    if project_type == "ui":
        expected_prototype = root / "docs" / "prototypes" / f"{feature_slug}-prototype.html"
        alternate_prototype = (
            root
            / ARTIFACT_ROOT
            / "artifacts"
            / f"{feature_slug}-prototype.html"
        )
        if not expected_prototype.is_file() and not alternate_prototype.is_file():
            missing.append(f"docs/prototypes/{feature_slug}-prototype.html")
    elif project_type == "non_ui":
        contract = root / ARTIFACT_ROOT / "artifacts" / "non-ui-behavior-contract.md"
        if not contract.is_file():
            missing.append(".product-delivery/artifacts/non-ui-behavior-contract.md")
    else:
        missing.append("project_type must be ui or non_ui")

    return GuardResult(passed=not missing, missing_items=missing)
