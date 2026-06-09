"""
Reviewer Agent — 双层审稿

审稿维度：
  I1-I10: 指令遵从
  F1-F5:  AI味检测
  Q1-Q3:  叙事质量
  S1-S16: 风格对齐（动态生成）
"""

from __future__ import annotations

import json
import re

from aura.api import AuraAPI
from aura.prompts.reviewer_prompt import assemble_reviewer_prompt, _parse_instructions
from aura.types import (
    AgentResponse,
    AuraConfig,
    InstructionComplianceResult,
    InstructionItem,
    InstructionPriority,
    ReviewIssue,
    ReviewReport,
    Severity,
    StyleAlignedRule,
    StyleAlignmentResult,
    StyleProfile,
    WritingTask,
)


class Reviewer:
    """审稿 Agent"""

    def __init__(self, api: AuraAPI, config: AuraConfig):
        self.api = api
        self.config = config

    def review(
        self,
        draft: str,
        task: WritingTask,
        style_profile: StyleProfile | None = None,
    ) -> ReviewReport:
        """
        对初稿进行双层审稿。

        Args:
            draft: 待审初稿
            task: 原始写作任务
            style_profile: 可选的风格档案

        Returns:
            ReviewReport
        """
        # 组装系统提示词
        system = assemble_reviewer_prompt(
            task=task,
            draft=draft,
            style_profile=style_profile,
        )

        messages = [{
            "role": "user",
            "content": "请审稿。输出严格的 JSON。",
        }]

        # 调用 API（低温，确保一致性）
        model = self.api.get_model_name(
            "reviewer",
            self.config.model.reviewer,
            self.config.model.deepseek_reviewer,
        )
        text, cost = self.api.call(
            model=model,
            system=system,
            messages=messages,
            temperature=0.2,
            max_tokens=8192,
        )

        # 解析 JSON
        data = _parse_json(text)

        # 从原始任务中解析指令列表，用于保留优先级
        original_instructions = _parse_instructions(task)

        # 构建 ReviewReport
        report = self._build_report(data, task, draft, original_instructions, style_profile)

        return report

    def _build_report(
        self,
        data: dict,
        task: WritingTask,
        draft: str,
        original_instructions: list[InstructionItem] | None = None,
        style_profile: StyleProfile | None = None,
    ) -> ReviewReport:
        """从 API 响应的 JSON 构建 ReviewReport —— 扣分制"""
        report = ReviewReport()

        scores = data.get("scores", {})
        raw_issues = data.get("issues", [])

        # 解析 issues (扣分项)
        instruction_blocked = False
        for ri in raw_issues:
            dim = ri.get("dimension", "")
            sev_str = ri.get("severity", "moderate")
            sev = Severity.CRITICAL if sev_str == "critical" else (
                Severity.MODERATE if sev_str == "moderate" else Severity.MINOR
            )
            issue = ReviewIssue(
                dimension=dim,
                dimension_name=dim,
                layer=_dim_layer(dim),
                severity=sev,
                deduction=ri.get("deduction", 0),
                location=ri.get("location", ""),
                issue=ri.get("issue", ""),
                suggestion=ri.get("fix", ri.get("suggestion", "")),
            )
            report.all_issues.append(issue)

            if sev == Severity.CRITICAL and dim.startswith("I") and scores.get(dim, 100) < 70:
                instruction_blocked = True

        # Fill scores
        report.flavor_scores = {}
        report.quality_scores = {}
        for dim, score in scores.items():
            if dim.startswith("F"):
                report.flavor_scores[dim] = score
            elif dim.startswith("Q"):
                report.quality_scores[dim] = score
            elif dim.startswith("S"):
                report.style_alignment_results.append(StyleAlignmentResult(
                    rule=None, score=score,
                    deviation_level="minor" if score >= 80 else ("moderate" if score >= 60 else "critical"),
                ))

        # Fill defaults
        for prefix, store, count in [("F", report.flavor_scores, 5), ("Q", report.quality_scores, 3)]:
            for i in range(1, count + 1):
                store.setdefault(f"{prefix}{i}", 100)

        # instruction_results
        if original_instructions:
            for oi in original_instructions:
                score = scores.get(oi.id, 100)
                dim_issues = [i for i in report.all_issues if i.dimension == oi.id]
                total_ded = sum(i.deduction for i in dim_issues)
                report.instruction_results.append(InstructionComplianceResult(
                    instruction=oi,
                    passed=score >= 70,
                    score=max(0, 100 - total_ded),
                    violations=[i.issue for i in dim_issues],
                    locations=[i.location for i in dim_issues],
                    suggestion="; ".join(i.suggestion for i in dim_issues),
                ))

        report.instruction_blocked = instruction_blocked
        report.composite_score = data.get("composite_score", _compute_composite_from_scores(scores))
        report.overall_assessment = data.get("overall_assessment", "")

        # Critical issues
        for ri in raw_issues:
            if ri.get("severity") == "critical":
                report.critical_issues.append(ReviewIssue(
                    dimension=ri.get("dimension", ""), severity=Severity.CRITICAL,
                    deduction=ri.get("deduction", 0),
                    location=ri.get("location", ""),
                    issue=ri.get("issue", ""),
                    suggestion=ri.get("fix", ""),
                ))

        # Revision priority by deduction desc
        sorted_issues = sorted(raw_issues, key=lambda x: x.get("deduction", 0), reverse=True)
        report.revision_priority = [i.get("dimension", "") for i in sorted_issues[:10]]

        # === 规则层二次校验 ===
        rule_violations = _rule_based_safety_check(task, draft, report)
        if rule_violations:
            report.instruction_blocked = True
            for v in rule_violations:
                report.critical_issues.append(v)
                report.all_issues.append(v)

        # Passed
        report.passed = (
            not report.instruction_blocked
            and report.composite_score >= self.config.review.auto_approve_threshold
        )
        return report



