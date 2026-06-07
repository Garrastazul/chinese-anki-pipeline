import pytest
from unittest.mock import patch, MagicMock
import json
import requests
from src.models import ExampleSentence, GrammarPoint, GrammarLevel
from src.config import get
from src.validator import (
    validate_sentence, validate_grammar_point, validate_level,
)


def _expected_model() -> str:
    return get("ollama.model", "qwen2.5:7b")


class TestValidateSentence:
    @patch("src.validator.requests.post")
    def test_valid_sentence(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": True,
                "hanzi_errors": "",
                "pinyin_errors": "",
                "translation_errors": "",
                "key_word": "和",
                "notes": "",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(sample_sentence, "Test point")
        assert result["is_valid"] is True
        assert result["key_word"] == "和"

    @patch("src.validator.requests.post")
    def test_invalid_sentence(self, mock_post):
        s = ExampleSentence(hanzi="错句", pinyin="Cuò jù", translation="Wrong")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": False,
                "hanzi_errors": "Typo",
                "pinyin_errors": "",
                "translation_errors": "",
                "key_word": "",
                "notes": "",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Test")
        assert result["is_valid"] is False

    @patch("src.validator.requests.post")
    def test_returns_garbage_fallback(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "not json at all"}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is False
        assert "Validation error" in result.get("notes", "")

    @patch("src.validator.requests.post")
    def test_timeout_retry(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"is_valid": True, "key_word": "key"})}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.side_effect = [requests.Timeout("timeout"), mock_resp]

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is True

    @patch("src.validator.requests.post")
    def test_connection_error_returns_immediately(self, mock_post, sample_sentence):
        mock_post.side_effect = requests.ConnectionError("Connection refused")
        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is False
        assert "connection error" in result.get("notes", "").lower()
        assert mock_post.call_count == 1

    @patch("src.validator.requests.post")
    def test_wsl_not_suggested_in_error(self, mock_post, sample_sentence):
        mock_post.side_effect = requests.ConnectionError("Connection refused")
        result = validate_sentence(sample_sentence, "Test")
        assert "wsl" not in result.get("notes", "").lower()
        assert "ubuntu" not in result.get("notes", "").lower()

    @patch("src.validator.requests.post")
    def test_retry_three_attempts(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"is_valid": true, "key_word": "ok"}'}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.side_effect = [
            requests.Timeout("timeout"),
            requests.Timeout("timeout2"),
            mock_resp,
        ]

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is True
        assert result["key_word"] == "ok"
        assert mock_post.call_count == 3

    @patch("src.validator.requests.post")
    def test_prompt_contains_all_fields(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"is_valid": True, "key_word": ""})}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        validate_sentence(sample_sentence, "Test Grammar Point")

        sent_messages = mock_post.call_args[1]["json"]["messages"]
        user_content = sent_messages[1]["content"]
        assert "Hanzi: 我 爱 你。" in user_content
        assert "Pinyin: Wǒ ài nǐ." in user_content
        assert "EN: I love you." in user_content
        assert "Validate sentence for 'Test Grammar Point'" in user_content
        assert "JSON" in user_content
        assert "translation_errors" in user_content

    @patch("src.validator.requests.post")
    def test_prompt_includes_pattern_when_provided(self, mock_post):
        s = ExampleSentence("我 爱 你。", "Wǒ ài nǐ.", "I love you.")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"is_valid": True, "key_word": ""})}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        validate_sentence(s, "Test Point", "Subj. + Verb + Obj.")
        content = mock_post.call_args[1]["json"]["messages"][1]["content"]
        assert "Pattern: Subj. + Verb + Obj." in content

    @patch("src.validator.requests.post")
    def test_prompt_omits_pattern_when_empty(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"is_valid": True, "key_word": ""})}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        validate_sentence(sample_sentence, "Test Point")
        content = mock_post.call_args[1]["json"]["messages"][1]["content"]
        assert "Pattern:" not in content

    @patch("src.validator.requests.post")
    def test_pattern_graceful_without_pattern_param(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"is_valid": True})}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is True

    @patch("src.validator.requests.post")
    def test_prompt_uses_correct_model_and_format(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"is_valid": true}'}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        validate_sentence(sample_sentence, "Test")
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == _expected_model()
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["temperature"] == 0
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"


