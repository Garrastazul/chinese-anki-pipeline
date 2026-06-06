import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from bs4 import BeautifulSoup

from src.scraper import (
    fetch_page, fetch_grammar_point_page, parse_grammar_point_links,
    parse_example_sentences, _extract_hanzi, _extract_pinyin,
    scrape_level, save_level_data, load_level_data,
)
from src.models import GrammarLevel, GrammarPoint, ExampleSentence


class TestExtractHanzi:
    def test_extract_hanzi_simple(self):
        html = '<td>我 <span class="pinyin">Wǒ</span></td>'
        soup = BeautifulSoup(html, "lxml")
        cell = soup.find("td")
        assert _extract_hanzi(cell) == "我"

    def test_extract_hanzi_multi_word(self):
        html = '<td>我 爱 <span class="pinyin">ài</span> 你 <span class="pinyin">nǐ</span></td>'
        soup = BeautifulSoup(html, "lxml")
        cell = soup.find("td")
        result = _extract_hanzi(cell)
        assert result == "我 爱 你"
        assert "ài" not in result

    def test_extract_hanzi_no_pinyin(self):
        html = "<td>你好</td>"
        soup = BeautifulSoup(html, "lxml")
        cell = soup.find("td")
        assert _extract_hanzi(cell) == "你好"

    def test_extract_hanzi_empty(self):
        soup = BeautifulSoup("<td></td>", "lxml")
        cell = soup.find("td")
        assert _extract_hanzi(cell) == ""


class TestExtractPinyin:
    def test_extract_pinyin_simple(self):
        html = '<td>我 <span class="pinyin">Wǒ</span></td>'
        soup = BeautifulSoup(html, "lxml")
        cell = soup.find("td")
        assert _extract_pinyin(cell) == "Wǒ"

    def test_extract_pinyin_multi(self):
        html = '<td>我 <span class="pinyin">Wǒ</span> 爱 <span class="pinyin">ài</span> 你。</td>'
        soup = BeautifulSoup(html, "lxml")
        cell = soup.find("td")
        assert _extract_pinyin(cell) == "Wǒ ài"

    def test_extract_pinyin_none(self):
        soup = BeautifulSoup("<td>你好</td>", "lxml")
        cell = soup.find("td")
        assert _extract_pinyin(cell) == ""

    def test_extract_pinyin_empty_cell(self):
        soup = BeautifulSoup('<td><span class="pinyin"></span></td>', "lxml")
        cell = soup.find("td")
        assert _extract_pinyin(cell) == ""


class TestParseExampleSentences:
    def test_parse_finds_sentences(self, sample_grammar_html):
        if not sample_grammar_html:
            pytest.skip("No fixture")
        sentences = parse_example_sentences(sample_grammar_html)
        assert len(sentences) >= 2

    def test_parse_sentences_have_keys(self, sample_grammar_html):
        if not sample_grammar_html:
            pytest.skip("No fixture")
        sentences = parse_example_sentences(sample_grammar_html)
        for s in sentences:
            assert "hanzi" in s
            assert "pinyin" in s
            assert "translation" in s

    def test_parse_empty_html(self):
        assert parse_example_sentences("<html></html>") == []

    def test_parse_multi_column_svo_table(self):
        html = (
            '<table class="table-bordered">'
            '<tr><th>Subject</th><th>Verb</th><th>Object</th><th>Translation</th></tr>'
            '<tr>'
            '<td>我<span class="pinyin">Wǒ</span></td>'
            '<td>爱<span class="pinyin">ài</span></td>'
            '<td>你。<span class="pinyin">nǐ.</span></td>'
            '<td>I love you.</td>'
            '</tr>'
            '</table>'
        )
        sentences = parse_example_sentences(html)
        assert len(sentences) == 1
        assert sentences[0]["hanzi"] == "我 爱 你。"
        assert sentences[0]["pinyin"] == "Wǒ ài nǐ."
        assert sentences[0]["translation"] == "I love you."

    def test_parse_multi_column_does_not_include_translation_in_content(self):
        html = (
            '<table class="table-bordered">'
            '<tr><td>他<span class="pinyin">Tā</span></td>'
            '<td>是<span class="pinyin">shì</span></td>'
            '<td>老师。<span class="pinyin">lǎoshī.</span></td>'
            '<td>He is a teacher.</td></tr>'
            '</table>'
        )
        sentences = parse_example_sentences(html)
        assert len(sentences) == 1
        assert "teacher" not in sentences[0]["hanzi"]
        assert "He is" not in sentences[0]["pinyin"]

    def test_parse_two_column_still_works(self):
        html = (
            '<table class="table-bordered">'
            '<tr><td>你好<span class="pinyin">Nǐ hǎo</span></td><td>Hello</td></tr>'
            '</table>'
        )
        sentences = parse_example_sentences(html)
        assert len(sentences) == 1
        assert sentences[0]["hanzi"] == "你好"
        assert sentences[0]["pinyin"] == "Nǐ hǎo"
        assert sentences[0]["translation"] == "Hello"


