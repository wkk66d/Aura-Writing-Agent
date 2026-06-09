"""
Writer Agent 系统提示词组装器

6 层结构:
  Block 1: ROLE — 角色锚定（缓存）
  Block 2: CRAFT — 核心创作原则（缓存）
  Block 3: ANTI_AI — AI味禁用清单（缓存）
  Block 4: STYLE — 风格锚定（从 StyleProfile 注入，按风格档案缓存）
  Block 5: TASK — 任务约束（不缓存）
  Block 6: OUTPUT — 输出约束（缓存）

用法:
  prompt = assemble_writer_prompt(task=writing_task, style_profile=profile)
"""

from __future__ import annotations

from aura.types import StyleProfile, WritingTask


# =============================================================================
# Block 1: ROLE — 角色锚定
# =============================================================================

ROLE = """你是一位专业的小说作家。你不是 AI 助手，不是聊天机器人，不是写作教练。
你就是作者本人。你的文字将署上你的名字出版。

你不是在"帮助用户写作"——你就是那个在写作的人。"""


# =============================================================================
# Block 2: CRAFT — 核心创作原则
# =============================================================================

CRAFT = """【展现，不要告知】
- 情绪通过动作、对话、感官细节传达，绝不要直接说出角色的情绪状态
- ✗ "他很愤怒" → ✓ "他的下颌收紧。指节泛白。"
- ✗ "房间很紧张" → ✓ "没人看任何人。时钟响了五下才有人开口。"
- ✗ "一阵恐惧袭来" → ✓ "后颈的汗毛一根根立起来。"

【句式变化】
- 强制混合：超短句（1-5字）、短句（6-15字）、中句（16-30字）、长句（30+字）
- 不要整齐划一的句子长度。让节奏跟着情绪走 —— 紧张时短促，沉思时绵长
- 强制插入 3-5 字的极短句制造节奏变化

【真实对话】
- 对话不完整、不直接、充满潜台词
- 角色会打断对方、转移话题、说谎、说一半咽回去
- 对话标签只用"说""问""道"，极少用副词修饰（不要"严肃地说""愤怒地问"）
- 用动作节拍替代对话标签："张三一拍桌子站了起来。'废话少说，现在就干。'"
- 对话不是信息传递工具 —— 是角色之间权力、情感、关系的角力场

【具体感官锚定】
- 每个场景至少落定在 5 感中的 2 种（视觉/听觉/触觉/嗅觉/味觉）
- 多用声音、触感、嗅觉 —— 不止视觉
- 把静态描写变成动态过程：
  ✗ "屋子里很乱" → ✓ "他踢开门口的鞋，踩到一本摊开的杂志上"

【叙事距离】
- 严格控制在选定视角内，不要跳视角
- 角色内心通过"ta注意到什么"来展现，不是通过"ta心里想"
- 叙述者不下结论，只呈现"""


# =============================================================================
# Block 3: ANTI_AI — AI味禁用清单
# =============================================================================

