"""Reviewer Agent 单元测试"""

import pytest

from aura.reviewer import _compute_composite_from_scores, _parse_json
from aura.types import (
    InstructionComplianceResult, InstructionItem, InstructionPriority,
    StyleAlignmentResult,
)


class TestJSONParsing:
    """JSON 解析测试"""

    def test_parse_valid_json(self):
        data = _parse_json('{"key": "value"}')
        assert data["key"] == "value"

    def test_parse_json_with_markdown(self):
        raw = '这是一些文本\n```json\n{"score": 85}\n```\n更多文本'
        data = _parse_json(raw)
        assert data["score"] == 85

    def test_parse_invalid_returns_empty(self):
        data = _parse_json("这不是 JSON")
        assert data == {}


class TestCompositeScoring:
    """综合评分测试"""

    def test_perfect_scores(self):
        """全满分"""
        scores = {"I1": 100, "F1": 100, "F2": 95, "Q1": 100, "Q2": 95}
        score = _compute_composite_from_scores(scores)
        assert score >= 90

    def test_low_scores(self):
        """低分"""
        scores = {"I1": 40, "F1": 50, "F2": 50, "Q1": 60, "Q2": 60}
        score = _compute_composite_from_scores(scores)
        assert score < 70

    def test_mixed_scores(self):
        """混合分数"""
        scores = {"I1": 90, "I3": 85, "F1": 85, "F2": 85, "Q1": 85, "Q2": 85}
        score = _compute_composite_from_scores(scores)
        assert score >= 70
