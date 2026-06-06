import json
import pytest
from pathlib import Path
from src.models import ExampleSentence, GrammarPoint, GrammarLevel


@pytest.fixture
def sample_sentence() -> ExampleSentence:
    return ExampleSentence(
        hanzi="我 爱 你。",
        pinyin="Wǒ ài nǐ.",
        translation="I love you.",
    )


@pytest.fixture
def sample_sentence_full() -> ExampleSentence:
    return ExampleSentence(
        hanzi="我 和 他 都 不 去。",
        pinyin="Wǒ hé tā dōu bù qù.",
        translation="He and I are both not going.",
        is_valid=True,
        key_word="和",
        audio_filename="abc123.mp3",
    )


@pytest.fixture
def sample_grammar_point(sample_sentence_full, sample_sentence) -> GrammarPoint:
    return GrammarPoint(
        name="Expressing 'and' with 'he'",
        level="A1",
        url_slug="ASGP0KFF",
        full_url="https://resources.allsetlearning.com/chinese/grammar/ASGP0KFF",
        sentences=[sample_sentence_full, sample_sentence],
    )


@pytest.fixture
def sample_level(sample_grammar_point) -> GrammarLevel:
    return GrammarLevel(level="A1", grammar_points=[sample_grammar_point])


@pytest.fixture
def sample_index_html() -> str:
    path = Path(__file__).parent / "fixtures" / "sample_index.html"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture
def sample_grammar_html() -> str:
    path = Path(__file__).parent / "fixtures" / "sample_grammar_page.html"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture
def sample_json_data() -> dict:
    path = Path(__file__).parent / "fixtures" / "sample_level_data.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
