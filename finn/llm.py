"""Two-tier model routing.

  fast  — bulk, mechanical work: pull numbers out of a results PDF, list guidance
          statements in a transcript, write a one-line filing summary.
  smart — the one step per company that needs judgment: weighing what management
          said against what the numbers show.

Every provider here speaks the OpenAI chat-completions shape, so switching is an
env var, not a code change. Responses are cached on the prompt hash, so a re-run
of the pipeline costs nothing. If no key is set, `complete_json` returns None and
callers fall back to their deterministic path; the app still works, just with
fewer summaries.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass

import requests

from . import cache
from .config import CACHE_DIR


@dataclass
class Provider:
    name: str
    base_url: str
    key_env: str
    fast: str
    smart: str


PROVIDERS = {
    # Groq: free tier, very fast inference — good default for bulk extraction.
    "groq": Provider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY",
                     "openai/gpt-oss-20b", "openai/gpt-oss-120b"),
    # Gemini: free tier with long context — useful when transcripts are big.
    "gemini": Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
                       "GEMINI_API_KEY", "gemini-2.5-flash-lite", "gemini-2.5-flash"),
    # Anything else OpenAI-compatible (OpenRouter, a local Ollama, ...).
    "custom": Provider("custom", os.getenv("FINN_LLM_BASE_URL", ""), "FINN_LLM_API_KEY",
                       os.getenv("FINN_FAST_MODEL", ""), os.getenv("FINN_SMART_MODEL", "")),
}


def _active() -> Provider | None:
    wanted = os.getenv("FINN_LLM_PROVIDER")
    order = [wanted] if wanted else ["groq", "gemini", "custom"]
    for name in order:
        p = PROVIDERS.get(name)
        if p and p.base_url and os.getenv(p.key_env):
            return p
    return None


def available() -> bool:
    return _active() is not None


def describe() -> str:
    p = _active()
    if not p:
        return "no model configured (deterministic mode)"
    return f"{p.name}: fast={os.getenv('FINN_FAST_MODEL') or p.fast}, smart={os.getenv('FINN_SMART_MODEL') or p.smart}"


# ---- usage ledger: lets the writeup say exactly what a run cost ----------------
_lock = threading.Lock()
_LEDGER = CACHE_DIR / "usage.json"


def _record(tier: str, model: str, usage: dict, cached: bool) -> None:
    with _lock:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        try:
            led = json.loads(_LEDGER.read_text())
        except Exception:
            led = {}
        row = led.setdefault(f"{tier}:{model}", {"calls": 0, "cache_hits": 0, "prompt_tokens": 0, "completion_tokens": 0})
        if cached:
            row["cache_hits"] += 1
        else:
            row["calls"] += 1
            row["prompt_tokens"] += usage.get("prompt_tokens", 0)
            row["completion_tokens"] += usage.get("completion_tokens", 0)
        _LEDGER.write_text(json.dumps(led, indent=2))


def _parse_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: the outermost {...} or [...]
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                return None
    return None


def complete_json(tier: str, system: str, user: str, max_tokens: int = 1200):
    """Ask for a JSON answer. Returns parsed JSON, or None if unavailable/failed."""
    p = _active()
    if not p:
        return None
    model = (os.getenv("FINN_FAST_MODEL") if tier == "fast" else os.getenv("FINN_SMART_MODEL")) or (
        p.fast if tier == "fast" else p.smart)
    key = hashlib.sha256(f"{model}\n{system}\n{user}".encode()).hexdigest()
    hit = cache.get_json("llm", key)
    if hit is not None:
        _record(tier, model, {}, cached=True)
        return hit

    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system + "\nRespond with a single JSON object."},
                     {"role": "user", "content": user}],
    }
    if "gpt-oss" in model:
        # Reasoning models spend tokens thinking before they answer: keep the
        # thinking short for extraction, and leave room for it in the budget.
        body["reasoning_effort"] = "low" if tier == "fast" else "medium"
        body["max_tokens"] = max_tokens + 3000
    headers = {"Authorization": f"Bearer {os.getenv(p.key_env)}", "Content-Type": "application/json"}
    for attempt in range(4):
        try:
            r = requests.post(f"{p.base_url}/chat/completions", json=body, headers=headers, timeout=90)
            if r.status_code == 429:           # free tiers rate-limit; back off and retry
                time.sleep(float(r.headers.get("retry-after", 2 ** attempt * 3)))
                continue
            r.raise_for_status()
            data = r.json()
            out = _parse_json(data["choices"][0]["message"]["content"])
            _record(tier, model, data.get("usage", {}), cached=False)
            if out is not None:
                cache.put_json("llm", key, out)
            return out
        except (requests.RequestException, KeyError, ValueError):
            time.sleep(2 ** attempt)
    return None
