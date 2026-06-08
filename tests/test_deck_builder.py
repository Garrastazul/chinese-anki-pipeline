import pytest
from unittest.mock import patch
from pathlib import Path
import genanki
from src.models import GrammarLevel, GrammarPoint, ExampleSentence
from src.deck_builder import (
    create_models, _get_keyword_pinyin, _apply_cloze, _apply_pinyin_cloze,
    _get_available_types, build_sentence_cards, build_deck, export_deck, build_and_export,
)


class TestCreateModels:
    def test_returns_dict_with_expected_keys(self):
        models = create_models()
        assert set(models.keys()) == {"hanzi_full", "en_hanzi", "cloze", "reorder"}

    def test_models_are_genanki_model(self):
        models = create_models()
        for key, model in models.items():
            assert isinstance(model, genanki.Model), f"{key} is not a genanki.Model"

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
        assert result == "ài"

    def test_keyword_not_found_returns_empty(self):
        result = _get_keyword_pinyin("你好", "Nǐ hǎo", "x")
        assert result == ""

    def test_empty_pinyin_returns_empty(self):
        result = _get_keyword_pinyin("你好", "", "你")
        assert result == ""

    def test_multi_char_keyword(self):
        result = _get_keyword_pinyin("我们 没有 钱", "Wǒmen méiyǒu qián", "没有")
        assert result == "méiyǒu"

    def test_keyword_with_spaces(self):
        result = _get_keyword_pinyin("我 没 有 钱", "Wǒ méi yǒu qián", "没 有")
        assert result == "méi yǒu"

    def test_keyword_with_spaces_strategy2(self):
        result = _get_keyword_pinyin("我没钱", "Wǒ méi qián", "没")
        assert result == "méi"


class TestApplyCloze:
    def test_simple_keyword(self):
        result = _apply_cloze("我爱你", "爱")
        assert result == "我{{c1::爱}}你"

    def test_keyword_with_spaces(self):
        result = _apply_cloze("我 爱 你", "爱")
        assert result == "我 {{c1::爱}} 你"

    def test_keyword_inside_word_uses_jieba(self):
        result = _apply_cloze("但是 是", "是")
        assert result == "但是 {{c1::是}}"

    def test_keyword_with_spaces_multiword(self):
        result = _apply_cloze("我 没 有 钱", "没 有")
        assert result == "我 {{c1::没 有}} 钱"

    def test_keyword_not_found(self):
        result = _apply_cloze("你好", "x")
        assert result == "你好"


class TestApplyPinyinCloze:
    def test_simple_pinyin_cloze(self):
        result = _apply_pinyin_cloze("我 爱 你", "Wǒ ài nǐ", "爱")
        assert result == "Wǒ {{c1::ài}} nǐ"

    def test_pinyin_cloze_preserves_correct_token(self):
        result = _apply_pinyin_cloze("事实 是", "shì shí shì", "是")
        assert result == "shì shí {{c1::shì}}"

    def test_pinyin_cloze_no_substring_collision(self):
        result = _apply_pinyin_cloze("晚上 是", "wǎnshàng shì", "是")
        assert result == "wǎnshàng {{c1::shì}}"

    def test_pinyin_cloze_multiword(self):
        result = _apply_pinyin_cloze("我 没 有 钱", "Wǒ méi yǒu qián", "没 有")
        assert result == "Wǒ {{c1::méi yǒu}} qián"

    def test_pinyin_cloze_not_found(self):
        result = _apply_pinyin_cloze("你好", "Nǐ hǎo", "x")
        assert result == "Nǐ hǎo"


class TestClozeConsistency:
    """_apply_cloze and _apply_pinyin_cloze must hide the same position."""

    def test_danshi_shi(self):
        hanzi = "但是 是"
        pinyin = "dàn shì shì"
        kw = "是"
        h_cloze = _apply_cloze(hanzi, kw)
        p_cloze = _apply_pinyin_cloze(hanzi, pinyin, kw)
        assert h_cloze == "但是 {{c1::是}}"
        assert p_cloze == "dàn shì {{c1::shì}}"

    def test_shi_shishi(self):
        hanzi = "是 事实"
        pinyin = "shì shì shí"
        kw = "是"
        jieba_lcut_result = ["是", " ", "事实"]
        with patch("src.deck_builder.jieba.lcut", return_value=jieba_lcut_result):
            with patch("src.deck_builder.jieba.cut", return_value=iter(jieba_lcut_result)):
                h_cloze = _apply_cloze(hanzi, kw)
                p_cloze = _apply_pinyin_cloze(hanzi, pinyin, kw)
        assert h_cloze == "{{c1::是}} 事实"
        assert p_cloze == "{{c1::shì}} shì shí"


