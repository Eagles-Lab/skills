"""Strict public data models for the v3 resume analyzer contract."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SCHEMA_VERSION = "3.0"

DimensionName = Literal[
    "monitoring",
    "alerting",
    "automation",
    "containerization",
    "incident_handling",
    "resume_quality",
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


class Contact(StrictModel):
    phone: NonEmptyText = Field(min_length=1, max_length=128)
    email: NonEmptyText = Field(min_length=1, max_length=320)


class BasicInfo(StrictModel):
    name: NonEmptyText = Field(min_length=1, max_length=256)
    school: NonEmptyText = Field(min_length=1, max_length=512)
    major: NonEmptyText = Field(min_length=1, max_length=256)
    degree: NonEmptyText = Field(min_length=1, max_length=128)
    graduation_year: int = Field(ge=1900, le=2200)
    contact: Optional[Contact] = None


class Internship(StrictModel):
    company: NonEmptyText = Field(min_length=1, max_length=512)
    role: NonEmptyText = Field(min_length=1, max_length=256)
    duration: NonEmptyText = Field(min_length=1, max_length=256)
    description: NonEmptyText = Field(min_length=1, max_length=20_000)
    tech_stack: List[NonEmptyText]
    achievements: List[NonEmptyText]


class Project(StrictModel):
    name: NonEmptyText = Field(min_length=1, max_length=512)
    role: NonEmptyText = Field(min_length=1, max_length=256)
    duration: NonEmptyText = Field(min_length=1, max_length=256)
    description: NonEmptyText = Field(min_length=1, max_length=20_000)
    tech_stack: List[NonEmptyText]
    achievements: List[NonEmptyText]


class Skills(StrictModel):
    programming_languages: List[NonEmptyText]
    monitoring_tools: List[NonEmptyText]
    container_tech: List[NonEmptyText]
    cloud_platforms: List[NonEmptyText]
    cicd_tools: List[NonEmptyText]


class Resume(StrictModel):
    """The only accepted structured input shape for analyzer v3."""

    resume_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    basic_info: BasicInfo
    internships: List[Internship]
    projects: List[Project]
    skills: Skills


class EvidenceLevel(str, Enum):
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
    weight: float = Field(gt=0.0, le=1.0)
    weighted_score: float = Field(ge=0.0, le=10.0)
    evidence: List[Evidence]
    keyword_count: int = Field(ge=0)
    breakdown: Dict[str, float] = Field(default_factory=dict)


class AIApplication(StrictModel):
    category: NonEmptyText = Field(min_length=1)
    keyword: NonEmptyText = Field(min_length=1)
    source_kind: Literal["internship", "project"]
    source_id: NonEmptyText = Field(min_length=1)
    context: NonEmptyText = Field(min_length=1)
    level: EvidenceLevel
    quantified: bool = False


class AIBonus(StrictModel):
    score: float = Field(ge=0.0, le=1.5)
    level: NonEmptyText = Field(min_length=1)
    category_count: int = Field(ge=0)
    applications: Dict[str, List[AIApplication]]
    max_score: float = 1.5


class GradeInfo(StrictModel):
    grade: Literal["A+", "A", "B", "C", "D", "F"]
    label: NonEmptyText = Field(min_length=1)
    description: NonEmptyText = Field(min_length=1)
    range: Tuple[float, float]


class ScoreResult(StrictModel):
    schema_version: str = SCHEMA_VERSION
    scoring_config_version: NonEmptyText = Field(min_length=1)
    base_score: float = Field(ge=1.0, le=10.0)
    ai_bonus: AIBonus
    total_score: float = Field(ge=1.0, le=11.5)
    dimension_scores: Dict[DimensionName, DimensionScore]
    grade: GradeInfo
