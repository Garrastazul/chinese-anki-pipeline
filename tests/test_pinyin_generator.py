import pytest
from src.models import ExampleSentence, GrammarLevel, GrammarPoint
from src.pinyin_generator import regenerate_pinyin, regenerate_sentence_pinyin, regenerate_level_pinyin


class TestRegeneratePinyin:
    def test_hanzi_without_spaces(self):
        hanzi = "我 没有 问题。"
        result = regenerate_pinyin(hanzi)
        assert " " in result

    def test_hanzi_already_without_spaces(self):
        hanzi = "我没有问题。"
        result = regenerate_pinyin(hanzi)
        assert " " in result

    def test_pinyin_has_spaces(self):
        hanzi = "我 没有 问题。"
        result = regenerate_pinyin(hanzi)
        assert "wǒ" in result
        assert "méiyǒu" in result
        assert "wèntí" in result


class TestRegenerateSentencePinyin:
    def test_strips_hanzi_spaces(self):
        s = ExampleSentence(hanzi="我 没有 问题。", pinyin="", translation="")
        s = regenerate_sentence_pinyin(s)
        assert " " not in s.hanzi

    def test_generates_pinyin_with_spaces(self):
        s = ExampleSentence(hanzi="我 没有 问题。", pinyin="", translation="")
        s = regenerate_sentence_pinyin(s)
        assert " " in s.pinyin

    def test_strips_keyword_spaces(self):
        s = ExampleSentence(hanzi="我 没有 问题。", pinyin="", translation="", key_word="没 有")
        s = regenerate_sentence_pinyin(s)
        assert s.key_word == "没有"

    def test_keyword_none_not_crashed(self):
        s = ExampleSentence(hanzi="我 没有 问题。", pinyin="", translation="", key_word=None)
        s = regenerate_sentence_pinyin(s)
        assert s.key_word is None


class TestRegenerateLevelPinyin:
    def test_all_sentences_processed(self):
        s1 = ExampleSentence(hanzi="我 没有 问题。", pinyin="", translation="")
        s2 = ExampleSentence(hanzi="他 是 学生。", pinyin="", translation="")
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s1, s2])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        level = regenerate_level_pinyin(level)
        for s in level.grammar_points[0].sentences:
            assert " " not in s.hanzi
            assert " " in s.pinyin

    def test_invalid_sentences_skipped(self):
        valid = ExampleSentence(hanzi="我 好。", pinyin="", translation="", is_valid=True)
        invalid = ExampleSentence(hanzi="坏", pinyin="", translation="", is_valid=False)
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[valid, invalid])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        level = regenerate_level_pinyin(level)
        assert " " not in valid.hanzi
        assert invalid.hanzi == "坏"
