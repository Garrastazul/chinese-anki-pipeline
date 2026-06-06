from __future__ import annotations

import hashlib
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_audio_dir() -> Path:
    return get_project_root() / "audio"


def get_output_dir() -> Path:
    return get_project_root() / "output"


def get_data_raw_dir() -> Path:
    return get_project_root() / "data" / "raw"


def get_data_processed_dir() -> Path:
    return get_project_root() / "data" / "processed"


def hash_string(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]
