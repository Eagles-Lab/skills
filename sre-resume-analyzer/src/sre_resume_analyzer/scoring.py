"""Deterministic scoring for strict v3 canonical resumes."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .matching import (
    DEFAULT_MATCHING_CONFIG,
    EvidenceMatcher,
    classify_evidence,
    is_quantified,
    iter_resume_records,
    iter_sentences,
    normalize_text,
)
from .models import (
    AIApplication,
    AIBonus,
    DimensionName,
    DimensionScore,
    Evidence,
    EvidenceLevel,
    GradeInfo,
    Resume,
    ScoreResult,
)
from .security import is_instruction_like

SCORING_CONFIG_VERSION = "3.0.0"

DIMENSION_WEIGHTS: Dict[str, float] = {
    "monitoring": 0.20,
    "alerting": 0.15,
    "automation": 0.20,
    "containerization": 0.15,
    "incident_handling": 0.15,
    "resume_quality": 0.15,
}

EVIDENCE_SCORES: Dict[str, float] = {
    "mention": 2.0,
    "usage": 4.0,
    "implementation": 6.0,
    "ownership": 8.0,
    "production": 9.0,
    "outcome": 9.0,
}

GRADE_RANGES: Dict[str, Tuple[float, float]] = {
    "A+": (9.5, 11.5),
    "A": (8.5, 9.4),
    "B": (7.0, 8.4),
    "C": (5.5, 6.9),
    "D": (4.0, 5.4),
    "F": (0.0, 3.9),
}

GRADE_THRESHOLDS: Dict[str, Dict[str, object]] = {
    "A+": {
        "range": list(GRADE_RANGES["A+"]),
        "label": "卓越",
        "description": "简历证据覆盖度卓越",
    },
    "A": {
        "range": list(GRADE_RANGES["A"]),
        "label": "优秀",
        "description": "简历证据覆盖度优秀",
    },
    "B": {
        "range": list(GRADE_RANGES["B"]),
        "label": "良好",
        "description": "简历证据覆盖度良好",
    },
    "C": {
        "range": list(GRADE_RANGES["C"]),
        "label": "中等",
        "description": "简历证据覆盖度中等",
    },
    "D": {
        "range": list(GRADE_RANGES["D"]),
        "label": "需改进",
        "description": "简历证据覆盖度有限",
    },
    "F": {
        "range": list(GRADE_RANGES["F"]),
        "label": "证据不足",
        "description": "简历中的相关证据不足",
    },
}

DEFAULT_SCORING_CONFIG: Dict[str, object] = {
    "version": SCORING_CONFIG_VERSION,
    "dimension_weights": copy.deepcopy(DIMENSION_WEIGHTS),
    "evidence_scores": copy.deepcopy(EVIDENCE_SCORES),
    "grade_thresholds": copy.deepcopy(GRADE_THRESHOLDS),
    "max_ai_bonus": 1.5,
    "matching": copy.deepcopy(DEFAULT_MATCHING_CONFIG),
}

_TECHNICAL_DIMENSIONS: Tuple[DimensionName, ...] = (
    "monitoring",
    "alerting",
    "automation",
    "containerization",
    "incident_handling",
)
_ALL_DIMENSIONS: Tuple[DimensionName, ...] = (*_TECHNICAL_DIMENSIONS, "resume_quality")


class GradeThreshold(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    range: List[float] = Field(min_length=2, max_length=2)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> GradeThreshold:
        if self.range[0] > self.range[1]:
            raise ValueError("grade range minimum must not exceed maximum")
        return self


class MatchingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: str = Field(min_length=1)
    dimension_keywords: Dict[str, Dict[str, List[str]]]
    ai_keywords: Dict[str, List[str]]


class ScoringConfig(BaseModel):
    """Validated, serializable scoring and matching configuration."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: str = Field(min_length=1)
    dimension_weights: Dict[str, float]
    evidence_scores: Dict[str, float]
    grade_thresholds: Dict[str, GradeThreshold]
    max_ai_bonus: float = Field(ge=0.0, le=1.5)
    matching: MatchingSettings

    @model_validator(mode="after")
    def validate_contract(self) -> ScoringConfig:
        if set(self.dimension_weights) != set(_ALL_DIMENSIONS):
            raise ValueError("dimension_weights must define exactly the six v3 dimensions")
        if abs(sum(self.dimension_weights.values()) - 1.0) > 1e-9:
            raise ValueError("dimension weights must sum to 1.0")
        if any(weight <= 0.0 for weight in self.dimension_weights.values()):
            raise ValueError("dimension weights must be positive")
        if any(
            abs(self.dimension_weights[key] - expected) > 1e-9
            for key, expected in DIMENSION_WEIGHTS.items()
        ):
            raise ValueError("v3 dimension weights are fixed and cannot be changed")
        if set(self.evidence_scores) != {level.value for level in EvidenceLevel}:
            raise ValueError("evidence_scores must define every evidence level")
        if set(self.grade_thresholds) != {"A+", "A", "B", "C", "D", "F"}:
            raise ValueError("grade_thresholds must define A+, A, B, C, D, and F")
        if any(
            tuple(self.grade_thresholds[grade].range) != GRADE_RANGES[grade]
            for grade in GRADE_RANGES
        ):
            raise ValueError("v3 grade boundaries are fixed and cannot be changed")
        if set(self.matching.dimension_keywords) != set(_TECHNICAL_DIMENSIONS):
            raise ValueError(
                "matching.dimension_keywords must define the five technical dimensions"
            )
        return self

    @classmethod
    def from_source(
        cls,
        source: Optional[Union[ScoringConfig, Mapping[str, Any], str, Path]] = None,
    ) -> ScoringConfig:
        if source is None:
            return cls.model_validate(copy.deepcopy(DEFAULT_SCORING_CONFIG))
        if isinstance(source, cls):
            return source
        if isinstance(source, (str, Path)):
            path = Path(source)
            try:
                with path.open("r", encoding="utf-8") as handle:
                    if path.suffix.lower() == ".json":
                        data = json.load(handle)
                    else:
                        data = yaml.safe_load(handle)
            except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
                raise ValueError(
                    f"scoring configuration could not be read: {type(exc).__name__}"
                ) from exc
            if not isinstance(data, Mapping):
                raise ValueError("scoring configuration root must be an object")
            return cls.model_validate(dict(data))
        return cls.model_validate(dict(source))


