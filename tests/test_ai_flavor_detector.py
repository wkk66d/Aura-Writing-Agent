"""AI Flavor Detector 单元测试"""

import pytest
from aura.ai_flavor_detector import scan_text, ALL_BANNED


class TestBannedWords:
    """禁用词扫描测试"""

    def test_detect_ai_adverb(self):
        result = scan_text("他仿佛看到了什么。")
        words = [item["word"] for item in result.banned_words_found]
        assert "仿佛" in words

    def test_detect_cliche(self):
        result = scan_text("综上所述，这是值得注意的是，值得注意的一个问题。")
        words = [item["word"] for item in result.banned_words_found]
        assert "综上所述" in words
        assert "值得注意的是" in words

    def test_detect_translationese(self):
        result = scan_text("然而，此外，因此，这是一个不可忽视的问题。")
        words = [item["word"] for item in result.banned_words_found]
        assert "然而" in words

    def test_clean_text_no_flags(self):
        result = scan_text("雨打在窗上。他推开门。屋里很暗。他摸索着墙壁，找到了开关。灯亮了。")
        assert len(result.banned_words_found) == 0

    def test_ai_flavored_text_heavily_flagged(self, ai_flavored_draft):
        result = scan_text(ai_flavored_draft)
        # 应该标记大量禁用词
        words = [item["word"] for item in result.banned_words_found]
        assert len(words) >= 5  # 至少有5个禁用词


class TestAdverbDe:
    """'地'字副词检测"""

    def test_zero_adverbs(self):
        result = scan_text("他站在那里看着远方不动。")
        assert result.adverb_de_count == 0

    def test_detect_ly_adverb(self):
        result = scan_text("他慢慢地走了过来。她轻轻地叹了口气。")
        assert result.adverb_de_count >= 2

    def test_density_calculation(self):
        # "慢慢地走了" — 4字 + "地"字副词
        text = "他慢慢地走了过来。她轻轻地叹了口气。" * 10
        result = scan_text(text)
        assert result.adverb_de_density > 0
        assert result.total_chars > 0


class TestSentenceUniformity:
    """句式均匀度检测"""

    def test_varied_sentences(self):
        text = "他站住。门开着。雨下得很大，从屋檐上倾泻下来。他犹豫了很长一段时间。"
        result = scan_text(text)
        # 有变化的句子应该均匀度 < 0.5
        assert result.sentence_uniformity < 0.5

    def test_uniform_sentences(self):
        # 每句话都差不多长度
        text = "这是一个很普通的故事。他说了一些很普通的话。天上下起了很大的雨。"
        result = scan_text(text)
        assert result.sentence_uniformity is not None


class TestParagraphVariance:
    """段落方差检测"""

    def test_varied_paragraphs(self):
        text = "短段。\n\n这是一个中等长度的段落，包含了一些描述。\n\n这是一个很长的段落。它包含了很多句话。它描述了很多事情。它还在继续说。它终于接近尾声了。"
        result = scan_text(text)
        assert not result.paragraph_is_uniform

    def test_uniform_paragraphs(self):
        text = "三个句子的一段。第二个句子。第三个句子。\n\n还是三个句子。又一个。又一。\n\n三个句子的一段。这样写。三个句子。"
        result = scan_text(text)
        # 三段的长度非常均匀
        assert result.paragraph_variance > 0.5


class TestQualityScoring:
    """质量评分"""

    def test_clean_text_scores_high(self):
        text = "雨打在窗上。他推开门。屋里很暗。他摸索着墙壁，找到了开关。灯亮了。屋里空无一人。桌上摆着吃了一半的晚饭。"
        result = scan_text(text)
        assert result.quality_total >= 30

    def test_ai_text_scores_low(self, ai_flavored_draft):
        result = scan_text(ai_flavored_draft)
        assert result.quality_total < 40


class TestFormatReport:
    """报告格式化"""

    def test_report_contains_key_sections(self):
        from aura.ai_flavor_detector import format_scan_report
        result = scan_text("他慢慢地走了过来。仿佛看到了什么。")
        report = format_scan_report(result)
        assert "禁用词" in report or "禁用" in report
        assert "副词" in report
