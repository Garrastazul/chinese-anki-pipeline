from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_config_cache: dict[str, Any] | None = None


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> dict[str, Any]:
    root = Path(__file__).resolve().parent.parent
    config_path = root / "config.json"
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Config file not found at {config_path}. "
            "Create a config.json or run the setup."
        )
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in {config_path}: {e.msg}",
            e.doc,
            e.pos,
        )

    local_path = root / "config.local.json"
    if local_path.exists():
        try:
            with open(local_path, encoding="utf-8") as f:
                local_config = json.load(f)
            config = _deep_merge(config, local_config)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in {local_path}: {e.msg}",
                e.doc,
                e.pos,
            )

    return config


def get(key: str, default: Any = None) -> Any:
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    keys = key.split(".")
    val = _config_cache
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    return val if val is not None else default
