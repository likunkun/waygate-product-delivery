"""Skill allocation and review gate policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class SkillGateError(RuntimeError):
    """Raised when a required skill gate is not satisfied."""


@dataclass(frozen=True)
class SkillGateResult:
    stage: str
    required_skills: list[str]
    used_skills: list[str]
    missing_skills: list[str]
    passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "required_skills": self.required_skills,
            "used_skills": self.used_skills,
            "missing_skills": self.missing_skills,
            "passed": self.passed,
        }


STAGE_SKILLS: dict[str, tuple[str, ...]] = {
    "active_mode_startup": (
        "superpowers:using-superpowers",
        "planning-with-files",
        "waygate-product-delivery",
    ),
    "agent_startup": ("superpowers:using-superpowers",),
    "long_running_recovery": ("planning-with-files",),
    "open_spec_planning": ("open-spec",),
    "product_blueprint": ("superpowers:brainstorming",),
    "version_scope": ("superpowers:brainstorming",),
    "version_plan": ("superpowers:writing-plans",),
    "implementation_plan": ("superpowers:writing-plans",),
    "test_coverage_audit": ("test-strategy|testing-strategy",),
    "ui_prototype_confirmation": ("ui-ux-pro-max",),
    "webapp_verification": ("webapp-testing",),
    "pre_handoff_verification": ("superpowers:verification-before-completion",),
    "implementation": (
        "superpowers:test-driven-development",
        "superpowers:executing-plans|superpowers:subagent-driven-development",
    ),
    "rework": ("superpowers:systematic-debugging",),
    "refinement": ("code-simplifier",),
    "review_request": ("superpowers:requesting-code-review",),
    "review_response": ("superpowers:receiving-code-review",),
    "feature_closure": (
        "open-spec-feature-closure",
        "superpowers:verification-before-completion",
    ),
}

FILE_SKILLS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
}


def required_skills_for_stage(
    stage: str,
    *,
    file_paths: Iterable[str | Path] | None = None,
) -> list[str]:
    """Return reviewable skill requirements for a workflow stage."""
    required = list(STAGE_SKILLS.get(stage, ()))
    for file_path in file_paths or ():
        suffix = Path(file_path).suffix.lower()
        skill = FILE_SKILLS.get(suffix)
        if skill and skill not in required:
            required.append(skill)
    return required


def validate_skill_gate(
    stage: str,
    used_skills: Iterable[str],
    *,
    file_paths: Iterable[str | Path] | None = None,
) -> SkillGateResult:
    """Validate that the given stage used its required skills."""
    used = list(dict.fromkeys(used_skills))
    required = required_skills_for_stage(stage, file_paths=file_paths)
    missing = [
        requirement
        for requirement in required
        if not _requirement_satisfied(requirement, used)
    ]
    return SkillGateResult(
        stage=stage,
        required_skills=required,
        used_skills=used,
        missing_skills=missing,
        passed=not missing,
    )


def _requirement_satisfied(requirement: str, used_skills: list[str]) -> bool:
    alternatives = requirement.split("|")
    return any(skill in used_skills for skill in alternatives)