class TestValidateGrammarPoint:
    @patch("src.validator.validate_sentence")
    def test_validates_all_sentences(self, mock_vs, sample_grammar_point):
        mock_vs.return_value = {"is_valid": True, "key_word": "和"}
        result = validate_grammar_point(sample_grammar_point)
        assert mock_vs.call_count == 2
        assert result.sentences[0].is_valid is True
        assert result.sentences[0].key_word == "和"

    @patch("src.validator.validate_sentence")
    def test_passes_pattern_to_validate_sentence(self, mock_vs):
        s = ExampleSentence("A", "B", "C")
        gp = GrammarPoint(
            name="T", level="A1", url_slug="t",
            full_url="x", pattern="Pattern: XYZ", sentences=[s]
        )
        mock_vs.return_value = {"is_valid": True, "key_word": ""}
        validate_grammar_point(gp)
        mock_vs.assert_called_with(s, "T", "Pattern: XYZ")

    @patch("src.validator.validate_sentence")
    def test_pattern_empty_by_default(self, mock_vs):
        s = ExampleSentence("A", "B", "C")
        gp = GrammarPoint(
            name="T", level="A1", url_slug="t",
            full_url="x", sentences=[s]
        )
        mock_vs.return_value = {"is_valid": True, "key_word": ""}
        validate_grammar_point(gp)
        mock_vs.assert_called_with(s, "T", "")


class TestTranslationErrorDetection:
    @patch("src.validator.requests.post")
    def test_translation_reversed_meaning(self, mock_post):
        s = ExampleSentence("我 爱 你。", "Wǒ ài nǐ.", "I hate you.")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": False,
                "hanzi_errors": "",
                "pinyin_errors": "",
                "translation_errors": "Translation says 'hate' but hanzi means 'love' (爱)",
                "key_word": "",
                "notes": "",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Expressing love with 'ai'")
        assert result["is_valid"] is False
        assert "hate" in result["translation_errors"]

    @patch("src.validator.requests.post")
    def test_translation_wrong_negation(self, mock_post):
        s = ExampleSentence("我 不 去。", "Wǒ bù qù.", "I am going.")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": False,
                "translation_errors": "Hanzi has negation 不 (not), but translation is positive",
                "notes": "Negation mismatch",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Negation with bu")
        assert result["is_valid"] is False

    @patch("src.validator.requests.post")
    def test_translation_swapped_subject_object(self, mock_post):
        s = ExampleSentence("他 爱 我。", "Tā ài wǒ.", "I love him.")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": False,
                "translation_errors": "Subject/object reversed: 他 (he) is subject, 我 (I) is object",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Basic sentence order")
        assert result["is_valid"] is False

    @patch("src.validator.requests.post")
    def test_translation_correct_passes(self, mock_post):
        s = ExampleSentence("他 是 老师。", "Tā shì lǎoshī.", "He is a teacher.")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": True,
                "hanzi_errors": "",
                "pinyin_errors": "",
                "translation_errors": "",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Connecting nouns with shi")
        assert result["is_valid"] is True
        assert result["translation_errors"] == ""


class TestPinyinErrorDetection:
    @patch("src.validator.requests.post")
    def test_wrong_tone_in_pinyin(self, mock_post):
        s = ExampleSentence("妈妈", "Māmā", "Mom")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": False,
                "pinyin_errors": "Second character should be neutral tone, not first tone",
                "translation_errors": "",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Family members")
        assert result["is_valid"] is False
        assert result["pinyin_errors"]

    @patch("src.validator.requests.post")
    def test_wrong_word_in_pinyin(self, mock_post):
        s = ExampleSentence("我 吃 苹果。", "Wǒ hē píngguǒ.", "I eat apples.")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": False,
                "pinyin_errors": "吃 should be chī, not hē (喝)",
                "hanzi_errors": "",
                "translation_errors": "",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Eating and drinking")
        assert result["is_valid"] is False
        assert "chī" in result["pinyin_errors"]


