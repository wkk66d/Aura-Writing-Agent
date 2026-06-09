"""
Reviewer Agent 系统提示词组装器

双层审稿:
  - 通用规则层：指令遵从 (I1-I10) + AI味 (F1-F5) + 叙事质量 (Q1-Q3)
  - 风格对齐层：从 StyleProfile 动态生成 (S1-S16)
"""

from __future__ import annotations

from aura.types import StyleProfile, WritingTask, InstructionItem, InstructionPriority, CheckMethod


# =============================================================================
# Reviewer 角色
# =============================================================================

ROLE = """你是一位严苛的文学编辑。你的工作是**找问题**，不是夸奖。

## 扣分制评分规则

每个维度满分 100 分。每发现一个具体问题，从满分中扣分。
**每一个扣分必须绑定一条具体的修改建议**——没有建议就不扣分。

扣分标准（必须严格执行——宁多扣不少扣）：
- **Critical 问题**：每个 -25~-40 分（视角越界、节拍缺失、必须包含缺失、必须避免出现、风格严重偏离）
- **Moderate 问题**：每个 -15~-25 分（角色OOC、对话失真、句式均匀度过高、风格明显偏差、语域碰撞消失）
- **Minor 问题**：每个 -8~-12 分（单个禁用词、单处副词过多、轻微字数偏差、单处标点风格不一致）

重要：如果一个 Critical 问题出现多次，每次都要扣分，不要只扣一次。
例如：视角越界出现3处 → 扣 3×30=90 分，该维度最终分数 = 10 分。

## 审查流程

对每条指令/维度：
1. 找出所有具体问题（引用原文位置）
2. 判定每个问题的严重程度
3. 为每个问题分配扣分
4. 为每个问题写一条**可执行的**修改建议
5. 计算该维度最终分数 = max(0, 100 - 该维度所有扣分之和)

## 核心原则
- 你的默认立场是**怀疑**——假设每条指令都未被充分执行
- 宁可误报，不可漏报
- 每个问题必须绑定一条 fix 建议。没有 fix = 不存在问题
- 不要在 JSON 外输出任何文本"""


# =============================================================================
# 指令遵从审查提示词
# =============================================================================

def format_instruction_compliance_prompt(task: WritingTask, style_profile: StyleProfile | None = None) -> str:
    """生成指令遵从审查提示词（I1-I12）"""
    instructions = _parse_instructions(task, style_profile)
    if not instructions:
        return ""

    lines = ["【指令遵从审查】", "", "请逐条验证以下用户指令是否在初稿中被忠实地执行：", ""]

    for inst in instructions:
        lines.append(f"## {inst.id}. {inst.category} — {inst.description}")
        lines.append(f"   优先级：{inst.priority}")
        if inst.must_include:
            lines.append(f"   必须包含：{', '.join(inst.must_include)}")
        if inst.must_avoid:
            lines.append(f"   必须避免：{', '.join(inst.must_avoid)}")
        lines.append(f"   请检查：初稿中是否满足了这条指令？")
        lines.append(f"   - found: 找到了什么正面证据")
        lines.append(f"   - missing: 缺失了什么")
        lines.append(f"   - violations: 违反了什么")
        lines.append(f"   - locations: 相关位置（引用原文）")
        lines.append(f"   - passed: true/false")
        lines.append(f"   - score: 0-100")
        lines.append(f"   - suggestion: 具体修改建议")
        lines.append("")

        # I11: 风格一致性 — 展开详细的对比审查维度
        if inst.id == "I11":
            lines.append(_STYLE_CONSISTENCY_CHECKLIST)
            lines.append("")

        # I12: 风格档案一致性 — 注入语料锚点原文，展开详细对比
        if inst.id == "I12":
            corpus_text = _format_corpus_for_review(style_profile)
            checklist = _STYLE_PROFILE_CONSISTENCY_CHECKLIST.replace(
                "{corpus_anchors}", corpus_text
            )
            lines.append(checklist)
            lines.append("")

    return "\n".join(lines)


