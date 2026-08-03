"""Strict canonical and score contracts for development resume analyzer v1."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

SCHEMA_VERSION: Literal["1.0"] = "1.0"
SCORING_PROFILE: Literal["cn-campus-software-development-general"] = (
    "cn-campus-software-development-general"
)
SCORING_CONFIG_VERSION: Literal["cn-campus-software-development-general-1.0.0"] = (
    "cn-campus-software-development-general-1.0.0"
)

DimensionName = Literal[
    "computer_science_software_foundation",
    "programming_code_quality",
    "application_development_architecture",
    "debugging_performance_problem_solving",
    "engineering_delivery_collaboration",
    "ai_assisted_development_ai_engineering",
]
SourceKind = Literal["skills", "internship", "project"]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _none_to_list(value: object) -> object:
    return [] if value is None else value


def _none_to_mapping(value: object) -> object:
    return {} if value is None else value


OptionalText = Annotated[str | None, BeforeValidator(_blank_to_none)]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TextList = Annotated[list[NonEmptyText], BeforeValidator(_none_to_list)]


class Contact(StrictModel):
    phone: OptionalText = Field(default=None, max_length=128)
    email: OptionalText = Field(default=None, max_length=320)


class BasicInfo(StrictModel):
    name: OptionalText = Field(default=None, max_length=256)
    school: OptionalText = Field(default=None, max_length=512)
    major: OptionalText = Field(default=None, max_length=256)
    degree: OptionalText = Field(default=None, max_length=128)
    graduation_year: int | None = Field(default=None, ge=1900, le=2200)
    contact: Contact | None = None


class Experience(StrictModel):
    organization: OptionalText = Field(default=None, max_length=512)
    name: OptionalText = Field(default=None, max_length=512)
    role: OptionalText = Field(default=None, max_length=256)
    duration: OptionalText = Field(default=None, max_length=256)
    description: OptionalText = Field(default=None, max_length=20_000)
    tech_stack: TextList = Field(default_factory=list)
    achievements: TextList = Field(default_factory=list)


class Internship(Experience):
    pass


class ProjectCategory(StrEnum):
    course_project = "course_project"
    personal_project = "personal_project"
    open_source = "open_source"
    competition = "competition"
    research = "research"
    hackathon = "hackathon"
    internship_project = "internship_project"
    other = "other"


def _category_value(value: object) -> object:
    return ProjectCategory(value) if isinstance(value, str) else value


class Project(Experience):
    category: Annotated[ProjectCategory | None, BeforeValidator(_category_value)] = None


class Skills(StrictModel):
    programming_languages: TextList = Field(default_factory=list)
    frontend_client_technologies: TextList = Field(default_factory=list)
    backend_technologies: TextList = Field(default_factory=list)
    frameworks_libraries: TextList = Field(default_factory=list)
    databases_storage: TextList = Field(default_factory=list)
    testing_quality: TextList = Field(default_factory=list)
    engineering_devops: TextList = Field(default_factory=list)
    ai_tools: TextList = Field(default_factory=list)


class Resume(StrictModel):
    resume_id: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )
    basic_info: Annotated[
        BasicInfo,
        BeforeValidator(_none_to_mapping, json_schema_input_type=BasicInfo | None),
    ] = Field(default_factory=BasicInfo)
    internships: Annotated[
        list[Internship],
        BeforeValidator(_none_to_list, json_schema_input_type=list[Internship] | None),
    ] = Field(default_factory=list)
    projects: Annotated[
        list[Project],
        BeforeValidator(_none_to_list, json_schema_input_type=list[Project] | None),
    ] = Field(default_factory=list)
    skills: Annotated[
        Skills,
        BeforeValidator(_none_to_mapping, json_schema_input_type=Skills | None),
    ] = Field(default_factory=Skills)


class DataQualityWarning(StrictModel):
    code: NonEmptyText
    path: NonEmptyText
    message: NonEmptyText


class EvidenceLevel(StrEnum):
    mention = "mention"
    usage = "usage"
    implementation = "implementation"
    ownership = "ownership"
    production = "production"
    outcome = "outcome"


class Evidence(StrictModel):
    dimension: DimensionName
    concept: NonEmptyText
    evidence_group: NonEmptyText
    source_kind: SourceKind
    source_id: NonEmptyText
    context: NonEmptyText
    level: EvidenceLevel
    position: int = Field(ge=0)
    quantified: bool = False


class DimensionScore(StrictModel):
    score: float = Field(ge=1.0, le=10.0)
    depth_score: float = Field(ge=1.0, le=10.0)
    coverage_cap: float = Field(ge=1.0, le=10.0)
    weight: float = Field(gt=0.0, le=1.0)
    weighted_score: float = Field(ge=0.0, le=10.0)
    evidence: list[Evidence]
    evidence_group_scores: dict[str, float]
    covered_evidence_groups: list[str]
    applied_evidence_groups: list[str]
    missing_evidence_groups: list[str]
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    strongest_evidence_level: EvidenceLevel | None = None


class ResumeQualityDiagnostic(StrictModel):
    score: float = Field(ge=1.0, le=10.0)
    weight: float = Field(default=0.0, ge=0.0, le=0.0)
    breakdown: dict[str, float]
    findings: dict[str, NonEmptyText]


class GradeInfo(StrictModel):
    grade: Literal["A+", "A", "B", "C", "D", "F"]
    label: NonEmptyText
    range: tuple[float, float]


class ScoreResult(StrictModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    scoring_profile: Literal["cn-campus-software-development-general"] = SCORING_PROFILE
    scoring_config_version: Literal["cn-campus-software-development-general-1.0.0"] = (
        SCORING_CONFIG_VERSION
    )
    dimension_weights: dict[DimensionName, float]
    total_score: float = Field(ge=1.0, le=10.0)
    dimension_scores: dict[DimensionName, DimensionScore]
    resume_quality: ResumeQualityDiagnostic
    grade: GradeInfo
