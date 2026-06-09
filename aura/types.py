"""
AuraWritingAgent — 核心数据模型

所有 Agent 共享的数据类型定义。
使用 Pydantic v2 进行数据验证和序列化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# 枚举类型
# =============================================================================


class Severity(str, Enum):
    """审稿问题严重程度"""
    CRITICAL = "critical"    # 阻塞审批，必须修复
    MODERATE = "moderate"    # 应该修复
    MINOR = "minor"          # 可以改进但不强制


class InstructionPriority(str, Enum):
    """用户指令优先级"""
    CRITICAL = "critical"    # 一票否决级
    MODERATE = "moderate"    # 重要但可商榷
    MINOR = "minor"          # 建议级


class StyleType(str, Enum):
    """风格类型"""
    CONVENTIONAL = "conventional"
    UNCONVENTIONAL = "unconventional"
    MIXED = "mixed"


class Language(str, Enum):
    """语言"""
    ZH = "zh"
    EN = "en"
    AUTO = "auto"


class Provider(str, Enum):
    """API 提供商"""
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"


class Strictness(str, Enum):
    """审稿严格度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CheckMethod(str, Enum):
    """检查方式"""
    RULE = "rule"
    LLM = "LLM"
    RULE_LLM = "rule+LLM"


# =============================================================================
# 风格系统数据模型
# =============================================================================


class SentenceLengthProfile(BaseModel):
    """句长分布"""
    mean_chars: float = 0
    median_chars: float = 0
    stddev: float = 0
    distribution: dict[str, float] = Field(default_factory=lambda: {
        "ultra_short_1_5": 0,
        "short_6_15": 0,
        "medium_16_30": 0,
        "long_31_60": 0,
        "extended_60_plus": 0,
    })
    fluctuation_pattern: str = ""


class SentenceStructureProfile(BaseModel):
    """句式结构"""
    simple_pct: float = 0
    compound_pct: float = 0
    complex_pct: float = 0
    fragment_pct: float = 0
    subject_dropping_rate: float = 0
    inversion_frequency_per_1k: float = 0
    shi_de_emphasis_per_1k: float = 0
    ba_vs_bei_ratio: str = "0:0"
    you_existential_per_1k: float = 0
    serial_verb_pct: float = 0
    pivotal_construction_pct: float = 0


class PunctuationFingerprint(BaseModel):
    """标点指纹"""
    comma_density_per_1k: float = 0
    period_density_per_1k: float = 0
    semicolon_usage: str = "rare"
    ellipsis_density_per_1k: float = 0
    em_dash_density_per_1k: float = 0
    exclamation_density_per_1k: float = 0
    quote_style: str = ""
    sentence_final_particles: dict[str, float] = Field(default_factory=dict)


class VocabularyProfile(BaseModel):
    """词汇特征"""
    cttr: float = 0
    tier: str = "mixed"
    top_30_words: list[str] = Field(default_factory=list)
    preferred_transitions: list[str] = Field(default_factory=list)
    avoided_transitions: list[str] = Field(default_factory=list)
    idiom_density_per_1k: float = 0
    dialect_colloquial_pct: float = 0
    classical_chinese_pct: float = 0
    internet_slang_pct: float = 0
    loanword_pct: float = 0
    color_word_density_per_1k: float = 0
    color_preferences: list[str] = Field(default_factory=list)
    body_part_density_per_1k: float = 0
    body_part_preferences: list[str] = Field(default_factory=list)
    concrete_vs_abstract_noun_ratio: str = "0:0"
    jargon_density_per_1k: float = 0


class DialogueProfile(BaseModel):
    """对话风格"""
    tag_style: str = ""
    said_asked_pct: float = 0
    action_beat_instead_of_tag_pct: float = 0
    adverb_tag_pct: float = 0
    direct_speech_ratio: float = 0
    avg_turns_per_scene: float = 0
    subtext_density: str = ""
    dialogue_quotes_style: str = ""


class ParagraphProfile(BaseModel):
    """段落特征"""
    avg_sentences_per_paragraph: float = 0
    length_variance: float = 0
    common_openers: list[str] = Field(default_factory=list)
    rare_openers: list[str] = Field(default_factory=list)
    opener_distribution: dict[str, float] = Field(default_factory=dict)


class NarrativeDistanceProfile(BaseModel):
    """叙事距离"""
    type: str = ""
    interiority_signals: list[str] = Field(default_factory=list)
    authorial_intrusion_frequency: float = 0
    free_indirect_speech_per_1k: float = 0
    psychic_distance_shifts_per_1k: float = 0
    metanarrative_markers_per_1k: float = 0
    reader_address_per_1k: float = 0


