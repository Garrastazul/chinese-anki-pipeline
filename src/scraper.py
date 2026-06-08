from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

from src.config import get
from src.models import ExampleSentence, GrammarLevel, GrammarPoint
from src.utils import get_data_processed_dir

logger = logging.getLogger(__name__)

PINYIN_CLASS_PATTERNS = ["pinyin", "py", "romanization"]

_DEFAULT_SELECTORS: dict[str, list[str]] = {
    "index_table": ["table.wikitable", "table.sortable", "table"],
    "liju_block": ["div.liju", "[class*=liju]"],
    "pinyin_span": ["span.pinyin", "span.py", "span.romanization", "[class*=pinyin]"],
    "translation_span": ["span.trans", "span.translation", "span.english", "[class*=trans]"],
    "example_table": ["table.table-bordered", "table.big-text", "table.wikitable", "table"],
}


def _get_base_url() -> str:
    return get("scraper.base_url", "https://resources.allsetlearning.com/chinese/grammar")


def _get_selectors(key: str) -> list[str]:
    return get(f"scraper.selectors.{key}", _DEFAULT_SELECTORS.get(key, []))


def _select_first(soup: BeautifulSoup | Tag, selectors: list[str], label: str) -> list[Tag]:
    for i, sel in enumerate(selectors):
        found = soup.select(sel)
        if found:
            if i > 0:
                logger.warning("Wiki structure may have changed: using fallback selector '%s' for %s (preferred: '%s')", sel, label, selectors[0])
            return found
    return []


def _is_pinyin_tag(tag: Tag | None) -> bool:
    if tag is None:
        return False
    classes = tag.get("class", [])
    return any(cls in PINYIN_CLASS_PATTERNS for cls in classes)


def _has_pinyin_ancestor(text_node: str, parent: Tag | None) -> bool:
    if parent is None:
        return False
    return any(_is_pinyin_tag(a) for a in [parent] + list(parent.parents) if isinstance(a, Tag))


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}

_PATTERN_KEYWORDS = ["Subj", "Verb", "Obj", "Adj", "N", "NP", "VP", "Prep", "Num", "M", "Cl", "S", "O", "+", "。", "？"]

_CHINESE_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def _is_pattern_cell(text: str) -> bool:
    if len(text) < 2:
        return False
    has_chinese = bool(_CHINESE_RE.search(text))
    has_keyword = any(kw in text for kw in _PATTERN_KEYWORDS)
    return has_chinese or has_keyword


def _is_translation_cell(cell: Tag) -> bool:
    text = cell.get_text(strip=True)
    if not text:
        return False
    if _CHINESE_RE.search(text):
        return False
    if cell.select_one("span.pinyin, span.py, span.romanization"):
        return False
    non_ascii = sum(1 for c in text if ord(c) > 127)
    return non_ascii / max(len(text), 1) < 0.1


def validate_page_structure(html: str, page_type: str = "index") -> None:
    soup = BeautifulSoup(html, "lxml")
    if page_type == "index":
        tables = _select_first(soup, _get_selectors("index_table"), "index table")
        if not tables:
            logger.warning("No tables found in grammar index page – wiki layout may have changed")
        else:
            rows = tables[0].select("tr")
            data_rows = [r for r in rows if r.find_all("td")]
            if len(data_rows) == 0:
                logger.warning("Index table has no data rows – wiki structure may have changed")
    elif page_type == "grammar":
        liju_blocks = _select_first(soup, _get_selectors("liju_block"), "liju block")
        tables = _select_first(soup, _get_selectors("example_table"), "example table")
        if not liju_blocks and not tables:
            logger.warning("No liju blocks or example tables found in grammar page – wiki layout may have changed")


def _try_extract_gp_standard(cells: list[Tag]) -> dict | None:
    if len(cells) < 3:
        return None
    anchor = cells[0].find("a")
    if not anchor:
        return None
    name = anchor.get_text(strip=True)
    if not name:
        return None
    href = anchor.get("href", "")
    if not href:
        return None
    url_slug = href.rstrip("/").split("/")[-1]
    pattern = cells[1].get_text(strip=True)
    liju_span = cells[2].select_one("span.liju")
    examples_raw = liju_span.get_text(strip=True) if liju_span else cells[2].get_text(strip=True)
    return {
        "name": name,
        "url_slug": url_slug,
        "pattern": pattern,
        "examples_raw": examples_raw,
    }