class TestMultiErrorDetection:
    @patch("src.validator.requests.post")
    def test_both_pinyin_and_translation_wrong(self, mock_post):
        s = ExampleSentence("我 很 好。", "Wǒ hěn hǎo.", "I am bad.")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": False,
                "pinyin_errors": "",
                "translation_errors": "好 means 'good', not 'bad'",
                "notes": "Complete meaning mismatch",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Simple noun+adjective")
        assert result["is_valid"] is False
        assert result["translation_errors"]

    @patch("src.validator.requests.post")
    def test_all_fields_wrong(self, mock_post):
        s = ExampleSentence("我 好。", "Wǒ hǎo.", "I bad.")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": False,
                "hanzi_errors": "Sentence seems incomplete",
                "pinyin_errors": "Missing tone on hǎo",
                "translation_errors": "好 is 'good' not 'bad'",
                "notes": "Multiple issues",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Adj sentence")
        assert result["is_valid"] is False
        assert result["hanzi_errors"]
        assert result["pinyin_errors"]
        assert result["translation_errors"]
        assert result["notes"]


class TestValidationEdgeCases:
    @patch("src.validator.requests.post")
    def test_empty_translation(self, mock_post):
        s = ExampleSentence("你好", "Nǐ hǎo", "")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": False,
                "translation_errors": "Translation is empty",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Greetings")
        assert result["is_valid"] is False

    @patch("src.validator.requests.post")
    def test_says_valid_but_empty_keyword(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": True,
                "key_word": "",
                "hanzi_errors": "",
                "pinyin_errors": "",
                "translation_errors": "",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is True
        assert result["key_word"] == ""

    @patch("src.validator.requests.post")
    def test_says_invalid_but_no_details(self, mock_post):
        s = ExampleSentence("测试", "Cèshì", "Test")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": False,
                "hanzi_errors": "",
                "pinyin_errors": "",
                "translation_errors": "",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Test")
        assert result["is_valid"] is False

    @patch("src.validator.requests.post")
    def test_punctuation_mismatch(self, mock_post):
        s = ExampleSentence("你好。", "Nǐ hǎo.", "Hello")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_valid": True,
                "translation_errors": "",
                "notes": "Minor: Chinese period vs no punctuation in English, but acceptable",
            })}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Greetings")
        assert result["is_valid"] is True

    @patch("src.validator.requests.post")
    def test_long_sentence(self, mock_post):
        s = ExampleSentence(
            "昨天 我 和 朋友 一起 去 了 电影院 看 了 一 部 非常 好看 的 电影。",
            "Zuótiān wǒ hé péngyou yīqǐ qù le diànyǐngyuàn kàn le yī bù fēicháng hǎokàn de diànyǐng.",
            "Yesterday I went to the cinema with a friend and watched a very good movie."
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"is_valid": True, "key_word": "了"})}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Expressing completion with le")
        assert result["is_valid"] is True

    @patch("src.validator.requests.post")
    def test_translation_with_quotes(self, mock_post):
        s = ExampleSentence(
            '他 说 "你好"。',
            'Tā shuō "nǐ hǎo".',
            'He says "hello."'
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"is_valid": True})}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Quoting speech")
        assert result["is_valid"] is True


class TestAlwaysSendsDelay:
    @patch("src.validator.time.sleep")
    @patch("src.validator.validate_sentence")
    def test_sleeps_always_even_after_validation_error(self, mock_vs, mock_sleep):
        mock_vs.return_value = {
            "is_valid": False,
            "hanzi_errors": "",
            "pinyin_errors": "",
            "translation_errors": "",
            "key_word": "",
            "notes": "Validation error: all attempts failed",
        }
        s = ExampleSentence("A", "B", "C")
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s])
        validate_grammar_point(gp)
        mock_sleep.assert_called_once()
        assert s.notes.startswith("Validation error")

    @patch("src.validator.time.sleep")
    @patch("src.validator.validate_sentence")
    def test_sleeps_always_even_after_success(self, mock_vs, mock_sleep):
        mock_vs.return_value = {
            "is_valid": True,
            "hanzi_errors": "",
            "pinyin_errors": "",
            "translation_errors": "",
            "key_word": "",
            "notes": "",
        }
        s = ExampleSentence("A", "B", "C")
        gp = GrammarPoint(name="T", level="A1", url_slug="t", full_url="x", sentences=[s])
        validate_grammar_point(gp)
        mock_sleep.assert_called_once()


