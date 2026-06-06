from src.models import ExampleSentence, GrammarPoint, GrammarLevel


def test_example_sentence_defaults():
    s = ExampleSentence(hanzi="你好", pinyin="Nǐ hǎo", translation="Hello")
    assert s.hanzi == "你好"
    assert s.pinyin == "Nǐ hǎo"
    assert s.translation == "Hello"
    assert s.is_valid is True
    assert s.key_word is None
    assert s.audio_filename is None


def test_example_sentence_all_fields():
    s = ExampleSentence(hanzi="你好", pinyin="Nǐ hǎo", translation="Hello", is_valid=False, key_word="你", audio_filename="abc.mp3")
    assert s.is_valid is False
    assert s.key_word == "你"
    assert s.audio_filename == "abc.mp3"


def test_example_sentence_repr(sample_sentence):
    r = repr(sample_sentence)
    assert "ExampleSentence" in r
    assert "我 爱 你" in r


def test_grammar_point_defaults():
    gp = GrammarPoint(name="Test", level="A1", url_slug="test", full_url="https://example.com/test")
    assert gp.sentences == []
    assert gp.name == "Test"


def test_grammar_point_with_sentences(sample_grammar_point):
    assert len(sample_grammar_point.sentences) == 2
    assert sample_grammar_point.full_url == "https://resources.allsetlearning.com/chinese/grammar/ASGP0KFF"


def test_grammar_point_repr(sample_grammar_point):
    r = repr(sample_grammar_point)
    assert "GrammarPoint" in r
    assert "ASGP0KFF" in r


def test_grammar_level_defaults():
    gl = GrammarLevel(level="A1")
    assert gl.grammar_points == []


def test_grammar_level_with_points(sample_level):
    assert len(sample_level.grammar_points) == 1
    assert sample_level.level == "A1"


def test_grammar_level_repr(sample_level):
    r = repr(sample_level)
    assert "GrammarLevel" in r
    assert "A1" in r


def test_example_sentence_fields_are_mutable():
    s = ExampleSentence(hanzi="你好", pinyin="Nǐ hǎo", translation="Hello")
    assert hasattr(s, "hanzi")

    s.key_word = "你"
    assert s.key_word == "你"


def test_empty_sentences_list(sample_grammar_point):
    gp = sample_grammar_point
    assert isinstance(gp.sentences, list)
    for s in gp.sentences:
        assert isinstance(s, ExampleSentence)
