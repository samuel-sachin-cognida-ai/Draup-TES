"""Text normalisation, language detection, and string sanitisation helpers."""
from __future__ import annotations

import re

_NON_LATIN_RANGES = [
    (0x3000, 0x9FFF), (0xAC00, 0xD7AF), (0x0600, 0x06FF),
    (0x0900, 0x097F), (0x0400, 0x04FF), (0x0370, 0x03FF),
    (0x0E00, 0x0E7F), (0xF900, 0xFAFF), (0x20000, 0x2A6DF),
]


def normalize_text(value) -> str:
    if value is None:
        return ""
    value = str(value).lower().strip()
    return re.sub(r"\s+", " ", value)


def clean_string_list(values) -> list[str]:
    if not values:
        return []
    if not isinstance(values, list):
        values = [values]
    cleaned, seen = [], set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = normalize_text(text)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def is_english_text(text: str, threshold: float = 0.15) -> bool:
    if not text:
        return True
    stripped = text.replace(" ", "")
    if len(stripped) <= 3:
        return True
    non_latin = sum(
        1 for ch in stripped
        if any(lo <= ord(ch) <= hi for lo, hi in _NON_LATIN_RANGES)
    )
    return (non_latin / len(stripped)) < threshold


def sanitize_string_field(value: str | None, field_name: str = "") -> str | None:
    if value is None:
        return None
    if not is_english_text(value):
        print(f"[LANG] Non-English text rejected in field '{field_name}': {value!r}")
        return None
    return value


def sanitize_string_list(values: list[str], field_name: str = "") -> list[str]:
    result = []
    for v in values:
        if is_english_text(v):
            result.append(v)
        else:
            print(f"[LANG] Non-English item removed from '{field_name}': {v!r}")
    return result
