import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import genanki
from src.models import GrammarLevel, GrammarPoint, ExampleSentence
from src.deck_builder import (
    create_models, _get_keyword_pinyin, build_sentence_cards,
    build_deck, export_deck, build_and_export,
)


class TestCreateModels:
    def test_returns_dict_with_expected_keys(self):
        models = create_models()
        assert set(models.keys()) == {"hanzi_full", "en_hanzi", "cloze", "ordenar"}

    def test_models_are_genanki_model(self):
        models = create_models()
        for key, model in models.items():
            assert isinstance(model, genanki.Model), f"{key} no es genanki.Model"

    def test_hanzi_full_has_all_fields(self):
        models = create_models()
        m = models["hanzi_full"]
        field_names = [f["name"] for f in m.fields]
        assert "Hanzi" in field_names
        assert "Pinyin" in field_names
        assert "Translation" in field_names
        assert "AudioField" in field_names
        assert "GrammarPoint" in field_names
        assert "WikiUrl" in field_names

    def test_cloze_model_type(self):
        models = create_models()
        assert models["cloze"].model_type == genanki.CLOZE_MODEL.model_type

    def test_models_have_different_ids(self):
        models = create_models()
        ids = [m.model_id for m in models.values()]
        assert len(ids) == len(set(ids)), "Model IDs are not unique"


class TestGetKeywordPinyin:
    def test_simple_keyword(self):
        result = _get_keyword_pinyin("我 爱 你", "Wǒ ài nǐ", "爱")
        assert "ài" in result

    def test_keyword_not_found_returns_empty(self):
        result = _get_keyword_pinyin("你好", "Nǐ hǎo", "x")
        assert result == ""

    def test_empty_pinyin_returns_empty(self):
        result = _get_keyword_pinyin("你好", "", "你")
        assert result == ""

    def test_multi_char_keyword(self):
        result = _get_keyword_pinyin("我们 没有 钱", "Wǒmen méiyǒu qián", "没有")
        assert "méiyǒu" in result


class TestBuildSentenceCards:
    def test_generates_all_card_types(self, sample_sentence_full):
        gp = GrammarPoint(
            name="Test Point", level="A1", url_slug="test",
            full_url="https://example.com/test",
            sentences=[sample_sentence_full],
        )
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.random.shuffle", return_value=None):
            notes = build_sentence_cards(level, models)

        assert len(notes) == 4

    def test_skips_invalid_sentences(self):
        valid = ExampleSentence(hanzi="好", pinyin="hǎo", translation="good", is_valid=True, key_word="好", audio_filename="x.mp3")
        invalid = ExampleSentence(hanzi="坏", pinyin="huài", translation="bad", is_valid=False, key_word=None)
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[valid, invalid])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.random.shuffle", return_value=None):
            notes = build_sentence_cards(level, models)
        assert len(notes) == 3

    def test_skips_cloze_when_no_keyword(self):
        s = ExampleSentence(hanzi="好 吗", pinyin="Hǎo ma", translation="OK?", is_valid=True, key_word=None)
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.random.shuffle", return_value=None):
            notes = build_sentence_cards(level, models)
        assert len(notes) == 3
        assert models is not None

    def test_skips_ordenar_when_single_word(self):
        s = ExampleSentence(hanzi="好", pinyin="hǎo", translation="good", is_valid=True, key_word="好")
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.random.shuffle", return_value=None):
            notes = build_sentence_cards(level, models)
        assert len(notes) == 3

    def test_all_notes_have_guid(self):
        s = ExampleSentence(hanzi="我们 去 学校", pinyin="Wǒmen qù xuéxiào", translation="We go to school", is_valid=True, key_word="去", audio_filename="x.mp3")
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.random.shuffle", return_value=None):
            notes = build_sentence_cards(level, models)
        for note in notes:
            assert note.guid is not None
            assert len(note.guid) > 0

    def test_guids_are_unique(self):
        s = ExampleSentence(hanzi="我们 去 学校", pinyin="Wǒmen qù xuéxiào", translation="We go to school", is_valid=True, key_word="去", audio_filename="x.mp3")
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.random.shuffle", return_value=None):
            notes = build_sentence_cards(level, models)
        guids = [n.guid for n in notes]
        assert len(guids) == len(set(guids))


class TestBuildDeck:
    def test_build_deck_returns_deck_and_models(self, sample_level):
        with patch("src.deck_builder.random.shuffle", return_value=None):
            deck, models = build_deck(sample_level)
        assert isinstance(deck, genanki.Deck)
        assert isinstance(models, dict)
        assert "Chinese Grammar - A1" in deck.name


class TestExportDeck:
    def test_export_creates_apkg(self, sample_level, tmp_path):
        with patch("src.deck_builder.random.shuffle", return_value=None):
            deck, models = build_deck(sample_level)

        with patch("src.deck_builder.get_output_dir", return_value=tmp_path):
            with patch("src.deck_builder.get_audio_dir", return_value=tmp_path / "audio"):
                with patch("genanki.Package.write_to_file") as mock_write:
                    export_deck(deck, models, "A1")
                    mock_write.assert_called_once()
                    path_arg = mock_write.call_args[0][0]
                    assert "a1" in path_arg.lower()
                    assert path_arg.endswith(".apkg")


class TestBuildAndExport:
    def test_build_and_export_returns_path(self, sample_level, tmp_path):
        with patch("src.deck_builder.random.shuffle", return_value=None):
            with patch("src.deck_builder.get_output_dir", return_value=tmp_path):
                with patch("src.deck_builder.get_audio_dir", return_value=tmp_path / "audio"):
                    with patch("genanki.Package.write_to_file") as mock_write:
                        mock_write.return_value = None
                        result = build_and_export(sample_level)
                        mock_write.assert_called_once()
                        assert result is not None
