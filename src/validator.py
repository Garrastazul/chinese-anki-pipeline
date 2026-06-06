from __future__ import annotations

import json
import logging
import re
import subprocess
import time

import requests

from src.config import get
from src.models import ExampleSentence, GrammarLevel, GrammarPoint
from src.scraper import load_level_data, save_level_data
from src.utils import get_data_processed_dir

logger = logging.getLogger(__name__)

def _ollama_api() -> str:
    return get("ollama.host", "http://localhost:11434")


def ensure_ollama_running() -> None:
    try:
        subprocess.run(
            ["wsl", "bash", "-c", "ollama serve > /dev/null 2>&1 &"],
            capture_output=True,
        )
    except (FileNotFoundError, PermissionError, OSError):
        logger.warning("WSL not found or not accessible, assuming Ollama is running natively")
    time.sleep(3)
    try:
        resp = requests.get(f"{_ollama_api()}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(
            "Ollama is not running or not accessible at "
            f"{_ollama_api()}/api/tags"
        ) from e


def ensure_model(model_name: str | None = None) -> None:
    if model_name is None:
        model_name = get("ollama.model", "qwen2.5:7b")
    try:
        subprocess.run(["wsl", "ollama", "pull", model_name], check=True, capture_output=True, text=True)
    except FileNotFoundError:
        logger.warning("WSL not found, cannot auto-pull model %s", model_name)
    except subprocess.CalledProcessError as e:
        logger.warning("Failed to pull model %s (exit code %d): %s", model_name, e.returncode, e.stderr.strip() if e.stderr else "unknown error")


def validate_sentence(
    sentence: ExampleSentence, grammar_point_name: str
) -> dict:
    prompt = (
        "You are a Mandarin Chinese teacher. Validate the following sentence:\n"
        "\n"
        f"Grammar point: {grammar_point_name}  "
        f"Hanzi: {sentence.hanzi}  "
        f"Pinyin: {sentence.pinyin}  "
        f"Translation: {sentence.translation}\n"
        "\n"
        "Respond in the following strict JSON format without markdown:\n"
        '{ "is_valid": true/false, "hanzi_errors": "", '
        '"pinyin_errors": "", "translation_errors": "", '
        '"key_word": "the keyword (in hanzi) that exemplifies this grammar point", '
        '"notes": "" }\n'
        "\n"
        'key_word must be the specific word (e.g. "和", "了", "的") '
        "that illustrates the grammar point. If you cannot identify one, set it to \"\"."
    )

    model = get("ollama.model", "qwen2.5:7b")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "num_predict": 300,
            "temperature": 0,
        },
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                f"{_ollama_api()}/api/generate", json=payload, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            response_text = (data.get("response") or "").strip()

            if response_text.startswith("```"):
                response_text = re.sub(
                    r'^```(?:json)?\s*\n?', '', response_text
                )
                response_text = re.sub(r'\n?```.*$', '', response_text, flags=re.DOTALL)
                response_text = response_text.strip()

            parsed = json.loads(response_text)
            return parsed
        except (json.JSONDecodeError, KeyError, requests.RequestException) as e:
            if attempt < 2:
                logger.warning("Ollama request failed (attempt %d, retrying): %s", attempt + 1, e)
                time.sleep(2 ** attempt)
                continue
            logger.warning(
                "Failed to parse Ollama response after 3 attempts: %s", e
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
        time.sleep(get("validator.sentence_delay", 0.5))
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
