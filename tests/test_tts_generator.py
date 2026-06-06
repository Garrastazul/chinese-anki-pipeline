import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.models import ExampleSentence, GrammarLevel, GrammarPoint
from src.tts_generator import get_voice, generate_sentence_audio, generate_level_audio

class TestGetVoice:
    def test_returns_voice_string(self):
        voice = get_voice()
        assert isinstance(voice, str)
        assert "Xiaoxiao" in voice

class TestGenerateSentenceAudio:
    @patch("src.tts_generator.asyncio.run")
    @patch("src.tts_generator.hash_string")
    def test_generates_and_updates_filename(self, mock_hash, mock_asyncio_run):
        mock_hash.return_value = "abc123def456"
        s = ExampleSentence(hanzi="你好", pinyin="Nǐ hǎo", translation="Hello")
        result = generate_sentence_audio(s)
        assert result.audio_filename == "abc123def456.mp3"
        mock_hash.assert_called_once_with("你好")
        mock_asyncio_run.assert_called_once()

    @patch("src.tts_generator.asyncio.run")
    @patch("src.tts_generator.hash_string")
    def test_does_not_regenerate_existing(self, mock_hash, mock_asyncio_run, tmp_path):
        mock_hash.return_value = "existingfile"
        (tmp_path / "existingfile.mp3").write_text("dummy")
        s = ExampleSentence(hanzi="你好", pinyin="Nǐ hǎo", translation="Hello")

        with patch("src.tts_generator.get_audio_dir", return_value=tmp_path):
            result = generate_sentence_audio(s)

        assert result.audio_filename == "existingfile.mp3"
        # asyncio.run no debería llamarse porque el archivo ya existe
        mock_asyncio_run.assert_not_called()

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