def _format_corpus_for_review(style_profile: StyleProfile | None) -> str:
    """将风格档案中的语料锚点格式化为 Reviewer 可对比的文本"""
    if not style_profile or not style_profile.style_corpus:
        return "（无可用语料锚点）"

    corpus = style_profile.style_corpus
    if corpus.total_entries == 0:
        return "（语料库为空）"

    lines = []
    entries = corpus.all_entries

    # 按类别分组
    by_category: dict[str, list] = {}
    for e in entries:
        cat = e.category or "其他"
        by_category.setdefault(cat, []).append(e)

    for cat, cat_entries in by_category.items():
        lines.append(f"   #### {cat}")
        for e in cat_entries[:5]:  # 每类最多5条
            text = e.original[:200].replace('\n', '\\n')
            note = e.feature_note or e.usage or ""
            lines.append(f"   - 原文：「{text}」")
            if note:
                lines.append(f"     特征说明：{note}")
        lines.append("")

    return "\n".join(lines) if lines else "（无可用语料锚点）"


_STYLE_CONSISTENCY_CHECKLIST = """   【I11 风格一致性详细审查 —— 逐维对比前文与初稿】

   你必须将初稿与前文进行**逐维比较**。不要笼统地说"风格基本一致"。
   要找出**具体的**偏差，引用**具体的**原文作为证据。

   ## 审查维度：

   ### A. 句长与节奏
   - 对比前文的平均句长和句长波动模式与初稿
   - 对比短句/中句/长句的分布比例
   - 对比段落长度的变化模式（前文多短段？初稿变长段？）
   - 举例：前文"开T1。"(2字独立段) → 初稿是否保留了这种极短独立段？

   ### B. 叙事语气与叙事者存在感
   - 对比叙事者的语气态度：前文是戏谑/冷峻/温情/克制？
   - 对比叙事者的存在感：前文是隐身/偶尔现身/强势介入/吐槽式？
   - 对比叙事者与读者的距离
   - 举例：前文"不会吧，NOB考试怎么这么长时间啊"(叙事者直接喊话)
     → 初稿是否保留了这种直接喊话的语气？

   ### C. 用词风格与语域
   - 对比词汇层级（口语化/文学性/技术术语密度）
   - 对比语域碰撞模式（前文多语域混搭？初稿变单一语域？）
   - 对比圈层用语/口头禅/标志性措辞的使用
   - 举例：前文有"我草""妈的""打胶"等粗鄙口语
     → 初稿是否延续了这种口语底色？

   ### D. 对话/独白风格
   - 对比对话标签的使用方式（极简"说/道" vs 带副词修饰）
   - 对比独白的出现频率和语气
   - 举例：前文叙事者大量内心吐槽 → 初稿是否消失了？

   ### E. 非文字符号与结构标记
   - 对比特殊符号的使用（LaTeX、时间戳、分隔符等）
   - 对比章节/段落的结构标记方式
   - 举例：前文用"$-00:05$"作为时间标记
     → 初稿是否保留了类似的结构标记？

   ## 评分标准：
   - 5个维度全部一致，无明显偏差 → score≥90, passed=true
   - 1-2个维度有轻微偏差（可以接受的范围） → score 70-89, passed=true
   - 1个维度有明显突变（如语气突然从戏谑变严肃） → score 40-69, passed=false
   - 2个以上维度明显突变，或整体"像另一个人写的" → score<40, passed=false, CRITICAL

   ## suggestion 格式：
   不要写"请保持风格一致"这种废话。必须写具体的修改方案，例如：
   ✓ "前文叙事者语气为戏谑吐槽式（如'妈的终于把这题读懂了'），初稿变为中性客观叙述。
      建议：将第X段'他分析了当前局面'改为吐槽式叙述，如'他妈的这局面，我看了三遍才看懂。'"
   ✗ "请保持与前文一致的叙事风格。" """


