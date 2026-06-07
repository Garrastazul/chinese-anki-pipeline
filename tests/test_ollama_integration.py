import os
import pytest
import requests
from src.models import ExampleSentence
from src.validator import validate_sentence


def ollama_available() -> bool:
    if not os.environ.get("OLLAMA_INTEGRATION"):
        return False
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code != 200:
            return False
        from src.config import get
        expected = get("ollama.model", "qwen2.5:7b")
        models = resp.json().get("models", [])
        model_names = [m.get("name", "") for m in models]
        return any(expected in name for name in model_names)
    except Exception:
        return False


@pytest.mark.skipif(not ollama_available(), reason="Set OLLAMA_INTEGRATION=1 and ensure Ollama is running")
class TestIntegrationWithOllama:
    """Real integration tests against local Ollama. Requires Ollama running."""

    def test_correct_sentences_pass(self):
        cases = [
            ("我 爱 你。", "Wǒ ài nǐ.", "I love you."),
            ("他 去 学校。", "Tā qù xuéxiào.", "He goes to school."),
            ("我们 都 是 学生。", "Wǒmen dōu shì xuésheng.", "We are all students."),
            ("他 和 我 都 去。", "Tā hé wǒ dōu qù.", "He and I are both going."),
            ("我 很 好。", "Wǒ hěn hǎo.", "I am fine."),
        ]
        failures = []
        for hanzi, pinyin, translation in cases:
            s = ExampleSentence(hanzi, pinyin, translation)
            result = validate_sentence(s, "Various")
            if not result["is_valid"]:
                failures.append(f"{hanzi}: {result.get('notes', '')}")
        assert not failures, (
            f"False negatives on correct sentences:\n" + "\n".join(failures)
        )

    def test_wrong_word_in_pinyin_fails(self):
        cases = [
            ("我 吃 苹果。", "Wǒ hē píngguǒ.", "I eat apples."),
            ("我 喝 水。", "Wǒ chī shuǐ.", "I drink water."),
        ]
        for hanzi, pinyin, translation in cases:
            s = ExampleSentence(hanzi, pinyin, translation)
            result = validate_sentence(s, "Vocabulary test")
            assert result["is_valid"] is False, (
                f"Failed to catch wrong pinyin word: {hanzi} / {pinyin}"
            )
            has_description = (
                result.get("pinyin_errors")
                or result.get("hanzi_errors")
                or result.get("notes")
            )
            assert has_description, (
                f"No error description for: {hanzi} / {pinyin}"
            )

    def test_wrong_tone_changes_meaning_fails(self):
        cases = [
            ("我 是 学生。", "Wǒ shī xuésheng.", "I am a student.",
             "是=shì, not shī"),
            ("我 要 去。", "Wǒ yāo qù.", "I want to go.",
             "要=yào, not yāo"),
            ("他 说 话。", "Tā shuì huà.", "He speaks.",
             "说=shuō, not shuì"),
        ]
        for hanzi, pinyin, translation, desc in cases:
            s = ExampleSentence(hanzi, pinyin, translation)
            result = validate_sentence(s, "Tone test")
            assert result["is_valid"] is False, (
                f"Failed to catch wrong tone: {desc}"
            )
            has_description = (
                result.get("pinyin_errors")
                or result.get("hanzi_errors")
                or result.get("notes")
            )
            assert has_description, (
                f"No error description for tone error: {desc}"
            )

    def test_missing_negation_fails(self):
        cases = [
            ("我 不 去。", "Wǒ bù qù.", "I am going."),
            ("他 不 是 老师。", "Tā bù shì lǎoshī.", "He is a teacher."),
            ("我 不 吃 肉。", "Wǒ bù chī ròu.", "I eat meat."),
        ]
        for hanzi, pinyin, translation in cases:
            s = ExampleSentence(hanzi, pinyin, translation)
            result = validate_sentence(s, "Negation with bu")
            assert result["is_valid"] is False, (
                f"Failed to catch missing negation: {hanzi} → {translation}"
            )
            assert result["translation_errors"], (
                f"translation_errors empty for: {hanzi} → {translation}"
            )

    def test_reversed_meaning_fails(self):
        cases = [
            ("我 爱 你。", "Wǒ ài nǐ.", "I hate you."),
            ("我 很 好。", "Wǒ hěn hǎo.", "I am bad."),
            ("他 是 学生。", "Tā shì xuésheng.", "He is a teacher."),
            ("我 不 高。", "Wǒ bù gāo.", "I am tall."),
        ]
        for hanzi, pinyin, translation in cases:
            s = ExampleSentence(hanzi, pinyin, translation)
            result = validate_sentence(s, "Meaning test")
            assert result["is_valid"] is False, (
                f"Failed to catch wrong meaning: {hanzi} → {translation}"
            )
            assert result["translation_errors"], (
                f"translation_errors empty for: {hanzi} → {translation}"
            )

    def test_wrong_subject_object_fails(self):
        cases = [
            ("他 爱 我。", "Tā ài wǒ.", "I love him.",
             "Subject 他 and object 我 reversed"),
            ("我 打 他。", "Wǒ dǎ tā.", "He hits me.",
             "Subject 我 and object 他 reversed"),
        ]
        for hanzi, pinyin, translation, desc in cases:
            s = ExampleSentence(hanzi, pinyin, translation)
            result = validate_sentence(s, "Subject-object test")
            assert result["is_valid"] is False, (
                f"Failed to catch swapped subject/object: {desc}"
            )
            assert result["translation_errors"], (
                f"translation_errors empty for: {desc}"
            )

    def test_keyword_detection(self):
        cases = [
            ("他 和 我 都 去。", "Tā hé wǒ dōu qù.",
             "He and I are both going.", "和"),
            ("我 的 书。", "Wǒ de shū.", "My book.", "的"),
            ("我 吃 了。", "Wǒ chī le.", "I ate.", "了"),
        ]
        for hanzi, pinyin, translation, expected_keyword in cases:
            s = ExampleSentence(hanzi, pinyin, translation)
            result = validate_sentence(s, f"Keyword test: {expected_keyword}")
            assert result["key_word"] == expected_keyword, (
                f"Expected keyword '{expected_keyword}' but got '{result['key_word']}' "
                f"for {hanzi}"
            )

    def test_empty_translation_fails(self):
        s = ExampleSentence("我 是 学生。", "Wǒ shì xuésheng.", "")
        result = validate_sentence(s, "Empty translation test")
        assert result["is_valid"] is False
        assert result["translation_errors"]
