import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.main import install_dependencies, run_pipeline


class TestInstallDependencies:
    @patch("src.main.subprocess.run")
    @patch("importlib.import_module")
    def test_install_success(self, mock_import, mock_run):
        install_dependencies()
        mock_import.assert_called()

    @patch("subprocess.run")
    @patch("importlib.import_module")
    def test_install_missing_packages_exits(self, mock_import, mock_run):
        mock_import.side_effect = ImportError("missing")
        with pytest.raises(SystemExit):
            install_dependencies()


class TestRunPipeline:
    @patch("src.main.scraper.scrape_level")
    @patch("src.main.scraper.save_level_data")
    @patch("src.main.validator.ensure_ollama_running")
    @patch("src.main.validator.ensure_model")
    @patch("src.main.validator.validate_level")
    @patch("src.main.tts_generator.generate_level_audio")
    @patch("src.main.deck_builder.build_and_export")
    @patch("src.main.scraper.load_level_data")
    def test_pipeline_full(
        self, mock_load, mock_build, mock_tts, mock_validate_level,
        mock_ensure_model, mock_ensure_ollama, mock_save, mock_scrape,
        sample_level
    ):
        mock_scrape.return_value = sample_level
        mock_load.return_value = sample_level
        mock_build.return_value = Path("/fake/output.apkg")

        run_pipeline(level_name="A1", skip_scrape=False, skip_validate=False, skip_tts=False)

        mock_scrape.assert_called_once_with("A1")
        mock_save.assert_called()
        mock_ensure_ollama.assert_called_once()
        mock_ensure_model.assert_called_once()
        mock_tts.assert_called_once()
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
        mock_load.assert_called()
        mock_build.assert_called_once()

    @patch("src.main.argparse.ArgumentParser.parse_args")
    def test_main_arguments_default(self, mock_parse):
        from src.main import main
