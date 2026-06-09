"""
AI Flavor Detector — 规则层 AI 味检测

纯规则检测，零 API 成本:
  - 禁用词/句式扫描 (Level 2)
  - 副词密度
  - 句式均匀度
  - 段落方差
  - 质量评分（stop-slop 50 分制）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# =============================================================================
# 中文 AI 禁用词表
# =============================================================================

# AI标志副词
CN_AI_ADVERBS = [
    "仿佛", "忽然", "竟然", "不禁", "宛如", "猛地",
    "深深", "无比", "悄然", "缓缓", "渐渐",
    "似乎", "隐约", "莫名", "突然", "竟然",
]

# AI腔调套话
CN_AI_CLICHES = [
    "显而易见", "不言而喻", "毋庸置疑", "综上所述",
    "总而言之", "由此可见", "值得注意的是", "需要强调的是",
    "在某种程度上", "从某种意义上说", "不容置喙",
    "难以形容", "无法言喻", "不可名状",
]

# 英语直译腔
CN_TRANSLATIONESE = [
    "然而", "此外", "不过", "因此", "从而", "进而",
    "与此同时", "与此相对",
]

# 空洞形容词
CN_HOLLOW_ADJ = [
    "卓越", "杰出", "深刻", "全面", "系统",
    "有效", "高效", "显著", "明显",
    "赋能", "底层逻辑", "闭环", "抓手", "痛点",
]

# 网文陈词—环境
CN_ENV_CLICHES = [
    "月光如水", "微风拂面", "阳光明媚", "夕阳西下",
    "夜幕降临", "华灯初上",
]

# 网文陈词—情感
CN_EMOTION_CLICHES = [
    "百感交集", "心如刀割", "五味杂陈", "心潮澎湃",
    "热血沸腾", "热泪盈眶",
]

# 网文陈词—动作
CN_ACTION_CLICHES = [
    "缓缓开口", "微微一笑", "深吸一口气", "眉头微皱",
    "瞳孔骤缩", "不可置信", "咬了咬牙", "握紧拳头",
    "眼神一暗", "眸光一闪",
]

# 英式比喻 —— 纯字符串部分（可用 text.count() 匹配）
CN_EN_METAPHORS_PLAIN = [
    "像淬了毒", "像一记重锤",
]

# 英式比喻 —— 正则部分（需用 re.finditer 匹配）
CN_EN_METAPHORS_REGEX = [
    r"眼神里有.*?但更多的是",
    r"显得.{1,4}又.{1,4}",
]

# 禁用开头 —— 正则（以 ^ 开头，需按行或段落匹配）
CN_BANNED_OPENINGS_REGEX = [
    r"^时间来到了", r"^让我们把目光转向", r"^在一个.*?的世界里",
]

# 全部禁用词合并（纯字符串，可用 text.count() 匹配）
ALL_BANNED = (
    CN_AI_ADVERBS + CN_AI_CLICHES + CN_TRANSLATIONESE +
    CN_HOLLOW_ADJ + CN_ENV_CLICHES + CN_EMOTION_CLICHES +
    CN_ACTION_CLICHES + CN_EN_METAPHORS_PLAIN
)

# 正则禁用模式合并
ALL_REGEX_BANNED = CN_EN_METAPHORS_REGEX + CN_BANNED_OPENINGS_REGEX


# =============================================================================
# "地"字副词检测
# =============================================================================

# 非副词的"地"字词
LY_EXCEPTIONS_ZH = {
    "地", "土地", "大地", "天地", "心地", "本地",
    "外地", "草地", "野地", "腹地", "各地", "领地",
    "场地", "基地", "阵地", "驻地", "空地", "园地",
    "地方", "地图", "地址", "地铁", "地区", "地点",
    "地面", "地球", "地理", "地下", "地位", "地狱",
    "地板", "地盘", "地形", "地道", "地震", "地势",
    "地步", "地域", "地带", "地段", "地层", "地基",
}

DE_PATTERN = re.compile(
    r'(?P<word>[一-鿿]{1,4})地(?![\s，。！？…—·"''「」\)\)\]\]》>])'
)

# -ly 副词翻译式"地"字高频词
CN_LY_ADVERBS = [
    "慢慢地", "轻轻地", "悄悄地", "静静地", "渐渐地",
    "深深地", "狠狠地", "默默地", "淡淡地", "冷冷地",
    "缓缓地", "微微地", "细细地", "紧紧地看着地",
    "久久地", "远远地", "稳稳地", "重重地",
    "小心地", "温柔地", "用力地", "愤怒地",
    "悲伤地", "愉快地", "焦急地", "不安地",
    "认真地", "仔细地", "耐心地", "无奈地",
]


# =============================================================================
# 检测结果
# =============================================================================

@dataclass
class FlavorScanResult:
    """AI 味扫描结果"""
    banned_words_found: list[dict] = field(default_factory=list)
    # [{"word": "仿佛", "count": 3, "locations": ["第3段", ...]}]

    adverb_de_count: int = 0
    adverb_de_density: float = 0.0   # per 1k chars
    adverb_de_flagged: list[str] = field(default_factory=list)

    sentence_uniformity: float = 0.0  # 0-1, lower is better
    sentence_lengths: list[int] = field(default_factory=list)

    paragraph_variance: float = 0.0
    paragraph_is_uniform: bool = False

    em_dash_count: int = 0
    em_dash_density: float = 0.0     # per 500 chars

    quality_scores: dict[str, int] = field(default_factory=dict)
    quality_total: int = 0
    quality_verdict: str = ""         # "pass" | "needs_revision"

    total_chars: int = 0
    warnings: list[str] = field(default_factory=list)


# =============================================================================
# 主检测函数
# =============================================================================

def scan_text(text: str, config=None) -> FlavorScanResult:
    """对文本执行完整的 AI 味扫描

    Args:
        text: 待扫描文本
        config: AuraConfig 或 AiFlavorConfig（可选），用于读取可配置阈值。
                为 None 时使用内置默认值。
    """
    result = FlavorScanResult()
    result.total_chars = len(text)

    # 从配置读取阈值，未提供配置时使用默认值
    thresholds = _resolve_thresholds(config)

    # 1. 禁止词扫描（纯字符串）
    _scan_banned_words(text, result)

    # 1b. 禁止正则扫描（正则表达式）
    _scan_regex_patterns(text, result)

    # 2. "地"字副词密度
    _scan_adverb_de(text, result, thresholds)

    # 3. 句式均匀度
    _scan_sentence_uniformity(text, result, thresholds)

    # 4. 段落方差
    _scan_paragraph_variance(text, result, thresholds)

    # 5. 破折号密度
    _scan_em_dash(text, result, thresholds)

    # 6. 质量评分
    _score_quality(text, result, thresholds)

    return result


def _resolve_thresholds(config) -> dict:
    """从配置对象解析阈值，返回字典。config 为 None 时使用默认值。"""
    defaults = {
        "adverb_de_threshold_per_1k": 15.0,
        "uniformity_warning": 0.35,
        "paragraph_variance_warning": 0.7,
        "em_dash_max_per_500": 2,
        "quality_score_min": 35,
    }
    if config is None:
        return defaults
    # 支持传入 AuraConfig 或 AiFlavorConfig
    ai_flavor = getattr(config, "ai_flavor", config)
    return {
        "adverb_de_threshold_per_1k": getattr(ai_flavor, "adverb_de_threshold_per_1k", defaults["adverb_de_threshold_per_1k"]),
        "uniformity_warning": getattr(ai_flavor, "uniformity_warning", defaults["uniformity_warning"]),
        "paragraph_variance_warning": getattr(ai_flavor, "paragraph_variance_warning", defaults["paragraph_variance_warning"]),
        "em_dash_max_per_500": getattr(ai_flavor, "em_dash_max_per_500", defaults["em_dash_max_per_500"]),
        "quality_score_min": getattr(ai_flavor, "quality_score_min", defaults["quality_score_min"]),
    }


def _scan_banned_words(text: str, result: FlavorScanResult) -> None:
    """扫描禁用词"""
    for word in ALL_BANNED:
        count = text.count(word)
        if count > 0:
            # 找位置
            locations = []
            idx = 0
            for _ in range(min(count, 3)):  # 最多标记3处
                idx = text.find(word, idx)
                if idx >= 0:
                    # 估计段落
                    para_num = text[:idx].count('\n\n') + 1
                    locations.append(f"第{para_num}段")
                    idx += len(word)

            result.banned_words_found.append({
                "word": word,
                "count": count,
                "locations": locations,
            })

            if count > 3:
                result.warnings.append(f"禁用词 '{word}' 出现 {count} 次")


def _scan_regex_patterns(text: str, result: FlavorScanResult) -> None:
    """扫描正则禁止模式（如眼神里有X但更多的是Y、时间来到了XX等）"""
    for pattern in ALL_REGEX_BANNED:
        matches = list(re.finditer(pattern, text, re.MULTILINE))
        if matches:
            locations = []
            for m in matches[:3]:  # 最多标记3处
                para_num = text[:m.start()].count('\n\n') + 1
                locations.append(f"第{para_num}段")

            result.banned_words_found.append({
                "word": f"regex:{pattern}",
                "count": len(matches),
                "locations": locations,
            })

            if len(matches) > 3:
                result.warnings.append(f"禁用模式 '{pattern[:30]}...' 匹配 {len(matches)} 次")


def _scan_adverb_de(text: str, result: FlavorScanResult, thresholds: dict) -> None:
    """扫描'地'字副词"""
    for adv in CN_LY_ADVERBS:
        count = text.count(adv)
        if count > 0:
            result.adverb_de_count += count
            if count >= 2:
                result.adverb_de_flagged.append(f"{adv}(×{count})")

    if result.total_chars > 0:
        result.adverb_de_density = result.adverb_de_count / result.total_chars * 1000

    adverb_threshold = thresholds.get("adverb_de_threshold_per_1k", 15.0)
    if result.adverb_de_density > adverb_threshold:
        result.warnings.append(f"'地'字副词密度过高: {result.adverb_de_density:.1f}/千字 (阈值: {adverb_threshold:.1f})")


def _scan_sentence_uniformity(text: str, result: FlavorScanResult, thresholds: dict) -> None:
    """扫描句子均匀度"""
    # 按句末标点切分
    sentences = re.split(r'[。！？；\n]+', text)
    lengths = [len(s.strip()) for s in sentences if s.strip()]

    if len(lengths) < 5:
        result.sentence_uniformity = 0.0
        result.sentence_lengths = lengths
        return

    result.sentence_lengths = lengths

    mean_len = sum(lengths) / len(lengths)
    if mean_len == 0:
        result.sentence_uniformity = 0.0
        return

    deviations = [abs(l - mean_len) for l in lengths]
    avg_deviation = sum(deviations) / len(deviations)
    result.sentence_uniformity = 1.0 - min(avg_deviation / mean_len, 1.0)

    uniformity_warn = thresholds.get("uniformity_warning", 0.35)
    if result.sentence_uniformity > uniformity_warn:
        result.warnings.append(f"句子长度过于均匀 (uniformity={result.sentence_uniformity:.2f}, 阈值: {uniformity_warn})")


def _scan_paragraph_variance(text: str, result: FlavorScanResult, thresholds: dict) -> None:
    """扫描段落长度方差"""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    if len(paragraphs) < 3:
        return

    # 每段句子数
    para_lengths = []
    for para in paragraphs:
        sentences = re.split(r'[。！？]+', para)
        sent_count = len([s for s in sentences if s.strip()])
        para_lengths.append(sent_count)

    if len(para_lengths) < 3 or sum(para_lengths) == 0:
        return

    mean = sum(para_lengths) / len(para_lengths)
    if mean == 0:
        return

    # 计算在 ±1 句范围内的段落比例
    within_one = sum(1 for l in para_lengths if abs(l - mean) <= 1)
    result.paragraph_variance = within_one / len(para_lengths)
    para_warn = thresholds.get("paragraph_variance_warning", 0.7)
    result.paragraph_is_uniform = result.paragraph_variance > para_warn

    if result.paragraph_is_uniform:
        result.warnings.append(f"段落长度过于均匀 ({result.paragraph_variance:.0%} 在±1句范围内, 阈值: {para_warn:.0%})")


def _scan_em_dash(text: str, result: FlavorScanResult, thresholds: dict) -> None:
    """扫描破折号密度"""
    result.em_dash_count = text.count('——')
    if result.total_chars > 0:
        result.em_dash_density = result.em_dash_count / result.total_chars * 500
    em_dash_max = thresholds.get("em_dash_max_per_500", 2)
    if result.em_dash_density > em_dash_max:
        result.warnings.append(f"破折号密度过高: {result.em_dash_density:.1f}/500字 (阈值: {em_dash_max})")


def _score_quality(text: str, result: FlavorScanResult, thresholds: dict) -> None:
    """stop-slop 风格 50 分质量评分"""
    scores = {}

    # Directness (0-10): 有没有绕弯子
    cliche_count = sum(
        text.count(w) for w in CN_AI_CLICHES + CN_TRANSLATIONESE
    )
    scores["directness"] = max(0, 10 - cliche_count)

    # Rhythm (0-10): 句长变化
    if result.sentence_lengths and len(result.sentence_lengths) >= 5:
        scores["rhythm"] = max(0, int(10 - result.sentence_uniformity * 10))
    else:
        scores["rhythm"] = 7

    # Trust (0-10): 像不像 AI
    banned_count = sum(item["count"] for item in result.banned_words_found)
    scores["trust"] = max(0, 10 - banned_count // 2)

    # Authenticity (0-10): 自然程度
    trans_count = sum(text.count(w) for w in CN_TRANSLATIONESE)
    scores["authenticity"] = max(0, 10 - trans_count)

    # Density (0-10): 信息密度
    hollow_count = sum(text.count(w) for w in CN_HOLLOW_ADJ)
    scores["density"] = max(0, 10 - hollow_count)

    result.quality_scores = scores
    result.quality_total = sum(scores.values())

    quality_min = thresholds.get("quality_score_min", 35)
    if result.quality_total < quality_min:
        result.quality_verdict = "needs_revision"
    else:
        result.quality_verdict = "pass"


def format_scan_report(result: FlavorScanResult) -> str:
    """格式化扫描报告"""
    lines = ["=== AI 味扫描报告 ===", ""]

    lines.append(f"文本长度: {result.total_chars} 字")
    lines.append("")

    # 禁用词
    if result.banned_words_found:
        lines.append("【禁用词/句式】")
        for item in result.banned_words_found:
            lines.append(f"  ✗ {item['word']} ×{item['count']} ({', '.join(item['locations'])})")
        lines.append("")
    else:
        lines.append("【禁用词/句式】✓ 未发现")
        lines.append("")

    # 副词密度
    lines.append(f"【'地'字副词密度】{result.adverb_de_density:.1f}/千字")
    if result.adverb_de_flagged:
        lines.append(f"  标记: {', '.join(result.adverb_de_flagged)}")
    lines.append("")

    # 句式均匀度
    lines.append(f"【句式均匀度】{result.sentence_uniformity:.2f} (0=变化丰富, 1=完全均匀)")
    lines.append("")

    # 段落方差
    lines.append(f"【段落长度均匀度】{result.paragraph_variance:.0%} 段落长度趋同")
    lines.append("")

    # 破折号
    lines.append(f"【破折号密度】{result.em_dash_density:.1f}/500字")
    lines.append("")

    # 质量评分
    lines.append("【质量评分 (50分制)】")
    for dim, score in result.quality_scores.items():
        dim_names = {
            "directness": "直接性", "rhythm": "节奏感",
            "trust": "可信度", "authenticity": "真实感", "density": "信息密度",
        }
        lines.append(f"  {dim_names.get(dim, dim)}: {score}/10")
    lines.append(f"  总分: {result.quality_total}/50 — {result.quality_verdict}")
    lines.append("")

    # 警告
    if result.warnings:
        lines.append("【警告】")
        for w in result.warnings:
            lines.append(f"  ⚠ {w}")

    return "\n".join(lines)
