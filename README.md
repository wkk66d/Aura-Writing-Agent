# AuraWritingAgent

AI 小说写作 Agent — 严格遵循指令、文本风格对齐、消除 AI 味。

## 核心能力

### 多 Agent 流水线
```
Writer → Reviewer → Reviser → 循环（最多 N 轮）
   ↓         ↓          ↓
 生成初稿   扣分制审稿   定向修订
```

- **Writer**：6 层系统提示词（角色锚定 → 创作原则 → AI味禁用清单 → 风格锚定 → 任务约束 → 输出约束）
- **Reviewer**：扣分制审稿，每个问题绑定 `deduction` + `location` + `fix`。12 条指令遵从维度 + 5 条 AI 味维度 + 3 条叙事质量 + 16 条风格对齐
- **Reviser**：只修改审稿标记的部分，保留未标记段落

### 风格指纹系统
```
参考文本 → Style Analyzer → StyleProfile JSON → Writer 第四层注入 + Reviewer I12 审查
```

- **16 维量化特征**：句长/句式/标点/词汇/对话/段落/叙事距离/语域/感官/修辞/节奏/语篇/语调/题材
- **非常规风格标记**（子层 D）：夸张修辞/语域碰撞/叙事者表演性/圈层梗/口头禅/非文字符号/特种结构/极端情感
- **原文语料库**（子层 F）：6 类原文锚点（句式模板/功能句式/标志措辞/节奏样本/语域碰撞/独白样本）

### 扣分制审稿体系

满分 100，找到问题就扣分。**每个扣分项必须绑定一条可执行的 fix 建议**。

| 严重度 | 扣分 | 示例 |
|--------|------|------|
| Critical | -25~-40 | 视角越界、节拍缺失、必须包含缺失、风格严重偏离 |
| Moderate | -15~-25 | 角色OOC、对话失真、句式均匀度过高、语域碰撞消失 |
| Minor | -8~-12 | 单个禁用词、单处副词过多、标点风格不一致 |

同一问题多次出现 → 每次独立扣分。无 fix 不扣分。

### 审查维度 (I1-I12, F1-F5, Q1-Q3, S1-S16)

| 类别 | 维度 | 说明 |
|------|------|------|
| I1 | 叙述视角 | POV 类型/人称/视角人物全程一致 |
| I2 | 情节节拍 | 每个大纲要求的节拍覆盖 + 展开质量 |
| I3 | 角色人设 | 言行与人设卡一致 |
| I4 | 时态一致 | 无时态漂移 |
| I5 | 字数范围 | 目标范围 ±15% |
| I6 | 必须包含 | 指定元素逐项检查 |
| I7 | 必须避免 | 指定禁项逐项检查 |
| I8 | 对话约束 | 指定对话内容/长度/风格 |
| I9 | 场景约束 | 场景位置/时间/氛围 |
| I10 | 格式约束 | 章节结构/段落组织/特殊格式 |
| I11 | 前文风格一致 | 与前文章节逐维对比（句长/语气/用词/符号/结构） |
| I12 | 档案风格一致 | 与 StyleProfile 逐维对比（语料锚点优先，9 维指标） |
| F1-F5 | AI 味检测 | 禁用词/副词密度/句式均匀度/对话真实性/结构自然度 |
| Q1-Q3 | 叙事质量 | 展现vs告知/节奏/钩子强度 |
| S1-S16 | 风格对齐 | 句长/句式/对话/叙事距离/感官/段落/词汇语调/非常规标记/语料相似度 |

### 5 层 AI 味防御

| 层级 | 机制 | 成本 |
|------|------|------|
| 1. 写前禁用 | Writer 系统提示词中的禁用词清单（200+ 中文 AI 标志词） | 零 |
| 2. 规则扫描 | `ai_flavor_detector.py` — regex + 副词密度 + 句式均匀度 + 段落方差 + 50 分质量评分 | 零 |
| 3. LLM 检测 | Reviewer F1-F5 维度审稿 | API 调用 |
| 4. 反检测闭环 | Reviser 修订后重新扫描，AI 味增加则回退 | API 调用 |
| 5. 质量评分 | stop-slop 风格 50 分制（直接性/节奏感/可信度/真实感/信息密度） | 零 |

