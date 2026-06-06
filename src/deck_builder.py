from __future__ import annotations

import logging
import random
from pathlib import Path

import genanki
import jieba

from src.models import GrammarLevel
from src.utils import get_audio_dir, get_output_dir, hash_string

logger = logging.getLogger(__name__)

_CSS = """
body { font-size: 24px; text-align: center; font-family: 'Noto Sans SC', sans-serif; }
.pinyin { color: #666; font-size: 18px; }
.translation { color: #444; font-size: 16px; }
"""


def create_models() -> dict[str, genanki.Model]:
    m1 = genanki.Model(
        1607392319,
        "Hanzi->Full",
        fields=[
            {"name": "Hanzi"},
            {"name": "Pinyin"},
            {"name": "Translation"},
            {"name": "AudioField"},
            {"name": "GrammarPoint"},
            {"name": "WikiUrl"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": "{{Hanzi}}<br>{{AudioField}}",
                "afmt": '{{Pinyin}}<br><br>{{Translation}}<br><br>{{AudioField}}<br><br>\U0001f4d6 <a href="{{WikiUrl}}" target="_blank">{{GrammarPoint}}</a>',
            }
        ],
        css=_CSS,
    )

    m2 = genanki.Model(
        1607392320,
        "EN->Hanzi",
        fields=[
            {"name": "Translation"},
            {"name": "Hanzi"},
            {"name": "Pinyin"},
            {"name": "AudioField"},
            {"name": "GrammarPoint"},
            {"name": "WikiUrl"},
        ],
        templates=[
            {
                "name": "Card 2",
                "qfmt": "{{Translation}}",
                "afmt": '{{Hanzi}}<br><span class="pinyin">{{Pinyin}}</span><br><br>{{AudioField}}<br><br>\U0001f4d6 <a href="{{WikiUrl}}" target="_blank">{{GrammarPoint}}</a>',
            }
        ],
        css=_CSS,
    )

    m3 = genanki.Model(
        1607392321,
        "Cloze",
        model_type=genanki.CLOZE_MODEL,
        fields=[
            {"name": "HanziCloze"},
            {"name": "PinyinCloze"},
            {"name": "KeyWord"},
            {"name": "KeyPinyin"},
            {"name": "KeyTranslation"},
            {"name": "WikiUrl"},
            {"name": "GrammarPoint"},
        ],
        templates=[
            {
                "name": "Card 3",
                "qfmt": '{{cloze:HanziCloze}}<br><span class="pinyin">{{cloze:PinyinCloze}}</span>',
                "afmt": '{{cloze:HanziCloze}}<br><span class="pinyin">{{cloze:PinyinCloze}}</span><br><br>{{KeyWord}} ({{KeyPinyin}}) = {{KeyTranslation}}<br><br>\U0001f4d6 <a href="{{WikiUrl}}" target="_blank">{{GrammarPoint}}</a>',
            }
        ],
        css=_CSS,
    )

    m4 = genanki.Model(
        1607392322,
        "Ordenar",
        fields=[
            {"name": "Scrambled"},
            {"name": "Hanzi"},
            {"name": "Pinyin"},
            {"name": "Translation"},
            {"name": "AudioField"},
            {"name": "WikiUrl"},
            {"name": "GrammarPoint"},
        ],
        templates=[
            {
                "name": "Card 4",
                "qfmt": "Ordena las palabras:<br><br>{{Scrambled}}",
                "afmt": '{{Hanzi}}<br><span class="pinyin">{{Pinyin}}</span><br><br>{{Translation}}<br><br>{{AudioField}}<br><br>\U0001f4d6 <a href="{{WikiUrl}}" target="_blank">{{GrammarPoint}}</a>',
            }
        ],
        css=_CSS,
    )

    return {"hanzi_full": m1, "en_hanzi": m2, "cloze": m3, "ordenar": m4}


def _get_keyword_pinyin(hanzi: str, pinyin_str: str, keyword: str) -> str:
    start = hanzi.find(keyword)
    if start == -1 or not pinyin_str:
        return ""

    tokens = pinyin_str.split()
    char_count = len(hanzi)

    char_to_token: dict[int, int] = {}
    for i in range(char_count):
        char_to_token[i] = i if i < len(tokens) else len(tokens) - 1

    end = start + len(keyword)
    first_ti = char_to_token.get(start, 0)
    last_ti = char_to_token.get(end - 1, len(tokens) - 1)

    if first_ti < len(tokens) and last_ti < len(tokens):
        return " ".join(tokens[first_ti : last_ti + 1])
    return ""


