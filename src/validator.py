from __future__ import annotations

import json
import logging
import re
import time

import requests
from tqdm import tqdm

from src.config import get
from src.models import ExampleSentence, GrammarLevel, GrammarPoint
from src.scraper import load_level_data, save_level_data
from src.utils import get_data_processed_dir

logger = logging.getLogger(__name__)


def validate_sentence(
    sentence: ExampleSentence, grammar_point_name: str
) -> dict:
    prompt = (
        "Validate sentence for '%s':\n"
        "Hanzi: %s\nPinyin: %s\nEN: %s\n\n"
        "Return JSON:\n"
        '- "is_valid": false if hanzi wrong/missing, pinyin mismatch, or translation empty/wrong\n'
        '- "hanzi_errors", "pinyin_errors", "translation_errors": "" or description\n'
        '- "key_word": keyword in hanzi (e.g. "\u4e86") or ""\n'
        '- "notes": "" or brief explanation\n\n'
        "Rules: pinyin must match hanzi exactly. Empty translation = error."
    ) % (grammar_point_name, sentence.hanzi, sentence.pinyin, sentence.translation)

    model = get("ollama.model", "qwen2.5:7b")
    endpoint = get("ollama.endpoint", "http://localhost:11434/v1/chat/completions")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You validate Chinese sentences. Respond in JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }

    for attempt in range(3):
        try:
            resp = requests.post(endpoint, json=payload, timeout=120)
            resp.raise_for_status()
            try:
                data = resp.json()
            except json.JSONDecodeError:
                logger.warning(
                    "Ollama returned non-JSON response (attempt %d): %.200s",
                    attempt + 1, resp.text,
                )
                time.sleep(2 ** attempt)
                continue
            try:
                response_text = data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError):
                logger.warning(
                    "Unexpected Ollama response structure (attempt %d): %.200s",
                    attempt + 1, resp.text,
                )
                time.sleep(2 ** attempt)
                continue
            try:
                parsed = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(
                    "Ollama returned invalid JSON in content (attempt %d): %.200s",
                    attempt + 1, response_text,
                )
                time.sleep(2 ** attempt)
                continue
            return parsed
        except requests.ConnectionError:
            logger.error(
                "Ollama not reachable at %s. Is it running? "
                "Start with: wsl -d Ubuntu -u root -- ollama serve",
                endpoint,
            )
            return {
                "is_valid": False,
                "hanzi_errors": "",
                "pinyin_errors": "",
                "translation_errors": "",
                "key_word": "",
                "notes": f"Ollama connection error (attempt {attempt + 1})",
            }
        except requests.Timeout:
            logger.warning(
                "Ollama request timed out (attempt %d), retrying...", attempt + 1,
            )
            time.sleep(2 ** attempt)
            continue
        except requests.HTTPError as e:
            status = e.response.status_code
            try:
                body_preview = e.response.text[:500]
            except Exception:
                body_preview = "<unreadable>"
            logger.warning(
                "Ollama request failed (attempt %d): status=%d, body=%.200s",
                attempt + 1, status, body_preview,
            )
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return {
                "is_valid": False,
                "hanzi_errors": "",
                "pinyin_errors": "",
                "translation_errors": "",
                "key_word": "",
                "notes": f"Ollama error (HTTP {status}): {body_preview[:200]}",
            }

    return {
        "is_valid": False,
        "hanzi_errors": "",
        "pinyin_errors": "",
        "translation_errors": "",
        "key_word": "",
        "notes": "Validation error: all attempts failed",
    }


def validate_grammar_point(gp: GrammarPoint, pbar: tqdm | None = None) -> GrammarPoint:
    for sentence in gp.sentences:
        result = validate_sentence(sentence, gp.name)
        sentence.is_valid = result.get("is_valid", True)
        sentence.key_word = result.get("key_word") or None
        sentence.hanzi_errors = result.get("hanzi_errors", "")
        sentence.pinyin_errors = result.get("pinyin_errors", "")
        sentence.translation_errors = result.get("translation_errors", "")
        sentence.notes = result.get("notes", "")
        if pbar is not None:
            pbar.update(1)
            pbar.set_postfix_str(gp.name[:40], refresh=False)
        if not sentence.notes.startswith("Validation error"):
            time.sleep(get("validator.sentence_delay", 0.5))
    return gp


def validate_level(level: GrammarLevel) -> GrammarLevel:
    total = sum(len(gp.sentences) for gp in level.grammar_points)
    with tqdm(total=total, desc="Validating", unit="sent", ncols=100) as pbar:
        for gp in level.grammar_points:
            validate_grammar_point(gp, pbar)
    return level


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

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
