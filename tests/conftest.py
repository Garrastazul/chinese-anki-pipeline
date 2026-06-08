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
        pattern="N. + 和 + N.",
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
def index_no_wikitable_html() -> str:
    path = Path(__file__).parent / "fixtures" / "index_no_wikitable_class.html"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture
def index_shuffled_html() -> str:
    path = Path(__file__).parent / "fixtures" / "index_shuffled_columns.html"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture
def grammar_liju_alt_html() -> str:
    path = Path(__file__).parent / "fixtures" / "grammar_liju_alt_class.html"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture
def grammar_no_liju_html() -> str:
    path = Path(__file__).parent / "fixtures" / "grammar_no_liju_table_only.html"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture
def grammar_py_class_html() -> str:
    path = Path(__file__).parent / "fixtures" / "grammar_pinyin_as_py_class.html"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture
def grammar_trans_last_td_html() -> str:
    path = Path(__file__).parent / "fixtures" / "grammar_trans_in_last_td.html"
    return path.read_text(encoding="utf-8") if path.exists() else ""

