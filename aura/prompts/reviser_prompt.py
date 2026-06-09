"""
Reviser Agent 系统提示词组装器

定向修订 + 反检测闭环:
- 只修改审稿标记的部分
- 保留未被标记的段落
- 修订后 AI 味不增反降
"""

from __future__ import annotations

from aura.types import ReviewReport


ROLE = """你是一位细致的文字编辑。你的工作是修改被标记的问题，同时保护原文中好的部分。

核心原则：
1. 只修改审稿报告中明确标记的部分
2. 保留未被标记的段落原文不变
3. 修改要自然——修改后的句子读起来应该像是原作者自己改的
4. 当你修改 AI 味标记的句子时，要整句重新构思，而不是替换个别词汇
   ✗ 把"他感到一阵恐惧"改成"他感到一阵害怕" — 还是AI味
   ✓ 改成"后颈的汗毛一根根立起来" — 这才是人的写法
5. 修改风格偏差时，参照风格档案中的原文锚点来校准语气和节奏
6. 修改指令违规时，优先用最小的改动满足指令——不要为了修一个地方重写整个段落

输出：完整的修订后全文。不要输出任何评注或解释。"""


def assemble_reviser_prompt(
    draft: str,
    report: ReviewReport,
) -> str:
    """组装 Reviser 的系统提示词"""
    sections = [ROLE, ""]

    # 优先修复清单
    if report.revision_priority:
        sections.append("【优先修复顺序】")
        for i, dim in enumerate(report.revision_priority, 1):
            sections.append(f"{i}. {dim}")
        sections.append("")

    # 详细问题清单
    sections.append("【需要修改的问题】")
    for issue in report.all_issues:
        sections.append(f"- [{issue.dimension}] {issue.severity.upper()}: {issue.issue}")
        if issue.location:
            sections.append(f"  位置: {issue.location}")
        if issue.suggestion:
            sections.append(f"  建议: {issue.suggestion}")
        sections.append("")

    # Critical 问题
    if report.critical_issues:
        sections.append("【必须修复的严重问题】")
        for issue in report.critical_issues:
            sections.append(f"- {issue.dimension}: {issue.issue}")
            sections.append(f"  建议: {issue.suggestion}")
        sections.append("")

    # 总体评估
    if report.overall_assessment:
        sections.append("【编辑评语】")
        sections.append(report.overall_assessment)
        sections.append("")

    # 原文
    sections.append("【原始初稿】")
    sections.append(draft)
    sections.append("")
    sections.append("现在输出修订后的完整全文（只输出正文，无评注）。")

    return "\n".join(sections)
