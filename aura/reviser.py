"""
Reviser Agent — 定向修订 + 反检测闭环

只修改审稿标记的部分，保留未被标记的段落。
修订后 AI 味不增反降。
"""

from __future__ import annotations

from aura.api import AuraAPI
from aura.prompts.reviser_prompt import assemble_reviser_prompt
from aura.types import AgentResponse, AuraConfig, ReviewReport


class Reviser:
    """修订 Agent"""

    def __init__(self, api: AuraAPI, config: AuraConfig):
        self.api = api
        self.config = config

    def revise(
        self,
        draft: str,
        report: ReviewReport,
    ) -> AgentResponse:
        """
        对初稿进行定向修订。

        Args:
            draft: 待修订初稿
            report: 审稿报告

        Returns:
            AgentResponse 包含修订后的正文和费用信息
        """
        if report.passed:
            return AgentResponse(text=draft)  # 无需修订

        # 组装系统提示词
        system = assemble_reviser_prompt(
            draft=draft,
            report=report,
        )

        messages = [{
            "role": "user",
            "content": "请修订。输出完整的修订后全文。",
        }]

        # 调用 API（中温，有创意但聚焦）
        model = self.api.get_model_name(
            "reviser",
            self.config.model.reviser,
            self.config.model.deepseek_reviser,
        )
        text, cost = self.api.call(
            model=model,
            system=system,
            messages=messages,
            temperature=0.5,
            max_tokens=self.config.writing.max_tokens,
        )

        return AgentResponse(text=_clean_revision(text), cost=cost)

    def anti_detect_revise(
        self,
        draft: str,
        ai_flavor_flags: list[dict],
    ) -> str:
        """
        第四层反检测修订：只针对 AI 味标记进行改写。
        如果修订后 AI 味增加了，回退到原文。
        """
        if not ai_flavor_flags:
            return draft

        # 简单策略：逐句/逐段修订 AI 味标记的位置
        # 这里只返回原文，实际实现由 Reviser Agent 的完整修订覆盖
        return draft


def _clean_revision(text: str) -> str:
    """清理修订输出"""
    # 去除可能的元文本
    prefixes = ["修订后的全文：", "修订版：", "以下是修订后的", "修改后的正文："]
    for p in prefixes:
        if text.startswith(p):
            text = text[len(p):]
            break
    return text.strip()
