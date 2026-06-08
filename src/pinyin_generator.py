from __future__ import annotations

import logging

import jieba
from pypinyin import lazy_pinyin, Style

from src.models import ExampleSentence, GrammarLevel
from src.scraper import load_level_data, save_level_data

logger = logging.getLogger(__name__)


def regenerate_pinyin(hanzi: str) -> str:
    clean = hanzi.replace(" ", "")
    words = jieba.lcut(clean)
    pinyin_parts = []
    for word in words:
        py = "".join(lazy_pinyin(word, style=Style.TONE))
        pinyin_parts.append(py)
    return " ".join(pinyin_parts)


def regenerate_sentence_pinyin(sentence: ExampleSentence) -> ExampleSentence:
    sentence.hanzi = sentence.hanzi.replace(" ", "")
    sentence.pinyin = regenerate_pinyin(sentence.hanzi)
    if sentence.key_word:
        sentence.key_word = sentence.key_word.replace(" ", "")
    return sentence


def regenerate_level_pinyin(level: GrammarLevel) -> GrammarLevel:
    for gp in level.grammar_points:
        for sentence in gp.sentences:
            if sentence.is_valid:
                regenerate_sentence_pinyin(sentence)
    return level


def main() -> None:
    level = load_level_data("A1")
    regenerate_level_pinyin(level)
    save_level_data(level)
    count = sum(
        1 for gp in level.grammar_points for s in gp.sentences if s.is_valid
    )
    print(f"Regenerated pinyin for {count} valid sentences")


if __name__ == "__main__":
    main()
