import pytest
from unittest.mock import patch
from pathlib import Path
from src.models import ExampleSentence, GrammarLevel, GrammarPoint
from src.tts_generator import get_voice, generate_sentence_audio, generate_level_audio, _EXECUTOR

class TestGetVoice:
    @patch("src.tts_generator.get", return_value="female")
    def test_default_is_female(self, mock_get):
        voice = get_voice()
        assert "Xiaoxiao" in voice
        mock_get.assert_called_once_with("tts.voice_gender", "female")

    @patch("src.tts_generator.get")
    def test_male_voice(self, mock_get):
        mock_get.return_value = "male"
        voice = get_voice()
        assert "Yunxi" in voice
        mock_get.assert_called_once_with("tts.voice_gender", "female")

    @patch("src.tts_generator.get")
    def test_female_voice(self, mock_get):
        mock_get.return_value = "female"
        voice = get_voice()
        assert "Xiaoxiao" in voice
        mock_get.assert_called_once_with("tts.voice_gender", "female")

class TestExecutor:
    def test_executor_is_module_level_singleton(self):
        assert _EXECUTOR is not None
        from concurrent.futures import ThreadPoolExecutor
        assert isinstance(_EXECUTOR, ThreadPoolExecutor)
        assert _EXECUTOR._max_workers == 1

    @patch("src.tts_generator._run_async")
    @patch("src.tts_generator.hash_string")
    def test_generates_and_updates_filename(self, mock_hash, mock_run):
        mock_hash.return_value = "abc123def456"
        s = ExampleSentence(hanzi="你好", pinyin="Nǐ hǎo", translation="Hello")
        result = generate_sentence_audio(s)
        assert result.audio_filename == "abc123def456.mp3"
        mock_hash.assert_called_once_with("你好")
        mock_run.assert_called_once()

    @patch("src.tts_generator._run_async")
    @patch("src.tts_generator.hash_string")
    def test_does_not_regenerate_existing(self, mock_hash, mock_run, tmp_path):
        mock_hash.return_value = "existingfile"
        (tmp_path / "existingfile.mp3").write_text("dummy")
        s = ExampleSentence(hanzi="你好", pinyin="Nǐ hǎo", translation="Hello")

        with patch("src.tts_generator.get_audio_dir", return_value=tmp_path):
            result = generate_sentence_audio(s)

        assert result.audio_filename == "existingfile.mp3"
        mock_run.assert_not_called()

class TestGenerateLevelAudio:
    @patch("src.tts_generator.generate_sentence_audio")
    def test_skips_invalid(self, mock_gsa):
        valid_s = ExampleSentence(hanzi="好", pinyin="hǎo", translation="good", is_valid=True)
        invalid_s = ExampleSentence(hanzi="坏", pinyin="huài", translation="bad", is_valid=False)
        gp = GrammarPoint(name="Test", level="A1", url_slug="test", full_url="x", sentences=[valid_s, invalid_s])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        generate_level_audio(level)
        assert mock_gsa.call_count == 1

    @patch("src.tts_generator.generate_sentence_audio")
    def test_generates_for_all_valid(self, mock_gsa):
        s1 = ExampleSentence(hanzi="好", pinyin="hǎo", translation="good", is_valid=True)
        s2 = ExampleSentence(hanzi="大", pinyin="dà", translation="big", is_valid=True)
        gp = GrammarPoint(name="Test", level="A1", url_slug="test", full_url="x", sentences=[s1, s2])
        level = GrammarLevel(level="A1", grammar_points=[gp])
        generate_level_audio(level)
        assert mock_gsa.call_count == 2
