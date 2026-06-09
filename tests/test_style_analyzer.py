"""Style Analyzer 单元测试"""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from aura.style_analyzer import StyleAnalyzer, _parse_json


class TestJSONParsing:
    """JSON 解析测试"""

    def test_parse_style_json(self):
        raw = json.dumps({
            "meta": {"profile_name": "test"},
            "sentence_length": {"mean_chars": 25.0, "stddev": 10.0},
            "voice_description": "冷峻的第三人称。",
        })
        data = _parse_json(raw)
        assert data["meta"]["profile_name"] == "test"
        assert data["sentence_length"]["mean_chars"] == 25.0

    def test_parse_with_noise(self):
        raw = '这里是分析结果：\n\n```json\n{"meta": {"profile_name": "test"}}\n```\n\n分析完毕。'
        data = _parse_json(raw)
        assert data["meta"]["profile_name"] == "test"
