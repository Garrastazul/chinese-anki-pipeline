import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
from src.models import ExampleSentence, GrammarLevel, GrammarPoint
from src.tts_generator import get_voice, generate_audio, generate_sentence_audio, generate_level_audio


class TestGetVoice:
    def test_returns_voice_string(self):
        voice = get_voice()
        assert isinstance(voice, str)
        assert "Xiaoxiao" in voice


class TestGenerateAudio:
    @pytest.mark.asyncio
    @patch("src.tts_generator.get_audio_dir")
    @patch("src.tts_generator.edge_tts.Communicate")
    async def test_generate_audio_new_file(self, mock_comm, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        mock_tts = AsyncMock()
        mock_comm.return_value = mock_tts

        result = await generate_audio("你好", "test123.mp3")
        assert result == tmp_path / "test123.mp3"
        mock_tts.save.assert_awaited_once_with(str(tmp_path / "test123.mp3"))

    @patch("src.tts_generator.get_audio_dir")
    async def test_generate_audio_skips_existing(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        existing = tmp_path / "existing.mp3"
        existing.write_text("dummy")

        result = await generate_audio("你好", "existing.mp3")
        assert result == existing


class TestGenerateSentenceAudio:
    @patch("src.tts_generator.generate_audio")
    @patch("src.tts_generator.hash_string")
    def test_generates_and_updates_filename(self, mock_hash, mock_ga, sample_sentence):
        mock_hash.return_value = "abc123def456"
        mock_ga.return_value = Path("/audio/abc123def456.mp3")

        result = generate_sentence_audio(sample_sentence)
        assert result.audio_filename == "abc123def456.mp3"
        mock_hash.assert_called_once_with(sample_sentence.hanzi)


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
