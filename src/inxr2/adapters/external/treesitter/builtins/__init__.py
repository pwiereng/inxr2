"""Builtin constants for language parsers, loaded from JSON data files."""

import json
from pathlib import Path

_DIR = Path(__file__).parent


def _load(filename: str, key: str) -> set[str]:
    with open(_DIR / filename, encoding="utf-8") as f:
        return set(json.load(f)[key])