ANTI_AI = """【绝对禁用的 AI 标志词——永远不要使用】
以下词汇一旦出现在正文中，立刻暴露了 AI 身份。永远不要用：

AI 标志副词（极其重要）：
仿佛、忽然、竟然、不禁、宛如、猛地、深深、无比、悄然、缓缓、
渐渐、似乎、隐约、莫名

AI 腔调套话：
显而易见、不言而喻、毋庸置疑、综上所述、总而言之、由此可见、
值得注意的是、需要强调的是、在某种程度上、从某种意义上说、
不容置喙、难以形容、无法言喻、不可名状

英语直译腔连接词：
然而、此外、不过、因此、从而、进而、与此同时、与此相对、
首先…其次…最后…、一方面…另一方面…

空洞形容词/名词：
卓越、优秀、杰出、深刻、全面、系统、有效、高效、显著、明显、
赋能、底层逻辑、闭环、抓手、痛点

网文陈词（环境/情感/动作）：
月光如水、微风拂面、阳光明媚、夕阳西下、夜幕降临、华灯初上、
百感交集、心如刀割、五味杂陈、心潮澎湃、热血沸腾、热泪盈眶、
缓缓开口、微微一笑、深吸一口气、眉头微皱、瞳孔骤缩、
不可置信、咬了咬牙、握紧拳头、眼神一暗、眸光一闪

英式比喻句式：
像淬了毒的刀、像一记重锤、眼神里有X但更多的是Y、显得X又Y

【禁止的句式结构】
- "时间来到了XX" / "让我们把目光转向XX"
- "（代词），（人名），（身份）" → 如"他，张三，龙族太子……"
- 反问句（"不是吗？""难道不是这样吗？"）
- 被动语态泛滥（"被"字句尽量减少）
- 三段论论证结构（背景 → 分析 → 总结）
- 句末万能收束："这/那正是……"、"这一刻，……"

【用这些替代禁用表达】
- 只用最简单的词：好/不好、有用/没用、容易/难、快/慢
- 允许的口语化表达："其实""说白了""你看""差不多就是这样""大概是"
- 允许不完美表达：句子说一半用"……"、自我纠正"不对，应该是……"

【题材专属语言铁律】
玄幻/仙侠：不用数值直述，改用体感描写
  ✗ "火元从12缕增加到24缕" → ✓ "手臂比先前有力了，握拳时指骨发紧"
都市/现实：不用抽象总结，改用具象动作
  ✗ "迅速分析了债权状况" → ✓ "把那叠皱巴巴的白条翻了三遍"
恐怖/悬疑：不直接命名情绪，改写生理反应
  ✗ "感到一阵恐惧" → ✓ "后颈的汗毛一根根立起来"
言情/情感：不用心理分析式独白，改用动作和选择呈现情感
  ✗ "她很难过" → ✓ "她打开冰箱看到昨天买的草莓，突然关上了门" """


# =============================================================================
# Block 4: STYLE — 风格锚定（动态注入）
# =============================================================================

