"""
llm_client.py – shared, provider-agnostic LLM helpers.
Supports multiple API keys with automatic failover on rate-limit errors.
Used by both crawlers and the API.
"""

from __future__ import annotations

import json
import os
import re
import threading

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY      = os.getenv("LLM_API_KEY", "")
LLM_API_KEYS_RAW = os.getenv("LLM_API_KEYS", "")
LLM_BASE_URL     = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL        = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


# ──────────────────────────────────────────────
# KEY COLLECTION
# ──────────────────────────────────────────────

def _collect_llm_api_keys() -> list[str]:
    keys = []
    if LLM_API_KEY:
        keys.append(LLM_API_KEY.strip())
    idx = 2
    while True:
        env_key = os.getenv(f"LLM_API_KEY_{idx}", "").strip()
        if not env_key:
            break
        keys.append(env_key)
        idx += 1
    if LLM_API_KEYS_RAW:
        keys.extend([k.strip() for k in LLM_API_KEYS_RAW.split(",") if k.strip()])
    deduped, seen = [], set()
    for key in keys:
        if key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped


LLM_API_KEYS = _collect_llm_api_keys()

_llm_clients: list[OpenAI] = [
    OpenAI(api_key=api_key, base_url=LLM_BASE_URL)
    for api_key in LLM_API_KEYS
]
_llm_client_index = 0
_llm_client_lock  = threading.Lock()


def has_llm_client() -> bool:
    return len(_llm_clients) > 0


# ──────────────────────────────────────────────
# FAILOVER LOGIC
# ──────────────────────────────────────────────

def _is_failover_eligible(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(s in text for s in [
        "rate limit", "rate_limit", "429", "quota",
        "insufficient_quota", "tokens per day", "token limit",
        "exceeded", "authentication", "invalid api key",
        "api key expired", "401",
    ])


def _switch_client(failed_index: int, exc: Exception) -> None:
    global _llm_client_index
    with _llm_client_lock:
        if _llm_client_index == failed_index:
            _llm_client_index = (_llm_client_index + 1) % len(_llm_clients)
            print(
                f"[LLM] Switching API key "
                f"({failed_index + 1} → {_llm_client_index + 1}/{len(_llm_clients)}) "
                f"due to: {exc}"
            )


_IS_ANTHROPIC = "anthropic.com" in LLM_BASE_URL


def _sanitize_kwargs(kwargs: dict) -> dict:
    """
    Strip / rewrite kwargs that are valid for OpenAI but rejected by Anthropic.

    - response_format={"type": "json_object"}  →  removed
      Anthropic doesn't support json_object mode; JSON output is controlled
      via the prompt instead (which the callers already do).
    """
    if not _IS_ANTHROPIC:
        return kwargs
    rf = kwargs.get("response_format")
    if isinstance(rf, dict) and rf.get("type") == "json_object":
        kwargs = {k: v for k, v in kwargs.items() if k != "response_format"}
    return kwargs


def parse_json_content(completion) -> dict | list:
    """
    Parse JSON from a chat completion response.

    Robustly handles Anthropic responses that may:
      1. Wrap output in markdown fences  (```json ... ```)
      2. Prepend a preamble line         ("Here is the data:\n{...}")
      3. Contain trailing text after the JSON value

    Strategy: strip fences, seek the first { or [, then use
    JSONDecoder.raw_decode() which stops at the end of the first
    complete JSON value and ignores anything after it.
    """
    raw = completion.choices[0].message.content or ""

    # 1. Strip markdown code fences
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped.strip())

    # 2. Seek the first JSON value opener ({ or [), skipping any preamble
    match = re.search(r"[{\[]", stripped)
    if match:
        stripped = stripped[match.start():]

    # 3. Decode only the first complete JSON value; ignore trailing content
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(stripped)
    return obj


def create_chat_completion(**kwargs):
    """
    Drop-in for openai.chat.completions.create with multi-key failover.
    Pass the same kwargs as you would to the OpenAI client.
    """
    if not has_llm_client():
        raise RuntimeError("No LLM API key configured. Set LLM_API_KEY in .env")

    kwargs = _sanitize_kwargs(kwargs)
    max_attempts = len(_llm_clients)
    last_error   = None

    for attempt in range(max_attempts):
        with _llm_client_lock:
            active_index  = _llm_client_index
            active_client = _llm_clients[active_index]
        try:
            return active_client.chat.completions.create(**kwargs)
        except Exception as exc:
            last_error = exc
            should_failover = (
                max_attempts > 1
                and attempt < max_attempts - 1
                and _is_failover_eligible(exc)
            )
            if not should_failover:
                raise
            _switch_client(active_index, exc)

    raise last_error