class TestGetAvailableTypes:
    def test_all_types_available(self):
        s = ExampleSentence(hanzi="我们 去 学校", pinyin="Wǒmen qù xuéxiào", translation="We go to school", is_valid=True, key_word="去")
        assert _get_available_types(s) == ["hanzi_full", "en_hanzi", "cloze", "reorder"]

    def test_no_keyword(self):
        s = ExampleSentence(hanzi="我们 去 学校", pinyin="Wǒmen qù xuéxiào", translation="We go to school", is_valid=True, key_word=None)
        assert _get_available_types(s) == ["hanzi_full", "en_hanzi", "reorder"]

    def test_single_word(self):
        s = ExampleSentence(hanzi="好", pinyin="hǎo", translation="good", is_valid=True, key_word="好")
        assert _get_available_types(s) == ["hanzi_full", "en_hanzi", "cloze"]

    def test_basic_only(self):
        s = ExampleSentence(hanzi="好", pinyin="hǎo", translation="good", is_valid=True, key_word=None)
        assert _get_available_types(s) == ["hanzi_full", "en_hanzi"]


class TestBuildSentenceCardsRotate:
    def test_rotate_one_card_per_sentence(self, sample_level):
        with patch("src.deck_builder.get") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "generation.mode": "rotate",
                "generation.card_types": ["hanzi_full", "en_hanzi", "cloze", "reorder"],
            }.get(key, default)

            models = create_models()
            notes = build_sentence_cards(sample_level, models)
            assert len(notes) == 2

    def test_rotate_cycles_through_types(self):
        sentences = [
            ExampleSentence(hanzi="我们 去 学校", pinyin="Wǒmen qù xuéxiào", translation="We go to school", is_valid=True, key_word="去", audio_filename="1.mp3"),
            ExampleSentence(hanzi="我 很 好", pinyin="Wǒ hěn hǎo", translation="I am good", is_valid=True, key_word="很", audio_filename="2.mp3"),
            ExampleSentence(hanzi="他 是 学生", pinyin="Tā shì xuéshēng", translation="He is a student", is_valid=True, key_word="是", audio_filename="3.mp3"),
            ExampleSentence(hanzi="你 吃 饭 了 吗", pinyin="Nǐ chī fàn le ma", translation="Have you eaten?", is_valid=True, key_word="了", audio_filename="4.mp3"),
        ]
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=sentences)
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.get") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "generation.mode": "rotate",
                "generation.card_types": ["hanzi_full", "en_hanzi", "cloze", "reorder"],
            }.get(key, default)

            notes = build_sentence_cards(level, models)
            assert len(notes) == 4
            model_names = [n.model.name for n in notes]
            assert model_names == ["Hanzi->Full", "EN->Hanzi", "Cloze", "Reorder"]

    def test_rotate_falls_back_when_cloze_unavailable(self):
        sentences = [
            ExampleSentence(hanzi="好", pinyin="hǎo", translation="good", is_valid=True, key_word=None, audio_filename="1.mp3"),
        ]
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=sentences)
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.get") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "generation.mode": "rotate",
                "generation.card_types": ["hanzi_full", "en_hanzi", "cloze", "reorder"],
            }.get(key, default)

            notes = build_sentence_cards(level, models)
            assert len(notes) == 1
            assert notes[0].model.name == "Hanzi->Full"

    def test_rotate_falls_back_to_next_available(self):
        """Sentence 3 lacks keyword and is single-word → only hanzi_full, en_hanzi."""
        sentences = [
            ExampleSentence(hanzi="我们 去 学校", pinyin="Wǒmen qù xuéxiào", translation="We go to school", is_valid=True, key_word="去", audio_filename="1.mp3"),
            ExampleSentence(hanzi="我 很 好", pinyin="Wǒ hěn hǎo", translation="I am good", is_valid=True, key_word="很", audio_filename="2.mp3"),
            ExampleSentence(hanzi="好", pinyin="hǎo", translation="good", is_valid=True, key_word=None, audio_filename="3.mp3"),
        ]
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=sentences)
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.get") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "generation.mode": "rotate",
                "generation.card_types": ["hanzi_full", "en_hanzi", "cloze", "reorder"],
            }.get(key, default)

            notes = build_sentence_cards(level, models)
            assert len(notes) == 3
            model_names = [n.model.name for n in notes]
            # 0 → hanzi_full, 1 → en_hanzi, 2 → cloze not avail, reorder not avail, → hanzi_full
            assert model_names == ["Hanzi->Full", "EN->Hanzi", "Hanzi->Full"]

    def test_rotate_guids_unique(self, sample_level):
        with patch("src.deck_builder.get") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "generation.mode": "rotate",
                "generation.card_types": ["hanzi_full", "en_hanzi", "cloze", "reorder"],
            }.get(key, default)

            models = create_models()
            notes = build_sentence_cards(sample_level, models)
            guids = [n.guid for n in notes]
            assert len(guids) == len(set(guids))

    def test_rotate_with_custom_card_types(self):
        sentences = [
            ExampleSentence(hanzi="我们 去 学校", pinyin="Wǒmen qù xuéxiào", translation="We go to school", is_valid=True, key_word="去", audio_filename="1.mp3"),
            ExampleSentence(hanzi="我 很 好", pinyin="Wǒ hěn hǎo", translation="I am good", is_valid=True, key_word="很", audio_filename="2.mp3"),
        ]
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=sentences)
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.get") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "generation.mode": "rotate",
                "generation.card_types": ["cloze", "reorder"],
            }.get(key, default)

            notes = build_sentence_cards(level, models)
            assert len(notes) == 2
            model_names = [n.model.name for n in notes]
            assert model_names == ["Cloze", "Reorder"]

    def test_rotate_skips_invalid_sentences(self):
        valid = ExampleSentence(hanzi="我们 去 学校", pinyin="Wǒmen qù xuéxiào", translation="We go to school", is_valid=True, key_word="去", audio_filename="1.mp3")
        invalid = ExampleSentence(hanzi="坏", pinyin="huài", translation="bad", is_valid=False, key_word=None)
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[valid, invalid])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        with patch("src.deck_builder.get") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "generation.mode": "rotate",
                "generation.card_types": ["hanzi_full", "en_hanzi", "cloze", "reorder"],
            }.get(key, default)

            notes = build_sentence_cards(level, models)
            assert len(notes) == 1


