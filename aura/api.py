"""
AuraWritingAgent — 多 Provider API 封装

支持:
- Anthropic (原生 Anthropic SDK)
- DeepSeek (Anthropic 兼容模式, base_url=https://api.deepseek.com/anthropic)

提供:
- 带重试逻辑的 API 调用
- Prompt 缓存辅助
- 费用追踪
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError, APIStatusError

from aura.types import CostInfo, Provider

logger = logging.getLogger(__name__)

# 重试配置
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 60.0


class AuraAPI:
    """多 Provider API 封装 — 通过 Anthropic SDK 统一接口"""

    def __init__(
        self,
        api_key: str | None = None,
        provider: Provider = Provider.ANTHROPIC,
        base_url: str = "",
    ):
        """
        Args:
            api_key: API key。为 None 时按优先级查找:
                     ANTHROPIC_API_KEY → DEEPSEEK_API_KEY → env
            provider: API 提供商
            base_url: 自定义 base URL（覆盖默认值）
        """
        self.provider = provider

        # 确定 API key
        resolved_key = api_key or self._resolve_api_key()
        if not resolved_key:
            raise ValueError(
                f"No API key found. Set {'ANTHROPIC_API_KEY' if provider == Provider.ANTHROPIC else 'DEEPSEEK_API_KEY'} "
                f"environment variable or pass api_key parameter."
            )

        # 确定 base_url
        if base_url:
            resolved_url = base_url
        elif provider == Provider.DEEPSEEK:
            resolved_url = "https://api.deepseek.com/anthropic"
        else:
            resolved_url = None  # Anthropic 默认

        # 初始化客户端
        if resolved_url:
            logger.info(f"Using {provider.value} API at {resolved_url}")
            self.client = Anthropic(api_key=resolved_key, base_url=resolved_url)
        else:
            logger.info(f"Using Anthropic API (default)")
            self.client = Anthropic(api_key=resolved_key)

        self._total_cost = CostInfo()

    def _resolve_api_key(self) -> str:
        """解析 API key（按 provider 优先级）"""
        if self.provider == Provider.DEEPSEEK:
            return os.environ.get("DEEPSEEK_API_KEY", "")
        return os.environ.get("ANTHROPIC_API_KEY", "")

    @property
    def total_cost(self) -> CostInfo:
        """累计费用"""
        return self._total_cost

    def reset_cost(self) -> None:
        """重置费用统计"""
        self._total_cost = CostInfo()

    def set_progress(self, tracker):
        """设置进度追踪器（注入方式，不强制依赖）"""
        self._progress = tracker

    def call(
        self,
        model: str,
        system: str | list[dict[str, Any]],
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.75,
        max_tokens: int = 16384,
        thinking_budget: int | None = None,
        cached_system_blocks: int | None = None,
    ) -> tuple[str, CostInfo]:
        """
        调用 API，带重试和费用追踪。

        Args:
            model: 模型 ID
            system: 系统提示词（字符串或 content block 列表）
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大输出 token
            thinking_budget: extended thinking 预算（None = 禁用）
            cached_system_blocks: 预期被缓存的系统提示词 block 数量

        Returns:
            (响应文本, 费用信息)
        """
        # 进度追踪
        tracker = getattr(self, '_progress', None)

        # 将 system 转换为 API 接受的格式
        system_param = _normalize_system(system, self.provider)

        if tracker:
            tracker.api_start()

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "system": system_param,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if thinking_budget:
                    kwargs["thinking"] = {
                        "type": "enabled",
                        "budget_tokens": thinking_budget,
                    }

                response = self.client.messages.create(**kwargs)
                return self._process_response(response, model, tracker)

            except RateLimitError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    logger.warning(f"Rate limited, retrying in {delay:.1f}s (attempt {attempt+1}/{MAX_RETRIES})")
                    time.sleep(delay)

            except (APIConnectionError, APIStatusError) as e:
                last_error = e
                if attempt < MAX_RETRIES and _is_retryable(e):
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    logger.warning(f"API error, retrying in {delay:.1f}s: {e}")
                    time.sleep(delay)

            except APIError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    logger.warning(f"API error, retrying in {delay:.1f}s: {e}")
                    time.sleep(delay)

        raise RuntimeError(f"API call failed after {MAX_RETRIES} retries: {last_error}")

    def _process_response(self, response: Any, model: str, tracker=None) -> tuple[str, CostInfo]:
        """处理 API 响应，提取文本和费用"""
        # 提取文本
        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "thinking":
                pass

        # 提取费用
        usage = response.usage
        cost = CostInfo(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
            total_cost_usd=_estimate_cost(
                model=model,
                provider=self.provider,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
                cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
            ),
        )

        # 累加
        self._total_cost.input_tokens += cost.input_tokens
        self._total_cost.output_tokens += cost.output_tokens
        self._total_cost.cache_read_tokens += cost.cache_read_tokens
        self._total_cost.cache_write_tokens += cost.cache_write_tokens
        self._total_cost.total_cost_usd += cost.total_cost_usd

        if tracker:
            tracker.api_end(cost.total_cost_usd)

        return text, cost

    def get_model_name(self, agent_type: str, default_anthropic: str, deepseek_model: str) -> str:
        """根据 provider 返回正确的模型名"""
        if self.provider == Provider.DEEPSEEK:
            return deepseek_model
        return default_anthropic


def _is_retryable(error: APIStatusError | APIConnectionError) -> bool:
    """判断错误是否可重试。
    APIConnectionError (网络断开/超时) 没有 status_code，应始终重试。
    APIStatusError 依据 HTTP 状态码判断。
    """
    if not hasattr(error, 'status_code'):
        # APIConnectionError 等无状态码的错误 —— 网络问题应重试
        return True
    return error.status_code in (429, 500, 502, 503, 504)


def _estimate_cost(
    model: str,
    provider: Provider,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """估算 API 费用（USD）"""
    if provider == Provider.DEEPSEEK:
        # DeepSeek V4 价格 (per MTok):
        # deepseek-v4-pro: input $1.60, output $6.40
        # deepseek-v4-flash: input $0.50, output $2.00
        is_pro = "pro" in model.lower()
        input_price = 1.60 if is_pro else 0.50
        output_price = 6.40 if is_pro else 2.00
        cache_read_price = input_price * 0.1
        cache_write_price = input_price * 1.25
    else:
        # Anthropic 价格 (Sonnet 4, per MTok)
        if "sonnet" in model.lower():
            input_price = 3.0
            output_price = 15.0
            cache_read_price = 0.30
            cache_write_price = 3.75
        elif "opus" in model.lower():
            input_price = 15.0
            output_price = 75.0
            cache_read_price = 1.50
            cache_write_price = 18.75
        elif "haiku" in model.lower():
            input_price = 0.80
            output_price = 4.0
            cache_read_price = 0.08
            cache_write_price = 1.0
        else:
            input_price = 3.0
            output_price = 15.0
            cache_read_price = 0.30
            cache_write_price = 3.75

    cost = 0.0
    cost += (input_tokens / 1_000_000) * input_price
    cost += (output_tokens / 1_000_000) * output_price
    cost += (cache_read_tokens / 1_000_000) * cache_read_price
    cost += (cache_write_tokens / 1_000_000) * cache_write_price
    return cost


def cached_system_message(text: str) -> list[dict[str, Any]]:
    """
    创建带缓存标记的系统消息。

    返回 content 列表，包含带 cache_control 的 text block。
    注意：DeepSeek 的 Anthropic 兼容模式不支持 prompt caching，
    调用方应使用 _normalize_system 转换为字符串。
    """
    return [
        {
            "type": "text",
            "text": text,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _normalize_system(
    system: str | list[dict[str, Any]],
    provider: Provider,
) -> str | list[dict[str, Any]]:
    """
    将 system 参数规范化为 API 接受的格式。

    DeepSeek Anthropic 兼容端点只接受字符串格式的 system。
    Anthropic 原生 API 接受字符串或 content block 列表。
    """
    if isinstance(system, str):
        return system
    # system 是 content block 列表
    if provider == Provider.DEEPSEEK:
        # DeepSeek: 提取所有 text block 的文本并拼接
        texts = []
        for block in system:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n\n".join(texts)
    # Anthropic 原生: 直接传 content block 列表
    return system
