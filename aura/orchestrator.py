"""
Orchestrator — 流水线控制器

负责：写 → 审 → 修 → 循环
"""
from __future__ import annotations

import logging
from pathlib import Path

from aura.api import AuraAPI
from aura.types import AuraConfig
from aura.types import ReviewReport, StyleProfile, WritingTask
from aura.writer import Writer
from aura.reviewer import Reviewer
from aura.reviser import Reviser

logger = logging.getLogger(__name__)


class Orchestrator:
    """编排器——控制完整写作流水线"""

    def __init__(self, api: AuraAPI, config: AuraConfig):
        self.api = api
        self.config = config
        self.writer = Writer(api, config)
        self.reviewer = Reviewer(api, config)
        self.reviser = Reviser(api, config)

        self.iteration_log: list[dict] = []

    def run(
        self,
        task: WritingTask,
        style_profile: StyleProfile | None = None,
    ) -> tuple[str, ReviewReport, list[dict]]:
        """
        执行完整的写作流水线。

        Args:
            task: 写作任务
            style_profile: 可选的风格档案

        Returns:
            (最终文本, 最终审稿报告, 迭代日志)
        """
        self.iteration_log = []
        draft = ""
        report = None

        # 进度追踪
        from aura.progress import get_tracker, AgentPhase
        tracker = get_tracker()
        self.api.set_progress(tracker)
        total_iters = self.config.review.max_iterations + 1

        for iteration in range(total_iters):
            tracker.set_iteration(iteration + 1, total_iters)
            logger.info(f"迭代 {iteration + 1}/{total_iters}")

            if iteration == 0:
                # 第一轮：生成初稿
                tracker.phase(AgentPhase.WRITING)
                logger.info("  [Writer] 生成初稿...")
                response = self.writer.write(task=task, style_profile=style_profile)
                draft = response.text
                self._log_iteration(iteration, "write", draft, None, response.cost.total_cost_usd)
                tracker.add_cost(response.cost.total_cost_usd)
            else:
                # 修订轮：送 Reviser
                tracker.phase(AgentPhase.REVISING)
                logger.info("  [Reviser] 定向修订...")
                response = self.reviser.revise(draft=draft, report=report)
                draft = response.text
                self._log_iteration(iteration, "revise", draft, None, response.cost.total_cost_usd)
                tracker.add_cost(response.cost.total_cost_usd)

            # 审稿
            tracker.phase(AgentPhase.REVIEWING)
            logger.info("  [Reviewer] 审稿...")
            report = self.reviewer.review(
                draft=draft,
                task=task,
                style_profile=style_profile,
            )
            self._log_iteration(iteration, "review", draft, report, 0)

            tracker.score(report.composite_score, report.passed, report.instruction_blocked)
            logger.info(f"  综合评分: {report.composite_score:.1f}")
            logger.info(f"  通过: {report.passed}")
            if report.instruction_blocked:
                logger.info(f"  ⚠️ 指令遵从 blocked")

            # 检查是否通过
            if report.passed:
                tracker.success("通过！输出终稿。")
                logger.info(f"  ✅ 通过！输出终稿。")
                break

            if iteration >= self.config.review.max_iterations:
                tracker.warn("达到最大迭代次数，返回最佳结果。")
                logger.info(f"  ⚠️ 达到最大迭代次数，返回最佳结果。")
                break

        # 保存草稿
        if self.config.output.save_drafts:
            self._save_draft(draft, report)

        return draft, report, self.iteration_log

    def _log_iteration(
        self,
        iteration: int,
        phase: str,
        draft: str,
        report: ReviewReport | None,
        cost: float,
    ) -> None:
        """记录迭代日志"""
        entry = {
            "iteration": iteration + 1,
            "phase": phase,
            "draft_length": len(draft),
            "cost_usd": cost,
        }
        if report:
            entry["composite_score"] = report.composite_score
            entry["passed"] = report.passed
            entry["instruction_blocked"] = report.instruction_blocked
            entry["num_issues"] = len(report.all_issues)
            entry["num_critical"] = len(report.critical_issues)
        self.iteration_log.append(entry)

    def _save_draft(self, draft: str, report: ReviewReport | None) -> None:
        """Save draft to disk. Numbering uses max(existing) + 1 to avoid overwriting deleted files."""
        try:
            drafts_dir = Path(self.config.output.drafts_dir)
            drafts_dir.mkdir(parents=True, exist_ok=True)

            # Find next number based on max existing number + 1 (not file count)
            existing = list(drafts_dir.glob("draft_*.txt"))
            max_num = 0
            for f in existing:
                try:
                    n = int(f.stem.split('_')[1])
                    max_num = max(max_num, n)
                except (IndexError, ValueError):
                    pass
            num = max_num + 1

            path = drafts_dir / f"draft_{num:03d}.txt"
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# Draft {num}\n")
                if report:
                    f.write(f"# Score: {report.composite_score:.1f}\n")
                    f.write(f"# Passed: {report.passed}\n\n")
                f.write(draft)

            logger.info(f"Draft saved: {path}")
        except Exception as e:
            logger.warning(f"Failed to save draft: {e}")

    @property
    def total_cost(self) -> float:
        """总费用"""
        return self.api.total_cost.total_cost_usd

    @property
    def total_tokens(self) -> dict:
        """总 token 使用"""
        c = self.api.total_cost
        return {
            "input": c.input_tokens,
            "output": c.output_tokens,
            "cache_read": c.cache_read_tokens,
            "cache_write": c.cache_write_tokens,
        }