class RegisterAndVoiceProfile(BaseModel):
    """语域与声线"""
    narrator_person: str = ""
    narrator_visibility: str = ""
    slang_jargon_density_per_1k: float = 0
    honorific_humble_density_per_1k: float = 0
    profanity_density_per_1k: float = 0
    colloquial_filler_density_per_1k: float = 0


class SensoryProfile(BaseModel):
    """感官描写"""
    details_per_1000_chars: float = 0
    sense_distribution: dict[str, float] = Field(default_factory=lambda: {
        "视觉": 0, "听觉": 0, "触觉": 0, "嗅觉": 0, "味觉": 0,
    })


class RhetoricProfile(BaseModel):
    """修辞特征"""
    simile_metaphor_per_1k: float = 0
    simile_breakdown: dict[str, float] = Field(default_factory=dict)
    personification_per_1k: float = 0
    synaesthesia_per_1k: float = 0
    repetition_per_1k: float = 0
    antithesis_per_1k: float = 0
    allusion_per_1k: float = 0
    irony_per_1k: float = 0


class RhythmProfile(BaseModel):
    """节奏特征"""
    quad_syllabic_density_per_1k: float = 0
    reduplication_per_1k: float = 0
    reduplication_breakdown: dict[str, float] = Field(default_factory=dict)
    parallelism_per_1k: float = 0
    short_sentence_bursts_per_1k: float = 0
    long_sentence_extended_per_1k: float = 0


class DiscourseProfile(BaseModel):
    """语篇组织"""
    scene_transition_distribution: dict[str, float] = Field(default_factory=dict)
    time_jump_frequency: str = ""
    flashback_density_per_1k: float = 0
    chapter_ending_patterns: dict[str, float] = Field(default_factory=dict)
    chapter_opening_patterns: dict[str, float] = Field(default_factory=dict)


class ToneProfile(BaseModel):
    """语调"""
    primary: str = ""
    markers: list[str] = Field(default_factory=list)
    humor_type: str = ""
    emotional_regulation: str = ""
    language_temperature: str = ""
    texture: str = ""
    emotional_presentation: str = ""


class GenreSpecificProfile(BaseModel):
    """题材特征"""
    genre: str = ""
    action_pacing: str = ""
    cultivation_descriptions: str = ""
    power_fantasy_delivery: str = ""


class HyperboleAbsurdismProfile(BaseModel):
    """夸大/荒诞修辞"""
    absurd_claim_density_per_1k: float = 0
    numerical_exaggeration_per_1k: float = 0
    extreme_comparison_per_1k: float = 0
    self_aggrandize_vs_self_deprecate_ratio: str = "0:0"
    absurdity_level: str = "none"


class RegisterCollisionProfile(BaseModel):
    """语域碰撞"""
    collision_density_per_1k: float = 0
    register_distribution: dict[str, float] = Field(default_factory=dict)
    collision_pattern: str = "none"


class NarratorPerformativityProfile(BaseModel):
    """叙事者表演性"""
    self_reference_per_1k: float = 0
    direct_reader_address_per_1k: float = 0
    emotional_outburst_per_1k: float = 0
    meta_commentary_per_1k: float = 0
    emotional_volatility: str = "stable"
    narrator_character_distance: str = ""


class SubcultureMarkersProfile(BaseModel):
    """圈层梗"""
    subculture_reference_density_per_1k: float = 0
    circle_source_distribution: dict[str, float] = Field(default_factory=dict)
    reference_usage_style: str = ""
    outsider_readability: str = ""


class CatchphrasePatternsProfile(BaseModel):
    """口头禅/反复句式"""
    catchphrase_density_per_1k: float = 0
    signature_phrases: list[dict[str, Any]] = Field(default_factory=list)
    catchphrase_variation: str = ""
    catchphrase_function: list[str] = Field(default_factory=list)

    @field_validator("signature_phrases", mode="before")
    @classmethod
    def coerce_strings_to_dicts(cls, v: Any) -> list[dict[str, Any]]:
        """接受 ['字符串', ...] 或 [{'phrase': '...', ...}, ...] 两种格式"""
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"phrase": item, "frequency_per_1k": 0.0, "function": ""})
            elif isinstance(item, dict):
                result.append(item)
            else:
                result.append({"phrase": str(item), "frequency_per_1k": 0.0, "function": ""})
        return result


