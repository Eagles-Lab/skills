"""Strict canonical and score contracts for security resume analyzer v1."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

SCHEMA_VERSION: Literal["1.0"] = "1.0"
SCORING_CONFIG_VERSION: Literal["cn-campus-security-1.0.0"] = "cn-campus-security-1.0.0"


class Track(StrEnum):
    appsec_offensive = "appsec-offensive"
    defense_ir = "defense-ir"
    security_engineering_cloud = "security-engineering-cloud"


DimensionName = Literal[
    "systems_network_security_foundation",
    "programming_security_engineering_automation",
    "application_security_offensive",
    "detection_defense_incident_response",
    "cloud_identity_data_supply_chain",
    "ai_assisted_security_ai_system_security",
]
SourceKind = Literal["skills", "internship", "project", "security_activity"]


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


class Project(Experience):
    pass


class SecurityCategory(StrEnum):
    ctf = "ctf"
    lab = "lab"
    vulnerability_disclosure = "vulnerability_disclosure"
    bug_bounty = "bug_bounty"
    authorized_testing = "authorized_testing"
    open_source = "open_source"
    security_competition = "security_competition"
    certification = "certification"
    paper = "paper"
    other = "other"


class SecurityEnvironment(StrEnum):
    lab = "lab"
    ctf = "ctf"
    bug_bounty = "bug_bounty"
    authorized = "authorized"
    production_defense = "production_defense"
    academic = "academic"
    open_source = "open_source"
    unknown = "unknown"


def _category_value(value: object) -> object:
    return SecurityCategory(value) if isinstance(value, str) else value


def _environment_value(value: object) -> object:
    return SecurityEnvironment(value) if isinstance(value, str) else value


class SecurityActivity(Experience):
    category: Annotated[SecurityCategory | None, BeforeValidator(_category_value)] = None
    environment: Annotated[SecurityEnvironment | None, BeforeValidator(_environment_value)] = None


class Skills(StrictModel):
    programming_languages: TextList = Field(default_factory=list)
    systems_networking: TextList = Field(default_factory=list)
    appsec_offensive: TextList = Field(default_factory=list)
    defense_ir: TextList = Field(default_factory=list)
    cloud_identity_data: TextList = Field(default_factory=list)
    security_engineering_tools: TextList = Field(default_factory=list)
    ai_security: TextList = Field(default_factory=list)
    governance_standards: TextList = Field(default_factory=list)


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
    security_activities: Annotated[
        list[SecurityActivity],
        BeforeValidator(_none_to_list, json_schema_input_type=list[SecurityActivity] | None),
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
    authorization: SecurityEnvironment | None = None


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
    scoring_config_version: Literal["cn-campus-security-1.0.0"] = SCORING_CONFIG_VERSION
    target_track: Track
    dimension_weights: dict[DimensionName, float]
    total_score: float = Field(ge=1.0, le=10.0)
    dimension_scores: dict[DimensionName, DimensionScore]
    resume_quality: ResumeQualityDiagnostic
    grade: GradeInfo
