from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

from src.config import get
from src.models import ExampleSentence, GrammarLevel, GrammarPoint
from src.utils import get_data_processed_dir

logger = logging.getLogger(__name__)

BASE_URL = get("scraper.base_url", "https://resources.allsetlearning.com/chinese/grammar")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_grammar_point_links(html: str, level: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    result: list[dict] = []
    for table in soup.select("table.wikitable"):
        rows = table.select("tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue
            anchor = cells[0].find("a")
            if not anchor:
                continue
            name = anchor.get_text(strip=True)
            if not name:
                continue
            href = anchor.get("href", "")
            url_slug = href.rstrip("/").split("/")[-1]
            pattern = cells[1].get_text(strip=True)
            liju_span = cells[2].select_one("span.liju")
            examples_raw = liju_span.get_text(strip=True) if liju_span else cells[2].get_text(strip=True)
            result.append({
                "name": name,
                "url_slug": url_slug,
                "pattern": pattern,
                "examples_raw": examples_raw,
            })
    return result


def fetch_grammar_point_page(url_slug: str) -> str:
    url = f"{BASE_URL}/{url_slug}"
    resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _extract_hanzi(cell: Tag) -> str:
    texts: list[str] = []
    for t in cell.find_all(string=True, recursive=True):
        parent = t.parent
        if isinstance(parent, Tag) and parent.get("class") and "pinyin" in parent.get("class", []):
            continue
        stripped = t.strip()
        if stripped:
            texts.append(stripped)
    return "".join(texts)


def _extract_pinyin(cell: Tag) -> str:
    spans = cell.select("span.pinyin")
    return " ".join(s.get_text(strip=True) for s in spans)


def parse_example_sentences(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.select("table.table-bordered, table.big-text")
    sentences: list[dict] = []
    for table in tables:
        rows = table.select("tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 2:
                continue
            hanzi = _extract_hanzi(cells[0])
            if not hanzi:
                continue
            pinyin = _extract_pinyin(cells[0])
            translation = cells[-1].get_text(strip=True)
            sentences.append({
                "hanzi": hanzi,
                "pinyin": pinyin,
                "translation": translation,
            })
    return sentences


def scrape_level(level: str) -> GrammarLevel:
    url = f"{BASE_URL}/{level}_grammar_points"
    logger.info("Fetching %s grammar points index from %s", level, url)
    html = fetch_page(url)
    links = parse_grammar_point_links(html, level)
    logger.info("Found %d grammar point links for %s", len(links), level)

    grammar_points: list[GrammarPoint] = []
    for link in links:
        url_slug = link["url_slug"]
        full_url = f"{BASE_URL}/{url_slug}"
        try:
            point_html = fetch_grammar_point_page(url_slug)
            raw_sentences = parse_example_sentences(point_html)
            sentences = [
                ExampleSentence(
                    hanzi=s["hanzi"],
                    pinyin=s["pinyin"],
                    translation=s["translation"],
                )
                for s in raw_sentences
            ]
            gp = GrammarPoint(
                name=link["name"],
                level=level,
                url_slug=url_slug,
                full_url=full_url,
                sentences=sentences,
            )
            grammar_points.append(gp)
            logger.info("  %s: %d sentences", link["name"], len(sentences))
        except Exception:
            logger.warning("Failed to fetch %s (%s), skipping", link["name"], full_url, exc_info=True)
        time.sleep(get("scraper.request_delay", 1.0))

    return GrammarLevel(level=level, grammar_points=grammar_points)


def save_level_data(level: GrammarLevel) -> None:
    path: Path = get_data_processed_dir() / f"{level.level}.json"

    def _to_dict(gp: GrammarPoint) -> dict:
        return {
            "name": gp.name,
            "level": gp.level,
            "url_slug": gp.url_slug,
            "full_url": gp.full_url,
            "sentences": [
                {
                    "hanzi": s.hanzi,
                    "pinyin": s.pinyin,
                    "translation": s.translation,
                    "is_valid": s.is_valid,
                    "key_word": s.key_word,
                    "audio_filename": s.audio_filename,
                }
                for s in gp.sentences
            ],
        }

    data = {
        "level": level.level,
        "grammar_points": [_to_dict(gp) for gp in level.grammar_points],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %s data to %s", level.level, path)


def load_level_data(level_name: str) -> GrammarLevel:
    path: Path = get_data_processed_dir() / f"{level_name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    grammar_points = [
        GrammarPoint(
            name=gp["name"],
            level=gp["level"],
            url_slug=gp["url_slug"],
            full_url=gp["full_url"],
            sentences=[
                ExampleSentence(
                    hanzi=s["hanzi"],
                    pinyin=s["pinyin"],
                    translation=s["translation"],
                    is_valid=s.get("is_valid", True),
                    key_word=s.get("key_word"),
                    audio_filename=s.get("audio_filename"),
                )
                for s in gp["sentences"]
            ],
        )
        for gp in data["grammar_points"]
    ]
    return GrammarLevel(level=data["level"], grammar_points=grammar_points)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    level = scrape_level("A1")
    save_level_data(level)

    total_sentences = sum(len(gp.sentences) for gp in level.grammar_points)
    print(f"Level {level.level}: {len(level.grammar_points)} grammar points, {total_sentences} sentences")


if __name__ == "__main__":
    main()
