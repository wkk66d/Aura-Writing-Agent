"""
AuraWritingAgent CLI

Usage:
  aura write --instructions scene.json --profile my_style
  aura style analyze --ref-texts ref.txt --output my_style
  aura check --text draft.txt
  aura review --text draft.txt --instructions scene.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from aura.config import load_config
from aura.api import AuraAPI
from aura.types import WritingTask, Language, Provider
from aura.orchestrator import Orchestrator
from aura.style_analyzer import StyleAnalyzer
from aura.ai_flavor_detector import scan_text, format_scan_report


def _resolve_provider(config_provider: str, cli_provider: str | None) -> Provider:
    """解析 provider：CLI > 配置 > 默认"""
    if cli_provider:
        return Provider(cli_provider)
    return config_provider if isinstance(config_provider, Provider) else Provider(config_provider)


# Common click options
PROVIDER_OPTION = click.option(
    "--provider", type=click.Choice(["anthropic", "deepseek"]), default=None,
    help="API 提供商 (默认: anthropic)"
)
API_KEY_OPTION = click.option(
    "--api-key", type=str, default=None,
    help="API Key（不指定则使用环境变量 ANTHROPIC_API_KEY 或 DEEPSEEK_API_KEY）"
)
MODEL_OPTION = click.option(
    "--model", "-m", type=str, default=None,
    help="指定模型（覆盖配置文件中的模型设置）"
)
QUIET_OPTION = click.option(
    "--quiet", "-q", is_flag=True, default=False,
    help="静默模式（禁用进度显示）"
)

def _setup_progress(quiet: bool):
    """配置全局进度追踪器"""
    from aura.progress import set_tracker, ProgressTracker, DummyTracker
    if quiet:
        set_tracker(DummyTracker())
    else:
        set_tracker(ProgressTracker(enabled=True))


@click.group()
@click.version_option(version="0.1.0")
@click.pass_context
def main(ctx):
    """AuraWritingAgent — AI 小说写作助手"""
    ctx.ensure_object(dict)


# =============================================================================
# write 命令
# =============================================================================

@main.command()
@click.option(
    "--instructions", "-i", required=True, type=click.Path(exists=True),
    help="写作指令 JSON 文件路径"
)
@click.option(
    "--profile", "-p", default=None,
    help="风格档案名称（从 profiles/ 目录加载）"
)
@click.option(
    "--config", "-c", "config_path", type=click.Path(exists=True), default=None,
    help="配置文件路径"
)
@click.option("--temperature", type=float, default=None, help="温度参数")
@click.option("--max-iterations", type=int, default=None, help="最大迭代次数")
@click.option("--output", "-o", type=click.Path(), default=None, help="输出文件路径")
@PROVIDER_OPTION
@API_KEY_OPTION
@MODEL_OPTION
@QUIET_OPTION
def write(instructions, profile, config_path, temperature, max_iterations, output,
          provider, api_key, model, quiet):
    """执行完整写作流水线：写 → 审 → 修 → 循环"""
    _setup_progress(quiet)
    # 加载配置
    cli_overrides = {}
    if temperature:
        cli_overrides["writing"] = {"temperature": temperature}
    if max_iterations:
        cli_overrides["review"] = {"max_iterations": max_iterations}
    if provider:
        cli_overrides["model"] = cli_overrides.get("model", {})
        cli_overrides["model"]["provider"] = provider

    config = load_config(
        config_path=Path(config_path) if config_path else None,
        cli_overrides=cli_overrides,
    )

    # 构建 API 客户端
    resolved_provider = _resolve_provider(config.model.provider, provider)
    api = AuraAPI(
        api_key=api_key or config.model.api_key or None,
        provider=resolved_provider,
        base_url=config.model.deepseek_base_url if resolved_provider == Provider.DEEPSEEK else config.model.anthropic_base_url,
    )
    click.echo(f"✓ 使用 {resolved_provider.value} API")

    # 模型覆盖（同时覆盖 Anthropic 和 DeepSeek 字段）
    if model:
        config.model.writer = model
        config.model.reviewer = model
        config.model.reviser = model
        config.model.style_analyzer = model
        config.model.deepseek_writer = model
        config.model.deepseek_reviewer = model
        config.model.deepseek_reviser = model
        config.model.deepseek_style_analyzer = model
        click.echo(f"✓ 模型: {model}")

    # 加载写作任务
    with open(instructions, "r", encoding="utf-8") as f:
        task_data = json.load(f)
    task = WritingTask.model_validate(task_data)

    # 收集所有前文章节文件路径
    prev_files: list[str] = list(task.previous_chapter_files)
    if task.previous_chapter_file and task.previous_chapter_file not in prev_files:
        prev_files.append(task.previous_chapter_file)

    # 读取所有前文章节并合并注入为 continuity_context
    if prev_files:
        all_prev_text = ""
        for pf in prev_files:
            prev_path = Path(pf)
            if not prev_path.is_absolute():
                prev_path = Path(instructions).parent / prev_path
            if prev_path.exists():
                prev_text = prev_path.read_text("utf-8")
                all_prev_text += prev_text + "\n\n"
                click.echo(f"✓ 已加载前文章节: {prev_path} ({len(prev_text)} 字)")
            else:
                click.echo(f"⚠ 前文章节文件不存在: {prev_path}")
        if all_prev_text:
            task.continuity_context = all_prev_text.strip()

    # 加载风格档案
    style_profile = None
    if profile:
        analyzer = StyleAnalyzer(api, config)
        style_profile = analyzer.load_profile(profile)
        if style_profile:
            click.echo(f"✓ 已加载风格档案: {profile}")
        else:
            click.echo(f"⚠ 未找到风格档案: {profile}，使用通用标准")

    # 执行流水线
    orchestrator = Orchestrator(api, config)
    click.echo("开始写作流水线...")
    click.echo("")

    final_text, report, log = orchestrator.run(task=task, style_profile=style_profile)

    # 输出结果
    click.echo("")
    click.echo("=" * 60)
    click.echo(f"最终评分: {report.composite_score:.1f}")
    click.echo(f"通过: {'✅ 是' if report.passed else '⚠ 否'}")
    if report.instruction_blocked:
        click.echo(f"⚠ 指令遵从 blocked")
    click.echo(f"问题数: {len(report.all_issues)} ({len(report.critical_issues)} critical)")
    click.echo(f"费用: ${orchestrator.total_cost:.4f} USD")
    click.echo(f"迭代: {len(log)} 轮")
    click.echo("=" * 60)
    click.echo("")

    # 输出正文
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(final_text)
        click.echo(f"✓ 已保存到: {output}")
    else:
        click.echo(final_text)


# =============================================================================
# style 命令组
# =============================================================================

@main.group()
def style():
    """风格管理命令组"""
    pass


@style.command(name="analyze")
@click.option(
    "--ref-texts", "-r", required=True, multiple=True, type=click.Path(exists=True),
    help="参考文本文件路径（可多次指定）"
)
@click.option(
    "--output", "-o", required=True,
    help="输出风格档案名称"
)
@click.option(
    "--config", "-c", "config_path", type=click.Path(exists=True), default=None,
    help="配置文件路径"
)
@PROVIDER_OPTION
@API_KEY_OPTION
@MODEL_OPTION
@QUIET_OPTION
def style_analyze(ref_texts, output, config_path, provider, api_key, model, quiet):
    """从参考文本提取风格指纹"""
    _setup_progress(quiet)
    cli_overrides = {}
    if provider:
        cli_overrides["model"] = {"provider": provider}

    config = load_config(
        config_path=Path(config_path) if config_path else None,
        cli_overrides=cli_overrides,
    )

    resolved_provider = _resolve_provider(config.model.provider, provider)
    api = AuraAPI(
        api_key=api_key or config.model.api_key or None,
        provider=resolved_provider,
        base_url=config.model.deepseek_base_url if resolved_provider == Provider.DEEPSEEK else config.model.anthropic_base_url,
    )
    if model:
        config.model.style_analyzer = model

    analyzer = StyleAnalyzer(api, config)

    click.echo(f"分析 {len(ref_texts)} 个参考文本...")
    click.echo(f"参考文本: {', '.join(ref_texts)}")
    click.echo("")

    profile = analyzer.analyze(
        reference_texts=list(ref_texts),
        profile_name=output,
    )

    click.echo(f"✓ 风格档案已保存: profiles/{output}.json")
    click.echo(f"  分析字数: {profile.meta.total_chars_analyzed}")
    click.echo(f"  句长均值: {profile.sentence_length.mean_chars:.1f} 字")
    if profile.sentence_structure.simple_pct > 0:
        click.echo(f"  句式: 单句{profile.sentence_structure.simple_pct:.0f}%")
    click.echo(f"  语料条目: {profile.style_corpus.total_entries}")


# =============================================================================
# check 命令
# =============================================================================

@main.command()
@click.option(
    "--text", "-t", type=click.Path(exists=True), required=True,
    help="待检测文本文件"
)
@click.option(
    "--json-output", is_flag=True, default=False,
    help="以 JSON 格式输出"
)
def check(text, json_output):
    """检查文本的 AI 味"""
    with open(text, "r", encoding="utf-8") as f:
        content = f.read()

    result = scan_text(content)

    if json_output:
        import dataclasses
        click.echo(json.dumps(dataclasses.asdict(result), indent=2, ensure_ascii=False))
    else:
        click.echo(format_scan_report(result))


# =============================================================================
# review 命令
# =============================================================================

@main.command()
@click.option(
    "--text", "-t", type=click.Path(exists=True), required=True,
    help="待审文本文件"
)
@click.option(
    "--instructions", "-i", type=click.Path(exists=True), required=True,
    help="写作指令 JSON 文件"
)
@click.option(
    "--profile", "-p", default=None,
    help="风格档案名称"
)
@click.option(
    "--config", "-c", "config_path", type=click.Path(exists=True), default=None,
    help="配置文件路径"
)
@PROVIDER_OPTION
@API_KEY_OPTION
@MODEL_OPTION
@QUIET_OPTION
def review(text, instructions, profile, config_path, provider, api_key, model, quiet):
    """审稿（不写）"""
    cli_overrides = {}
    if provider:
        cli_overrides["model"] = {"provider": provider}

    config = load_config(
        config_path=Path(config_path) if config_path else None,
        cli_overrides=cli_overrides,
    )

    with open(text, "r", encoding="utf-8") as f:
        draft = f.read()

    with open(instructions, "r", encoding="utf-8") as f:
        task_data = json.load(f)
    task = WritingTask.model_validate(task_data)

    resolved_provider = _resolve_provider(config.model.provider, provider)
    api = AuraAPI(
        api_key=api_key or config.model.api_key or None,
        provider=resolved_provider,
        base_url=config.model.deepseek_base_url if resolved_provider == Provider.DEEPSEEK else config.model.anthropic_base_url,
    )
    if model:
        config.model.reviewer = model
    style_profile = None
    if profile:
        analyzer = StyleAnalyzer(api, config)
        style_profile = analyzer.load_profile(profile)

    from aura.reviewer import Reviewer
    reviewer = Reviewer(api, config)
    report = reviewer.review(draft=draft, task=task, style_profile=style_profile)

    click.echo(f"综合评分: {report.composite_score:.1f}")
    click.echo(f"通过: {'✅ 是' if report.passed else '⚠ 否'}")
    click.echo(f"问题: {len(report.all_issues)} total, {len(report.critical_issues)} critical")
    click.echo("")

    if report.instruction_results:
        click.echo("【指令遵从】")
        for r in report.instruction_results:
            status = "✓" if r.passed else "✗"
            click.echo(f"  {status} {r.instruction.id}: {r.instruction.description} — {r.score}/100")
        click.echo("")

    click.echo("【AI味】")
    for k, v in report.flavor_scores.items():
        click.echo(f"  {k}: {v}/100")
    click.echo("")

    click.echo("【叙事质量】")
    for k, v in report.quality_scores.items():
        click.echo(f"  {k}: {v}/100")
    click.echo("")

    if report.all_issues:
        click.echo("【问题清单】")
        for issue in report.all_issues[:10]:
            click.echo(f"  [{issue.dimension}] {issue.issue}")
    click.echo("")

    if report.overall_assessment:
        click.echo(f"【评语】\n{report.overall_assessment}")


# =============================================================================
# profiles 命令
# =============================================================================

@main.command()
@click.option(
    "--config", "-c", "config_path", type=click.Path(exists=True), default=None,
    help="配置文件路径"
)
def profiles(config_path):
    """列出所有缓存的风格档案"""
    config = load_config(
        config_path=Path(config_path) if config_path else None,
    )
    # profiles 命令只读本地缓存，无需 API key
    # 直接使用文件系统操作
    profiles_dir = Path(config.style.profile_cache_dir)
    if not profiles_dir.exists():
        click.echo("暂无缓存的风格档案")
        return

    import json
    names = [p.stem for p in profiles_dir.glob("*.json")]
    if not names:
        click.echo("暂无缓存的风格档案")
        return

    click.echo("缓存的风格档案:")
    for name in names:
        profile_path = profiles_dir / f"{name}.json"
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("meta", {})
            corpus = data.get("style_corpus", {})
            chars = meta.get("total_chars_analyzed", 0)
            entries = corpus.get("total_entries", 0) if isinstance(corpus, dict) else 0
            click.echo(f"  {name} — {chars}字, {entries}语料条目")
        except Exception:
            click.echo(f"  {name} — 无法读取")



if __name__ == "__main__":
    main()
