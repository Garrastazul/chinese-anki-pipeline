import pytest
import json
from pathlib import Path
from src.config import load_config, get


class TestLoadConfig:
    def test_load_config_returns_dict(self):
        cfg = load_config()
        assert isinstance(cfg, dict)

    def test_load_config_has_expected_keys(self):
        cfg = load_config()
        assert "levels" in cfg
        assert "ollama" in cfg
        assert "tts" in cfg
        assert "anki" in cfg
        assert "scraper" in cfg

    def test_load_config_levels(self):
        cfg = load_config()
        assert isinstance(cfg["levels"], list)
        assert "A1" in cfg["levels"]

    def test_load_config_ollama_host(self):
        cfg = load_config()
        assert "localhost" in cfg["ollama"]["host"]


class TestGet:
    def test_get_top_level(self):
        v = get("levels")
        assert isinstance(v, list)

    def test_get_nested_key(self):
        v = get("ollama.model")
        assert v is not None
        assert isinstance(v, str)

    def test_get_nested_deep(self):
        v = get("scraper.base_url")
        assert "allsetlearning" in v

    def test_get_default_on_missing_key(self):
        v = get("doesnt.exist", default="fallback")
        assert v == "fallback"

    def test_get_default_on_none_value(self):
        v = get("nonexistent", default=42)
        assert v == 42

    def test_get_returns_none_for_missing_without_default(self):
        v = get("completely.fake.key")
        assert v is None

    def test_get_ollama_model(self):
        v = get("ollama.model")
        assert isinstance(v, str)
        assert len(v) > 0

    def test_get_tts_voice(self):
        v = get("tts.voice")
        assert "Xiaoxiao" in v

    def test_get_anki_deck_template(self):
        v = get("anki.deck_name_template")
        assert "{level}" in v

    def test_get_scraper_delay_is_number(self):
        v = get("scraper.request_delay")
        assert isinstance(v, (int, float))
        assert v > 0
