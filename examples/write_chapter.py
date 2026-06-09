"""
示例：写一个小说场景

Usage:
  python examples/write_chapter.py scene.json [profile_name]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aura.config import load_config
from aura.api import AuraAPI
from aura.types import WritingTask
from aura.orchestrator import Orchestrator
from aura.style_analyzer import StyleAnalyzer


def main():
    if len(sys.argv) < 2:
        print("Usage: python write_chapter.py <scene.json> [profile_name]")
        print()
        print("scene.json format:")
        print(json.dumps({
            "scene_outline": "一个少年在雨夜回到家中，发现门开着。",
            "beats": ["到达家门口", "发现门开着", "推门进入", "发现异样"],
            "pov_type": "第三人称限制",
            "pov_character": "少年",
            "tense": "过去时",
            "target_word_count_min": 800,
            "target_word_count_max": 1200,
            "must_include": ["雨夜氛围", "门开着的关键细节"],
            "must_avoid": ["直接说出'他感到害怕'"],
            "characters": [{
                "name": "少年",
                "personality_keywords": ["谨慎", "敏感"],
                "behavioral_constraints": ["不主动说话"]
            }],
            "genre": "悬疑"
        }, indent=2, ensure_ascii=False))
        sys.exit(1)

    instruction_path = sys.argv[1]
    profile_name = sys.argv[2] if len(sys.argv) > 2 else None

    # 加载指令
    with open(instruction_path, "r", encoding="utf-8") as f:
        task_data = json.load(f)
    task = WritingTask.model_validate(task_data)

    # 初始化
    config = load_config()
    config.review.max_iterations = 2  # 限制迭代次数
    api = AuraAPI()

    # 加载风格
    style_profile = None
    if profile_name:
        analyzer = StyleAnalyzer(api, config)
        style_profile = analyzer.load_profile(profile_name)
        if style_profile:
            print(f"Loaded style: {profile_name}")
        else:
            print(f"Warning: profile '{profile_name}' not found")

    # 写作
    orchestrator = Orchestrator(api, config)
    print("Writing...")
    final_text, report, log = orchestrator.run(task=task, style_profile=style_profile)

    # 输出
    print()
    print("=" * 60)
    print(f"Score: {report.composite_score:.1f} | Passed: {report.passed}")
    print(f"Iterations: {len(log)} | Cost: ${orchestrator.total_cost:.4f}")
    print("=" * 60)
    print()
    print(final_text)


if __name__ == "__main__":
    main()
