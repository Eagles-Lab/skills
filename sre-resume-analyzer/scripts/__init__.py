"""
SRE 简历分析工具包
SRE Resume Analyzer Package

提供完整的简历分析功能
"""

__version__ = "2.3.0"
__author__ = "Claude Code Agent Skill"

from .scoring.keyword_matcher import KeywordMatcher
from .scoring.score_calculator import ScoreCalculator
from .scoring.ai_bonus_evaluator import AIBonusEvaluator
from .generators.interview_generator import InterviewGenerator
from .generators.suggestions_generator import SuggestionsGenerator

__all__ = [
    'KeywordMatcher',
    'ScoreCalculator',
    'AIBonusEvaluator',
    'InterviewGenerator',
    'SuggestionsGenerator'
]