class TestBuildSentenceCards:
    @patch("src.deck_builder.get")
    def test_generates_all_card_types(self, mock_get, sample_sentence_full):
        def mock_get_side_effect(key, default=None):
            if key == "generation.mode":
                return "all"
            return default
        mock_get.side_effect = mock_get_side_effect

        gp = GrammarPoint(
            name="Test Point", level="A1", url_slug="test",
            full_url="https://example.com/test",
            sentences=[sample_sentence_full],
        )
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        notes = build_sentence_cards(level, models)

        assert len(notes) == 4

    @patch("src.deck_builder.get")
    def test_skips_invalid_sentences(self, mock_get):
        def mock_get_side_effect(key, default=None):
            if key == "generation.mode":
                return "all"
            return default
        mock_get.side_effect = mock_get_side_effect
        valid = ExampleSentence(hanzi="好", pinyin="hǎo", translation="good", is_valid=True, key_word="好", audio_filename="x.mp3")
        invalid = ExampleSentence(hanzi="坏", pinyin="huài", translation="bad", is_valid=False, key_word=None)
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[valid, invalid])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        notes = build_sentence_cards(level, models)
        assert len(notes) == 3

    @patch("src.deck_builder.get")
    def test_skips_cloze_when_no_keyword(self, mock_get):
        def mock_get_side_effect(key, default=None):
            if key == "generation.mode":
                return "all"
            return default
        mock_get.side_effect = mock_get_side_effect
        s = ExampleSentence(hanzi="好 吗", pinyin="Hǎo ma", translation="OK?", is_valid=True, key_word=None)
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        notes = build_sentence_cards(level, models)
        assert len(notes) == 3
        assert models is not None

    @patch("src.deck_builder.get")
    def test_skips_reorder_when_single_word(self, mock_get):
        def mock_get_side_effect(key, default=None):
            if key == "generation.mode":
                return "all"
            return default
        mock_get.side_effect = mock_get_side_effect
        s = ExampleSentence(hanzi="好", pinyin="hǎo", translation="good", is_valid=True, key_word="好")
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        notes = build_sentence_cards(level, models)
        assert len(notes) == 3

    @patch("src.deck_builder.get")
    def test_all_notes_have_guid(self, mock_get):
        def mock_get_side_effect(key, default=None):
            if key == "generation.mode":
                return "all"
            return default
        mock_get.side_effect = mock_get_side_effect
        s = ExampleSentence(hanzi="我们 去 学校", pinyin="Wǒmen qù xuéxiào", translation="We go to school", is_valid=True, key_word="去", audio_filename="x.mp3")
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        notes = build_sentence_cards(level, models)
        for note in notes:
            assert note.guid is not None
            assert len(note.guid) > 0

    @patch("src.deck_builder.get")
    def test_guids_are_unique(self, mock_get):
        def mock_get_side_effect(key, default=None):
            if key == "generation.mode":
                return "all"
            return default
        mock_get.side_effect = mock_get_side_effect
        s = ExampleSentence(hanzi="我们 去 学校", pinyin="Wǒmen qù xuéxiào", translation="We go to school", is_valid=True, key_word="去", audio_filename="x.mp3")
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        models = create_models()

        notes = build_sentence_cards(level, models)
        guids = [n.guid for n in notes]
        assert len(guids) == len(set(guids))

    @patch("src.deck_builder.get")
    def test_skips_duplicate_hanzi_across_grammar_points(self, mock_get):
        def mock_get_side_effect(key, default=None):
            if key == "generation.mode":
                return "all"
            return default
        mock_get.side_effect = mock_get_side_effect
        s = ExampleSentence(hanzi="我们 去", pinyin="Wǒmen qù", translation="We go", is_valid=True, key_word="去", audio_filename="x.mp3")
        gp1 = GrammarPoint(name="GP1", level="A1", url_slug="gp1", full_url="x", sentences=[s])
        gp2 = GrammarPoint(name="GP2", level="A1", url_slug="gp2", full_url="y", sentences=[s])
        level = GrammarLevel(level="A1", grammar_points=[gp1, gp2])
        models = create_models()

        notes = build_sentence_cards(level, models)
        assert len(notes) == 4