_STYLE_PROFILE_CONSISTENCY_CHECKLIST = """   【I12 风格档案一致性详细审查 —— 以语料锚点为核心的逐句对比】

   风格档案包含从参考文本中提取的**原文锚点（Style Corpus）**。
   这些锚点是参考文本中最具风格代表性的原文句子——它们定义了"这个作者怎么写"。

   你的核心任务：**将初稿中的句子与语料锚点进行逐句对比**。
   不要只看抽象的数值指标——要比较具体的句子写法。

   ## 审查方法（按优先级）：

   ### 第一优先级：语料锚点相似度（权重 50%）——这是最重要的维度
   下面的原文锚点是从参考文本中提取的。请逐条将初稿与它们对比：

   {corpus_anchors}

   对比要点：
   - 初稿的开头句 → 是否与「句式模板」中的开头锚点具有相似的节奏和结构？
   - 初稿的收束句 → 是否与「句式模板」中的收束锚点具有相似的语气和力度？
   - 初稿的措辞 → 是否使用了与「标志性措辞」锚点同类型的表达？
   - 初稿的段落节奏 → 是否与「段落节奏样本」锚点匹配？
   - 初稿的语域碰撞 → 是否与「语域碰撞样本」锚点同构？
   - 初稿的叙事声音 → 是否与「对话/独白样本」锚点一致？

   对于每一类锚点，请找出初稿中**最相似的一句**和**最不相似的一句**，
   用具体引用说明为什么像/为什么不像。

   ### 第二优先级：数值指标对齐（权重 30%）
   - 句长分布：初稿平均句长 vs 档案 mean_chars（容差 ±0.5σ）
   - 句式结构：各类型比例 vs 档案（每个允许 ±12%）
   - 标点指纹：各标点密度 vs 档案
   - 词汇层级：CTTR vs 档案（容差 ±0.08），层级必须匹配

   ### 第三优先级：语调与叙事距离（权重 20%）
   - 叙事距离类型必须匹配
   - 语调 primary 必须一致
   - 语言温度和文字质地必须匹配

   ## 评分标准：
   - 锚点相似度高（≥80%锚点类型能找到对应），数值全部在容差内 → score≥90, passed=true
   - 锚点相似度中等（50-80%对应），数值大部分在容差内 → score 70-89, passed=true
   - 锚点相似度低（<50%对应），或 3 个以上数值指标超容差 → score 40-69, passed=false
   - 锚点几乎完全不匹配，整体"不像同一个人写的" → score<40, passed=false, CRITICAL

   ## suggestion 格式（必须有具体锚点对比）：
   ✓ "风格档案开头锚点：'$-00:05$\\\\n\\\\n写缺省源。'(时间戳+极短行动句)
      初稿开头：'夜幕低垂，星光点点洒落在屋檐上。'(环境描写长句)
      偏差：开头方式完全不同——锚点是冷启动动作句，初稿是传统环境铺陈。
      建议：将开头改为时间标记+短促动作，如'$-00:05$\\\\n\\\\n推开门。'"
   ✓ "风格档案措辞锚点：'我草''妈的'(粗鄙口语)
      初稿全篇无粗口，语气偏文雅——偏离了参考文本的口语底色。
      建议：在叙事者吐槽处加入粗口，如将'这情况很糟糕'改为'妈的，这情况糟透了。'"
   ✗ "请使风格更接近参考文本。" (没有引用锚点，太笼统)"""


