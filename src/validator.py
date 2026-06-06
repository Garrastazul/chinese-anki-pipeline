from __future__ import annotations

import json
import logging
import subprocess
import time

import requests

from src.config import get
from src.models import ExampleSentence, GrammarLevel, GrammarPoint
from src.scraper import load_level_data, save_level_data
from src.utils import get_data_processed_dir

logger = logging.getLogger(__name__)

OLLAMA_API = get("ollama.host", "http://localhost:11434")


def ensure_ollama_running() -> None:
    subprocess.run(
        ["wsl", "bash", "-c", "ollama serve > /dev/null 2>&1 &"],
        capture_output=True,
    )
    time.sleep(3)
    try:
        resp = requests.get(f"{OLLAMA_API}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(
            "Ollama is not running or not accessible at "
            f"{OLLAMA_API}/api/tags"
        ) from e


def ensure_model(model_name: str | None = None) -> None:
    if model_name is None:
        model_name = get("ollama.model", "qwen2.5:7b")
    subprocess.run(["wsl", "ollama", "pull", model_name], check=True)


def validate_sentence(
    sentence: ExampleSentence, grammar_point_name: str
) -> dict:
    prompt = (
        "Eres un profesor de chino mandarín. Valida la siguiente oración:\n"
        "\n"
        f"Punto gramatical: {grammar_point_name}  "
        f"Hanzi: {sentence.hanzi}  "
        f"Pinyin: {sentence.pinyin}  "
        f"Traducción: {sentence.translation}\n"
        "\n"
        "Responde en el siguiente formato JSON estricto sin markdown:\n"
        '{ "is_valid": true/false, "hanzi_errors": "", '
        '"pinyin_errors": "", "translation_errors": "", '
        '"key_word": "la palabra clave (en hanzi) que ejemplifica este punto gramatical", '
        '"notes": "" }\n'
        "\n"
        'key_word debe ser la palabra específica (ej: "和", "了", "的") '
        "que ilustra el punto gramatical. Si no puedes identificar una, pon \"\"."
    )

    model = get("ollama.model", "qwen2.5:7b")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    for attempt in range(2):
        try:
            resp = requests.post(
                f"{OLLAMA_API}/api/generate", json=payload, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            response_text = (data.get("response") or "").strip()

            if response_text.startswith("```"):
                lines = response_text.splitlines()
                if len(lines) >= 3:
                    response_text = "\n".join(lines[1:-1]).strip()

            parsed = json.loads(response_text)
            return parsed
        except (json.JSONDecodeError, KeyError, requests.RequestException) as e:
            if attempt == 1:
                logger.warning(
                    "Failed to parse Ollama response after 2 attempts: %s", e
                )
                return {
                    "is_valid": True,
                    "hanzi_errors": "",
                    "pinyin_errors": "",
                    "translation_errors": "",
                    "key_word": "",
                    "notes": f"Validation error: {e}",
                }


def validate_grammar_point(gp: GrammarPoint) -> GrammarPoint:
    for sentence in gp.sentences:
        result = validate_sentence(sentence, gp.name)
        sentence.is_valid = result.get("is_valid", True)
        sentence.key_word = result.get("key_word") or None
        time.sleep(0.5)
    return gp


def validate_level(level: GrammarLevel) -> GrammarLevel:
    for gp in level.grammar_points:
        validate_grammar_point(gp)
    return level


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Ensuring Ollama is running...")
    ensure_ollama_running()

    model = get("ollama.model", "qwen2.5:7b")
    logger.info("Ensuring model %s is available...", model)
    ensure_model(model)

    logger.info("Loading A1 data...")
    level = load_level_data("A1")

    logger.info("Validating grammar points...")
    level = validate_level(level)

    total = sum(len(gp.sentences) for gp in level.grammar_points)
    valid = sum(
        1 for gp in level.grammar_points for s in gp.sentences if s.is_valid
    )
    invalid = total - valid
    with_keyword = sum(
        1 for gp in level.grammar_points for s in gp.sentences if s.key_word
    )

    logger.info("Saving validated data...")
    save_level_data(level)

    print(
        f"Validation complete: {valid} valid, {invalid} invalid, "
        f"{with_keyword} with key_word (out of {total} total sentences)"
    )


if __name__ == "__main__":
    main()
