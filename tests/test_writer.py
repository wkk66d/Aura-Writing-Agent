"""Writer Agent 单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from aura.writer import Writer, _clean_output
from aura.types import AuraConfig, WritingTask, StyleProfile, StyleProfileMeta
from aura.prompts.writer_prompt import assemble_writer_prompt, format_style_anchoring, format_task_constraints


class TestPromptAssembly:
    """提示词组装测试"""

    def test_assemble_basic_prompt(self, sample_task):
        """基本提示词组装"""
        prompt = assemble_writer_prompt(task=sample_task, as_cached_blocks=False)
        assert "小说作家" in prompt
        assert "展现，不要告知" in prompt
        assert "仿佛" in prompt  # 禁用词
        assert "雨夜" in prompt  # 任务
        assert "少年" in prompt  # 角色
        assert "第三人称限制" in prompt

    def test_assemble_with_style(self, sample_task, sample_profile):
        """带风格档案的提示词组装"""
        prompt = assemble_writer_prompt(
            task=sample_task,
            style_profile=sample_profile,
            as_cached_blocks=False,
        )
        assert "冷峻" in prompt
        assert "雨打在窗上" in prompt  # 语料库锚点

    def test_cached_blocks_format(self, sample_task):
        """缓存块格式"""
        blocks = assemble_writer_prompt(task=sample_task, as_cached_blocks=True)
        assert isinstance(blocks, list)
        assert len(blocks) > 0
        # 第一个块应该有 cache_control
        first_block = blocks[0]
        assert "cache_control" in first_block

    def test_task_constraints_format(self, sample_task):
        """任务约束格式化"""
        constraints = format_task_constraints(sample_task)
        assert "雨夜" in constraints
        assert "800" in constraints
        assert "少年" in constraints

    def test_style_anchoring_format(self, sample_profile):
        """风格锚定格式化"""
        anchoring = format_style_anchoring(sample_profile)
        assert "25" in anchoring  # mean_chars
        assert "冷峻" in anchoring


class TestOutputCleaning:
    """输出清理测试"""

    def test_strip_prefix(self):
        text = "以下是场景：\n\n雨下得很大。"
        cleaned = _clean_output(text)
        assert not cleaned.startswith("以下是场景：")

    def test_strip_suffix(self):
        text = "雨下得很大。\n\n希望这符合你的要求。"
        cleaned = _clean_output(text)
        assert not cleaned.endswith("要求。")

    def test_no_change_needed(self):
        text = "雨下得很大。他推开了门。"
        cleaned = _clean_output(text)
        assert cleaned == text