class TestParseGrammarPointLinks:
    def test_parse_links_finds_correct_number(self, sample_index_html):
        if not sample_index_html:
            pytest.skip("No sample_index.html fixture")
        links = parse_grammar_point_links(sample_index_html)
        assert len(links) >= 2

    def test_parse_links_has_expected_keys(self, sample_index_html):
        if not sample_index_html:
            pytest.skip("No fixture")
        links = parse_grammar_point_links(sample_index_html)
        for link in links:
            assert "name" in link
            assert "url_slug" in link
            assert "pattern" in link
            assert "examples_raw" in link

    def test_parse_links_empty_html(self):
        links = parse_grammar_point_links("<html></html>")
        assert links == []

    def test_parse_links_no_tables(self):
        links = parse_grammar_point_links("<html><p>no table</p></html>")
        assert links == []

    def test_parse_links_skips_row_without_href(self):
        html = (
            '<html><table class="wikitable">'
            '<tr><td><a>no href</a></td><td>pattern</td><td>examples</td></tr>'
            '<tr><td><a href="/chinese/grammar/ASG">valid</a></td>'
            '<td>pattern</td><td>examples</td></tr>'
            '</table></html>'
        )
        links = parse_grammar_point_links(html)
        assert len(links) == 1
        assert links[0]["name"] == "valid"

    def test_parse_links_skips_row_with_empty_href(self):
        html = (
            '<html><table class="wikitable">'
            '<tr><td><a href="">empty</a></td><td>pattern</td><td>examples</td></tr>'
            '</table></html>'
        )
        links = parse_grammar_point_links(html)
        assert links == []


class TestFetchPage:
    @patch("src.scraper.requests.get")
    def test_fetch_page_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html>content</html>"
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = fetch_page("https://example.com")
        assert result == "<html>content</html>"
        mock_get.assert_called_once()

    @patch("src.scraper.requests.get")
    def test_fetch_page_raises_on_error(self, mock_get):
        from requests.exceptions import HTTPError
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = HTTPError("404")
        mock_get.return_value = mock_resp

        with pytest.raises(HTTPError):
            fetch_page("https://example.com/bad")


class TestSaveLoadRoundtrip:
    def test_save_and_load_level_data(self, sample_level, tmp_path):
        with patch("src.scraper.get_data_processed_dir", return_value=tmp_path):
            save_level_data(sample_level)
            loaded = load_level_data("A1")

        assert loaded.level == sample_level.level
        assert len(loaded.grammar_points) == len(sample_level.grammar_points)
        assert loaded.grammar_points[0].name == sample_level.grammar_points[0].name
        assert len(loaded.grammar_points[0].sentences) == len(sample_level.grammar_points[0].sentences)
        assert loaded.grammar_points[0].sentences[0].hanzi == sample_level.grammar_points[0].sentences[0].hanzi

    def test_save_creates_valid_json(self, sample_level, tmp_path):
        with patch("src.scraper.get_data_processed_dir", return_value=tmp_path):
            save_level_data(sample_level)
            json_path = tmp_path / "A1.json"
            assert json_path.exists()

            data = json.loads(json_path.read_text(encoding="utf-8"))
            assert "level" in data
            assert "grammar_points" in data


class TestScrapeLevel:
    @patch("src.scraper.fetch_page")
    @patch("src.scraper.fetch_grammar_point_page")
    @patch("src.scraper.time.sleep")
    def test_scrape_level_basic(self, mock_sleep, mock_fetch_point, mock_fetch):
        mock_fetch.return_value = (
            '<html><table class="wikitable">'
            '<tr><th>Grammar Point</th><th>Pattern</th><th>Examples</th></tr>'
            '<tr><td><a href="/chinese/grammar/ASGETNCO">Point A</a></td>'
            '<td>Subj. + Verb</td>'
            '<td><span class="liju">例句</span></td></tr>'
            '</table></html>'
        )
        mock_fetch_point.return_value = (
            '<html><table class="table-bordered">'
            '<tr><td>我 <span class="pinyin">Wǒ</span></td><td>hello</td></tr>'
            '</table></html>'
        )
        level = scrape_level("A1")
        assert isinstance(level, GrammarLevel)
        assert level.level == "A1"
        assert len(level.grammar_points) == 1
        assert level.grammar_points[0].name == "Point A"
        assert level.grammar_points[0].url_slug == "ASGETNCO"
        assert len(level.grammar_points[0].sentences) == 1
        assert level.grammar_points[0].sentences[0].hanzi == "我"
        assert level.grammar_points[0].sentences[0].pinyin == "Wǒ"

    @patch("src.scraper.fetch_page")
    @patch("src.scraper.fetch_grammar_point_page")
    @patch("src.scraper.time.sleep")
    def test_scrape_level_multi_column_sentence(self, mock_sleep, mock_fetch_point, mock_fetch):
        mock_fetch.return_value = (
            '<html><table class="wikitable">'
            '<tr><th>Grammar Point</th><th>Pattern</th><th>Examples</th></tr>'
            '<tr><td><a href="/chinese/grammar/ASBASIC">Basic SVO</a></td>'
            '<td>Subj. + Verb + Obj.</td>'
            '<td><span class="liju">例句</span></td></tr>'
            '</table></html>'
        )
        mock_fetch_point.return_value = (
            '<html><table class="table-bordered">'
            '<tr><td>我<span class="pinyin">Wǒ</span></td>'
            '<td>爱<span class="pinyin">ài</span></td>'
            '<td>你。<span class="pinyin">nǐ.</span></td>'
            '<td>I love you.</td></tr>'
            '</table></html>'
        )
        level = scrape_level("A1")
        assert isinstance(level, GrammarLevel)
        assert len(level.grammar_points) == 1
        assert len(level.grammar_points[0].sentences) == 1
        assert level.grammar_points[0].sentences[0].hanzi == "我 爱 你。"
        assert level.grammar_points[0].sentences[0].pinyin == "Wǒ ài nǐ."
        assert level.grammar_points[0].sentences[0].translation == "I love you."