class TestBuildDeck:
    def test_build_deck_returns_deck_and_models(self, sample_level):
        deck, models = build_deck(sample_level)
        assert isinstance(deck, genanki.Deck)
        assert isinstance(models, dict)
        assert "Grammar chinese wiki::A1" in deck.name


class TestExportDeck:
    def test_export_creates_apkg(self, sample_level, tmp_path):
        deck, models = build_deck(sample_level)

        with patch("src.deck_builder.get_output_dir", return_value=tmp_path):
            with patch("src.deck_builder.get_audio_dir", return_value=tmp_path / "audio"):
                with patch("genanki.Package.write_to_file") as mock_write:
                    export_deck(deck, models, sample_level)
                    mock_write.assert_called_once()
                    path_arg = mock_write.call_args[0][0]
                    assert "a1" in path_arg.lower()
                    assert path_arg.endswith(".apkg")


class TestExportDeckPrefix:
    def test_export_with_prefix(self, sample_level, tmp_path):
        deck, models = build_deck(sample_level)
        with patch("src.deck_builder.get_output_dir", return_value=tmp_path):
            with patch("src.deck_builder.get_audio_dir", return_value=tmp_path / "audio"):
                with patch("genanki.Package.write_to_file") as mock_write:
                    export_deck(deck, models, sample_level, filename_prefix="test_")
                    path_arg = mock_write.call_args[0][0]
                    assert "test_" in path_arg
                    assert "chinese-grammar-a1" in path_arg.lower()

    def test_export_without_prefix(self, sample_level, tmp_path):
        deck, models = build_deck(sample_level)
        with patch("src.deck_builder.get_output_dir", return_value=tmp_path):
            with patch("src.deck_builder.get_audio_dir", return_value=tmp_path / "audio"):
                with patch("genanki.Package.write_to_file") as mock_write:
                    export_deck(deck, models, sample_level)
                    path_arg = mock_write.call_args[0][0]
                    assert not path_arg.startswith("test_")
                    assert "chinese-grammar-a1" in path_arg.lower()


class TestBuildAndExport:
    def test_build_and_export_returns_path(self, sample_level, tmp_path):
        with patch("src.deck_builder.get_output_dir", return_value=tmp_path):
            with patch("src.deck_builder.get_audio_dir", return_value=tmp_path / "audio"):
                with patch("genanki.Package.write_to_file") as mock_write:
                    mock_write.return_value = None
                    result = build_and_export(sample_level)
                    mock_write.assert_called_once()
                    assert result is not None

    def test_build_and_export_with_prefix(self, sample_level, tmp_path):
        with patch("src.deck_builder.get_output_dir", return_value=tmp_path):
            with patch("src.deck_builder.get_audio_dir", return_value=tmp_path / "audio"):
                with patch("genanki.Package.write_to_file") as mock_write:
                    mock_write.return_value = None
                    result = build_and_export(sample_level, filename_prefix="test_")
                    mock_write.assert_called_once()
                    path_arg = mock_write.call_args[0][0]
                    assert "test_" in path_arg