def _parse_instructions(task: WritingTask, style_profile: StyleProfile | None = None) -> list[InstructionItem]:
    """从 WritingTask 解析出指令清单 (I1-I12)"""
    instructions = []

    # I1: 叙述视角
    if task.pov_type:
        instructions.append(InstructionItem(
            id="I1", category="POV", description=f"全程使用{task.pov_type}",
            must_include=[f"{task.pov_type}叙事" + (f"，POV角色为{task.pov_character}" if task.pov_character else "")],
            must_avoid=["头跳(head-hopping)", "未经标记的视角转换", "认知边界突破"],
            priority=InstructionPriority.CRITICAL, check_method=CheckMethod.LLM,
        ))

    # I2: 情节节拍
    if task.beats:
        instructions.append(InstructionItem(
            id="I2", category="PLOT", description="覆盖所有情节节拍",
            must_include=task.beats, must_avoid=[],
            priority=InstructionPriority.CRITICAL, check_method=CheckMethod.LLM,
        ))

    # I3: 角色人设
    if task.characters:
        char_names = [c.get("name", "") for c in task.characters]
        instructions.append(InstructionItem(
            id="I3", category="CHARACTER", description=f"角色人设一致性 ({', '.join(char_names)})",
            must_include=[f"{c.get('name','')}言行符合其人设" for c in task.characters],
            must_avoid=["角色OOC", "配角工具人化", "角色认知突破其知识边界"],
            priority=InstructionPriority.MODERATE, check_method=CheckMethod.LLM,
        ))

    # I4: 时态
    if task.tense:
        instructions.append(InstructionItem(
            id="I4", category="FORMAT", description=f"全程使用{task.tense}",
            must_include=[task.tense], must_avoid=["时态漂移"],
            priority=InstructionPriority.MODERATE, check_method=CheckMethod.RULE_LLM,
        ))

    # I5: 字数
    if task.target_word_count_min or task.target_word_count_max:
        instructions.append(InstructionItem(
            id="I5", category="FORMAT", description=f"字数在{task.target_word_count_min}-{task.target_word_count_max}",
            must_include=[], must_avoid=[],
            priority=InstructionPriority.MINOR, check_method=CheckMethod.RULE,
        ))

    # I6: 必须包含
    if task.must_include:
        instructions.append(InstructionItem(
            id="I6", category="CONTENT", description="必须包含指定元素",
            must_include=task.must_include, must_avoid=[],
            priority=InstructionPriority.CRITICAL, check_method=CheckMethod.LLM,
        ))

    # I7: 必须避免
    if task.must_avoid:
        instructions.append(InstructionItem(
            id="I7", category="CONTENT", description="必须避免指定元素",
            must_include=[], must_avoid=task.must_avoid,
            priority=InstructionPriority.CRITICAL, check_method=CheckMethod.LLM,
        ))

    # I8: 对话约束
    if task.dialogue_constraints:
        instructions.append(InstructionItem(
            id="I8", category="DIALOGUE", description="对话/台词约束",
            must_include=task.dialogue_constraints, must_avoid=[],
            priority=InstructionPriority.MODERATE, check_method=CheckMethod.LLM,
        ))

    # I9: 场景约束
    if task.setting_constraints:
        instructions.append(InstructionItem(
            id="I9", category="SETTING", description="场景/环境约束",
            must_include=task.setting_constraints, must_avoid=[],
            priority=InstructionPriority.MODERATE, check_method=CheckMethod.LLM,
        ))

    # I10: 格式约束
    if task.format_constraints:
        instructions.append(InstructionItem(
            id="I10", category="FORMAT", description="格式/结构约束",
            must_include=task.format_constraints, must_avoid=[],
            priority=InstructionPriority.MINOR, check_method=CheckMethod.RULE_LLM,
        ))

    # I11: 风格一致性 — 当前文存在时强制启用
    if task.continuity_context:
        instructions.append(InstructionItem(
            id="I11", category="STYLE_CONSISTENCY", description="与前文章节的风格一致性",
            must_include=["句长模式一致", "叙事语气一致", "用词风格一致", "节奏感一致"],
            must_avoid=["风格突变", "语气跳变", "用词层级漂移", "叙事距离突变", "新章节像另一个人写的"],
            priority=InstructionPriority.CRITICAL, check_method=CheckMethod.LLM,
        ))

    # I12: 风格档案一致性 — 当加载了 StyleProfile 时强制启用
    if style_profile and style_profile.meta.profile_name:
        has_corpus = style_profile.style_corpus and style_profile.style_corpus.total_entries > 0
        instructions.append(InstructionItem(
            id="I12", category="STYLE_PROFILE", description=f"与风格档案'{style_profile.meta.profile_name}'的一致性",
            must_include=[
                "句长分布匹配风格档案",
                "句式结构匹配风格档案",
                "词汇层级匹配风格档案",
                "叙事距离匹配风格档案",
                "标点指纹匹配风格档案",
            ] + (["语料锚点相似——初稿中的句式/措辞/节奏应与风格语料库中的原文锚点一致"] if has_corpus else []),
            must_avoid=[
                "句长偏离风格档案均值超过1个标准差",
                "句式结构比例偏离风格档案超过15%",
                "用词层级与风格档案不一致",
                "叙事语气与风格档案的voice_description描述不符",
            ],
            priority=InstructionPriority.CRITICAL, check_method=CheckMethod.LLM,
        ))

    return instructions


