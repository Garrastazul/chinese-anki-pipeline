# Chinese Grammar Flashcards

Generates Anki decks with Chinese grammar exercises from [Chinese Grammar Wiki](https://resources.allsetlearning.com/chinese/grammar).

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) (native or on WSL, model configurable in `config.json`)
- [Anki](https://apps.ankiweb.net/) (to import the `.apkg`)
- Python dependencies: `requests`, `beautifulsoup4`, `lxml`, `edge-tts`, `genanki`, `jieba`

## Setup

```powershell
.\setup.ps1
```

The script installs Python dependencies, starts Ollama in WSL, and downloads the `qwen2.5:7b` model.

## Tests

```powershell
pip install -e ".[test]"
pytest tests/ -v
```

## Usage

```powershell
python src/main.py --level A1
```

### Flags

| Flag | Description |
|------|-------------|
| `--level` | Level to scrape (`A1`, `A2`, `B1`, `B2`, `HSK1`, etc.). Default: `A1` |
| `--skip-scrape` | Skip scraping (use existing cache) |
| `--skip-validate` | Skip Ollama validation |
| `--skip-tts` | Skip audio generation |
| `--all-levels` | Process all levels defined in `config.json` |
| `--install` | Install dependencies and exit |

## Card types

| Type | Front | Back |
|------|-------|------|
| Hanzi → Full | Hanzi | Pinyin + Translation + Audio + Wiki link |
| EN → Hanzi | Translation EN | Hanzi + Pinyin + Audio + Wiki link |
| Cloze | Hanzi/Pinyin with hidden word | Keyword + Translation + Wiki link |
| Reorder | Scrambled words | Correct Hanzi + Pinyin + Translation + Audio + Wiki link |

## Project structure

```
grammar-flashcards/
├── audio/                  # TTS audio files (.mp3)
├── data/
│   └── processed/          # JSON per level (cache)
├── output/                 # Generated .apkg decks
├── src/
│   ├── main.py             # CLI and main pipeline
│   ├── scraper.py          # Chinese Grammar Wiki scraping
│   ├── validator.py        # Ollama validation (qwen2.5:7b)
│   ├── tts_generator.py    # Speech synthesis (edge-tts, Xiaoxiao Neural)
│   ├── deck_builder.py     # Anki deck building (genanki)
│   ├── models.py           # Dataclasses (ExampleSentence, GrammarPoint, GrammarLevel)
│   └── utils.py            # Utilities (paths, hash)
├── setup.ps1               # Setup script
├── config.json             # Configuration (model, voice, levels, etc.)
└── pyproject.toml          # Python dependencies
```

## Pipeline

1. **Scrape** — Fetch grammar points and sentences from Chinese Grammar Wiki
2. **Validate** — Ollama (model configurable in `config.json`) validates each sentence and detects the keyword for cloze
3. **TTS** — Generate audio with `edge-tts` (voice configurable by gender in `config.json`: `voice_gender: female` = Xiaoxiao, `male` = Yunxi)
4. **Build** — Assemble the `.apkg` deck with `genanki`

The generated deck can be imported into Anki by double-clicking the `.apkg` file.

## Notes

- Note GUIDs use a hash of the hanzi → re-importing does not create duplicates
- The wiki link appears on the answer side of each card
- `config.local.json` overrides `config.json` for local settings without modifying the base file