class TestErrorPropagation:
    @patch("src.validator.validate_sentence")
    def test_stores_all_error_fields_on_sentence(self, mock_vs):
        mock_vs.return_value = {
            "is_valid": False,
            "hanzi_errors": "Typo in character",
            "pinyin_errors": "Wrong tone",
            "translation_errors": "Wrong meaning",
            "key_word": "了",
            "notes": "Multiple issues found",
        }
        s = ExampleSentence("我 吃 了。", "Wǒ chī le.", "I ate.")
        gp = GrammarPoint(
            name="Completion le", level="A1", url_slug="le",
            full_url="x", sentences=[s]
        )
        result = validate_grammar_point(gp)

        assert result.sentences[0].is_valid is False
        assert result.sentences[0].hanzi_errors == "Typo in character"
        assert result.sentences[0].pinyin_errors == "Wrong tone"
        assert result.sentences[0].translation_errors == "Wrong meaning"
        assert result.sentences[0].key_word == "了"
        assert result.sentences[0].notes == "Multiple issues found"

    @patch("src.validator.validate_sentence")
    def test_revalidation_resets_old_errors(self, mock_vs):
        mock_vs.return_value = {
            "is_valid": True,
            "hanzi_errors": "",
            "pinyin_errors": "",
            "translation_errors": "",
            "key_word": "和",
            "notes": "",
        }
        s = ExampleSentence(
            hanzi="A", pinyin="B", translation="C",
            is_valid=False,
            hanzi_errors="old error",
            translation_errors="old error",
        )
        gp = GrammarPoint(name="Test", level="A1", url_slug="t", full_url="x", sentences=[s])
        result = validate_grammar_point(gp)

        assert result.sentences[0].is_valid is True
        assert result.sentences[0].hanzi_errors == ""
        assert result.sentences[0].translation_errors == ""

    @patch("src.validator.validate_sentence")
    def test_partial_error_fields(self, mock_vs):
        mock_vs.return_value = {
            "is_valid": False,
            "translation_errors": "Only translation is wrong",
            "hanzi_errors": "",
            "pinyin_errors": "",
            "notes": "",
            "key_word": "",
        }
        s = ExampleSentence("好", "hǎo", "bad")
        gp = GrammarPoint(name="Test", level="A1", url_slug="t", full_url="x", sentences=[s])
        result = validate_grammar_point(gp)

        assert result.sentences[0].is_valid is False
        assert result.sentences[0].translation_errors == "Only translation is wrong"
        assert result.sentences[0].hanzi_errors == ""
        assert result.sentences[0].pinyin_errors == ""


class TestValidateLevel:
    @patch("src.validator.validate_grammar_point")
    def test_validates_all_points(self, mock_vgp, sample_level):
        result = validate_level(sample_level)
        assert mock_vgp.call_count == 1
        assert result is sample_level

    @patch("src.validator.time.sleep")
    @patch("src.validator.validate_grammar_point")
    def test_returns_same_level_object(self, mock_vgp, mock_sleep, sample_level):
        result = validate_level(sample_level)
        assert result is sample_level
        assert result.level == "A1"
        assert len(result.grammar_points) == 1

    @patch("src.validator.validate_grammar_point")
    def test_empty_level_does_not_crash(self, mock_vgp):
        empty = GrammarLevel(level="A1", grammar_points=[])
        result = validate_level(empty)
        assert result is empty
        mock_vgp.assert_not_called()

    @patch("src.validator.tqdm")
    @patch("src.validator.validate_grammar_point")
    def test_tqdm_created_with_total_sentences(self, mock_vgp, mock_tqdm, sample_level):
        mock_pbar = MagicMock()
        mock_tqdm.return_value.__enter__.return_value = mock_pbar
        validate_level(sample_level)
        mock_tqdm.assert_called_once()
        assert mock_tqdm.call_args[1]["total"] == 2
        assert mock_tqdm.call_args[1]["desc"] == "Validating"
        assert mock_tqdm.call_args[1]["unit"] == "sent"