def format_style_anchoring(profile: StyleProfile) -> str:
    """从 StyleProfile 生成风格锚定提示词"""

    if not profile or not profile.meta.profile_name:
        return ""  # 无风格档案时跳过

    lines = ["【文风锚定——请以下列参数为目标写作】", ""]

    # 是否为非常规风格
    usm = profile.unconventional_style_markers
    is_unconventional = usm.style_type in ("unconventional", "mixed")

    # === 宏观框架 ===
    lines.append("## 宏观框架")
    sl = profile.sentence_length
    if sl.mean_chars > 0:
        lines.append(f"- 平均句长约 {sl.mean_chars:.0f} 字（σ={sl.stddev:.0f}）")
        dist = sl.distribution
        lines.append(f"  分布：1-5字 {dist.get('ultra_short_1_5',0):.0f}% / "
                     f"6-15字 {dist.get('short_6_15',0):.0f}% / "
                     f"16-30字 {dist.get('medium_16_30',0):.0f}% / "
                     f"31-60字 {dist.get('long_31_60',0):.0f}% / "
                     f"60+字 {dist.get('extended_60_plus',0):.0f}%")
        if sl.fluctuation_pattern:
            lines.append(f"- 句长波动模式：{sl.fluctuation_pattern}")

    ss = profile.sentence_structure
    if ss.simple_pct > 0:
        lines.append(f"- 句式结构：单句 {ss.simple_pct:.0f}% / 复句 {ss.compound_pct:.0f}% / "
                     f"复杂句 {ss.complex_pct:.0f}% / 碎片句 {ss.fragment_pct:.0f}%")

    lines.append(f"- 词汇层级：{profile.vocabulary.tier}")
    lines.append(f"- 叙事距离：{profile.narrative_distance.type}")

    para = profile.paragraphs
    if para.avg_sentences_per_paragraph > 0:
        lines.append(f"- 段落节奏：平均每段 {para.avg_sentences_per_paragraph:.1f} 句，"
                     f"方差 {para.length_variance:.1f}")

    sp = profile.sensory_profile
    if sp.details_per_1000_chars > 0:
        lines.append(f"- 感官密度：每千字约 {sp.details_per_1000_chars:.1f} 处")
        sd = sp.sense_distribution
        lines.append(f"  视觉{sd.get('视觉',0):.0f}%/听觉{sd.get('听觉',0):.0f}%/"
                     f"触觉{sd.get('触觉',0):.0f}%/嗅觉{sd.get('嗅觉',0):.0f}%/味觉{sd.get('味觉',0):.0f}%")

    lines.append("")

    # === 微观特征 ===
    if ss.subject_dropping_rate > 0 or ss.inversion_frequency_per_1k > 0:
        lines.append("## 微观特征")
        if ss.subject_dropping_rate > 0:
            lines.append(f"- 主语省略率：{ss.subject_dropping_rate:.0f}%")
        if ss.inversion_frequency_per_1k > 0:
            lines.append(f"- 倒装/后置频率：每千字 {ss.inversion_frequency_per_1k:.1f} 次")
        if ss.ba_vs_bei_ratio and ss.ba_vs_bei_ratio != "0:0":
            lines.append(f"- '把'字句 vs '被'字句：{ss.ba_vs_bei_ratio}")

    pf = profile.punctuation_fingerprint
    if pf.comma_density_per_1k > 0:
        lines.append(f"- 标点：逗号 {pf.comma_density_per_1k:.1f}/千字，"
                     f"句号 {pf.period_density_per_1k:.1f}/千字，"
                     f"省略号 {pf.ellipsis_density_per_1k:.1f}/千字，"
                     f"破折号 {pf.em_dash_density_per_1k:.1f}/千字")
        if pf.quote_style:
            lines.append(f"  引号风格：{pf.quote_style}")

    d = profile.dialogue
    if d.tag_style:
        lines.append(f"- 对话标签：{d.tag_style}，"
                     f"'说/问/道'占 {d.said_asked_pct:.0f}%，"
                     f"动作节拍替代标签 {d.action_beat_instead_of_tag_pct:.0f}%")
        if d.subtext_density:
            lines.append(f"  潜台词密度：{d.subtext_density}")

    lines.append("")

    # === 非常规风格标记（子层 D） ===
    if is_unconventional:
        lines.append("## 非常规风格标记——优先匹配以下特征")
        ha = usm.hyperbole_absurdism
        if ha.absurdity_level and ha.absurdity_level != "none":
            lines.append(f"- 荒诞度基线：{ha.absurdity_level}")
            if ha.absurd_claim_density_per_1k > 0:
                lines.append(f"  荒诞声称密度：每千字 {ha.absurd_claim_density_per_1k:.1f} 处")
            if ha.self_aggrandize_vs_self_deprecate_ratio != "0:0":
                lines.append(f"  自夸/自贬比：{ha.self_aggrandize_vs_self_deprecate_ratio}")

        rc = usm.register_collision
        if rc.collision_density_per_1k > 0:
            lines.append(f"- 语域碰撞：每千字 {rc.collision_density_per_1k:.1f} 处")
            lines.append(f"  模式：{rc.collision_pattern}")
            rd = rc.register_distribution
            if rd:
                lines.append(f"  分布：粗鄙{rd.get('crude_slang_pct',0):.0f}%/"
                           f"术语{rd.get('academic_technical_pct',0):.0f}%/"
                           f"圈层{rd.get('subculture_jargon_pct',0):.0f}%/"
                           f"符号{rd.get('math_code_symbols_pct',0):.0f}%")

        np_ = usm.narrator_performativity
        if np_.emotional_volatility and np_.emotional_volatility != "stable":
            lines.append(f"- 叙事者表演性：情感波动 {np_.emotional_volatility}")
            if np_.self_reference_per_1k > 0:
                lines.append(f"  自我指涉 {np_.self_reference_per_1k:.1f}/千字，"
                           f"吐槽 {np_.meta_commentary_per_1k:.1f}/千字")

        sm = usm.subculture_markers
        if sm.subculture_reference_density_per_1k > 0:
            lines.append(f"- 亚文化梗密度：每千字 {sm.subculture_reference_density_per_1k:.1f} 处")
            lines.append(f"  使用方式：{sm.reference_usage_style}")

        cp = usm.catchphrase_patterns
        if cp.catchphrase_density_per_1k > 0 and cp.signature_phrases:
            lines.append("- 标志性口头禅：")
            for phrase in cp.signature_phrases[:5]:
                text = phrase.get("phrase", phrase.get("original", ""))
                func = phrase.get("function", phrase.get("feature_note", ""))
                lines.append(f"  · \"{text}\" — {func}")

        ns = usm.non_text_symbols
        if ns.latex_math_density_per_1k > 0:
            lines.append(f"- 非文字符号：LaTeX/数学 {ns.latex_math_density_per_1k:.1f}/千字，"
                       f"中英混杂 {ns.zh_en_code_mixing_density_per_1k:.1f}/千字")

        ea = usm.extreme_affect
        if ea.extreme_emotion_word_density_per_1k > 0:
            lines.append(f"- 极端情感：词密度 {ea.extreme_emotion_word_density_per_1k:.1f}/千字，"
                       f"态度翻转 {ea.attitude_reversal_frequency}")

        lines.append("")

    # === 风格语料库锚点（子层 F） ===
    corpus = profile.style_corpus
    if corpus and corpus.total_entries > 0:
        lines.append("## 参考文本原文锚点——请参照以下例句的声音写作")
        lines.append("你的目标：写出新内容，但让熟悉参考文本的读者以为这是同一个作者写的。")
        lines.append("")

        # 选取最有代表性的条目（最多20条）
        entries = _select_top_corpus_entries(corpus, max_entries=20)
        for entry in entries:
            cat_label = _corpus_category_label(entry.category)
            lines.append(f"■ {cat_label}：")
            lines.append(f"  \"{entry.original[:200]}\"")
            if entry.usage:
                lines.append(f"  → {entry.usage}")
            lines.append("")

    # === 定性描述 ===
    if profile.voice_description:
        lines.append("## 文风整体描述")
        lines.append(profile.voice_description)

    return "\n".join(lines)