# =============================================================================
# AI味检测提示词 (F1-F5)
# =============================================================================

AI_FLAVOR_REVIEW_PROMPT = """【AI味检测】

请从以下五个维度评估初稿的 AI 味：

F1. 禁用词/句式：扫描初稿中是否出现了 AI 标志词（仿佛/忽然/竟然/不禁/综上所述等）、
    AI 腔调套话（显而易见/值得注意的是等）、网文陈词（月光如水/百感交集等）

F2. 副词密度：中文"地"字副词短语密度是否过高

F3. 句式均匀度：句子长度是否过于均匀（AI 典型特征——每句话差不多长）

F4. 对话真实性：对话是否有潜台词？是否自然？角色是否像心理治疗师一样完美表达情感？
   对话是否像两个 AI 在彬彬有礼地交换信息？

F5. 结构自然度：是否有模板化段落？是否有三段论结构？是否有"译制腔"？
   叙事者是否在"告知"而非"展现"？

对每个维度输出:
  - score: 0-100
  - issue: 问题描述（如有）
  - locations: 具体位置
  - suggestion: 修改建议"""


# =============================================================================
# 叙事质量提示词 (Q1-Q3)
# =============================================================================

QUALITY_REVIEW_PROMPT = """【叙事质量】

请从以下三个维度评估初稿的叙事质量：

Q1. 展现 vs 告知：情绪是否通过动作/感官传达？有没有直接说出"他很生气"、"房间很紧张"？
   有没有用抽象形容词替代具体描写？

Q2. 节奏：场景节奏是否适合内容？紧张处是否短促？沉思处是否舒展？
   有无拖节奏的段落？有无该展开却一笔带过的重要时刻？

Q3. 钩子强度：开头第一句/第一段能否抓住读者？结尾是否有余味或悬念？

对每个维度输出:
  - score: 0-100
  - issue: 问题描述（如有）
  - locations: 具体位置
  - suggestion: 修改建议"""


# =============================================================================
# 风格对齐审稿提示词（从 StyleProfile 动态生成）
# =============================================================================