class ScoreCalculator:
    """Calculate repeatable evidence-based scores from a validated resume."""

    def __init__(
        self,
        config: Optional[Union[ScoringConfig, Mapping[str, Any], str, Path]] = None,
        matcher: Optional[EvidenceMatcher] = None,
    ) -> None:
        self.config = ScoringConfig.from_source(config)
        self.matcher = matcher or EvidenceMatcher(self.config.matching.dimension_keywords)

    def calculate(self, resume: Resume) -> ScoreResult:
        dimensions: Dict[DimensionName, DimensionScore] = {}
        for dimension in _TECHNICAL_DIMENSIONS:
            evidence = self.matcher.find_evidence(resume, dimension)
            dimensions[dimension] = self._score_technical_dimension(dimension, evidence)
        dimensions["resume_quality"] = self._score_resume_quality(resume)

        base_score_raw = sum(item.weighted_score for item in dimensions.values())
        base_score = round(min(10.0, max(1.0, base_score_raw)), 1)
        ai_bonus = self._evaluate_ai_bonus(resume)
        total_score = round(min(11.5, max(1.0, base_score_raw + ai_bonus.score)), 1)

        return ScoreResult(
            scoring_config_version=self.config.version,
            base_score=base_score,
            ai_bonus=ai_bonus,
            total_score=total_score,
            dimension_scores=dimensions,
            grade=self.grade_for_score(total_score),
        )

    def calculate_scores(self, extracted_data: Union[Resume, Mapping[str, Any]]) -> ScoreResult:
        """Integration-friendly alias that still validates mappings strictly as v3."""

        resume = (
            extracted_data
            if isinstance(extracted_data, Resume)
            else Resume.model_validate(dict(extracted_data))
        )
        return self.calculate(resume)

    def _score_technical_dimension(
        self,
        dimension: DimensionName,
        evidence: Sequence[Evidence],
    ) -> DimensionScore:
        weight = self.config.dimension_weights[dimension]
        if not evidence:
            score = 1.0
        else:
            score = max(self.config.evidence_scores[item.level.value] for item in evidence)
            independent_sources = {
                item.source_id for item in evidence if item.source_kind in {"internship", "project"}
            }
            strong_sources = {
                item.source_id
                for item in evidence
                if self.config.evidence_scores[item.level.value] >= 6.0
            }
            if len(strong_sources) >= 2:
                score = min(10.0, score + 1.0)
            if score > 6.0 and len(independent_sources) < 2:
                score = 6.0
            if score > 8.0 and not any(
                item.level
                in {EvidenceLevel.ownership, EvidenceLevel.production, EvidenceLevel.outcome}
                for item in evidence
            ):
                score = 8.0
        return DimensionScore(
            score=float(score),
            weight=weight,
            weighted_score=float(score) * weight,
            evidence=list(evidence),
            keyword_count=len({item.keyword for item in evidence}),
        )

    def _score_resume_quality(self, resume: Resume) -> DimensionScore:
        records = list(resume.internships) + list(resume.projects)
        skill_count = sum(len(items) for items in resume.skills.model_dump(mode="python").values())

        if records and skill_count >= 2:
            completeness = 2.0
        elif records or skill_count:
            completeness = 1.0
        else:
            completeness = 0.0
        contexts = [
            sentence
            for record in iter_resume_records(resume)
            if record.source_kind != "skills" and not record.mention_only
            for sentence, _ in iter_sentences(record.text)
            if not is_instruction_like(sentence)
        ]

        action_count = sum(classify_evidence(text) != EvidenceLevel.mention for text in contexts)
        if contexts and action_count >= 2 and action_count / len(contexts) >= 0.6:
            action_result = 2.0
        elif action_count:
            action_result = 1.0
        else:
            action_result = 0.0

        quantified_count = sum(is_quantified(text) for text in contexts)
        quantified_result = (
            2.0 if quantified_count >= 2 else (1.0 if quantified_count == 1 else 0.0)
        )

        normalized_contexts = [normalize_text(text) for text in contexts if text.strip()]
        clear_count = sum(20 <= len(text) <= 500 for text in normalized_contexts)
        unique_ratio = (
            len(set(normalized_contexts)) / len(normalized_contexts) if normalized_contexts else 0.0
        )
        if (
            normalized_contexts
            and clear_count / len(normalized_contexts) >= 0.6
            and unique_ratio >= 0.75
        ):
            clarity = 2.0
        elif normalized_contexts:
            clarity = 1.0
        else:
            clarity = 0.0

        if records:
            durations_complete = all(bool(record.duration.strip()) for record in records)
            stacks_complete = all(bool(record.tech_stack) for record in records)
            consistency = (
                2.0
                if durations_complete and stacks_complete
                else (1.0 if durations_complete else 0.0)
            )
        else:
            consistency = 0.0

        breakdown = {
            "completeness": completeness,
            "action_result": action_result,
            "quantified_results": quantified_result,
            "clarity": clarity,
            "timeline_technical_consistency": consistency,
        }
        score = min(10.0, max(1.0, sum(breakdown.values())))
        weight = self.config.dimension_weights["resume_quality"]
        return DimensionScore(
            score=score,
            weight=weight,
            weighted_score=score * weight,
            evidence=[],
            keyword_count=0,
            breakdown=breakdown,
        )

    def _evaluate_ai_bonus(self, resume: Resume) -> AIBonus:
        applications: Dict[str, List[AIApplication]] = {}
        ai_keywords = self.config.matching.ai_keywords
        quantified_sources = {
            record.source_id
            for record in iter_resume_records(resume)
            if record.source_kind != "skills"
            and any(
                classify_evidence(sentence) == EvidenceLevel.outcome
                for sentence, _ in iter_sentences(record.text)
                if not is_instruction_like(sentence)
            )
        }
        for category in sorted(ai_keywords):
            terms = {category: ai_keywords[category]}
            category_items: Dict[str, AIApplication] = {}
            for record in iter_resume_records(resume):
                if record.source_kind == "skills" or record.mention_only:
                    continue
                for sentence, _ in iter_sentences(record.text):
                    if is_instruction_like(sentence):
                        continue
                    for match in self.matcher.match_terms(sentence, terms):
                        level = classify_evidence(sentence)
                        if level == EvidenceLevel.mention:
                            continue
                        item = AIApplication(
                            category=category,
                            keyword=match.variant,
                            source_kind=record.source_kind,
                            source_id=record.source_id,
                            context=sentence,
                            level=level,
                            quantified=record.source_id in quantified_sources,
                        )
                        previous = category_items.get(record.source_id)
                        if previous is None or _application_rank(item) > _application_rank(
                            previous
                        ):
                            category_items[record.source_id] = item
            if category_items:
                applications[category] = sorted(
                    category_items.values(),
                    key=lambda item: (item.source_kind, item.source_id, item.keyword, item.context),
                )

        category_count = len(applications)
        has_same_source_quantification = any(
            item.quantified for category_items in applications.values() for item in category_items
        )
        if category_count >= 3 and has_same_source_quantification:
            score = min(1.5, self.config.max_ai_bonus)
            bonus_level = "三类独立应用且包含同段量化成果"
        elif category_count >= 2:
            score = min(1.0, self.config.max_ai_bonus)
            bonus_level = "两类及以上实际应用"
        elif category_count == 1:
            score = min(0.5, self.config.max_ai_bonus)
            bonus_level = "一类实际应用"
        else:
            score = 0.0
            bonus_level = "无实际应用证据"
        return AIBonus(
            score=score,
            level=bonus_level,
            category_count=category_count,
            applications=applications,
            max_score=self.config.max_ai_bonus,
        )

    def grade_for_score(self, total_score: float) -> GradeInfo:
        rounded = round(total_score, 1)
        for grade in ("A+", "A", "B", "C", "D", "F"):
            threshold = self.config.grade_thresholds[grade]
            lower, upper = threshold.range
            if lower <= rounded <= upper:
                return GradeInfo(
                    grade=grade,
                    label=threshold.label,
                    description=threshold.description,
                    range=(lower, upper),
                )
        # ScoreResult bounds make this unreachable, but fail closed for custom callers.
        threshold = self.config.grade_thresholds["F"]
        return GradeInfo(
            grade="F",
            label=threshold.label,
            description=threshold.description,
            range=(threshold.range[0], threshold.range[1]),
        )


def _application_rank(application: AIApplication) -> Tuple[float, int, str]:
    return (
        EVIDENCE_SCORES[application.level.value],
        int(application.quantified),
        application.keyword,
    )