def build_sentence_cards(
    level: GrammarLevel, models: dict
) -> list[genanki.Note]:
    notes: list[genanki.Note] = []
    stats = {
        "hanzi_full": 0,
        "en_hanzi": 0,
        "cloze": 0,
        "ordenar": 0,
        "skipped_no_keyword": 0,
        "skipped_short": 0,
    }

    for gp in level.grammar_points:
        for sentence in gp.sentences:
            if not sentence.is_valid:
                continue

            audio_field = (
                f"[sound:{sentence.audio_filename}]"
                if sentence.audio_filename
                else ""
            )

            # Hanzi->Full
            notes.append(
                genanki.Note(
                    model=models["hanzi_full"],
                    fields=[
                        sentence.hanzi,
                        sentence.pinyin,
                        sentence.translation,
                        audio_field,
                        gp.name,
                        gp.full_url,
                    ],
                    guid=hash_string(sentence.hanzi + "hanzi_full"),
                )
            )
            stats["hanzi_full"] += 1

            # EN->Hanzi
            notes.append(
                genanki.Note(
                    model=models["en_hanzi"],
                    fields=[
                        sentence.translation,
                        sentence.hanzi,
                        sentence.pinyin,
                        audio_field,
                        gp.name,
                        gp.full_url,
                    ],
                    guid=hash_string(sentence.hanzi + "en_hanzi"),
                )
            )
            stats["en_hanzi"] += 1

            # Cloze
            kw = sentence.key_word
            if kw:
                hanzi_cloze = sentence.hanzi.replace(
                    kw, f"{{{{c1::{kw}}}}}", 1
                )
                kw_py = _get_keyword_pinyin(
                    sentence.hanzi, sentence.pinyin, kw
                )
                pinyin_cloze = sentence.pinyin
                if kw_py:
                    pinyin_cloze = sentence.pinyin.replace(
                        kw_py, f"{{{{c1::{kw_py}}}}}", 1
                    )

                notes.append(
                    genanki.Note(
                        model=models["cloze"],
                        fields=[
                            hanzi_cloze,
                            pinyin_cloze,
                            kw,
                            kw_py,
                            sentence.translation,
                            gp.full_url,
                            gp.name,
                        ],
                        guid=hash_string(sentence.hanzi + "cloze"),
                    )
                )
                stats["cloze"] += 1
            else:
                stats["skipped_no_keyword"] += 1

            # Ordenar
            words = jieba.lcut(sentence.hanzi)
            if len(words) >= 2:
                sc_words = words.copy()
                random.shuffle(sc_words)
                scrambled = " · ".join(sc_words)

                notes.append(
                    genanki.Note(
                        model=models["ordenar"],
                        fields=[
                            scrambled,
                            sentence.hanzi,
                            sentence.pinyin,
                            sentence.translation,
                            audio_field,
                            gp.full_url,
                            gp.name,
                        ],
                        guid=hash_string(sentence.hanzi + "ordenar"),
                    )
                )
                stats["ordenar"] += 1
            else:
                stats["skipped_short"] += 1

    logger.info("Card stats: %s", stats)
    return notes


def build_deck(
    level: GrammarLevel,
) -> tuple[genanki.Deck, dict[str, genanki.Model]]:
    deck_id = int(hash_string(level.level), 16) % 10_000_000_000
    deck = genanki.Deck(deck_id, f"Chinese Grammar - {level.level}")
    models = create_models()
    notes = build_sentence_cards(level, models)
    for note in notes:
        deck.add_note(note)
    return deck, models


def export_deck(
    deck: genanki.Deck, models: dict, level_name: str
) -> Path:
    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"chinese-grammar-{level_name.lower()}.apkg"
    filepath = output_dir / filename

    audio_dir = get_audio_dir()
    media_files = (
        [str(p) for p in audio_dir.glob("*.mp3")] if audio_dir.exists() else []
    )

    package = genanki.Package(deck)
    if media_files:
        package.media_files = media_files
    package.write_to_file(str(filepath))
    return filepath


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from src.scraper import load_level_data

    logger.info("Loading A1 data...")
    level = load_level_data("A1")

    audio_dir = get_audio_dir()
    audio_count = (
        len(list(audio_dir.glob("*.mp3"))) if audio_dir.exists() else 0
    )

    logger.info("Building deck...")
    deck, models = build_deck(level)

    logger.info("Exporting deck...")
    path = export_deck(deck, models, level.level)

    total_valid = sum(
        1
        for gp in level.grammar_points
        for s in gp.sentences
        if s.is_valid
    )
    total_sentences = sum(len(gp.sentences) for gp in level.grammar_points)

    print(f"\nDeck exported to: {path}")
    print(f"Audio files available: {audio_count}")
    print(f"Valid sentences: {total_valid}/{total_sentences}")
    print(f"Total notes in deck: {len(deck.notes)}")


if __name__ == "__main__":
    main()