def _try_extract_gp_heuristic(cells: list[Tag]) -> dict | None:
    name_cell = None
    pattern_cell = None
    example_cell = None
    for cell in cells:
        anchor = cell.find("a")
        if anchor and anchor.get("href", "").rstrip("/").split("/")[-1]:
            name_cell = cell
            continue
    if name_cell is None:
        return None
    anchor = name_cell.find("a")
    name = anchor.get_text(strip=True) if anchor else ""
    if not name:
        return None
    href = anchor.get("href", "") if anchor else ""
    if not href:
        return None
    url_slug = href.rstrip("/").split("/")[-1]
    remaining = [c for c in cells if c != name_cell]
    for cell in remaining:
        text = cell.get_text(strip=True)
        if _is_pattern_cell(text):
            pattern_cell = cell
            break
    for cell in remaining:
        if cell == pattern_cell:
            continue
        if cell.select_one("span.liju, span.trans, span.pinyin"):
            example_cell = cell
            break
    if example_cell is None:
        for cell in remaining:
            if cell == pattern_cell:
                continue
            text = cell.get_text(strip=True)
            if _CHINESE_RE.search(text):
                example_cell = cell
                break
    pattern = pattern_cell.get_text(strip=True) if pattern_cell else ""
    examples_raw = example_cell.get_text(strip=True) if example_cell else ""
    return {
        "name": name,
        "url_slug": url_slug,
        "pattern": pattern,
        "examples_raw": examples_raw,
    }


def parse_grammar_point_links(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    result: list[dict] = []
    selectors = _get_selectors("index_table")
    tables = _select_first(soup, selectors, "index table")
    for table in tables:
        rows = table.select("tr")
        for row in rows:
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue
            gp = _try_extract_gp_standard(cells)
            if gp is None:
                gp = _try_extract_gp_heuristic(cells)
            if gp is not None:
                result.append(gp)
    if not result:
        logger.warning("No grammar point links extracted – wiki structure may have changed")
    return result


def fetch_grammar_point_page(url_slug: str) -> str:
    url = f"{_get_base_url()}/{url_slug}"
    resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _extract_hanzi(cell: Tag) -> str:
    texts: list[str] = []
    for t in cell.find_all(string=True, recursive=True):
        parent = t.parent
        if isinstance(parent, Tag):
            if any(_is_pinyin_tag(a) for a in [parent] + list(parent.parents) if isinstance(a, Tag)):
                continue
        stripped = t.strip()
        if stripped:
            texts.append(stripped)
    return " ".join(texts)


def _extract_pinyin(cell: Tag) -> str:
    spans = cell.find_all(["span"], class_=lambda c: c and any(cls in c.split() for cls in PINYIN_CLASS_PATTERNS) if c else False)
    if not spans:
        spans = cell.select("[class*=pinyin], [class*=py], [class*=romanization]")
    return " ".join(s.get_text(strip=True) for s in spans if isinstance(s, Tag))


def _parse_liju_examples(soup: BeautifulSoup) -> list[dict] | None:
    liju_selectors = _get_selectors("liju_block")
    liju_divs = _select_first(soup, liju_selectors, "liju block")
    if not liju_divs:
        return None

    pinyin_selectors = _get_selectors("pinyin_span")
    trans_selectors = _get_selectors("translation_span")

    sentences: list[dict] = []
    for div in liju_divs:
        for li in div.select("li"):
            hanzi_parts = []
            for child in li.children:
                if isinstance(child, str):
                    t = child.strip()
                    if t:
                        hanzi_parts.append(t)
                elif child.name != "span":
                    t = child.get_text(strip=True)
                    if t:
                        hanzi_parts.append(t)
            hanzi = " ".join(hanzi_parts)
            if not hanzi:
                continue

            pinyin = ""
            pinyin_spans = _select_first(li, pinyin_selectors, "pinyin span")
            if pinyin_spans:
                pinyin = " ".join(s.get_text(strip=True) for s in pinyin_spans)

            translation = ""
            trans_spans = _select_first(li, trans_selectors, "translation span")
            if trans_spans:
                translation = trans_spans[0].get_text(strip=True)

            if not translation:
                continue
            sentences.append({
                "hanzi": hanzi,
                "pinyin": pinyin,
                "translation": translation,
            })
    return sentences if sentences else None


def _parse_table_examples(soup: BeautifulSoup) -> list[dict]:
    table_selectors = _get_selectors("example_table")
    tables = _select_first(soup, table_selectors, "example table")

    sentences = []
    for table in tables:
        rows = table.select("tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 2:
                continue

            trans_cell = None
            content_cells = []
            for cell in cells:
                if _is_translation_cell(cell):
                    trans_cell = cell
                else:
                    content_cells.append(cell)

            if trans_cell is None:
                content_cells = cells[:-1]
                trans_cell = cells[-1]

            hanzi_parts = []
            pinyin_parts = []
            for cell in content_cells:
                h = _extract_hanzi(cell)
                if h:
                    hanzi_parts.append(h)
                p = _extract_pinyin(cell)
                if p:
                    pinyin_parts.append(p)

            hanzi = " ".join(hanzi_parts)
            if not hanzi:
                continue
            pinyin = " ".join(pinyin_parts)
            translation = trans_cell.get_text(strip=True)
            sentences.append({
                "hanzi": hanzi,
                "pinyin": pinyin,
                "translation": translation,
            })
    return sentences


def parse_example_sentences(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    validate_page_structure(html, page_type="grammar")

    sentences = _parse_liju_examples(soup)
    if sentences is not None:
        return sentences

    return _parse_table_examples(soup)


def _fetch_single_point(link: dict, level: str, max_sentences: int | None) -> GrammarPoint | None:
    url_slug = link["url_slug"]
    full_url = f"{_get_base_url()}/{url_slug}"
    try:
        point_html = fetch_grammar_point_page(url_slug)
        raw_sentences = parse_example_sentences(point_html)
        if max_sentences is not None:
            raw_sentences = raw_sentences[:max_sentences]
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
            pattern=link.get("pattern", ""),
            sentences=sentences,
        )
        logger.info("  %s: %d sentences", link["name"], len(sentences))
        return gp
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError):
        logger.warning("Failed to fetch %s (%s), skipping", link["name"], full_url, exc_info=True)
        return None
    finally:
        time.sleep(get("scraper.request_delay", 1.0))


def scrape_level(level: str, max_points: int | None = None, max_sentences: int | None = None) -> GrammarLevel:
    url = f"{_get_base_url()}/{level}_grammar_points"
    logger.info("Fetching %s grammar points index from %s", level, url)
    try:
        html = fetch_page(url)
    except requests.RequestException:
        logger.error("Failed to fetch grammar points index for %s: %s", level, url)
        return GrammarLevel(level=level, grammar_points=[])
    links = parse_grammar_point_links(html)
    logger.info("Found %d grammar point links for %s", len(links), level)

    if max_points is not None:
        links = links[:max_points]

    grammar_points: list[GrammarPoint] = []
    max_workers = get("scraper.max_workers", 5)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_single_point, link, level, max_sentences): link
            for link in links
        }
        for future in as_completed(futures):
            gp = future.result()
            if gp is not None:
                grammar_points.append(gp)

    return GrammarLevel(level=level, grammar_points=grammar_points)


