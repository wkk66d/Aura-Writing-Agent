"""测试配置和共享 fixtures"""

import pytest

from aura.types import (
    AuraConfig, WritingTask, StyleProfile, StyleProfileMeta,
    StyleCorpus, StyleCorpusEntry,
)


@pytest.fixture
def sample_config() -> AuraConfig:
    """测试用配置"""
    config = AuraConfig()
    config.review.max_iterations = 2
    return config


@pytest.fixture
def sample_task() -> WritingTask:
    """测试用写作任务"""
    return WritingTask(
        scene_outline="一个少年在雨夜回到家中，发现门开着。",
        beats=["少年到达家门口", "发现门开着", "推门进入", "发现屋内异样"],
        pov_type="第三人称限制",
        pov_character="少年",
        tense="过去时",
        target_word_count_min=800,
        target_word_count_max=1200,
        must_include=["雨夜氛围", "门开着这一关键细节"],
        must_avoid=["直接说出'他感到害怕'"],
        characters=[
            {
                "name": "少年",
                "personality_keywords": ["谨慎", "敏感", "寡言"],
                "behavioral_constraints": ["不主动说话"],
                "language_style": "少言寡语",
                "knowledge_boundary": "不知道屋里有什么",
            }
        ],
        genre="悬疑",
    )


@pytest.fixture
def sample_profile() -> StyleProfile:
    """测试用风格档案"""
    return StyleProfile(
        meta=StyleProfileMeta(
            profile_name="test_style",
            version="2.0",
            total_chars_analyzed=5000,
        ),
        sentence_length={"mean_chars": 25.0, "stddev": 12.0},
        style_corpus=StyleCorpus(
            total_entries=2,
            sentence_templates=[
                StyleCorpusEntry(
                    category="典型开头句",
                    original="雨打在窗上。他推开门。",
                    char_count=11,
                    feature_note="短句开场+动作直接",
                    usage="场景开场：简短的动作句",
                ),
            ],
        ),
        voice_description="冷峻的第三人称，句子简短，注重感官细节。",
    )


@pytest.fixture
def sample_draft() -> str:
    """测试用初稿"""
    return """雨下得很大。他站在门口，看着那扇半开的门。

门缝里透出微弱的光。他记得出门前明明关了灯。

雨水顺着他的头发滴下来，落在门槛上。他伸出手，指尖碰到了门板。

门无声地滑开了。"""


@pytest.fixture
def ai_flavored_draft() -> str:
    """含 AI 味的测试文本"""
    return """在雨夜的世界里，他缓缓地走到了家门口。

显而易见，门是开着的。他不禁感到一阵难以形容的不安。

他深深地吸了一口气，轻轻地推开了门。忽然，一阵微风拂面而来。

总而言之，这是一个值得注意的夜晚。他感到一阵恐惧，仿佛有什么在等待着他。

在这个充满悬疑的夜晚，他缓缓地走进了那个不可名状的空间。"""
