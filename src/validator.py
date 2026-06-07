from __future__ import annotations

import json
import logging
import re
import time

import requests

from src.config import get
from src.models import ExampleSentence, GrammarLevel, GrammarPoint
from src.scraper import load_level_data, save_level_data
from src.utils import get_data_processed_dir

logger = logging.getLogger(__name__)

_GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


def _groq_headers() -> dict[str, str]:
    api_key = get("groq.api_key")
    if not api_key:
        raise RuntimeError(
            "Groq API key not configured. "
            "Set groq.api_key in config.local.json"
        )
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def validate_sentence(
    sentence: ExampleSentence, grammar_point_name: str
) -> dict:
    prompt = (
        "Validate sentence for '%s':\n"
        "Hanzi: %s\nPinyin: %s\nEN: %s\n\n"
        "Return JSON:\n"
        '- "is_valid": false if hanzi wrong/missing, pinyin mismatch, or translation empty/wrong\n'
        '- "hanzi_errors", "pinyin_errors", "translation_errors": "" or description\n'
        '- "key_word": keyword in hanzi (e.g. "了") or ""\n'
        '- "notes": "" or brief explanation\n\n'
        "Rules: pinyin must match hanzi exactly. Empty translation = error."
    ) % (grammar_point_name, sentence.hanzi, sentence.pinyin, sentence.translation)

    model = get("groq.model", "llama-3.3-70b-versatile")
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
            resp = requests.post(
                _GROQ_ENDPOINT,
                headers=_groq_headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            try:
                data = resp.json()
            except json.JSONDecodeError:
                logger.warning("Groq returned non-JSON response: %.200s", resp.text)
                time.sleep(2 ** attempt)
                continue
            try:
                response_text = data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError):
                logger.warning("Unexpected Groq response structure: %.200s", resp.text)
                time.sleep(2 ** attempt)
                continue
            try:
                parsed = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(
                    "Groq returned invalid JSON in content (attempt %d): %.200s",
                    attempt + 1, response_text,
                )
                time.sleep(2 ** attempt)
                continue
            return parsed
        except requests.HTTPError as e:
            status = e.response.status_code
            try:
                body_preview = e.response.text[:500]
            except Exception:
                body_preview = "<unreadable>"
            logger.warning(
                "Groq request failed (attempt %d): status=%d, body=%.200s",
                attempt + 1, status, body_preview,
            )
            if status == 429:
                retry_after = int(e.response.headers.get("retry-after", 4))
                logger.warning(
                    "Rate limited, waiting %ds...", retry_after,
                )
                time.sleep(retry_after)
                continue
            if attempt < 2:
                logger.warning(
                    "Retrying after %ds...", 2 ** attempt,
                )
                time.sleep(2 ** attempt)
                continue
            logger.warning(
                "Failed after 3 attempts (status %d): %s", status, body_preview,
            )
            return {
                "is_valid": False,
                "hanzi_errors": "",
                "pinyin_errors": "",
                "translation_errors": "",
                "key_word": "",
                "notes": f"Validation error (HTTP {status}): {body_preview[:200]}",
            }


def validate_grammar_point(gp: GrammarPoint, counter: list[int] | None = None, total: int = 0) -> GrammarPoint:
    for sentence in gp.sentences:
        result = validate_sentence(sentence, gp.name)
        sentence.is_valid = result.get("is_valid", True)
        sentence.key_word = result.get("key_word") or None
        sentence.hanzi_errors = result.get("hanzi_errors", "")
        sentence.pinyin_errors = result.get("pinyin_errors", "")
        sentence.translation_errors = result.get("translation_errors", "")
        sentence.notes = result.get("notes", "")
        if counter is not None:
            counter[0] += 1
            logger.info("Progress: %d/%d sentences validated", counter[0], total)
        if not sentence.notes.startswith("Validation error"):
            time.sleep(get("validator.sentence_delay", 0.5))
    return gp


def validate_level(level: GrammarLevel) -> GrammarLevel:
    total = sum(len(gp.sentences) for gp in level.grammar_points)
    counter = [0]
    for gp in level.grammar_points:
        validate_grammar_point(gp, counter, total)
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