### 规则层安全校验

不受 LLM 输出影响的硬规则兜底，在 LLM 审稿后追加执行：
- POV 硬检查（第一人称出现"他想"→Critical）
- I6 must_include 关键词未出现 → Critical
- I7 must_avoid 关键词出现 → Critical
- I5 字数严重不足 → Minor

## 安装

```bash
pip install -e ".[dev]"

# 设置 API Key
export ANTHROPIC_API_KEY=your_key_here
# 或 DeepSeek
export DEEPSEEK_API_KEY=your_key_here
```

## 快速开始

```bash
# 1. 从参考文本提取风格指纹
aura style analyze --ref-texts reference.txt --output my_style

# 2. 写新章节
aura write --instructions scene.json --profile my_style

# 3. 续写（引用前文章节）
aura write --instructions scene2.json --profile my_style

# 4. 检查文本 AI 味（纯规则，零 API 成本）
aura check --text draft.txt

# 5. 仅审稿（不写作）
aura review --text draft.txt --instructions scene.json --profile my_style

# 6. 列出已缓存的风格档案
aura profiles

# 7. 使用 DeepSeek
aura write --instructions scene.json --provider deepseek --model deepseek-chat

# 8. 静默模式
aura write --instructions scene.json --quiet
```

## scene.json 完整格式

```json
{
  "scene_outline": "场景/情节描述（自由文本）",
  "beats": ["必须覆盖的节拍1", "节拍2", "节拍3"],
  "pov_type": "第三人称限制",
  "pov_character": "主角名",
  "tense": "过去时",
  "target_word_count_min": 800,
  "target_word_count_max": 1200,
  "must_include": [
    "必须出现的元素（对话/描写/揭示等）"
  ],
  "must_avoid": [
    "必须避免的元素（禁止出现的词/情节/写法）"
  ],
  "dialogue_constraints": [
    "对话相关约束（如'张三的对话不超过三句'）"
  ],
  "setting_constraints": [
    "场景环境约束（如'场景必须在室内'）"
  ],
  "format_constraints": [
    "格式约束（如'使用时间戳标记每节'）"
  ],
  "characters": [
    {
      "name": "角色名",
      "personality_keywords": ["谨慎", "敏感", "寡言"],
      "behavioral_constraints": ["不主动说话", "不会伤害无辜"],
      "language_style": "少言寡语，每句话不超过10字",
      "knowledge_boundary": "不知道自己的身世"
    }
  ],
  "previous_chapter_files": [
    "chapter_1.txt",
    "chapter_2.txt"
  ],
  "previous_chapter_file": "chapter_0.txt",
  "continuity_context": "前文摘要（当文件路径未指定或文件不存在时使用）",
  "genre": "悬疑"
}
```

### 续写模式

- `previous_chapter_files`（数组）：指定多个前文章节文件，按顺序合并注入
- `previous_chapter_file`（字符串）：单个文件路径，兼容旧版
- 两种字段可同时使用，CLI 自动去重合并
- 相对路径相对于 `scene.json` 所在目录解析
- 文件内容 > `continuity_context`（文件优先级更高）

```json
{
  "scene_outline": "张三推开门，发现屋里有人来过。",
  "beats": ["推门进入", "发现异样", "寻找线索", "决定追查"],
  "pov_type": "第三人称限制",
  "pov_character": "张三",
  "previous_chapter_files": ["chapter_1.txt", "chapter_2.txt"]
}
```

## CLI 命令参考

| 命令 | 说明 |
|------|------|
| `aura write -i scene.json -p profile` | 完整写作流水线 |
| `aura style analyze -r ref.txt -o name` | 提取风格指纹 |
| `aura check -t draft.txt` | AI 味检测（纯规则） |
| `aura check -t draft.txt --json-output` | AI 味检测（JSON 输出） |
| `aura review -t draft.txt -i scene.json -p profile` | 仅审稿 |
| `aura profiles` | 列出缓存的风格档案 |

### 通用参数

