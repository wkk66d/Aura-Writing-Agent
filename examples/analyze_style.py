"""
示例：从参考文本提取风格指纹

Usage:
  python examples/analyze_style.py reference.txt my_style
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from aura.config import load_config
from aura.api import AuraAPI
from aura.style_analyzer import StyleAnalyzer


def main():
    if len(sys.argv) < 3:
        print("Usage: python analyze_style.py <reference.txt> <profile_name>")
        sys.exit(1)

    ref_path = sys.argv[1]
    profile_name = sys.argv[2]

    if not Path(ref_path).exists():
        print(f"Error: {ref_path} not found")
        sys.exit(1)

    # 初始化
    config = load_config()
    api = AuraAPI()
    analyzer = StyleAnalyzer(api, config)

    # 分析
    print(f"Analyzing {ref_path}...")
    profile = analyzer.analyze(
        reference_texts=[ref_path],
        profile_name=profile_name,
    )

    # 输出摘要
    print()
    print(f"Profile saved: profiles/{profile_name}.json")
    print(f"Total chars analyzed: {profile.meta.total_chars_analyzed}")
    print(f"Sentence: mean={profile.sentence_length.mean_chars:.1f} chars, σ={profile.sentence_length.stddev:.1f}")
    print(f"Structure: simple={profile.sentence_structure.simple_pct:.0f}%")
    print(f"Vocabulary tier: {profile.vocabulary.tier}")
    print(f"Dialogue tag style: {profile.dialogue.tag_style}")
    print(f"Narrative distance: {profile.narrative_distance.type}")
    print(f"Style type: {profile.unconventional_style_markers.style_type}")
    print(f"Corpus entries: {profile.style_corpus.total_entries}")
    print(f"Voice: {profile.voice_description[:100]}...")


if __name__ == "__main__":
    main()