class NonTextSymbolsProfile(BaseModel):
    """非文字符号嵌入"""
    latex_math_density_per_1k: float = 0
    code_snippet_density_per_1k: float = 0
    emoji_kaomoji_density_per_1k: float = 0
    special_formatting_density_per_1k: float = 0
    zh_en_code_mixing_density_per_1k: float = 0


class SpecialDiscourseStructureProfile(BaseModel):
    """特种语篇结构"""
    timestamp_as_structure: bool = False
    timestamp_format: Optional[str] = None
    chapter_heading_style: str = ""
    inter_paragraph_jump_style: str = ""
    non_narrative_insertion_per_1k: float = 0


class ExtremeAffectProfile(BaseModel):
    """极端情感"""
    extreme_emotion_word_density_per_1k: float = 0
    contempt_superiority_per_1k: float = 0
    self_mockery_per_1k: float = 0
    attitude_reversal_frequency: str = "none"
    universal_dismissal_pattern: str = "none"


class UnconventionalStyleMarkers(BaseModel):
    """非常规风格标记——捕获主流文学分析无法覆盖的维度"""
    style_type: StyleType = StyleType.CONVENTIONAL
    style_subtype: list[str] = Field(default_factory=list)
    absurdity_baseline: str = "none"
    hyperbole_absurdism: HyperboleAbsurdismProfile = Field(default_factory=HyperboleAbsurdismProfile)
    register_collision: RegisterCollisionProfile = Field(default_factory=RegisterCollisionProfile)
    narrator_performativity: NarratorPerformativityProfile = Field(default_factory=NarratorPerformativityProfile)
    subculture_markers: SubcultureMarkersProfile = Field(default_factory=SubcultureMarkersProfile)
    catchphrase_patterns: CatchphrasePatternsProfile = Field(default_factory=CatchphrasePatternsProfile)
    non_text_symbols: NonTextSymbolsProfile = Field(default_factory=NonTextSymbolsProfile)
    special_discourse_structure: SpecialDiscourseStructureProfile = Field(default_factory=SpecialDiscourseStructureProfile)
    extreme_affect: ExtremeAffectProfile = Field(default_factory=ExtremeAffectProfile)


# =============================================================================
# 风格语料库
# =============================================================================


class StyleCorpusEntry(BaseModel):
    """单条语料条目"""
    category: str              # 所属类别
    original: str              # 原文
    char_count: int = 0
    feature_note: str = ""     # 为什么被选中
    usage: str = ""            # Writer 应如何参考
    context: str = ""          # 可选的上下文


class StyleCorpus(BaseModel):
    """风格语料库——Writer 和 Reviewer 共享的原文锚点"""
    total_entries: int = 0
    sentence_templates: list[StyleCorpusEntry] = Field(default_factory=list)
    functional_sentences: list[StyleCorpusEntry] = Field(default_factory=list)
    signature_phrases: list[StyleCorpusEntry] = Field(default_factory=list)
    paragraph_rhythm_samples: list[StyleCorpusEntry] = Field(default_factory=list)
    register_collision_samples: list[StyleCorpusEntry] = Field(default_factory=list)
    dialogue_monologue_samples: list[StyleCorpusEntry] = Field(default_factory=list)

    @property
    def all_entries(self) -> list[StyleCorpusEntry]:
        """获取所有条目"""
        return (
            self.sentence_templates
            + self.functional_sentences
            + self.signature_phrases
            + self.paragraph_rhythm_samples
            + self.register_collision_samples
            + self.dialogue_monologue_samples
        )


# =============================================================================
# 风格档案
# =============================================================================


class StyleProfileMeta(BaseModel):
    """风格档案元信息"""
    profile_name: str = ""
    source_texts: list[str] = Field(default_factory=list)
    total_chars_analyzed: int = 0
    created_at: str = ""
    version: str = "2.0"


