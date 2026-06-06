import subprocess

import pytest
from unittest.mock import patch, MagicMock
import json
import requests
from src.models import ExampleSentence, GrammarPoint, GrammarLevel
from src.validator import (
    validate_sentence, validate_grammar_point, validate_level,
    ensure_ollama_running, ensure_model,
)


class TestEnsureOllamaRunning:
    @patch("src.validator.subprocess.run")
    @patch("src.validator.requests.get")
    @patch("src.validator.time.sleep")
    def test_ensure_ollama_running_success(self, mock_sleep, mock_get, mock_run):
        mock_get.return_value.raise_for_status.return_value = None
        ensure_ollama_running()
        mock_run.assert_called_once()
        mock_get.assert_called_once()

    @patch("src.validator.subprocess.run")
    @patch("src.validator.requests.get")
    @patch("src.validator.time.sleep")
    def test_ensure_ollama_running_failure(self, mock_sleep, mock_get, mock_run):
        mock_get.side_effect = requests.ConnectionError("No connection")
        with pytest.raises(RuntimeError, match="Ollama is not running"):
            ensure_ollama_running()


class TestEnsureModel:
    @patch("src.validator.subprocess.run")
    def test_ensure_model_default(self, mock_run):
        ensure_model()
        mock_run.assert_called_once()

    @patch("src.validator.subprocess.run")
    def test_ensure_model_custom_name(self, mock_run):
        ensure_model("llama3:8b")
        args = mock_run.call_args[0][0]
        assert "llama3:8b" in args

    @patch("src.validator.subprocess.run")
    def test_ensure_model_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("wsl not found")
        ensure_model("test-model")
        mock_run.assert_called_once()

    @patch("src.validator.subprocess.run")
    def test_ensure_model_called_process_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "wsl ollama pull test-model", stderr="model not found")
        ensure_model("test-model")
        mock_run.assert_called_once()


class TestValidateSentence:
    @patch("src.validator.requests.post")
    def test_valid_sentence(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "response": json.dumps({
                "is_valid": True,
                "hanzi_errors": "",
                "pinyin_errors": "",
                "translation_errors": "",
                "key_word": "和",
                "notes": "",
            })
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
            "response": json.dumps({
                "is_valid": False,
                "hanzi_errors": "Typo",
                "pinyin_errors": "",
                "translation_errors": "",
                "key_word": "",
                "notes": "",
            })
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(s, "Test")
        assert result["is_valid"] is False

    @patch("src.validator.requests.post")
    def test_ollama_returns_markdown_json(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "response": "```json\n{\"is_valid\": true, \"key_word\": \"和\"}\n```"
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is True
        assert result["key_word"] == "和"

    @patch("src.validator.requests.post")
    def test_ollama_returns_garbage_fallback(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "not json at all"}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is True
        assert "Validation error" in result.get("notes", "")

    @patch("src.validator.requests.post")
    def test_ollama_timeout_retry(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": json.dumps({"is_valid": True, "key_word": "key"})}
        mock_resp.raise_for_status.return_value = None
        mock_post.side_effect = [requests.Timeout("timeout"), mock_resp]

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is True

    @patch("src.validator.requests.post")
    def test_markdown_fence_no_closing(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "response": '```json\n{"is_valid": true, "key_word": "和"}'
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is True
        assert result["key_word"] == "和"

    @patch("src.validator.requests.post")
    def test_markdown_fence_inline_closing(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "response": '```json\n{"is_valid": true, "key_word": "和"}```'
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is True
        assert result["key_word"] == "和"

    @patch("src.validator.requests.post")
    def test_markdown_fence_trailing_text(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "response": '```json\n{"is_valid": true, "key_word": "和"}\n``` some trailing text'
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = validate_sentence(sample_sentence, "Test")
        assert result["is_valid"] is True
        assert result["key_word"] == "和"

    @patch("src.validator.requests.post")
    def test_retry_three_attempts(self, mock_post, sample_sentence):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": '{"is_valid": true, "key_word": "ok"}'}
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


class TestValidateGrammarPoint:
    @patch("src.validator.validate_sentence")
    def test_validates_all_sentences(self, mock_vs, sample_grammar_point):
        mock_vs.return_value = {"is_valid": True, "key_word": "和"}
        result = validate_grammar_point(sample_grammar_point)
        assert mock_vs.call_count == 2
        assert result.sentences[0].is_valid is True
        assert result.sentences[0].key_word == "和"


class TestValidateLevel:
    @patch("src.validator.validate_grammar_point")
    def test_validates_all_points(self, mock_vgp, sample_level):
        validate_level(sample_level)
        assert mock_vgp.call_count == 1