def _dim_layer(dim: str) -> str:
    """推断维度所属层"""
    if dim.startswith("I"):
        return "instruction"
    if dim.startswith("F"):
        return "flavor"
    if dim.startswith("Q"):
        return "quality"
    if dim.startswith("S"):
        return "style_aligned"
    return "unknown"


def _compute_composite_from_scores(scores: dict[str, int]) -> float:
    """从 scores dict 计算综合分（扣分制后备）"""
    if not scores:
        return 70
    return sum(scores.values()) / len(scores)


def _rule_based_safety_check(
    task: WritingTask, draft: str, report: ReviewReport
) -> list[ReviewIssue]:
    """规则层安全校验 —— 不受 LLM 输出影响，硬规则兜底"""
    issues: list[ReviewIssue] = []

    # === I1: POV 强制检查 ===
    if task.pov_type and task.pov_character:
        pov_violations = _check_pov_hard(task, draft)
        issues.extend(pov_violations)

    # === I5: 字数强制检查 ===
    if task.target_word_count_min > 0:
        char_count = len(draft.replace('\n', '').replace(' ', ''))
        if char_count < task.target_word_count_min * 0.7:
            # 严重不足
            already_flagged = any(
                i.instruction.id == "I5" and not i.passed
                for i in report.instruction_results
            )
            if not already_flagged:
                issues.append(ReviewIssue(
                    dimension="I5", dimension_name="字数范围",
                    layer="instruction", severity=Severity.MINOR,
                    location="", issue=f"字数严重不足: {char_count}/{task.target_word_count_min}",
                    suggestion="扩展内容到目标字数",
                ))

    # === I6: must_include 硬扫描 ===
    for item in task.must_include:
        # 简单关键词检测
        keywords = item.replace('"', '').replace("'", "").split()
        found_any = any(kw in draft for kw in keywords if len(kw) >= 2)
        if not found_any:
            already_flagged = any(
                i.instruction.id == "I6" and item in str(i.instruction.must_include)
                for i in report.instruction_results
            )
            if not already_flagged:
                issues.append(ReviewIssue(
                    dimension="I6", dimension_name="必须包含元素",
                    layer="instruction", severity=Severity.CRITICAL,
                    location="", issue=f"必须包含的元素未检测到: '{item}'",
                    suggestion=f"在适当位置加入: {item}",
                ))

    # === I7: must_avoid 硬扫描 ===
    for item in task.must_avoid:
        keywords = item.replace('"', '').replace("'", "").split()
        found_any = any(kw in draft for kw in keywords if len(kw) >= 2)
        if found_any:
            already_flagged = any(
                i.instruction.id == "I7" and item in str(i.instruction.must_avoid)
                for i in report.instruction_results
            )
            if not already_flagged:
                issues.append(ReviewIssue(
                    dimension="I7", dimension_name="必须避免元素",
                    layer="instruction", severity=Severity.CRITICAL,
                    location="", issue=f"必须避免的元素出现在初稿中: '{item}'",
                    suggestion=f"删除相关内容: {item}",
                ))

    return issues


def _check_pov_hard(task: WritingTask, draft: str) -> list[ReviewIssue]:
    """POV 硬规则检查"""
    issues: list[ReviewIssue] = []

    if task.pov_type == "第一人称":
        # 检查是否出现其他角色的内心描写
        if "他想" in draft or "她想" in draft or "心里想" in draft:
            if not any(p in draft for p in ["我想", "我心里想"]):
                issues.append(ReviewIssue(
                    dimension="I1", dimension_name="叙述视角",
                    layer="instruction", severity=Severity.CRITICAL,
                    location="", issue="第一人称视角中出现其他角色内心描写（'他想'/'她想'）",
                    suggestion="删除其他角色的内心描写，只能通过外部观察呈现其他角色",
                ))
    elif task.pov_type == "第三人称限制" and task.pov_character:
        # 检查是否出现"XX心里想"（非POV角色）
        # 简单规则：检查是否有非POV角色名的"想"
        pov_char = task.pov_character
        import re
        # 找所有"XX想/XX觉得/XX心里"模式
        thoughts = re.findall(r'([^\s，。！？]{1,4})(?:心想|心里想|暗自想|暗暗想|觉得|感到)', draft)
        for name in thoughts:
            if name != pov_char and name not in ("他", "她") and "我" not in name:
                issues.append(ReviewIssue(
                    dimension="I1", dimension_name="叙述视角",
                    layer="instruction", severity=Severity.CRITICAL,
                    location=f"'{name}想/觉得'",
                    issue=f"第三人称限制视角({pov_char})中出现非POV角色'{name}'的内心描写",
                    suggestion=f"删除'{name}'的内心描写，改为外部观察",
                ))

    return issues


def _parse_json(text: str) -> dict:
    """从 LLM 输出中解析 JSON。始终返回 dict，防御 JSON array。"""
    # 尝试直接解析
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        # LLM 可能幻觉返回 JSON array，忽略
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 块（只匹配 {…}，不匹配 […]）
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return {}
