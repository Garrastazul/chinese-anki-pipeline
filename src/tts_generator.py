from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

from src.config import get
from src.models import ExampleSentence, GrammarLevel
from src.scraper import load_level_data, save_level_data
from src.utils import get_audio_dir, hash_string


def get_voice() -> str:
    return get("tts.voice", "zh-CN-XiaoxiaoNeural")


async def generate_audio(text: str, filename: str) -> Path:
    audio_dir = get_audio_dir()
    audio_dir.mkdir(parents=True, exist_ok=True)
    filepath = audio_dir / filename
    if filepath.exists():
        return filepath
    tts = edge_tts.Communicate(text, get_voice())
    await tts.save(str(filepath))
    return filepath


def generate_sentence_audio(sentence: ExampleSentence) -> ExampleSentence:
    h = hash_string(sentence.hanzi)
    filename = f"{h}.mp3"
    audio_dir = get_audio_dir()
    if not (audio_dir / filename).exists():
        asyncio.run(generate_audio(sentence.hanzi, filename))
    sentence.audio_filename = filename
    return sentence


def generate_level_audio(level: GrammarLevel) -> GrammarLevel:
    for gp in level.grammar_points:
        for sentence in gp.sentences:
            if sentence.is_valid:
                generate_sentence_audio(sentence)
    return level


def main() -> None:
    level = load_level_data("A1")
    audio_dir = get_audio_dir()

    already_existed = 0
    for gp in level.grammar_points:
        for s in gp.sentences:
            if s.is_valid:
                h = hash_string(s.hanzi)
                if (audio_dir / f"{h}.mp3").exists():
                    already_existed += 1

    generate_level_audio(level)
    save_level_data(level)

    valid_count = sum(1 for gp in level.grammar_points for s in gp.sentences if s.is_valid)
    generated = valid_count - already_existed
    print(f"Generated {generated} new audio files, {already_existed} already existed")


if __name__ == "__main__":
    main()
