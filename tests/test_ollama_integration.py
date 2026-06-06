import pytest
import requests
from src.models import ExampleSentence
from src.validator import validate_sentence
from src.config import get


def ollama_available() -> bool:
    api = get("ollama.host", "http://localhost:11434")
    try:
        r = requests.get(f"{api}/api/tags", timeout=3)
        return r.ok
    except requests.RequestException:
        return False


@pytest.mark.skipif(not ollama_available(), reason="Ollama is not running")
class TestIntegrationWithOllama:
    """Pruebas REALES contra Ollama. Requiere modelo descargado y Ollama corriendo."""

    def test_correct_translation_passes(self):
        """Una traducción correcta debería pasar la validación"""
        s = ExampleSentence("我 爱 你。", "Wǒ ài nǐ.", "I love you.")
        result = validate_sentence(s, "Basic sentence order")
        assert result["is_valid"] is True
        assert result["translation_errors"] == ""

    def test_incorrect_translation_fails(self):
        """Una traducción con significado opuesto debería fallar"""
        s = ExampleSentence("我 爱 你。", "Wǒ ài nǐ.", "I hate you.")
        result = validate_sentence(s, "Basic sentence order")
        assert result["is_valid"] is False
        assert result["translation_errors"] != ""

    def test_keyword_detection(self):
        """Ollama identifica la palabra clave del punto gramatical"""
        s = ExampleSentence(
            "他 和 我 都 去。", "Tā hé wǒ dōu qù.",
            "He and I are both going."
        )
        result = validate_sentence(s, "Expressing 'and' with 'he'")
        assert result["key_word"] == "和"

    def test_negation_detected(self):
        """Omisión de negación debería detectarse"""
        s = ExampleSentence("我 不 去。", "Wǒ bù qù.", "I am going.")
        result = validate_sentence(s, "Negation with bu")
        assert result["is_valid"] is False
        assert result["translation_errors"]

    def test_empty_translation_detected(self):
        """Traducción vacía debería marcarse como inválida"""
        s = ExampleSentence("你好", "Nǐ hǎo", "")
        result = validate_sentence(s, "Greetings")
        assert result["is_valid"] is False

    def test_wrong_tone_detected(self):
        """Tono incorrecto en pinyin debería detectarse"""
        s = ExampleSentence("妈妈", "Mā má", "Mom")
        result = validate_sentence(s, "Family members")
        assert result["is_valid"] is False or result["pinyin_errors"]

    def test_all_correct_pinyins_pass(self):
        """Todas las oraciones con pinyin correcto pasan"""
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
        """Múltiples traducciones incorrectas: todas deberían fallar"""
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
