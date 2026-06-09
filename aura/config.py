"""
AuraWritingAgent — 配置加载器

优先级: CLI 参数 > 环境变量 (AURA_*) > ~/.aura/config.yaml > ./aura_config.yaml > 默认值
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

from aura import types


# 默认配置路径
DEFAULT_CONFIG_PATHS = [
    Path("aura_config.yaml"),                       # 项目级
    Path.home() / ".aura" / "config.yaml",          # 用户级
]

# 环境变量前缀
ENV_PREFIX = "AURA_"


def load_config(
    config_path: Optional[Path] = None,
    cli_overrides: Optional[dict[str, Any]] = None,
) -> types.AuraConfig:
    """
    加载配置，按优先级合并。

    Args:
        config_path: 可选的指定配置文件路径（优先级高于默认路径）
        cli_overrides: CLI 参数覆盖（最高优先级）

    Returns:
        AuraConfig 实例
    """
    # 1. 从默认值开始
    config = types.AuraConfig()

    # 2. 从项目级配置文件合并
    _merge_from_yaml(config, DEFAULT_CONFIG_PATHS[0])

    # 3. 从用户级配置文件合并
    _merge_from_yaml(config, DEFAULT_CONFIG_PATHS[1])

    # 4. 从指定配置文件合并
    if config_path:
        _merge_from_yaml(config, config_path)

    # 5. 从环境变量合并
    _merge_from_env(config)

    # 6. 从 CLI 覆盖合并
    if cli_overrides:
        _merge_from_dict(config, cli_overrides)

    return config


def _merge_from_yaml(config: types.AuraConfig, path: Path) -> None:
    """从 YAML 文件合并配置"""
    if not path.exists():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and isinstance(data, dict):
            _merge_from_dict(config, data)
    except Exception:
        pass  # 配置文件损坏时静默跳过


def _merge_from_env(config: types.AuraConfig) -> None:
    """从环境变量合并配置"""
    # 处理 provider —— 在 setattr 之前转换为枚举
    provider_val = os.environ.get("AURA_PROVIDER")
    if provider_val:
        try:
            config.model.provider = types.Provider(provider_val)
        except ValueError:
            pass

    mapping = {
        # model
        "AURA_MODEL_WRITER": ("model", "writer"),
        "AURA_MODEL_REVIEWER": ("model", "reviewer"),
        "AURA_MODEL_REVISER": ("model", "reviser"),
        "AURA_MODEL_STYLE_ANALYZER": ("model", "style_analyzer"),
        # review
        "AURA_REVIEW_MAX_ITERATIONS": ("review", "max_iterations"),
        "AURA_REVIEW_AUTO_APPROVE_THRESHOLD": ("review", "auto_approve_threshold"),
        "AURA_REVIEW_STRICTNESS": ("review", "strictness"),
        "AURA_REVIEW_LANGUAGE": ("review", "language"),
        # writing
        "AURA_WRITING_TEMPERATURE": ("writing", "temperature"),
        "AURA_WRITING_MAX_TOKENS": ("writing", "max_tokens"),
        "AURA_WRITING_EXTENDED_THINKING": ("writing", "extended_thinking"),
        "AURA_WRITING_THINKING_BUDGET": ("writing", "thinking_budget"),
        # AI flavor
        "AURA_AI_FLAVOR_SENSITIVITY": ("ai_flavor", "sensitivity"),
        "AURA_AI_FLAVOR_ADVERB_THRESHOLD": ("ai_flavor", "adverb_de_threshold_per_1k"),
        # output
        "AURA_OUTPUT_FORMAT": ("output", "format"),
        "AURA_OUTPUT_SAVE_DRAFTS": ("output", "save_drafts"),
        "AURA_OUTPUT_DRAFTS_DIR": ("output", "drafts_dir"),
        # style
        "AURA_STYLE_PROFILE_CACHE_DIR": ("style", "profile_cache_dir"),
        "AURA_STYLE_MIN_REFERENCE_CHARS": ("style", "min_reference_chars"),
        # provider — handled above via Provider() coercion
        "AURA_API_KEY": ("model", "api_key"),
        "AURA_DEEPSEEK_BASE_URL": ("model", "deepseek_base_url"),
        "AURA_ANTHROPIC_BASE_URL": ("model", "anthropic_base_url"),
    }

    for env_var, (section, field) in mapping.items():
        val = os.environ.get(env_var)
        if val is not None:
            _set_nested(config, [section, field], _coerce(val))


def _merge_from_dict(config: types.AuraConfig, data: dict[str, Any]) -> None:
    """从字典合并配置"""
    # 顶层 section 映射
    for section_name in ["model", "review", "ai_flavor", "writing", "output", "style"]:
        if section_name in data and isinstance(data[section_name], dict):
            section = getattr(config, section_name)
            for key, val in data[section_name].items():
                if hasattr(section, key):
                    # 将 provider 字符串强制转换为 Provider 枚举
                    if key == "provider" and isinstance(val, str):
                        try:
                            val = types.Provider(val)
                        except ValueError:
                            pass
                    setattr(section, key, val)


def _set_nested(obj: Any, path: list[str], value: Any) -> None:
    """按路径设置嵌套属性"""
    for part in path[:-1]:
        obj = getattr(obj, part)
    field = path[-1]
    if hasattr(obj, field):
        setattr(obj, field, value)


def _coerce(val: str) -> Any:
    """将字符串环境变量值转换为合适的类型"""
    # bool
    if val.lower() in ("true", "yes", "1"):
        return True
    if val.lower() in ("false", "no", "0"):
        return False
    # int
    try:
        return int(val)
    except ValueError:
        pass
    # float
    try:
        return float(val)
    except ValueError:
        pass
    return val


def save_default_config(path: Path) -> None:
    """保存默认配置为 YAML 文件"""
    config = types.AuraConfig()
    data = config.model_dump()
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
