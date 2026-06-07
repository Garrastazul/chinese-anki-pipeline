from __future__ import annotations

import argparse
import importlib
import logging
import subprocess
import sys
from pathlib import Path

from src import scraper, validator, tts_generator, deck_builder, pinyin_generator
from src.config import get
from src.utils import get_audio_dir

logger = logging.getLogger(__name__)

REQUIRED_PACKAGES = ["requests", "bs4", "lxml", "edge_tts", "genanki", "jieba", "pypinyin", "tqdm"]


def install_dependencies() -> None:
    logger.info("Installing dependencies...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        logger.info("Editable install failed (exit code %d), trying direct install...", e.returncode)
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install"] + REQUIRED_PACKAGES,
                check=True,
                capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e2:
            logger.error(
                "Direct install also failed (exit code %d). "
                "Try: pip install %s",
                e2.returncode, " ".join(REQUIRED_PACKAGES),
            )
            sys.exit(1)

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
    level_name: str | None = None,
    skip_scrape: bool = False,
    skip_validate: bool = False,
    skip_pinyin: bool = False,
    skip_tts: bool = False,
    all_levels: bool = False,
) -> None:
    levels: list[str] = get("levels", ["A1"])
    if level_name is None:
        level_name = levels[0] if levels else "A1"

    if all_levels:
        for ln in levels:
            _run_single_level(ln, skip_scrape, skip_validate, skip_pinyin, skip_tts)
        return

    _run_single_level(level_name, skip_scrape, skip_validate, skip_pinyin, skip_tts)


def _run_single_level(
    level_name: str,
    skip_scrape: bool,
    skip_validate: bool,
    skip_pinyin: bool,
    skip_tts: bool,
) -> None:
    level = None

    if not skip_scrape:
        logger.info("Step a) Scraping grammar points for %s...", level_name)
        level = scraper.scrape_level(level_name)
        scraper.save_level_data(level)
        total = sum(len(gp.sentences) for gp in level.grammar_points)
        print(f"  Scraped {len(level.grammar_points)} grammar points, {total} sentences")

    if not skip_validate:
        logger.info("Step b) Validating sentences for %s...", level_name)
        if level is None:
            level = scraper.load_level_data(level_name)
        try:
            level = validator.validate_level(level)
        except KeyboardInterrupt:
            scraper.save_level_data(level)
            print(f"\nInterrupted during validation. Partial results saved for {level_name}.")
            sys.exit(130)
        scraper.save_level_data(level)
        valid = sum(1 for gp in level.grammar_points for s in gp.sentences if s.is_valid)
        invalid = sum(1 for gp in level.grammar_points for s in gp.sentences if not s.is_valid)
        with_kw = sum(1 for gp in level.grammar_points for s in gp.sentences if s.key_word)
        print(f"  Validation: {valid} valid, {invalid} invalid, {with_kw} with key_word")

    if not skip_pinyin:
        logger.info("Step c) Regenerating pinyin for %s...", level_name)
        if level is None:
            level = scraper.load_level_data(level_name)
        level = pinyin_generator.regenerate_level_pinyin(level)
        scraper.save_level_data(level)
        print(f"  Pinyin regenerated for all valid sentences")

    if not skip_tts:
        logger.info("Step d) Generating TTS audio for %s...", level_name)
        if level is None:
            level = scraper.load_level_data(level_name)
        level = tts_generator.generate_level_audio(level)
        scraper.save_level_data(level)
        audio_dir = get_audio_dir()
        audio_count = len(list(audio_dir.glob("*.mp3"))) if audio_dir.exists() else 0
        print(f"  Audio files: {audio_count}")

    logger.info("Step e) Building Anki deck for %s...", level_name)
    if level is None:
        level = scraper.load_level_data(level_name)
    path = deck_builder.build_and_export(level)
    valid = sum(1 for gp in level.grammar_points for s in gp.sentences if s.is_valid)
    total = sum(len(gp.sentences) for gp in level.grammar_points)
    print(f"  Deck exported to: {path}")
    print(f"  Valid sentences: {valid}/{total}")

    print(f"\nPipeline for {level_name} completed successfully.")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Chinese Grammar Flashcard Pipeline")
    default_level = (get("levels", ["A1"]) or ["A1"])[0]
    parser.add_argument("--level", default=default_level, help=f"Grammar level (default: {default_level})")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping step")
    parser.add_argument("--skip-validate", action="store_true", help="Skip validation step")
    parser.add_argument("--skip-tts", action="store_true", help="Skip TTS generation step")
    parser.add_argument("--skip-pinyin", action="store_true", help="Skip pinyin regeneration step")
    parser.add_argument("--all-levels", action="store_true", help="Process all levels configured in config.json")
    parser.add_argument("--install", action="store_true", help="Install dependencies and exit")
    args = parser.parse_args()

    if args.install:
        install_dependencies()
        return

    valid_levels = get("levels", ["A1"])
    if args.level not in valid_levels:
        logger.warning("Level %r not in configured levels %s", args.level, valid_levels)

    run_pipeline(
        level_name=args.level,
        skip_scrape=args.skip_scrape,
        skip_validate=args.skip_validate,
        skip_pinyin=args.skip_pinyin,
        skip_tts=args.skip_tts,
        all_levels=args.all_levels,
    )


if __name__ == "__main__":
    main()
