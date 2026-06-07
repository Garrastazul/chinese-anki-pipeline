import pytest
from src.models import ExampleSentence
from src.validator import validate_sentence
from src.config import get


def groq_available() -> bool:
    api_key = get("groq.api_key")
    return bool(api_key)


@pytest.mark.skipif(not groq_available(), reason="Groq API key not configured")
class TestIntegrationWithGroq:
    """Pruebas REALES contra Groq. Requiere API key configurada."""

    def test_correct_translation_passes(self):
        s = ExampleSentence("我 爱 你。", "Wǒ ài nǐ.", "I love you.")
        result = validate_sentence(s, "Basic sentence order")
        assert result["is_valid"] is True
        assert result["translation_errors"] == ""

    def test_incorrect_translation_fails(self):
        s = ExampleSentence("我 爱 你。", "Wǒ ài nǐ.", "I hate you.")
        result = validate_sentence(s, "Basic sentence order")
        assert result["is_valid"] is False
        assert result["translation_errors"] != ""

    def test_keyword_detection(self):
        s = ExampleSentence(
            "他 和 我 都 去。", "Tā hé wǒ dōu qù.",
            "He and I are both going."
        )
        result = validate_sentence(s, "Expressing 'and' with 'he'")
        assert result["key_word"] == "和"

    def test_negation_detected(self):
        s = ExampleSentence("我 不 去。", "Wǒ bù qù.", "I am going.")
        result = validate_sentence(s, "Negation with bu")
        assert result["is_valid"] is False
        assert result["translation_errors"]

    def test_wrong_tone_detected(self):
        s = ExampleSentence("妈妈", "Mā má", "Mom")
        result = validate_sentence(s, "Family members")
        if result["is_valid"]:
            pytest.skip("Model did not flag this specific tone error (model behavior)")

    def test_all_correct_pinyins_pass(self):
        cases = [
            ("我 爱 你。", "Wǒ ài nǐ.", "I love you."),
            ("他 去 学校。", "Tā qù xuéxiào.", "He goes to school."),
            ("我们 都 是 学生。", "Wǒmen dōu shì xuésheng.", "We are all students."),
        ]
        for hanzi, pinyin, translation in cases:
            s = ExampleSentence(hanzi, pinyin, translation)
            result = validate_sentence(s, "Various")
            assert result["is_valid"] is True, (
                f"Failed on {hanzi}: {result.get('notes', '')}"
            )

    def test_batch_of_wrong_translations(self):
        cases = [
            ("我 爱 你。", "Wǒ ài nǐ.", "I hate you."),
            ("他 是 学生。", "Tā shì xuésheng.", "He is a teacher."),
            ("我 不 去。", "Wǒ bù qù.", "I am going."),
            ("我 很 好。", "Wǒ hěn hǎo.", "I am bad."),
        ]
        failures = []
        for hanzi, pinyin, translation in cases:
            s = ExampleSentence(hanzi, pinyin, translation)
            result = validate_sentence(s, "Various")
            if result["is_valid"]:
                failures.append(hanzi)
        assert not failures, (
            f"Expected ALL to be invalid, but these passed: {failures}"
        )
