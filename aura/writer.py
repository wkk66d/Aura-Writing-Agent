"""
Writer Agent — 小说正文生成

使用 6 层系统提示词结构：
  Block 1: ROLE
  Block 2: CRAFT
  Block 3: ANTI_AI
  Block 4: STYLE (from StyleProfile)
  Block 5: TASK (from WritingTask)
  Block 6: OUTPUT
"""

from __future__ import annotations

from aura.api import AuraAPI
from aura.prompts.writer_prompt import assemble_writer_prompt
from aura.types import AgentResponse, AuraConfig, StyleProfile, WritingTask


class Writer:
    """小说写手 Agent"""

    def __init__(self, api: AuraAPI, config: AuraConfig):
        self.api = api
        self.config = config

    def write(
        self,
        task: WritingTask,
        style_profile: StyleProfile | None = None,
        *,
        continuation_context: str | None = None,
    ) -> AgentResponse:
        """
        生成一段小说正文。

        Args:
            task: 写作任务
            style_profile: 可选的风格档案
            continuation_context: 可选的续写上下文（用于长章节分段）

        Returns:
            AgentResponse 包含生成的正文和费用信息
        """
        # 组装系统提示词（根据 provider 选择格式）
        provider = self.config.model.provider.value
        use_blocks = provider == "anthropic"
        system_blocks = assemble_writer_prompt(
            task=task,
            style_profile=style_profile,
            as_cached_blocks=use_blocks,
            provider=provider,
        )

        # 构建消息
        has_prior_text = bool(continuation_context or task.continuity_context)
        messages = []
        if has_prior_text:
            messages.append({
                "role": "user",
                "content": (
                    "上面是已经写好的前文。请从紧接着的下一段开始写新的内容。\n"
                    "只输出新内容——不要重复前文的任何句子。"
                ),
            })
        else:
            messages.append({
                "role": "user",
                "content": "开始写吧。直接输出正文。",
            })

        # 调用 API
        thinking_budget = (
            self.config.writing.thinking_budget
            if self.config.writing.extended_thinking
            else None
        )

        model = self.api.get_model_name(
            "writer",
            self.config.model.writer,
            self.config.model.deepseek_writer,
        )

        text, cost = self.api.call(
            model=model,
            system=system_blocks,
            messages=messages,
            temperature=self.config.writing.temperature,
            max_tokens=self.config.writing.max_tokens,
            thinking_budget=thinking_budget,
        )

        # 清理输出（去除可能的元文本）
        text = _clean_output(text)

        return AgentResponse(text=text, cost=cost)


def _clean_output(text: str) -> str:
    """清理 AI 可能输出的元文本"""
    # 常见的元文本前缀
    prefixes_to_strip = [
        "以下是场景：", "以下是正文：", "以下是小说正文：",
        "Here is the scene:", "Here is the story:",
        "好的，以下是", "好的，这是",
        "这是一段", "这是第",
    ]
    for prefix in prefixes_to_strip:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    # 常见的元文本后缀
    suffixes_to_strip = [
        "希望这符合你的要求。", "希望这满足你的要求。",
        "以上就是本章内容。", "（完）",
        "I hope this meets your requirements.",
    ]
    for suffix in suffixes_to_strip:
        if text.endswith(suffix):
            text = text[:-len(suffix)]
            break

    return text.strip()
