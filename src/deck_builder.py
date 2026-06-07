from __future__ import annotations

import logging
import random
from pathlib import Path

import genanki
import jieba

from src.config import get
from src.models import GrammarLevel
from src.utils import get_audio_dir, get_output_dir, hash_string

logger = logging.getLogger(__name__)

_CSS = """
body { font-size: 24px; text-align: center; font-family: 'Noto Sans SC', 'Noto Sans', 'Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', sans-serif; }
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
        model_type=1,
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
        "Reorder",
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
                "qfmt": "Arrange the words:<br><br>{{Scrambled}}",
                "afmt": '{{Hanzi}}<br><span class="pinyin">{{Pinyin}}</span><br><br>{{Translation}}<br><br>{{AudioField}}<br><br>\U0001f4d6 <a href="{{WikiUrl}}" target="_blank">{{GrammarPoint}}</a>',
            }
        ],
        css=_CSS,
    )

    return {"hanzi_full": m1, "en_hanzi": m2, "cloze": m3, "reorder": m4}


def _find_keyword_position(hanzi: str, keyword: str) -> int | None:
    """Find keyword position aligned with jieba word boundaries."""
    if not keyword:
        return None
    words = list(jieba.lcut(hanzi))
    kw_len = len(keyword)
    aligned = None
    first = None
    pos = 0
    while True:
        pos = hanzi.find(keyword, pos)
        if pos == -1:
            break
        if first is None:
            first = pos
        cum = 0
        for w in words:
            w_stripped = w.strip()
            if not w_stripped:
                cum += len(w)
                continue
            w_start = cum
            w_end = cum + len(w)
            if pos >= w_start and pos + kw_len <= w_end and (
                (pos == w_start and pos + kw_len == w_end) or kw_len == len(w_stripped)
            ):
                aligned = pos
                break
            cum = w_end
        if aligned is not None:
            return aligned
        pos += 1
    return first


def _apply_cloze(hanzi: str, keyword: str) -> str:
    pos = _find_keyword_position(hanzi, keyword)
    if pos is not None:
        return (
            hanzi[:pos]
            + f"{{{{c1::{keyword}}}}}"
            + hanzi[pos + len(keyword):]
        )
    return hanzi


def _get_keyword_token_range(hanzi: str, pinyin_str: str, keyword: str) -> tuple[int, int] | None:
    if not keyword or not pinyin_str:
        return None
    tokens = pinyin_str.split()
    kw_parts = [kp for kp in keyword.split() if kp]

    def _find_range(parts):
        for i in range(len(parts) - len(kw_parts) + 1):
            if parts[i:i + len(kw_parts)] == kw_parts:
                return (i, i + len(kw_parts))
        return None

    hanzi_parts = hanzi.split()
    if len(hanzi_parts) == len(tokens):
        result = _find_range(hanzi_parts)
        if result:
            return result

    words = [w for w in jieba.cut(hanzi) if w.strip()]
    if len(words) == len(tokens):
        result = _find_range(words)
        if result:
            return result

    pos = _find_keyword_position(hanzi, keyword)
    if pos is None:
        return None
    non_space = [i for i, c in enumerate(hanzi) if c != " "]
    if not non_space:
        return None
    kw_start = sum(1 for i in non_space if i < pos)
    kw_non_space_count = sum(1 for c in keyword if c != " ")
    kw_end = kw_start + kw_non_space_count - 1

    total_chars = len(non_space)
    num_tokens = len(tokens)

    base = total_chars // num_tokens
    rem = total_chars % num_tokens
    token_sizes = [base + (1 if i < rem else 0) for i in range(num_tokens)]

    char_to_token: list[int] = []
    for ti, size in enumerate(token_sizes):
        char_to_token.extend([ti] * size)

    first_ti = char_to_token[kw_start]
    last_ti = char_to_token[kw_end]
    return (first_ti, last_ti + 1)


def _get_keyword_pinyin(hanzi: str, pinyin_str: str, keyword: str, _token_range: tuple[int, int] | None = None) -> str:
    if _token_range is None:
        _token_range = _get_keyword_token_range(hanzi, pinyin_str, keyword)
    if _token_range is None:
        return ""
    tokens = pinyin_str.split()
    return " ".join(tokens[_token_range[0]:_token_range[1]])


def _apply_pinyin_cloze(hanzi: str, pinyin_str: str, keyword: str, _token_range: tuple[int, int] | None = None) -> str:
    if _token_range is None:
        _token_range = _get_keyword_token_range(hanzi, pinyin_str, keyword)
    if _token_range is None:
        return pinyin_str
    tokens = pinyin_str.split()
    kw_py = " ".join(tokens[_token_range[0]:_token_range[1]])
    prefix = " ".join(tokens[:_token_range[0]])
    suffix = " ".join(tokens[_token_range[1]:])
    cloze = f"{{{{c1::{kw_py}}}}}"
    parts = [p for p in (prefix, cloze, suffix) if p]
    return " ".join(parts)


def _get_available_types(sentence: ExampleSentence) -> list[str]:
    """Return which card types are available for the given sentence."""
    available = ["hanzi_full", "en_hanzi"]
    if sentence.key_word:
        available.append("cloze")
    if len(jieba.lcut(sentence.hanzi)) >= 2:
        available.append("reorder")
    return available


def _build_hanzi_full_card(
    sentence: ExampleSentence, gp: GrammarPoint, audio_field: str, models: dict
) -> genanki.Note:
    return genanki.Note(
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


def _build_en_hanzi_card(
    sentence: ExampleSentence, gp: GrammarPoint, audio_field: str, models: dict
) -> genanki.Note:
    return genanki.Note(
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


def _build_cloze_card(
    sentence: ExampleSentence, gp: GrammarPoint, audio_field: str, models: dict
) -> genanki.Note:
    kw = sentence.key_word
    hanzi_cloze = _apply_cloze(sentence.hanzi, kw)
    kw_tr = _get_keyword_token_range(sentence.hanzi, sentence.pinyin, kw)
    kw_py = _get_keyword_pinyin(sentence.hanzi, sentence.pinyin, kw, kw_tr)
    pinyin_cloze = _apply_pinyin_cloze(sentence.hanzi, sentence.pinyin, kw, kw_tr)
    return genanki.Note(
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


def _build_reorder_card(
    sentence: ExampleSentence, gp: GrammarPoint, audio_field: str, models: dict
) -> genanki.Note:
    words = jieba.lcut(sentence.hanzi)
    sc_words = words.copy()
    random.Random(sentence.hanzi).shuffle(sc_words)
    scrambled = " · ".join(sc_words)
    return genanki.Note(
        model=models["reorder"],
        fields=[
            scrambled,
            sentence.hanzi,
            sentence.pinyin,
            sentence.translation,
            audio_field,
            gp.full_url,
            gp.name,
        ],
        guid=hash_string(sentence.hanzi + "reorder"),
    )


_CARD_BUILDERS: dict[str, callable] = {
    "hanzi_full": _build_hanzi_full_card,
    "en_hanzi": _build_en_hanzi_card,
    "cloze": _build_cloze_card,
    "reorder": _build_reorder_card,
}


def build_sentence_cards(
    level: GrammarLevel, models: dict
) -> list[genanki.Note]:
    notes: list[genanki.Note] = []
    stats = {
        "hanzi_full": 0,
        "en_hanzi": 0,
        "cloze": 0,
        "reorder": 0,
        "skipped_no_keyword": 0,
        "skipped_short": 0,
    }

    mode = get("generation.mode", "all")
    config_types = get(
        "generation.card_types",
        ["hanzi_full", "en_hanzi", "cloze", "reorder"],
    )
    num_types = len(config_types)

    type_index = 0

    for gp in level.grammar_points:
        for sentence in gp.sentences:
            if not sentence.is_valid:
                continue

            audio_field = (
                f"[sound:{sentence.audio_filename}]"
                if sentence.audio_filename
                else ""
            )

            if mode == "rotate":
                available = _get_available_types(sentence)
                assigned_type = None
                for offset in range(num_types):
                    candidate = config_types[(type_index + offset) % num_types]
                    if candidate in available:
                        assigned_type = candidate
                        break

                if assigned_type is None:
                    continue

                type_index = (type_index + 1) % num_types

                builder = _CARD_BUILDERS[assigned_type]
                notes.append(builder(sentence, gp, audio_field, models))
                stats[assigned_type] += 1

            else:
                # Default "all" mode — original behavior

                notes.append(_build_hanzi_full_card(sentence, gp, audio_field, models))
                stats["hanzi_full"] += 1

                notes.append(_build_en_hanzi_card(sentence, gp, audio_field, models))
                stats["en_hanzi"] += 1

                if sentence.key_word:
                    notes.append(_build_cloze_card(sentence, gp, audio_field, models))
                    stats["cloze"] += 1
                else:
                    stats["skipped_no_keyword"] += 1

                if len(jieba.lcut(sentence.hanzi)) >= 2:
                    notes.append(_build_reorder_card(sentence, gp, audio_field, models))
                    stats["reorder"] += 1
                else:
                    stats["skipped_short"] += 1

    logger.info("Card stats: %s", stats)
    return notes


def build_deck(
    level: GrammarLevel,
) -> tuple[genanki.Deck, dict[str, genanki.Model]]:
    deck_name = get("anki.deck_name_template", "Chinese Grammar - {level}").format(level=level.level)
    deck_id = int(hash_string(level.level), 16) % 10_000_000_000
    deck = genanki.Deck(deck_id, deck_name)
    models = create_models()
    notes = build_sentence_cards(level, models)
    for note in notes:
        deck.add_note(note)
    return deck, models


def _get_needed_audio(level: GrammarLevel) -> set[str]:
    needed: set[str] = set()
    for gp in level.grammar_points:
        for s in gp.sentences:
            if s.is_valid and s.audio_filename:
                needed.add(s.audio_filename)
    return needed


def export_deck(
    deck: genanki.Deck, models: dict, level: GrammarLevel
) -> Path:
    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"chinese-grammar-{level.level.lower()}.apkg"
    filepath = output_dir / filename

    audio_dir = get_audio_dir()
    needed = _get_needed_audio(level)
    media_files = (
        [str(p) for p in audio_dir.glob("*.mp3") if p.name in needed]
        if audio_dir.exists() and needed
        else []
    )

    package = genanki.Package(deck)
    if media_files:
        package.media_files = media_files
    package.write_to_file(str(filepath))
    return filepath


def build_and_export(level: GrammarLevel) -> Path:
    deck, models = build_deck(level)
    return export_deck(deck, models, level)


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
    path = export_deck(deck, models, level)

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