| 参数 | 说明 |
|------|------|
| `--provider anthropic\|deepseek` | API 提供商（默认 anthropic） |
| `--api-key <key>` | API Key |
| `--model <model>` | 覆盖所有 Agent 的模型 |
| `--quiet`, `-q` | 静默模式（禁用进度旋转动画） |
| `--temperature <float>` | 覆盖写作温度 |
| `--max-iterations <int>` | 覆盖最大审稿迭代次数 |
| `--config <path>` | 指定配置文件路径 |
| `--output`, `-o <path>` | 输出文件路径 |

### 进度显示

默认显示旋转动画 + Agent 状态 + 迭代计数 + API 耗时 + 累计费用：

```
[Writer 正在生成初稿...] | 迭代 1/3
⠸ Writer 正在生成初稿... | 迭代 1/3 | $0.0012 (3s)
  ⏱️ API 耗时 3.2s, 费用 $0.0012
  📊 综合评分: 78.5 — ⚠️ 需修订
[Reviser 正在修订...] | 迭代 2/3
  📊 综合评分: 89.0 — ✅ 通过
```

使用 `--quiet` 禁用。

## 配置

默认配置在 `aura_config.yaml`。覆盖优先级：

```
CLI 参数 > 环境变量 (AURA_*) > ~/.aura/config.yaml > ./aura_config.yaml > 默认值
```

### 关键环境变量

```bash
# 模型配置
AURA_MODEL_PROVIDER=deepseek
AURA_MODEL_WRITER=deepseek-chat
AURA_MODEL_REVIEWER=deepseek-chat
AURA_MODEL_REVISER=deepseek-chat
AURA_MODEL_STYLE_ANALYZER=deepseek-chat

# 审稿配置
AURA_REVIEW_MAX_ITERATIONS=2
AURA_REVIEW_AUTO_APPROVE_THRESHOLD=85
AURA_REVIEW_STRICTNESS=high

# 写作配置
AURA_WRITING_TEMPERATURE=0.8
AURA_WRITING_MAX_TOKENS=16384
```

### 完整配置项

```yaml
# aura_config.yaml
model:
  provider: auto              # anthropic | deepseek | auto
  writer: claude-sonnet-4-20250514
  reviewer: claude-sonnet-4-20250514
  reviser: claude-sonnet-4-20250514
  style_analyzer: claude-sonnet-4-20250514

review:
  max_iterations: 3
  auto_approve_threshold: 85
  strictness: high

ai_flavor:
  sensitivity: medium
  adverb_de_threshold_per_1k: 8.0
  uniformity_warning: 0.35
  em_dash_max_per_500: 1

writing:
  temperature: 0.75
  max_tokens: 16384
  extended_thinking: true
  thinking_budget: 4000

output:
  save_drafts: true
  drafts_dir: ./drafts
```

## 项目结构

```
AuraWritingAgent/
├── aura/
│   ├── api.py                      # 多 Provider API（Anthropic + DeepSeek）
│   ├── orchestrator.py             # 流水线控制器（写→审→修循环）
│   ├── writer.py                   # 写手 Agent（6 层提示词）
│   ├── reviewer.py                 # 扣分制审稿 + 规则层安全校验
│   ├── reviser.py                  # 定向修订 Agent
│   ├── style_analyzer.py           # 风格指纹提取 + JSON 解析修复
│   ├── ai_flavor_detector.py      # AI 味规则检测（200+ 禁用词）
│   ├── progress.py                 # 进度旋转动画
│   ├── config.py                   # 6 级优先级配置加载
│   ├── types.py                    # 30+ Pydantic 数据模型
│   ├── cli.py                      # CLI 入口（click）
│   └── prompts/
│       ├── writer_prompt.py        # Writer 6 层提示词 + 风格锚定 + 语料库注入
│       ├── reviewer_prompt.py      # 扣分制审稿 + I1-I12 审查清单 + JSON Schema
│       ├── reviser_prompt.py       # 定向修订提示词
│       └── style_analyzer_prompt.py  # 16 维风格分析 + JSON Schema 模板
├── profiles/                       # 风格档案缓存（JSON）
├── examples/
│   ├── analyze_style.py
│   └── write_chapter.py
├── tests/                          # 31 个单元测试
├── drafts/                         # 草稿自动保存
├── pyproject.toml
└── README.md
```

## 许可证

MIT