def save_level_data(level: GrammarLevel, suffix: str = "") -> None:
    path: Path = get_data_processed_dir() / f"{level.level}{suffix}.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    def _to_dict(gp: GrammarPoint) -> dict:
        return {
            "name": gp.name,
            "level": gp.level,
            "url_slug": gp.url_slug,
            "full_url": gp.full_url,
            "pattern": gp.pattern,
            "sentences": [
                {
                    "hanzi": s.hanzi,
                    "pinyin": s.pinyin,
                    "translation": s.translation,
                    "is_valid": s.is_valid,
                    "key_word": s.key_word,
                    "audio_filename": s.audio_filename,
                    "hanzi_errors": s.hanzi_errors,
                    "pinyin_errors": s.pinyin_errors,
                    "translation_errors": s.translation_errors,
                    "notes": s.notes,
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


def load_level_data(level_name: str, suffix: str = "") -> GrammarLevel:
    path: Path = get_data_processed_dir() / f"{level_name}{suffix}.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    gp_list = data.get("grammar_points", [])
    grammar_points = [
        GrammarPoint(
            name=gp.get("name", "Unknown"),
            level=gp.get("level", level_name),
            url_slug=gp.get("url_slug", ""),
            full_url=gp.get("full_url", ""),
            pattern=gp.get("pattern", ""),
            sentences=[
                ExampleSentence(
                    hanzi=s.get("hanzi", ""),
                    pinyin=s.get("pinyin", ""),
                    translation=s.get("translation", ""),
                    is_valid=s.get("is_valid", True),
                    key_word=s.get("key_word"),
                    audio_filename=s.get("audio_filename"),
                    hanzi_errors=s.get("hanzi_errors", ""),
                    pinyin_errors=s.get("pinyin_errors", ""),
                    translation_errors=s.get("translation_errors", ""),
                    notes=s.get("notes", ""),
                )
                for s in gp.get("sentences", [])
            ],
        )
        for gp in gp_list
    ]
    return GrammarLevel(level=data.get("level", level_name), grammar_points=grammar_points)


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