def format_style_alignment_review_prompt(profile: StyleProfile) -> str:
    """从 StyleProfile 生成风格对齐审稿提示词（S1-S16）"""
    if not profile or not profile.meta.profile_name:
        return ""

    lines = ["【风格对齐审稿】", "", "将初稿与以下风格档案进行对比：", ""]

    # 句长
    sl = profile.sentence_length
    if sl.mean_chars > 0:
        lines.append(f"S1. 句长分布：目标 {sl.mean_chars:.0f}字(σ={sl.stddev:.0f})，"
                     f"容差 ±{sl.stddev*0.5:.0f}字")

    # 句式
    ss = profile.sentence_structure
    if ss.simple_pct > 0:
        lines.append(f"S2. 句式结构：单句{ss.simple_pct:.0f}%/复句{ss.compound_pct:.0f}%/"
                     f"复杂{ss.complex_pct:.0f}%/碎片{ss.fragment_pct:.0f}%，容差 ±12%")

    # 对话
    d = profile.dialogue
    if d.tag_style:
        lines.append(f"S3. 对话风格：{d.tag_style}，'说/道'{d.said_asked_pct:.0f}%±10%，"
                     f"动作节拍{d.action_beat_instead_of_tag_pct:.0f}%±15%，"
                     f"潜台词{d.subtext_density}")

    # 叙事距离
    nd = profile.narrative_distance
    if nd.type:
        lines.append(f"S4. 叙事距离：{nd.type}（必须匹配），"
                     f"自由间接引语{nd.free_indirect_speech_per_1k:.1f}/千字")

    # 感官
    sp = profile.sensory_profile
    if sp.details_per_1000_chars > 0:
        lines.append(f"S5. 感官描写：每千字{sp.details_per_1000_chars:.1f}处±2.0，"
                     f"分布 视觉{sp.sense_distribution.get('视觉',0):.0f}%等")

    # 段落
    para = profile.paragraphs
    if para.avg_sentences_per_paragraph > 0:
        lines.append(f"S6. 段落节奏：平均{para.avg_sentences_per_paragraph:.1f}句/段±1.5，"
                     f"方差≥{para.length_variance*0.5:.1f}")

    # 词汇语调
    v = profile.vocabulary
    t = profile.tone
    lines.append(f"S7. 词汇语调：CTTR {v.cttr:.2f}±0.08，层级{v.tier}（必须匹配），"
                 f"语调{t.primary}")

    # 非常规风格对齐 (S8-S15)
    usm = profile.unconventional_style_markers
    if usm.style_type in ("unconventional", "mixed"):
        lines.append("")
        lines.append("## 非常规风格对齐 (S8-S15)——权重60%")

        ha = usm.hyperbole_absurdism
        if ha.absurdity_level != "none":
            lines.append(f"S8. 夸大/荒诞修辞：基线{ha.absurdity_level}，"
                       f"密度{ha.absurd_claim_density_per_1k:.1f}/千字")

        rc = usm.register_collision
        if rc.collision_density_per_1k > 0:
            lines.append(f"S9. 语域碰撞：密度{rc.collision_density_per_1k:.1f}/千字，"
                       f"模式{rc.collision_pattern}")

        np_ = usm.narrator_performativity
        if np_.emotional_volatility != "stable":
            lines.append(f"S10. 叙事者表演性：波动{np_.emotional_volatility}，"
                       f"自我指涉{np_.self_reference_per_1k:.1f}/千字")

        ea = usm.extreme_affect
        if ea.extreme_emotion_word_density_per_1k > 0:
            lines.append(f"S11. 极端情感：词密度{ea.extreme_emotion_word_density_per_1k:.1f}/千字，"
                       f"翻转{ea.attitude_reversal_frequency}")

        sm = usm.subculture_markers
        if sm.subculture_reference_density_per_1k > 0:
            lines.append(f"S12. 圈层梗：密度{sm.subculture_reference_density_per_1k:.1f}/千字，"
                       f"风格{sm.reference_usage_style}")

        cp = usm.catchphrase_patterns
        if cp.catchphrase_density_per_1k > 0:
            lines.append(f"S13. 口头禅：密度{cp.catchphrase_density_per_1k:.1f}/千字，"
                       f"变异{cp.catchphrase_variation}")

        ns = usm.non_text_symbols
        if ns.latex_math_density_per_1k > 0:
            lines.append(f"S14. 非文字符号：LaTeX{ns.latex_math_density_per_1k:.1f}/千字，"
                       f"中英{ns.zh_en_code_mixing_density_per_1k:.1f}/千字")

        sds = usm.special_discourse_structure
        if sds.timestamp_as_structure:
            lines.append(f"S15. 特种结构：时间戳作为结构标记，格式{sds.timestamp_format}")

    # S16: 语料相似度
    corpus = profile.style_corpus
    if corpus and corpus.total_entries > 0:
        lines.append("")
        lines.append("S16. 语料相似度：将初稿与以下参考原文例句对比：")
        for entry in _select_corpus_for_review(corpus, max_entries=10):
            lines.append(f"  - \"{entry.original[:150]}\"")
        lines.append("  评分维度：句式相似度 / 措辞习惯 / 声音一致性 / 语域碰撞一致性")

    lines.append("")
    lines.append("对每个维度输出: score (0-100), deviation_level, deviation_detail, suggestions")

    return "\n".join(lines)


