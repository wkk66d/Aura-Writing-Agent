"""
Style Analyzer — 风格指纹提取

从参考文本中提取 16 个维度的量化风格特征 + 原文语料库。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from aura.api import AuraAPI
from aura.prompts.style_analyzer_prompt import assemble_style_analyzer_prompt
from aura.types import AuraConfig, StyleProfile

logger = logging.getLogger(__name__)


class StyleAnalyzer:
    """风格分析器"""

    def __init__(self, api: AuraAPI, config: AuraConfig):
        self.api = api
        self.config = config

    def analyze(
        self,
        reference_texts: list[str],
        *,
        profile_name: str = "default",
    ) -> StyleProfile:
        """
        从参考文本中提取风格档案。

        Args:
            reference_texts: 参考文本列表（可以是文件路径或原始文本）
            profile_name: 档案名称

        Returns:
            StyleProfile
        """
        # 读取参考文本
        combined_text = ""
        for ref in reference_texts:
            if Path(ref).exists():
                with open(ref, "r", encoding="utf-8") as f:
                    combined_text += f.read() + "\n\n"
            else:
                combined_text += ref + "\n\n"

        # 检查最小长度
        total_chars = len(combined_text)
        if total_chars < self.config.style.min_reference_chars:
            raise ValueError(
                f"参考文本总字数 ({total_chars}) 不足最小要求 "
                f"({self.config.style.min_reference_chars})"
            )

        # 组装提示词
        system = assemble_style_analyzer_prompt(combined_text)

        messages = [{
            "role": "user",
            "content": "请分析以上参考文本，输出完整的风格档案 JSON。",
        }]

        # 进度追踪
        from aura.progress import get_tracker, AgentPhase
        tracker = get_tracker()
        self.api.set_progress(tracker)
        tracker.phase(AgentPhase.STYLE_ANALYZING, f"分析 {len(combined_text)} 字参考文本...")

        # 调用 API（低温，确保一致的分析）
        model = self.api.get_model_name(
            "style_analyzer",
            self.config.model.style_analyzer,
            self.config.model.deepseek_style_analyzer,
        )
        text, cost = self.api.call(
            model=model,
            system=system,
            messages=messages,
            temperature=0.3,
            max_tokens=16384,
        )

        # Debug: 保存原始响应
        logger.info(f"API response length: {len(text)} chars")
        logger.debug(f"API response (first 500 chars): {text[:500]}")

        # 解析 JSON
        data = _parse_json(text)

        if not data:
            logger.error(
                f"Failed to parse JSON from API response. "
                f"Response length: {len(text)}. "
                f"First 200 chars: {text[:200]}"
            )
            # 保存原始响应用于调试
            _save_debug_response(text, profile_name)

        # 检查解析质量
        has_meaningful_data = (
            data.get("sentence_length", {}).get("mean_chars", 0) > 0
            or data.get("vocabulary", {}).get("cttr", 0) > 0
            or data.get("voice_description", "")
        )
        if not has_meaningful_data:
            logger.warning(
                f"Parsed data appears empty/zeroed. Possible causes:\n"
                f"  1. LLM did not follow the JSON schema\n"
                f"  2. JSON was wrapped in markdown or extra text\n"
                f"  3. API returned an error message instead of JSON\n"
                f"  First 300 chars of raw response: {text[:300]}"
            )
            _save_debug_response(text, profile_name)

        # 构建 StyleProfile
        profile = StyleProfile.model_validate(data) if data else StyleProfile()

        # 补充元信息
        if not profile.meta.profile_name:
            profile.meta.profile_name = profile_name
        profile.meta.source_texts = [
            str(r) if Path(r).exists() else r[:50] + "..."
            for r in reference_texts
        ]
        profile.meta.total_chars_analyzed = total_chars

        from datetime import datetime
        profile.meta.created_at = datetime.now().isoformat()

        # 保存
        cache_dir = Path(self.config.style.profile_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        profile_path = cache_dir / f"{profile_name}.json"
        profile.save(profile_path)

        return profile

    def load_profile(self, profile_name: str) -> StyleProfile | None:
        """从缓存加载风格档案"""
        cache_dir = Path(self.config.style.profile_cache_dir)
        profile_path = cache_dir / f"{profile_name}.json"
        if profile_path.exists():
            return StyleProfile.load(profile_path)
        return None

    def list_profiles(self) -> list[str]:
        """列出所有缓存的风格档案"""
        cache_dir = Path(self.config.style.profile_cache_dir)
        if not cache_dir.exists():
            return []
        return [p.stem for p in cache_dir.glob("*.json")]


def _save_debug_response(text: str, profile_name: str) -> None:
    """保存原始 API 响应用于调试"""
    debug_path = Path("drafts") / f"_debug_{profile_name}_response.txt"
    try:
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"Debug response saved to: {debug_path}")
    except Exception:
        pass


def _parse_json(text: str) -> dict:
    """从 LLM 输出中解析 JSON。始终返回 dict。

    尝试多种策略：
    1. 直接 JSON parse
    2. 提取 ```json``` 代码块
    3. 提取最外层 {...}
    4. 修复常见的 JSON 错误后重试
    """
    if not text or not text.strip():
        return {}

    # 策略 1: 直接解析
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and _has_style_data(data):
            return data
    except json.JSONDecodeError:
        pass

    # 策略 2: 提取 ```json ... ``` 包裹的代码块
    json_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_block_match:
        try:
            data = json.loads(json_block_match.group(1).strip())
            if isinstance(data, dict) and _has_style_data(data):
                return data
        except json.JSONDecodeError:
            pass

    # 策略 3: 贪婪匹配最外层 { ... }
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                if _has_style_data(data):
                    return data
                # 即使没有 recognisable keys 也返回（可能是空的 schema）
                if len(data) >= 5:  # 至少有一些字段
                    return data
        except json.JSONDecodeError:
            # 策略 4: 尝试修复常见的 JSON 错误
            raw = match.group(0)
            # 修复末尾多余逗号
            fixed = re.sub(r',\s*([}\]])', r'\1', raw)
            # 修复 LLM 返回的 invalid escape sequences (e.g. \s, \_, etc.)
            fixed = _fix_json_escapes(fixed)
            try:
                data = json.loads(fixed)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

    return {}


def _fix_json_escapes(raw: str) -> str:
    """修复 LLM 返回的 JSON 中的 invalid escape sequences。

    在 JSON 字符串内部，只有 \\", \\\\, \\/, \\b, \\f, \\n, \\r, \\t, \\uXXXX 是合法的。
    其他如 \\s, \\_, \\* 等会导致 json.loads 抛出 Invalid \\escape。
    此函数将这些非法转义中的反斜杠加倍（变为 \\\\s, \\\\_ 等），使其成为合法的字面反斜杠。
    """
    # 只在 JSON 字符串内部（双引号之间）修复
    # 简化策略：先将所有反斜杠加倍，然后将合法的还原
    import re as _re

    # 将 \\ 临时替换为占位符
    result = raw.replace('\\\\', '\x00')
    # 将合法转义序列中的反斜杠还原
    for esc in ['\\"', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']:
        result = result.replace(esc, '\x01' + esc[1:])
    # \\uXXXX 合法
    result = _re.sub(r'\\u[0-9a-fA-F]{4}', lambda m: '\x01' + m.group(0)[1:], result)
    # 现在所有剩余的 \\X（非法）→ 加倍为 \\\\X
    result = result.replace('\\', '\\\\')
    # 还原合法转义
    result = result.replace('\x01', '\\')
    # 还原 \\
    result = result.replace('\x00', '\\\\')
    return result


def _has_style_data(data: dict) -> bool:
    """检查 dict 是否包含风格档案的 recognizable 字段"""
    style_keys = {
        "sentence_length", "sentence_structure", "punctuation_fingerprint",
        "vocabulary", "dialogue", "paragraphs", "narrative_distance",
        "register_and_voice", "sensory_profile", "rhetoric", "rhythm",
        "discourse", "tone", "genre_specific", "unconventional_style_markers",
        "style_corpus", "voice_description", "meta",
    }
    present = style_keys & set(data.keys())
    # 至少 1 个 recognizable 字段，或者总字段数足够多
    return len(present) >= 1 or len(data) >= 5
