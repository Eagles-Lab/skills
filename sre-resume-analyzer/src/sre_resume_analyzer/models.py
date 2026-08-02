"""Public data models for the v3 campus SRE resume analyzer contract."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Dict, List, Literal, Optional, Tuple

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

SCHEMA_VERSION = "3.0"
SCORING_PROFILE = "cn-campus-sre"

DimensionName = Literal[
    "systems_network_foundation",
    "programming_automation",
    "troubleshooting",
    "cloud_distributed_infrastructure",
    "reliability_engineering",
    "ai_engineering_aiops",
]
SourceKind = Literal["skills", "internship", "project"]


class StrictModel(BaseModel):
    """Base class shared by every persisted v3 model."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _none_to_empty_list(value: object) -> object:
    return [] if value is None else value


def _none_to_empty_mapping(value: object) -> object:
    return {} if value is None else value


OptionalText = Annotated[
    Optional[str],
    BeforeValidator(_blank_to_none),
]
TextList = Annotated[List[NonEmptyText], BeforeValidator(_none_to_empty_list)]


class Contact(StrictModel):
    phone: OptionalText = Field(default=None, max_length=128)
    email: OptionalText = Field(default=None, max_length=320)


class BasicInfo(StrictModel):
    name: OptionalText = Field(default=None, max_length=256)
    school: OptionalText = Field(default=None, max_length=512)
    major: OptionalText = Field(default=None, max_length=256)
    degree: OptionalText = Field(default=None, max_length=128)
    graduation_year: Optional[int] = Field(default=None, ge=1900, le=2200)
    contact: Optional[Contact] = None


class Internship(StrictModel):
    company: OptionalText = Field(default=None, max_length=512)
    role: OptionalText = Field(default=None, max_length=256)
    duration: OptionalText = Field(default=None, max_length=256)
    description: OptionalText = Field(default=None, max_length=20_000)
    tech_stack: TextList = Field(default_factory=list)
    achievements: TextList = Field(default_factory=list)


class Project(StrictModel):
    name: OptionalText = Field(default=None, max_length=512)
    role: OptionalText = Field(default=None, max_length=256)
    duration: OptionalText = Field(default=None, max_length=256)
    description: OptionalText = Field(default=None, max_length=20_000)
    tech_stack: TextList = Field(default_factory=list)
    achievements: TextList = Field(default_factory=list)


class Skills(StrictModel):
    programming_languages: TextList = Field(default_factory=list)
    monitoring_tools: TextList = Field(default_factory=list)
    container_tech: TextList = Field(default_factory=list)
    cloud_platforms: TextList = Field(default_factory=list)
    cicd_tools: TextList = Field(default_factory=list)
    ai_tools: TextList = Field(default_factory=list)


class Resume(StrictModel):
    """The only accepted structured input shape for analyzer v3."""

    resume_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    basic_info: Annotated[
        BasicInfo,
        BeforeValidator(_none_to_empty_mapping, json_schema_input_type=BasicInfo | None),
    ] = Field(default_factory=BasicInfo)
    internships: Annotated[
        List[Internship],
        BeforeValidator(_none_to_empty_list, json_schema_input_type=List[Internship] | None),
    ] = Field(default_factory=list)
    projects: Annotated[
        List[Project],
        BeforeValidator(_none_to_empty_list, json_schema_input_type=List[Project] | None),
    ] = Field(default_factory=list)
    skills: Annotated[
        Skills,
        BeforeValidator(_none_to_empty_mapping, json_schema_input_type=Skills | None),
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
    keyword: NonEmptyText = Field(min_length=1)
    source_kind: SourceKind
    source_id: NonEmptyText = Field(min_length=1)
    context: NonEmptyText = Field(min_length=1)
    level: EvidenceLevel
    position: int = Field(ge=0)
    quantified: bool = False


class DimensionScore(StrictModel):
    score: float = Field(ge=1.0, le=10.0)
    depth_score: float = Field(ge=1.0, le=10.0)
    coverage_cap: float = Field(ge=1.0, le=10.0)
    weight: float = Field(gt=0.0, le=1.0)
    weighted_score: float = Field(ge=0.0, le=10.0)
    evidence: List[Evidence]
    keyword_count: int = Field(ge=0)
    evidence_group_scores: Dict[str, float]
    covered_evidence_groups: List[NonEmptyText]
    applied_evidence_groups: List[NonEmptyText]
    missing_evidence_groups: List[NonEmptyText]
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    strongest_evidence_level: Optional[EvidenceLevel] = None


class ResumeQualityDiagnostic(StrictModel):
    score: float = Field(ge=1.0, le=10.0)
    weight: float = Field(default=0.0, ge=0.0, le=0.0)
    breakdown: Dict[str, float]
    findings: Dict[str, NonEmptyText]


class GradeInfo(StrictModel):
    grade: Literal["A+", "A", "B", "C", "D", "F"]
    label: NonEmptyText = Field(min_length=1)
    description: NonEmptyText = Field(min_length=1)
    range: Tuple[float, float]


class ScoreResult(StrictModel):
    schema_version: str = SCHEMA_VERSION
    scoring_profile: Literal["cn-campus-sre"] = "cn-campus-sre"
    scoring_config_version: NonEmptyText = Field(min_length=1)
    total_score: float = Field(ge=1.0, le=10.0)
    dimension_scores: Dict[DimensionName, DimensionScore]
    resume_quality: ResumeQualityDiagnostic
    grade: GradeInfo
