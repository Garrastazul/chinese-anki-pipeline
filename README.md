# Chinese Grammar Flashcards

Genera mazos de Anki con ejercicios de gramática china a partir de [Chinese Grammar Wiki](https://resources.allsetlearning.com/chinese/grammar).

## Requisitos

- Python 3.10+
- [Ollama](https://ollama.com/) en WSL (con `qwen2.5:7b`)
- [Anki](https://apps.ankiweb.net/) (para importar el `.apkg`)

## Instalación

```powershell
.\setup.ps1
```

El script instala las dependencias Python, inicia Ollama en WSL y descarga el modelo `qwen2.5:7b`.

## Uso

```powershell
python src/main.py --level A1
```

### Flags

| Flag | Descripción |
|------|-------------|
| `--level` | Nivel a scrapear (`A1`, `A2`, `B1`, `B2`, `HSK1`, etc.). Default: `A1` |
| `--skip-scrape` | Saltar scraping (usa caché existente) |
| `--skip-validate` | Saltar validación con Ollama |
| `--skip-tts` | Saltar generación de audio |
| `--install` | Instalar dependencias y salir |

## Tipos de carta

| Tipo | Frente | Dorso |
|------|--------|-------|
| Hanzi → Todo | Hanzi | Pinyin + Traducción + Audio + Link wiki |
| EN → Hanzi | Traducción EN | Hanzi + Pinyin + Audio + Link wiki |
| Cloze | Hanzi/Pinyin con palabra oculta | Palabra clave + Traducción + Link wiki |
| Ordenar | Palabras desordenadas | Hanzi correcto + Pinyin + Traducción + Audio + Link wiki |

## Estructura del proyecto

```
grammar-flashcards/
├── audio/                  # Archivos TTS (.mp3)
├── data/
│   └── processed/          # JSON por nivel (cache)
├── output/                 # Mazos .apkg generados
├── src/
│   ├── main.py             # CLI y pipeline principal
│   ├── scraper.py          # Scraping de Chinese Grammar Wiki
│   ├── validator.py        # Validación con Ollama (qwen2.5:7b)
│   ├── tts_generator.py    # Síntesis de voz (edge-tts, Xiaoxiao Neural)
│   ├── deck_builder.py     # Construcción del mazo Anki (genanki)
│   ├── models.py           # Dataclasses (ExampleSentence, GrammarPoint, GrammarLevel)
│   └── utils.py            # Utilidades (paths, hash)
├── setup.ps1               # Script de instalación
└── pyproject.toml          # Dependencias Python
```

## Pipeline

1. **Scrapear** — Obtiene puntos gramaticales y oraciones desde Chinese Grammar Wiki
2. **Validar** — Ollama (`qwen2.5:7b`) valida cada oración y detecta la palabra clave para cloze
3. **TTS** — Genera audio con `edge-tts` (voz `zh-CN-XiaoxiaoNeural`)
4. **Construir** — Ensambla el mazo `.apkg` con `genanki`

El mazo generado se importa en Anki con doble clic en el archivo `.apkg`.

## Notas

- Los GUID de las notas usan un hash del hanzi → al re-importar no se duplican
- El enlace a la wiki aparece en la solución de cada carta