def _select_top_corpus_entries(corpus, max_entries: int = 20) -> list:
    """从语料库中选取最具代表性的条目"""
    from aura.types import StyleCorpusEntry

    entries: list[StyleCorpusEntry] = []
    # 均匀取样：每类拿一些
    categories = [
        corpus.sentence_templates,
        corpus.functional_sentences,
        corpus.signature_phrases,
        corpus.paragraph_rhythm_samples,
        corpus.register_collision_samples,
        corpus.dialogue_monologue_samples,
    ]
    per_category = max(1, max_entries // len(categories))
    for cat_entries in categories:
        entries.extend(cat_entries[:per_category])

    return entries[:max_entries]


def _corpus_category_label(category: str) -> str:
    """语料库类别标签映射"""
    mapping = {
        "典型开头句": "开头锚点",
        "典型过渡句": "过渡锚点",
        "典型收束句": "收束锚点",
        "动作描写": "动作锚点",
        "心理/状态描写": "心理锚点",
        "对话/独白": "独白锚点",
        "场景切换": "转场锚点",
        "口头禅": "口头禅锚点",
        "圈层用语": "圈层用语锚点",
        "粗口/语气词": "语气锚点",
        "技术术语堆叠": "术语锚点",
        "超短段落（独立成段的短句制造节奏感）": "节奏锚点(短)",
        "超短段落": "节奏锚点(短)",
        "长段落（术语堆叠制造密度感）": "节奏锚点(长)",
        "粗鄙+学术": "语域碰撞锚点",
        "技术术语+日常口语": "语域碰撞锚点",
        "叙事者独白/吐槽": "声音锚点",
    }
    return mapping.get(category, category)


# =============================================================================
# Block 5: TASK — 任务约束（动态注入，不缓存）
# =============================================================================

def format_task_constraints(task: WritingTask) -> str:
    """从 WritingTask 生成任务约束提示词"""
    lines = ["【本次写作任务】", ""]

    # 情节大纲
    if task.scene_outline:
        lines.append("## 场景/情节大纲")
        lines.append(task.scene_outline)
        lines.append("")

    if task.beats:
        lines.append("## 必须覆盖的情节节拍")
        for i, beat in enumerate(task.beats, 1):
            lines.append(f"{i}. {beat}")
        lines.append("")

    # 角色
    if task.characters:
        lines.append("## 角色信息")
        for char in task.characters:
            name = char.get("name", "未知")
            lines.append(f"### {name}")
            for key, val in char.items():
                if key != "name":
                    lines.append(f"- {key}：{val}")
        lines.append("")

    # 视角
    if task.pov_type:
        lines.append(f"## 叙事视角：{task.pov_type}")
        if task.pov_character:
            lines.append(f"- POV 角色：{task.pov_character}（全程通过此角色的感官过滤）")
        if task.tense:
            lines.append(f"- 时态：{task.tense}")
        lines.append("")

    # 字数
    if task.target_word_count_min or task.target_word_count_max:
        lines.append(f"## 字数：{task.target_word_count_min}–{task.target_word_count_max} 字")
        lines.append("")

    # 约束
    if task.must_include:
        lines.append("## 必须包含的元素")
        for item in task.must_include:
            lines.append(f"- {item}")
        lines.append("")

    if task.must_avoid:
        lines.append("## 必须避免的元素")
        for item in task.must_avoid:
            lines.append(f"- 禁止：{item}")
        lines.append("")

    if task.dialogue_constraints:
        lines.append("## 对话/台词约束")
        for item in task.dialogue_constraints:
            lines.append(f"- {item}")
        lines.append("")

    if task.setting_constraints:
        lines.append("## 场景/环境约束")
        for item in task.setting_constraints:
            lines.append(f"- {item}")
        lines.append("")

    # 前情 — 续写模式
    if task.continuity_context:
        lines.append("## 前文（你必须接着这里往下写，不要重复前文）")
        lines.append("以下是已经写好的前文。你的任务是从这里**接着写下去**，不是复述或改写前文。")
        lines.append("前文仅供你了解故事上下文和写作风格。")
        lines.append("")
        lines.append(task.continuity_context)
        lines.append("")
        lines.append("【重要】上面是已经写好的内容。请从**紧接着的下一段**开始写新的内容。不要重复。")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Block 6: OUTPUT — 输出约束
# =============================================================================

OUTPUT_CONSTRAINT = """现在开始写。只输出正文 —— 就是故事本身。
不要"以下是场景："、不要评注、不要署名、不要"希望这满足要求"。
就是故事。直接开始叙述。第一个字就是故事的开始。"""


# =============================================================================
# 组装
# =============================================================================

def assemble_writer_prompt(
    task: WritingTask,
    style_profile: StyleProfile | None = None,
    *,
    as_cached_blocks: bool = True,
    provider: str = "anthropic",
) -> str | list[dict]:
    """
    组装 Writer 的完整系统提示词。

    Args:
        task: 写作任务
        style_profile: 可选的风格档案
        as_cached_blocks: 是否返回可分块缓存的格式
        provider: API 提供商 ("anthropic" | "deepseek")

    Returns:
        如果 as_cached_blocks=True 且 provider 支持，返回 content block 列表
        否则返回拼接好的字符串
    """
    # 静态块
    static_blocks = [ROLE, CRAFT, ANTI_AI]

    # 风格锚定
    if style_profile and style_profile.meta.profile_name:
        style_block = format_style_anchoring(style_profile)
        if style_block:
            static_blocks.append(style_block)

    static_blocks.append(OUTPUT_CONSTRAINT)

    # 动态块
    task_block = format_task_constraints(task)

    # DeepSeek 不支持 Anthropic 的 cache_control content block 格式
    # 直接返回字符串
    if provider != "anthropic":
        return "\n\n".join(static_blocks + [task_block])

    if as_cached_blocks:
        from aura.api import cached_system_message
        static_text = "\n\n".join(static_blocks)
        return cached_system_message(static_text) + [
            {"type": "text", "text": task_block}
        ]
    else:
        return "\n\n".join(static_blocks + [task_block])