class StyleProfile(BaseModel):
    """完整的风格档案"""
    meta: StyleProfileMeta = Field(default_factory=StyleProfileMeta)
    sentence_length: SentenceLengthProfile = Field(default_factory=SentenceLengthProfile)
    sentence_structure: SentenceStructureProfile = Field(default_factory=SentenceStructureProfile)
    punctuation_fingerprint: PunctuationFingerprint = Field(default_factory=PunctuationFingerprint)
    vocabulary: VocabularyProfile = Field(default_factory=VocabularyProfile)
    dialogue: DialogueProfile = Field(default_factory=DialogueProfile)
    paragraphs: ParagraphProfile = Field(default_factory=ParagraphProfile)
    narrative_distance: NarrativeDistanceProfile = Field(default_factory=NarrativeDistanceProfile)
    register_and_voice: RegisterAndVoiceProfile = Field(default_factory=RegisterAndVoiceProfile)
    sensory_profile: SensoryProfile = Field(default_factory=SensoryProfile)
    rhetoric: RhetoricProfile = Field(default_factory=RhetoricProfile)
    rhythm: RhythmProfile = Field(default_factory=RhythmProfile)
    discourse: DiscourseProfile = Field(default_factory=DiscourseProfile)
    tone: ToneProfile = Field(default_factory=ToneProfile)
    genre_specific: GenreSpecificProfile = Field(default_factory=GenreSpecificProfile)
    unconventional_style_markers: UnconventionalStyleMarkers = Field(default_factory=UnconventionalStyleMarkers)
    style_corpus: StyleCorpus = Field(default_factory=StyleCorpus)
    voice_description: str = ""

    @classmethod
    def load(cls, path: Path) -> "StyleProfile":
        """从 JSON 文件加载"""
        import json
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate(json.load(f))

    def save(self, path: Path) -> None:
        """保存为 JSON 文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2, ensure_ascii=False))


# =============================================================================
# 写作任务
# =============================================================================


class WritingTask(BaseModel):
    """用户的写作任务定义"""
    # 情节与大纲
    scene_outline: str = ""                          # 场景/情节大纲（自由文本）
    beats: list[str] = Field(default_factory=list)   # 必须覆盖的情节节拍

    # 角色
    characters: list[dict[str, Any]] = Field(default_factory=list)
    # 每个角色: {name, personality_keywords, behavioral_constraints,
    #             language_style, knowledge_boundary, ...}

    # 视角与叙事
    pov_type: str = ""           # 第一人称 / 第三人称限制 / 第三人称全知 / 第二人称
    pov_character: str = ""      # POV 角色名（第三人称限制时必填）
    tense: str = ""              # 过去时 / 现在时

    # 字数与格式
    target_word_count_min: int = 0
    target_word_count_max: int = 0

    # 约束
    must_include: list[str] = Field(default_factory=list)   # 必须包含的元素
    must_avoid: list[str] = Field(default_factory=list)     # 必须避免的元素
    dialogue_constraints: list[str] = Field(default_factory=list)
    setting_constraints: list[str] = Field(default_factory=list)
    format_constraints: list[str] = Field(default_factory=list)

    # 前情
    continuity_context: str = ""            # 前文摘要（文本）
    previous_chapter_file: str = ""         # 前文章节文件路径（单个，兼容旧版）
    previous_chapter_files: list[str] = Field(default_factory=list)  # 前文章节文件路径（多个）

    # 元数据
    genre: str = ""
    language: Language = Language.ZH


# =============================================================================
# 审稿系统
# =============================================================================


class InstructionItem(BaseModel):
    """用户给出的单条写作指令，从 WritingTask 解析而来"""
    id: str
    category: str           # POV / PLOT / CHARACTER / DIALOGUE / SETTING / FORMAT
    description: str
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    priority: InstructionPriority = InstructionPriority.MODERATE
    check_method: CheckMethod = CheckMethod.LLM


class InstructionComplianceResult(BaseModel):
    """单条指令的审稿结果"""
    instruction: InstructionItem
    passed: bool = False
    score: int = 0                               # 0-100
    found: list[str] = Field(default_factory=list)       # 正面证据
    missing: list[str] = Field(default_factory=list)     # 缺失项
    violations: list[str] = Field(default_factory=list)  # 违规项
    locations: list[str] = Field(default_factory=list)   # 相关位置
    suggestion: str = ""


class ReviewIssue(BaseModel):
    """审稿中发现的问题 —— 扣分制，每个问题绑定一个 fix"""
    dimension: str           # "I1"-"I12" | "F1"-"F5" | "Q1"-"Q3" | "S1"-"S16"
    dimension_name: str = ""
    layer: str = ""          # "instruction" | "flavor" | "quality" | "style_aligned"
    severity: Severity = Severity.MODERATE
    deduction: int = 0       # 扣分值（5/10/15/20/25/30）
    location: str = ""       # 初稿中的位置引用
    issue: str = ""
    suggestion: str = ""     # fix 建议

    @field_validator("location", mode="before")
    @classmethod
    def coerce_list_to_str(cls, v: Any) -> str:
        """接受 ['...'] 或 '...' 两种格式"""
        if isinstance(v, list):
            return "; ".join(str(x) for x in v)
        return str(v) if v else ""


class StyleAlignedRule(BaseModel):
    """从 StyleProfile 动态生成的单条风格对齐审稿规则"""
    dimension: str
    name: str
    reference_value: dict[str, Any] = Field(default_factory=dict)
    tolerance: dict[str, Any] = Field(default_factory=dict)
    scoring: dict[str, Any] = Field(default_factory=dict)
    check_method: CheckMethod = CheckMethod.RULE


class StyleAlignmentResult(BaseModel):
    """某条风格对齐规则的审稿结果"""
    rule: StyleAlignedRule | None = None
    score: int = 0
    deviation_level: str = "within"   # "within" | "minor" | "moderate" | "critical"
    actual_value: dict[str, Any] = Field(default_factory=dict)
    deviation_detail: str = ""
    suggestions: list[str] = Field(default_factory=list)


class ReviewReport(BaseModel):
    """完整的审稿报告"""
    # 指令遵从
    instruction_results: list[InstructionComplianceResult] = Field(default_factory=list)
    instruction_blocked: bool = False

    # AI味
    flavor_scores: dict[str, int] = Field(default_factory=dict)   # F1-F5

    # 叙事质量
    quality_scores: dict[str, int] = Field(default_factory=dict)  # Q1-Q3

    # 风格对齐
    style_alignment_results: list[StyleAlignmentResult] = Field(default_factory=list)

    # 综合
    composite_score: float = 0
    all_issues: list[ReviewIssue] = Field(default_factory=list)
    critical_issues: list[ReviewIssue] = Field(default_factory=list)
    passed: bool = False
    overall_assessment: str = ""
    revision_priority: list[str] = Field(default_factory=list)


# =============================================================================
# 配置
# =============================================================================


class ModelConfig(BaseModel):
    """模型配置"""
    provider: Provider = Provider.ANTHROPIC
    # Anthropic models
    writer: str = "claude-sonnet-4-20250514"
    reviewer: str = "claude-sonnet-4-20250514"
    reviser: str = "claude-sonnet-4-20250514"
    style_analyzer: str = "claude-sonnet-4-20250514"
    # DeepSeek models (used when provider=deepseek)
    # deepseek-v4-pro (thinking), deepseek-v4-flash (fast)
    deepseek_writer: str = "deepseek-v4-pro"
    deepseek_reviewer: str = "deepseek-v4-pro"
    deepseek_reviser: str = "deepseek-v4-pro"
    deepseek_style_analyzer: str = "deepseek-v4-pro"
    # API configuration
    api_key: str = ""
    anthropic_base_url: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/anthropic"


class ReviewConfig(BaseModel):
    """审稿配置"""
    max_iterations: int = 3
    auto_approve_threshold: int = 85
    strictness: Strictness = Strictness.HIGH
    language: Language = Language.ZH
    style_compliance_min_per_dim: int = 50


class AiFlavorConfig(BaseModel):
    """AI味检测配置"""
    sensitivity: str = "medium"
    adverb_de_threshold_per_1k: float = 8.0
    uniformity_warning: float = 0.35
    em_dash_max_per_500: int = 1
    paragraph_variance_warning: float = 0.7
    quality_score_min: int = 35
    banned_words_max_per_3k: int = 1


class WritingConfig(BaseModel):
    """写作配置"""
    temperature: float = 0.75
    max_tokens: int = 16384
    extended_thinking: bool = True
    thinking_budget: int = 4000


class OutputConfig(BaseModel):
    """输出配置"""
    format: str = "plain"
    save_drafts: bool = True
    drafts_dir: str = "./drafts"


class StyleConfig(BaseModel):
    """风格配置"""
    profile_cache_dir: str = "./profiles"
    min_reference_chars: int = 3000
    profile_path: Optional[str] = None
    reference_texts: list[str] = Field(default_factory=list)
    auto_analyze: bool = True


class AuraConfig(BaseModel):
    """顶层配置"""
    model: ModelConfig = Field(default_factory=ModelConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    ai_flavor: AiFlavorConfig = Field(default_factory=AiFlavorConfig)
    writing: WritingConfig = Field(default_factory=WritingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    style: StyleConfig = Field(default_factory=StyleConfig)


# =============================================================================
# API 响应
# =============================================================================


class CostInfo(BaseModel):
    """API 费用信息"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_cost_usd: float = 0.0


class AgentResponse(BaseModel):
    """Agent 通用响应"""
    text: str
    cost: CostInfo = Field(default_factory=CostInfo)
    raw_response: Optional[Any] = None