def _select_corpus_for_review(corpus, max_entries: int = 10) -> list:
    """为审稿选取语料库条目"""
    return corpus.all_entries[:max_entries]


# =============================================================================
# 完整的 Reviewer 系统提示词
# =============================================================================

def assemble_reviewer_prompt(
    task: WritingTask,
    draft: str,
    style_profile: StyleProfile | None = None,
) -> str:
    """
    组装 Reviewer 的完整系统提示词。

    Args:
        task: 原始写作任务
        draft: 待审初稿
        style_profile: 可选的风格档案

    Returns:
        完整的系统提示词字符串
    """
    sections = [ROLE, ""]

    # 指令遵从审查
    inst_section = format_instruction_compliance_prompt(task, style_profile)
    if inst_section:
        sections.append(inst_section)

    # AI味检测
    sections.append(AI_FLAVOR_REVIEW_PROMPT)
    sections.append("")

    # 叙事质量
    sections.append(QUALITY_REVIEW_PROMPT)
    sections.append("")

    # 风格对齐
    if style_profile:
        style_section = format_style_alignment_review_prompt(style_profile)
        if style_section:
            sections.append(style_section)
            sections.append("")

    # 输出格式
    sections.append(_OUTPUT_SCHEMA)
    sections.append("")
    sections.append(f"【待审初稿】\n\n{draft}")

    return "\n".join(sections)


_OUTPUT_SCHEMA = """【输出格式 —— 扣分制】

每个维度满分 100 分。分数 = max(0, 100 - 该维度所有 issues 的 deduction 之和)。

请输出严格的 JSON。不要输出任何其他文本。

{
  "issues": [
    {
      "dimension": "I1",
      "severity": "critical",
      "deduction": 25,
      "location": "第X段 '引用的原文...'",
      "issue": "具体问题描述",
      "fix": "可执行的修改建议——不要笼统，要能直接应用"
    },
    {
      "dimension": "F4",
      "severity": "moderate",
      "deduction": 10,
      "location": "第Y段 '...'",
      "issue": "...",
      "fix": "..."
    },
    {
      "dimension": "S3",
      "severity": "minor",
      "deduction": 5,
      "location": "...",
      "issue": "...",
      "fix": "..."
    }
  ],
  "scores": {
    "I1": 75,
    "I2": 100,
    "I3": 90,
    "I4": 100,
    "I5": 100,
    "I6": 100,
    "I7": 100,
    "I8": 100,
    "I9": 100,
    "I10": 100,
    "I11": 85,
    "I12": 80,
    "F1": 90,
    "F2": 95,
    "F3": 100,
    "F4": 70,
    "F5": 85,
    "Q1": 90,
    "Q2": 95,
    "Q3": 100,
    "S1": 90,
    "S2": 100,
    "...": "..."
  },
  "composite_score": 85,
  "blocked": false,
  "overall_assessment": "叙述性总结——哪些问题最严重、优先修什么",
  "revision_priority": ["需要优先修复的维度ID列表，按扣分降序排列"]
}

## dimension 说明：
- I1-I12：指令遵从
- F1-F5：AI味检测
- Q1-Q3：叙事质量
- S1-S16：风格对齐

## 关键规则：
1. 每个 issue 必须包含 deduction（扣分值）、location（原文引用）、fix（可执行建议）
2. 没有发现问题的维度不输出 issue，scores 中该维度为 100
3. blocked 为 true 的条件：存在 any critical issue 且 score < 70
4. revision_priority 按 deduction 降序排列（扣分最多的排最前）
5. fix 必须可执行——不要说"改善风格"，要说"将第X句'ABC'改为'DEF'以匹配风格档案中'GHI'的节奏" """
