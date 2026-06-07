import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.main import install_dependencies, run_pipeline, main


class TestInstallDependencies:
    @patch("src.main.subprocess.run")
    @patch("src.main.importlib.import_module")
    def test_install_success(self, mock_import, mock_run):
        install_dependencies()
        mock_import.assert_called()

    @patch("src.main.subprocess.run")
    @patch("src.main.importlib.import_module")
    def test_install_missing_packages_exits(self, mock_import, mock_run):
        mock_import.side_effect = ImportError("missing")
        with pytest.raises(SystemExit):
            install_dependencies()

class TestRunPipeline:
    @patch("src.main.scraper.scrape_level")
    @patch("src.main.scraper.save_level_data")
    @patch("src.main.validator.validate_level")
    @patch("src.main.tts_generator.generate_level_audio")
    @patch("src.main.deck_builder.build_and_export")
    @patch("src.main.scraper.load_level_data")
    def test_pipeline_full(
        self, mock_load, mock_build, mock_tts, mock_validate_level,
        mock_save, mock_scrape, sample_level
    ):
        mock_scrape.return_value = sample_level
        mock_load.return_value = sample_level
        mock_build.return_value = Path("/fake/output.apkg")
        run_pipeline(level_name="A1", skip_scrape=False, skip_validate=False, skip_tts=False)
        mock_scrape.assert_called_once_with("A1")
        mock_save.assert_called()
        mock_tts.assert_called_once()
        mock_load.assert_not_called()
        mock_build.assert_called_once()

    @patch("src.main.scraper.load_level_data")
    @patch("src.main.deck_builder.build_and_export")
    def test_pipeline_skip_all(self, mock_build, mock_load, sample_level):
        mock_load.return_value = sample_level
        mock_build.return_value = Path("/fake/output.apkg")
        run_pipeline(level_name="A1", skip_scrape=True, skip_validate=True, skip_tts=True)
        mock_build.assert_called_once()

    @patch("src.main.scraper.scrape_level")
    @patch("src.main.scraper.save_level_data")
    @patch("src.main.scraper.load_level_data")
    @patch("src.main.deck_builder.build_and_export")
    def test_pipeline_scrape_only(self, mock_build, mock_load, mock_save, mock_scrape, sample_level):
        mock_scrape.return_value = sample_level
        mock_load.return_value = sample_level
        mock_build.return_value = Path("/fake/output.apkg")
        run_pipeline(level_name="A1", skip_scrape=False, skip_validate=True, skip_tts=True)
        mock_scrape.assert_called_once()
        mock_save.assert_called_once()
        mock_load.assert_not_called()
        mock_build.assert_called_once()

    @patch("src.main.scraper.scrape_level")
    @patch("src.main.scraper.save_level_data")
    @patch("src.main.validator.validate_level")
    @patch("src.main.tts_generator.generate_level_audio")
    @patch("src.main.deck_builder.build_and_export")
    @patch("src.main.scraper.load_level_data")
    def test_pipeline_all_levels(
        self, mock_load, mock_build, mock_tts, mock_validate_level,
        mock_save, mock_scrape, sample_level
    ):
        mock_scrape.return_value = sample_level
        mock_load.return_value = sample_level
        mock_build.return_value = Path("/fake/output.apkg")
        run_pipeline(all_levels=True)
        mock_scrape.assert_called_once_with("A1")
        mock_save.assert_called()
        mock_tts.assert_called_once()
        mock_build.assert_called_once()

    @patch("src.main.validator.validate_level")
    @patch("src.main.scraper.save_level_data")
    @patch("src.main.scraper.load_level_data")
    def test_keyboard_interrupt_during_validate_saves_partial(
        self, mock_load, mock_save, mock_validate, sample_level
    ):
        mock_load.return_value = sample_level
        mock_validate.side_effect = KeyboardInterrupt()
        with pytest.raises(SystemExit) as exc:
            run_pipeline(level_name="A1", skip_scrape=True, skip_validate=False, skip_tts=True)
        assert exc.value.code == 130
        mock_save.assert_called_once()

    @patch("src.main.get")
    def test_main_warns_on_invalid_level(self, mock_get):
        mock_get.side_effect = lambda key, default=None: {
            "levels": ["A1"],
            "ollama.model": "qwen2.5:7b",
            "ollama.endpoint": "http://localhost:11434/v1/chat/completions",
            "tts.voice_gender": "female",
            "anki.deck_name_template": "Chinese Grammar - {level}",
            "scraper.base_url": "https://resources.allsetlearning.com/chinese/grammar",
            "scraper.request_delay": 1.0,
            "validator.sentence_delay": 0.5,
        }.get(key, default)

        with patch("src.main.logger") as mock_logger:
            with patch("src.main.run_pipeline"):
                with patch("sys.argv", ["main.py", "--level", "B2"]):
                    main()
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args[0]
                assert "B2" in str(call_args)
                assert "A1" in str(call_args)
