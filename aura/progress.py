"""
AuraWritingAgent — 进度追踪与状态显示

提供 Agent 工作流中的实时进度反馈。
"""

from __future__ import annotations

import sys
import time
import threading
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Optional


class AgentPhase(str, Enum):
    """Agent 工作阶段"""
    IDLE = "idle"
    STYLE_ANALYZING = "分析参考文本风格..."
    WRITING = "Writer 正在生成初稿..."
    REVIEWING = "Reviewer 正在审稿..."
    REVISING = "Reviser 正在修订..."
    WAITING = "等待 API 响应..."


class ProgressTracker:
    """进度追踪器 — 显示 Agent 工作流状态"""

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    # 回退: "|/-\" for terminals that don't support Unicode
    FALLBACK_FRAMES = ["|", "/", "-", "\\"]

    def __init__(
        self,
        *,
        enabled: bool = True,
        stream: Any = None,
        use_unicode: bool = True,
    ):
        self.enabled = enabled
        self.stream = stream or sys.stderr
        self.use_unicode = use_unicode
        self.frames = self.SPINNER_FRAMES if use_unicode else self.FALLBACK_FRAMES

        self._current_phase = AgentPhase.IDLE
        self._spinner_idx = 0
        self._spinner_thread: Optional[threading.Thread] = None
        self._running = False
        self._status_line = ""
        self._api_start_time: float = 0
        self._total_cost: float = 0
        self._iteration = 0
        self._total_iterations = 0

    # === 公共 API ===

    def set_iteration(self, current: int, total: int) -> None:
        """设置当前迭代进度"""
        self._iteration = current
        self._total_iterations = total

    def add_cost(self, usd: float) -> None:
        """累加费用"""
        self._total_cost += usd

    def phase(self, phase: AgentPhase, detail: str = "") -> None:
        """设置当前阶段并显示"""
        self._current_phase = phase
        if self.enabled:
            msg = f"[{phase.value}]"
            if detail:
                msg += f" {detail}"
            self._write(f"\r{msg}\n")

    def step(self, msg: str) -> None:
        """显示一条步骤消息"""
        if self.enabled:
            self._write(f"\r  → {msg}\n")

    def info(self, msg: str) -> None:
        """显示信息消息"""
        if self.enabled:
            self._write(f"\r  ℹ {msg}\n")

    def success(self, msg: str) -> None:
        """显示成功消息"""
        if self.enabled:
            self._write(f"\r  ✅ {msg}\n")

    def warn(self, msg: str) -> None:
        """显示警告"""
        if self.enabled:
            self._write(f"\r  ⚠️  {msg}\n")

    def error(self, msg: str) -> None:
        """显示错误"""
        self._write(f"\r  ❌ {msg}\n")  # errors always shown

    def score(self, composite: float, passed: bool, blocked: bool = False) -> None:
        """显示评分"""
        if not self.enabled:
            return
        status = "✅ 通过" if passed else ("🚫 阻断" if blocked else "⚠️ 需修订")
        self._write(f"\r  📊 综合评分: {composite:.1f} — {status}\n")

    def api_start(self) -> None:
        """标记 API 调用开始"""
        self._api_start_time = time.time()
        self._start_spinner()

    def api_end(self, cost: float) -> None:
        """标记 API 调用结束"""
        self._stop_spinner()
        self._total_cost += cost
        elapsed = time.time() - self._api_start_time
        if self.enabled:
            self._write(f"\r  ⏱️  API 耗时 {elapsed:.1f}s, 费用 ${cost:.4f}\n")

    def summary(self) -> None:
        """打印最终摘要"""
        if not self.enabled:
            return
        self._write(f"\r{'─' * 50}\n")
        self._write(f"\r  总费用: ${self._total_cost:.4f} USD\n")
        self._write(f"\r{'─' * 50}\n")

    # === 内部 ===

    def _write(self, msg: str) -> None:
        """写入消息到输出流"""
        try:
            self.stream.write(msg)
            self.stream.flush()
        except Exception:
            pass

    def _start_spinner(self) -> None:
        """启动旋转动画线程"""
        if not self.enabled or self._running:
            return
        self._running = True
        self._spinner_thread = threading.Thread(target=self._spin, daemon=True)
        self._spinner_thread.start()

    def _stop_spinner(self) -> None:
        """停止旋转动画"""
        self._running = False
        if self._spinner_thread:
            self._spinner_thread.join(timeout=0.5)
        # 清除 spinner 行
        self._write("\r" + " " * 80 + "\r")

    def _spin(self) -> None:
        """旋转动画循环"""
        phase_label = self._current_phase.value
        while self._running:
            frame = self.frames[self._spinner_idx % len(self.frames)]
            self._spinner_idx += 1
            elapsed = time.time() - self._api_start_time
            iter_info = ""
            if self._total_iterations > 0:
                iter_info = f" | 迭代 {self._iteration}/{self._total_iterations}"
            cost_info = f" | ${self._total_cost:.4f}" if self._total_cost > 0 else ""
            self._write(f"\r{frame} {phase_label}{iter_info}{cost_info} ({elapsed:.0f}s)")
            time.sleep(0.1)


# =============================================================================
# 全局进度追踪器
# =============================================================================

_global_tracker: Optional[ProgressTracker] = None


def get_tracker() -> ProgressTracker:
    """获取全局进度追踪器（始终返回一个实例）"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ProgressTracker()
    return _global_tracker


def set_tracker(tracker: ProgressTracker) -> None:
    """设置全局进度追踪器"""
    global _global_tracker
    _global_tracker = tracker


@contextmanager
def api_call_context(phase: AgentPhase, detail: str = ""):
    """API 调用上下文管理器 — 自动管理 spinner 和计时"""
    tracker = get_tracker()
    tracker.phase(phase, detail)
    tracker.api_start()
    try:
        yield
    finally:
        pass  # api_end 由调用者手动触发（需要 cost 信息）


class DummyTracker(ProgressTracker):
    """空进度追踪器 — 不输出任何内容"""

    def __init__(self):
        super().__init__(enabled=False)
