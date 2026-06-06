from __future__ import annotations

import argparse
import importlib
import logging
import subprocess
import sys
from pathlib import Path

from src import scraper, validator, tts_generator, deck_builder
from src.utils import get_audio_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

REQUIRED_PACKAGES = ["requests", "bs4", "lxml", "edge_tts", "genanki", "jieba", "mutagen"]


def install_dependencies() -> None:
    logger.info("Installing dependencies...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError:
        logger.info("Editable install failed, trying direct install...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install"] + REQUIRED_PACKAGES,
            check=True,
        )

    logger.info("Verifying installations...")
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        logger.error("Missing packages: %s", missing)
        sys.exit(1)
    logger.info("All dependencies installed successfully.")


def run_pipeline(
    level_name: str = "A1",
    skip_scrape: bool = False,
    skip_validate: bool = False,
    skip_tts: bool = False,
) -> None:
    if not skip_scrape:
        logger.info("Step a) Scraping grammar points for %s...", level_name)
        level = scraper.scrape_level(level_name)
        scraper.save_level_data(level)
        total = sum(len(gp.sentences) for gp in level.grammar_points)
        print(f"  Scraped {len(level.grammar_points)} grammar points, {total} sentences")

    if not skip_validate:
        logger.info("Step b) Validating sentences for %s...", level_name)
        validator.ensure_ollama_running()
        validator.ensure_model()
        level = scraper.load_level_data(level_name)
        level = validator.validate_level(level)
        scraper.save_level_data(level)
        valid = sum(1 for gp in level.grammar_points for s in gp.sentences if s.is_valid)
        invalid = sum(1 for gp in level.grammar_points for s in gp.sentences if not s.is_valid)
        with_kw = sum(1 for gp in level.grammar_points for s in gp.sentences if s.key_word)
        print(f"  Validation: {valid} valid, {invalid} invalid, {with_kw} with key_word")

    if not skip_tts:
        logger.info("Step c) Generating TTS audio for %s...", level_name)
        level = scraper.load_level_data(level_name)
        level = tts_generator.generate_level_audio(level)
        scraper.save_level_data(level)
        audio_dir = get_audio_dir()
        audio_count = len(list(audio_dir.glob("*.mp3"))) if audio_dir.exists() else 0
        print(f"  Audio files: {audio_count}")

    logger.info("Step d) Building Anki deck for %s...", level_name)
    level = scraper.load_level_data(level_name)
    path = deck_builder.build_and_export(level)
    valid = sum(1 for gp in level.grammar_points for s in gp.sentences if s.is_valid)
    total = sum(len(gp.sentences) for gp in level.grammar_points)
    print(f"  Deck exported to: {path}")
    print(f"  Valid sentences: {valid}/{total}")

    print(f"\nPipeline for {level_name} completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chinese Grammar Flashcard Pipeline")
    parser.add_argument("--level", default="A1", help="Grammar level (default: A1)")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping step")
    parser.add_argument("--skip-validate", action="store_true", help="Skip validation step")
    parser.add_argument("--skip-tts", action="store_true", help="Skip TTS generation step")
    parser.add_argument("--install", action="store_true", help="Install dependencies and exit")
    args = parser.parse_args()

    if args.install:
        install_dependencies()
        return

    run_pipeline(
        level_name=args.level,
        skip_scrape=args.skip_scrape,
        skip_validate=args.skip_validate,
        skip_tts=args.skip_tts,
    )


if __name__ == "__main__":
    main()
