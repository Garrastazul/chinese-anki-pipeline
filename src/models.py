from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExampleSentence:
    hanzi: str
    pinyin: str
    translation: str
    is_valid: bool = True
    key_word: str | None = None
    audio_filename: str | None = None
    hanzi_errors: str = ""
    pinyin_errors: str = ""
    translation_errors: str = ""
    notes: str = ""

    def __repr__(self) -> str:
        return f"ExampleSentence(hanzi={self.hanzi!r}, pinyin={self.pinyin!r}, translation={self.translation!r})"


@dataclass
class GrammarPoint:
    name: str
    level: str
    url_slug: str
    full_url: str
    pattern: str = ""
    sentences: list[ExampleSentence] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"GrammarPoint(name={self.name!r}, level={self.level!r}, url_slug={self.url_slug!r})"


@dataclass
class GrammarLevel:
    level: str
    grammar_points: list[GrammarPoint] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"GrammarLevel(level={self.level!r}, grammar_points={len(self.grammar_points)})"
